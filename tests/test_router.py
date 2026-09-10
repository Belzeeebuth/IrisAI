import json

import pytest

from iris.config import CustomCommand
from iris.core.router import Router
from iris.nlu.intents import Intent, IntentParser


@pytest.fixture
def router(cfg, phrases, journal, fake_system):
    fake_system.available |= {
        "hyprctl",
        "wpctl",
        "brightnessctl",
        "playerctl",
        "notify-send",
        "xdg-open",
    }
    return Router(cfg, phrases, journal)


def parse(text: str, commands=()) -> Intent:
    intent = IntentParser(commands).parse(text)
    assert intent is not None
    return intent


def test_volume_set_uses_wpctl(router, fake_system):
    reply = router.execute(parse("mets le volume à 40"))
    assert reply.ok and reply.text == "Volume à 40 pour cent."
    assert "wpctl set-volume -l 1.0 @DEFAULT_AUDIO_SINK@ 40%" in fake_system.joined_calls()


def test_volume_up_reads_back_volume(router, fake_system):
    fake_system.outputs["wpctl get-volume"] = "Volume: 0.55"
    reply = router.execute(parse("monte le son"))
    assert reply.text == "Volume à 55 pour cent."
    assert "wpctl set-volume -l 1.0 @DEFAULT_AUDIO_SINK@ 5%+" in fake_system.joined_calls()


def test_volume_down_custom_step(router, fake_system):
    fake_system.outputs["wpctl get-volume"] = "Volume: 0.30"
    router.execute(parse("baisse le son de 20"))
    assert "wpctl set-volume -l 1.0 @DEFAULT_AUDIO_SINK@ 20%-" in fake_system.joined_calls()


def test_mute(router, fake_system):
    fake_system.outputs["wpctl get-volume"] = "Volume: 0.30 [MUTED]"
    assert router.execute(parse("coupe le son")).text == "Son coupé."
    assert "wpctl set-mute @DEFAULT_AUDIO_SINK@ 1" in fake_system.joined_calls()


def test_pactl_fallback(router, fake_system):
    fake_system.available.discard("wpctl")
    fake_system.available.add("pactl")
    router.execute(parse("volume 20"))
    assert "pactl set-sink-volume @DEFAULT_SINK@ 20%" in fake_system.joined_calls()


def test_brightness(router, fake_system):
    fake_system.outputs["brightnessctl -m"] = "intel_backlight,backlight,12000,50%,24000"
    assert router.execute(parse("luminosité à 70")).text == "Luminosité à 70 pour cent."
    assert "brightnessctl -q set 70%" in fake_system.joined_calls()
    assert router.execute(parse("monte la luminosité")).text == "Luminosité à 50 pour cent."
    assert "brightnessctl -q -n1 set 10%+" in fake_system.joined_calls()


def test_workspace_switch(router, fake_system):
    reply = router.execute(parse("va sur le workspace 3"))
    assert reply.text == "Workspace 3."
    assert "hyprctl dispatch workspace 3" in fake_system.joined_calls()


def test_workspace_next_and_window_actions(router, fake_system):
    router.execute(parse("workspace suivant"))
    router.execute(parse("ferme cette fenêtre"))
    router.execute(parse("plein écran"))
    router.execute(parse("envoie cette fenêtre sur le workspace 2"))
    calls = fake_system.joined_calls()
    assert "hyprctl dispatch workspace e+1" in calls
    assert "hyprctl dispatch killactive" in calls
    assert "hyprctl dispatch fullscreen 0" in calls
    assert "hyprctl dispatch movetoworkspace 2" in calls


def test_hyprland_unavailable_is_a_spoken_error(router, fake_system):
    fake_system.available.discard("hyprctl")
    reply = router.execute(parse("workspace 2"))
    assert not reply.ok
    assert "Hyprland" in reply.text


def test_close_all_closes_each_client(router, fake_system):
    clients = [{"address": "0x1", "class": "firefox"}, {"address": "0x2", "class": "ghostty"}]
    fake_system.outputs["hyprctl -j clients"] = json.dumps(clients)
    reply = router.execute(parse("ferme tout"))
    assert reply.text == "2 fenêtres fermées."
    assert "hyprctl dispatch closewindow address:0x1" in fake_system.joined_calls()
    assert "hyprctl dispatch closewindow address:0x2" in fake_system.joined_calls()


def test_close_app_by_window_class(router, fake_system):
    fake_system.available.add("firefox")
    fake_system.outputs["hyprctl -j clients"] = json.dumps(
        [{"address": "0xa", "class": "firefox", "title": "Mozilla Firefox"}]
    )
    reply = router.execute(parse("ferme firefox"))
    assert reply.text == "firefox fermé."
    assert "hyprctl dispatch closewindow address:0xa" in fake_system.joined_calls()


def test_close_app_not_running(router, fake_system):
    fake_system.outputs["hyprctl -j clients"] = "[]"
    reply = router.execute(parse("ferme spotify"))
    assert not reply.ok and "spotify" in reply.text


def test_open_app_resolves_alias_and_launches(router, fake_system, monkeypatch):
    monkeypatch.setenv("TERMINAL", "ghostty")
    fake_system.available.add("ghostty")
    reply = router.execute(parse("ouvre le terminal"))
    assert reply.ok and reply.text == "ghostty est lancé."
    assert ["ghostty"] in fake_system.launched


