from iris.core.journal import Journal


def test_actions_roundtrip(journal: Journal) -> None:
    journal.log_action(
        "volume_set", {"n": 50}, "mets le volume à 50", True, "Volume à 50 pour cent.", 12
    )
    journal.log_action("open_app", {"app": "x"}, "ouvre x", False, "introuvable", 3)
    records = journal.recent(10)
    assert [r.intent for r in records] == ["open_app", "volume_set"]
    assert (
        records[1].slots == {"n": 50}
        and records[1].ok is True
        and records[1].text == "mets le volume à 50"
    )
    assert journal.intent_counts() == {"open_app": 1, "volume_set": 1}
    journal.clear()
    assert journal.recent() == []


def test_transcripts_are_not_stored_by_default() -> None:
    j = Journal(":memory:", store_transcripts=False)
    j.log_action("time", {}, "quelle heure", True, "Il est 10 heures.")
    assert j.recent()[0].text == ""
    j.log_utterance("hey iris", True, True)
    assert j._db.execute("SELECT COUNT(*) FROM utterances").fetchone()[0] == 0


def test_journal_actions_can_be_disabled() -> None:
    j = Journal(":memory:", journal_actions=False)
    j.log_action("time", {}, "", True)
    assert j.recent() == []


def test_prefs(journal: Journal) -> None:
    assert journal.get_pref("tone", "warm") == "warm"
    journal.set_pref("tone", "direct")
    journal.set_pref("morning", {"hour": 9, "apps": ["ghostty"]})
    assert journal.get_pref("tone") == "direct"
    assert journal.all_prefs()["morning"]["apps"] == ["ghostty"]


def test_file_backed_journal(tmp_path) -> None:
    j = Journal(tmp_path / "state" / "iris.db")
    j.log_action("greet", {}, "", True, "Bonjour")
    j.close()
    j2 = Journal(tmp_path / "state" / "iris.db")
    assert j2.recent()[0].intent == "greet"
    j2.close()
