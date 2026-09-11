"""« iris restart » : relancer le service et attendre qu'Iris écoute de nouveau."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

from iris import service
from iris.cli import main


@pytest.fixture
def unit(fake_system, tmp_path, monkeypatch):
    """Unité installée, systemctl disponible, fichier d'état dans un dossier neutre."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "run"))
    path = service.unit_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(service.render_unit("/usr/bin/iris"), encoding="utf-8")
    fake_system.available.add("systemctl")
    fake_system.outputs["systemctl --user is-active"] = "active\n"
    return fake_system


def _write_state(state: str = "idle", *, ts: float | None = None) -> Path:
    from iris.core.status import default_status_file

    path = default_status_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"state": state, "ts": time.time() if ts is None else ts}
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


@pytest.fixture
def becomes_ready():
    """Simule l'instance qui charge son modèle puis écrit « idle » un instant plus tard."""
    timers: list[threading.Timer] = []

    def arm(delay: float = 0.2, state: str = "idle") -> None:
        timer = threading.Timer(delay, lambda: _write_state(state))
        timers.append(timer)
        timer.start()

    yield arm
    for timer in timers:
        timer.cancel()


def test_relance_puis_attend_lecoute(unit, becomes_ready):
    becomes_ready()
    ok, messages = service.restart(wait_s=5.0)
    assert ok
    assert ["systemctl", "--user", "restart", "iris.service"] in unit.calls
    assert "écoute de nouveau" in " ".join(messages)


def test_un_etat_perime_ne_prouve_rien(unit):
    """Le fichier d'état survit à l'arrêt : sans horodatage, on croirait Iris vivante."""
    _write_state("idle", ts=time.time() - 300)
    ok, messages = service.restart(wait_s=0.5)
    assert not ok
    assert "journalctl" in " ".join(messages)


def test_service_retombe_aussitot(unit):
    _write_state("off", ts=time.time() - 1)
    unit.outputs["systemctl --user is-active"] = "failed\n"
    ok, messages = service.restart(wait_s=5.0)
    assert not ok
    assert "arrêté aussitôt" in " ".join(messages)


def test_sans_unite_installee(fake_system, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    fake_system.available.add("systemctl")
    fake_system.outputs["systemctl --user cat"] = None  # unité inconnue
    ok, messages = service.restart(wait_s=1.0)
    assert not ok
    assert "iris service install" in " ".join(messages)
    assert not any("restart" in " ".join(c) for c in fake_system.calls)


def test_sans_systemctl(fake_system, monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    ok, messages = service.restart(wait_s=1.0)
    assert not ok
    assert "iris run" in " ".join(messages)


def test_echec_de_systemctl_signale(unit):
    unit.outputs["systemctl --user restart"] = None
    ok, messages = service.restart(wait_s=1.0)
    assert not ok
    assert "Relance impossible" in " ".join(messages)


@pytest.mark.parametrize("argv", [["restart"], ["service", "restart"]])
def test_la_commande_existe(unit, becomes_ready, capsys, argv):
    becomes_ready()
    assert main([*argv, "--timeout", "5"]) == 0
    assert "écoute de nouveau" in capsys.readouterr().out


def test_la_commande_rend_un_code_derreur(unit, capsys):
    _write_state("idle", ts=time.time() - 300)
    assert main(["restart", "--timeout", "0.5"]) == 1
    assert "journalctl" in capsys.readouterr().err
