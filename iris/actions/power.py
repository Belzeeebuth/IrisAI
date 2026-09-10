"""Veille / extinction / redémarrage (toujours après confirmation vocale)."""

from __future__ import annotations

from iris.actions import system


def _systemctl(verb: str) -> None:
    res = system.run(["systemctl", verb], timeout=10)
    if not res.ok:
        raise RuntimeError(res.err or f"systemctl {verb} a échoué")


def suspend() -> None:
    _systemctl("suspend")


def poweroff() -> None:
    _systemctl("poweroff")


def reboot() -> None:
    _systemctl("reboot")