def test_open_app_user_alias_wins(cfg, phrases, journal, fake_system, monkeypatch):
    cfg.apps = {"mon éditeur": "zed --new-window"}
    fake_system.available.add("zed")
    router = Router(cfg, phrases, journal)
    reply = router.execute(parse("ouvre mon éditeur"))
    assert reply.ok
    assert ["zed", "--new-window"] in fake_system.launched


def test_open_webapp_uses_omarchy_launcher(router, fake_system):
    fake_system.available.add("omarchy-launch-webapp")
    reply = router.execute(parse("ouvre youtube"))
    assert reply.ok and "youtube" in reply.text
    assert ["omarchy-launch-webapp", "https://youtube.com"] in fake_system.launched


def test_open_app_not_found(router, fake_system):
    reply = router.execute(parse("ouvre logicielinexistant"))
    assert not reply.ok and "logicielinexistant" in reply.text


def test_web_search_and_url(router, fake_system):
    router.execute(parse("cherche des crêpes sur internet"))
    router.execute(parse("ouvre github.com"))
    assert ["xdg-open", "https://duckduckgo.com/?q=des+crepes"] in fake_system.launched
    assert ["xdg-open", "https://github.com"] in fake_system.launched


def test_media(router, fake_system):
    fake_system.outputs["playerctl metadata"] = "Daft Punk - Around the World"
    assert router.execute(parse("pause")).text == "Lecture basculée."
    assert (
        router.execute(parse("musique suivante")).text
        == "Piste suivante. Daft Punk - Around the World"
    )
    assert "playerctl play-pause" in fake_system.joined_calls()
    assert "playerctl next" in fake_system.joined_calls()


def test_power_actions_call_systemctl(router, fake_system):
    fake_system.available.add("systemctl")
    assert router.execute(parse("éteins l'ordinateur")).text == "Extinction. À bientôt."
    assert "systemctl poweroff" in fake_system.joined_calls()
    router.execute(parse("mets en veille"))
    assert "systemctl suspend" in fake_system.joined_calls()


def test_confirmation_questions(router):
    assert (
        router.confirmation_question(parse("ferme tout"))
        == "Veux-tu vraiment fermer toutes les applications ?"
    )
    assert (
        router.confirmation_question(parse("éteins le pc"))
        == "Veux-tu vraiment éteindre l'ordinateur ?"
    )
    assert router.confirmation_question(parse("monte le son")) is None
    cmd = CustomCommand("danger", ["nettoie"], "true", confirm=True)
    assert (
        router.confirmation_question(parse("nettoie", [cmd]))
        == "Veux-tu vraiment lancer « danger » ?"
    )


def test_omarchy_theme(router, fake_system, tmp_path, monkeypatch):
    themes = tmp_path / "themes"
    (themes / "tokyo-night").mkdir(parents=True)
    (themes / "catppuccin").mkdir()
    monkeypatch.setenv("OMARCHY_PATH", str(tmp_path))
    fake_system.available |= {"omarchy-theme-set", "omarchy-theme-next"}
    assert router.execute(parse("mets le thème tokyo night")).text == "Thème tokyo night appliqué."
    assert "omarchy-theme-set tokyo-night" in fake_system.joined_calls()
    assert router.execute(parse("change de thème")).text == "Thème changé."
    reply = router.execute(parse("mets le thème inexistant"))
    assert not reply.ok and "catppuccin" in reply.text


def test_lock_screen_prefers_omarchy(router, fake_system):
    fake_system.available |= {"omarchy-lock-screen", "hyprlock"}
    assert router.execute(parse("verrouille l'écran")).text == "Écran verrouillé."
    assert ["omarchy-lock-screen"] in fake_system.launched


def test_custom_command_wait_runs_shell(router):
    cmd = CustomCommand(
        "echo", ["dis coucou en shell"], "echo coucou", wait=True, reply="Coucou lancé."
    )
    reply = router.execute(parse("dis coucou en shell", [cmd]))
    assert reply.ok and reply.text == "Coucou lancé."


def test_custom_command_failure(router):
    cmd = CustomCommand("fail", ["plante"], "exit 3", wait=True)
    reply = router.execute(parse("plante", [cmd]))
    assert not reply.ok and "fail" not in reply.text.lower() or "code 3" in reply.text


def test_time_date_and_help(router):
    assert router.execute(parse("quelle heure est-il")).text.startswith("Il est ")
    assert router.execute(parse("quel jour sommes-nous")).text.startswith("Nous sommes le ")
    assert "workspace" in router.execute(parse("aide")).text


def test_control_replies(router):
    assert router.execute(parse("stop")).control == "stop"
    pause = router.execute(parse("mets-toi en pause pendant 3 minutes"))
    assert pause.control == "pause" and pause.data["minutes"] == 3
    assert router.execute(parse("reprends l'écoute")).control == "resume"


def test_agent_disabled_by_default(router):
    reply = router.execute(parse("demande à claude bonjour"))
    assert not reply.ok and "désactivé" in reply.text


def test_journal_records_each_action(router, journal):
    router.execute(parse("quelle heure est-il"))
    router.execute(parse("ouvre appinconnue"))
    records = journal.recent()
    assert [r.intent for r in records] == ["open_app", "time"]
    assert records[0].ok is False and records[1].ok is True
