"""Périphériques : Bluetooth (bluetoothctl), Wi-Fi / mode avion (rfkill), batterie, sortie audio."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from pathlib import Path

from iris.actions import system
from iris.nlu.normalize import canonical

_BT_DEVICE = re.compile(r"^Device\s+([0-9A-F:]{17})\s+(.+)$", re.IGNORECASE)


# ---------------------------------------------------------------------------- Bluetooth
def _bluetoothctl(*args: str, timeout: float = 15) -> str:
    if not system.which("bluetoothctl"):
        raise RuntimeError("bluetoothctl n'est pas installé (paquet bluez-utils)")
    res = system.run(["bluetoothctl", *args], timeout=timeout)
    if not res.ok:
        raise RuntimeError(res.err or res.out or "bluetoothctl a échoué")
    return res.out


def bluetooth_power(state: bool) -> None:
    _bluetoothctl("power", "on" if state else "off")


def bluetooth_devices(paired_only: bool = False) -> list[tuple[str, str]]:
    """[(adresse, nom)] des appareils connus (appairés si ``paired_only``)."""
    out = _bluetoothctl("devices", "Paired" if paired_only else "")
    devices = []
    for line in out.splitlines():
        m = _BT_DEVICE.match(line.strip())
        if m:
            devices.append((m.group(1).upper(), m.group(2).strip()))
    return devices


def resolve_bluetooth(query: str, aliases: dict[str, str] | None = None) -> tuple[str, str]:
    """Trouve (adresse, nom) depuis un nom prononcé, un alias ou une adresse."""
    aliases = {canonical(k): v for k, v in (aliases or {}).items()}
    q = canonical(query)
    if q in aliases:
        query = aliases[q]
        q = canonical(query)
    if re.fullmatch(r"[0-9A-Fa-f:]{17}", query.strip()):
        return query.strip().upper(), query.strip()
    devices = bluetooth_devices()
    if not devices:
        raise RuntimeError("aucun appareil Bluetooth connu")
    scored = sorted(
        (
            (
                SequenceMatcher(None, q, canonical(name)).ratio()
                + (0.5 if q in canonical(name) else 0),
                addr,
                name,
            )
            for addr, name in devices
        ),
        reverse=True,
    )
    score, addr, name = scored[0]
    if score < 0.5:
        raise RuntimeError(
            f"appareil inconnu : {query} (connus : {', '.join(n for _, n in devices)})"
        )
    return addr, name


def bluetooth_connect(query: str, aliases: dict[str, str] | None = None) -> str:
    addr, name = resolve_bluetooth(query, aliases)
    bluetooth_power(True)
    out = _bluetoothctl("connect", addr, timeout=30)
    if "Failed" in out or "not available" in out:
        raise RuntimeError(f"connexion à {name} impossible")
    return name


def bluetooth_disconnect(query: str, aliases: dict[str, str] | None = None) -> str:
    addr, name = resolve_bluetooth(query, aliases)
    _bluetoothctl("disconnect", addr, timeout=20)
    return name


# ---------------------------------------------------------------------------- Wi-Fi / avion
def _rfkill(action: str, kind: str) -> None:
    if not system.which("rfkill"):
        raise RuntimeError("rfkill n'est pas disponible")
    res = system.run(["rfkill", action, kind], timeout=5)
    if not res.ok:
        raise RuntimeError(res.err or "rfkill a échoué")


def wifi_power(state: bool) -> None:
    if system.which("nmcli"):
        res = system.run(["nmcli", "radio", "wifi", "on" if state else "off"], timeout=10)
        if res.ok:
            return
    _rfkill("unblock" if state else "block", "wifi")


def airplane_mode(state: bool) -> None:
    _rfkill("block" if state else "unblock", "all")


# ---------------------------------------------------------------------------- batterie
def battery(power_supply: Path = Path("/sys/class/power_supply")) -> tuple[int, str] | None:
    """(pourcentage, état) de la première batterie, ou None sans batterie."""
    if not power_supply.is_dir():
        return None
    for entry in sorted(power_supply.iterdir()):
        cap = entry / "capacity"
        if cap.exists():
            try:
                percent = int(cap.read_text().strip())
                status = (
                    (entry / "status").read_text().strip() if (entry / "status").exists() else ""
                )
                return percent, status
            except (OSError, ValueError):
                continue
    return None


# ---------------------------------------------------------------------------- sortie audio
def switch_audio_output() -> str:
    if system.which("omarchy-cmd-audio-switch"):
        res = system.run(["omarchy-cmd-audio-switch"], timeout=10)
        if not res.ok:
            raise RuntimeError(res.err or "omarchy-cmd-audio-switch a échoué")
        return res.out.strip() or "sortie suivante"
    if not system.which("wpctl"):
        raise RuntimeError("wpctl indisponible")
    status = system.run(["wpctl", "status"], timeout=5).out
    sinks: list[tuple[int, str, bool]] = []
    in_sinks = False
    for line in status.splitlines():
        if "Sinks:" in line:
            in_sinks = True
            continue
        if in_sinks and ("Sources:" in line or "Filters:" in line or not line.strip("│ ")):
            if sinks:
                break
            continue
        if in_sinks:
            m = re.search(r"(\*?)\s*(\d+)\.\s+(.+?)\s+\[vol:", line)
            if m:
                sinks.append((int(m.group(2)), m.group(3).strip(), m.group(1) == "*"))
    if len(sinks) < 2:
        raise RuntimeError("une seule sortie audio disponible")
    current = next((i for i, s in enumerate(sinks) if s[2]), 0)
    target = sinks[(current + 1) % len(sinks)]
    res = system.run(["wpctl", "set-default", str(target[0])], timeout=5)
    if not res.ok:
        raise RuntimeError(res.err or "changement de sortie impossible")
    return target[1]
