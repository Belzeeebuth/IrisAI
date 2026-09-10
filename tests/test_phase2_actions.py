import json

import pytest

from iris.actions import devices, monitors, notifications, typing
from iris.actions.apps import AppResolver
from iris.actions.sessions import SessionManager
from iris.config import Session, SessionApp

BT_LIST = "Device AC:12:2F:00:11:22 WH-1000XM5\nDevice 11:22:33:44:55:66 Clavier Logitech\n"
MAKO_HISTORY = json.dumps(
    {
        "type": "aa{sv}",
        "data": [
            [
                {
                    "app-name": {"type": "s", "data": "Signal"},
                    "summary": {"type": "s", "data": "Alice"},
                    "body": {"type": "s", "data": "On se voit à 18h ?"},
                },
                {
                    "app-name": {"type": "s", "data": "Mail"},
                    "summary": {"type": "s", "data": "Facture"},
                    "body": {"type": "s", "data": ""},
                },
            ]
        ],
    }
)
WPCTL_STATUS = """PipeWire 'pipewire-0' [1.2.0]
Audio
 ├─ Devices:
 ├─ Sinks:
 │  *   45. Casque USB                    [vol: 0.60]
 │      52. Haut-parleurs internes        [vol: 1.00]
 │
 ├─ Sources:
 │      60. Micro                         [vol: 1.00]
"""


# ---------------------------------------------------------------- dictée
def test_typing_tool_order(fake_system):
    assert typing.available_tool() is None
    fake_system.available.add("wl-copy")
    assert typing.available_tool() == "clipboard"
    fake_system.available.add("wtype")
    assert typing.available_tool() == "wtype"
    assert typing.available_tool("clipboard") == "clipboard"


def test_type_text_wtype(fake_system):
    fake_system.available.add("wtype")
    assert typing.type_text("bonjour", press_enter=True) == "wtype"
    assert ["wtype", "--", "bonjour"] in fake_system.calls and [
        "wtype",
        "-k",
        "Return",
    ] in fake_system.calls


def test_type_text_clipboard_fallback(fake_system):
    fake_system.available |= {"wl-copy", "notify-send"}
    assert typing.type_text("texte") == "clipboard"
    assert ["wl-copy", "--", "texte"] in fake_system.calls
    assert any(c[0] == "notify-send" for c in fake_system.calls)


def test_type_text_without_tool(fake_system):
    with pytest.raises(RuntimeError, match="wtype"):
        typing.type_text("x")


# ---------------------------------------------------------------- écrans
def test_monitors(fake_system):
    fake_system.available.add("hyprctl")
    monitors.move_window_to_monitor("droite")
    monitors.focus_monitor("left")
    assert "hyprctl dispatch movewindow mon:r" in fake_system.joined_calls()
    assert "hyprctl dispatch focusmonitor l" in fake_system.joined_calls()
    with pytest.raises(RuntimeError):
        monitors.focus_monitor("diagonale")


# ---------------------------------------------------------------- périphériques
def test_bluetooth_devices_and_resolution(fake_system):
    fake_system.available.add("bluetoothctl")
    fake_system.outputs["bluetoothctl devices"] = BT_LIST
    assert devices.bluetooth_devices() == [
        ("AC:12:2F:00:11:22", "WH-1000XM5"),
        ("11:22:33:44:55:66", "Clavier Logitech"),
    ]
    assert devices.resolve_bluetooth("mes écouteurs", {"mes écouteurs": "WH-1000XM5"}) == (
        "AC:12:2F:00:11:22",
        "WH-1000XM5",
    )
    assert devices.resolve_bluetooth("clavier")[1] == "Clavier Logitech"
    assert devices.resolve_bluetooth("11:22:33:44:55:66")[0] == "11:22:33:44:55:66"
    with pytest.raises(RuntimeError, match="inconnu"):
        devices.resolve_bluetooth("grille-pain")


def test_bluetooth_connect_flow(fake_system):
    fake_system.available.add("bluetoothctl")
    fake_system.outputs["bluetoothctl devices"] = BT_LIST
    fake_system.outputs["bluetoothctl connect"] = "Connection successful"
    assert devices.bluetooth_connect("casque sony", {"casque sony": "WH-1000XM5"}) == "WH-1000XM5"
    calls = fake_system.joined_calls()
    assert "bluetoothctl power on" in calls and "bluetoothctl connect AC:12:2F:00:11:22" in calls
    fake_system.outputs["bluetoothctl connect"] = "Failed to connect"
    with pytest.raises(RuntimeError, match="impossible"):
        devices.bluetooth_connect("WH-1000XM5")


def test_wifi_and_airplane(fake_system):
    fake_system.available.add("rfkill")
    devices.wifi_power(False)
    devices.airplane_mode(True)
    assert (
        "rfkill block wifi" in fake_system.joined_calls()
        and "rfkill block all" in fake_system.joined_calls()
    )
    fake_system.available.add("nmcli")
    devices.wifi_power(True)
    assert "nmcli radio wifi on" in fake_system.joined_calls()


def test_battery(tmp_path):
    assert devices.battery(tmp_path / "absent") is None
    bat = tmp_path / "BAT0"
    bat.mkdir()
    (bat / "capacity").write_text("73\n")
    (bat / "status").write_text("Charging\n")
    assert devices.battery(tmp_path) == (73, "Charging")


def test_switch_audio_output_wpctl(fake_system):
    fake_system.available.add("wpctl")
    fake_system.outputs["wpctl status"] = WPCTL_STATUS
    assert devices.switch_audio_output() == "Haut-parleurs internes"
    assert "wpctl set-default 52" in fake_system.joined_calls()


def test_switch_audio_output_prefers_omarchy(fake_system):
    fake_system.available |= {"omarchy-cmd-audio-switch", "wpctl"}
    assert devices.switch_audio_output()
    assert ["omarchy-cmd-audio-switch"] in fake_system.calls


# ---------------------------------------------------------------- notifications
def test_notifications_history_and_summary(fake_system):
    fake_system.available.add("makoctl")
    fake_system.outputs["makoctl history"] = MAKO_HISTORY
    items = notifications.history()
    assert [(n.app, n.summary, n.body) for n in items] == [
        ("Signal", "Alice", "On se voit à 18h ?"),
        ("Mail", "Facture", ""),
    ]
    text = notifications.summarize(items, "fr")
    assert text.startswith("2 notifications : Signal : Alice, On se voit à 18h ?. Mail : Facture")
    assert notifications.summarize([], "fr") == "Aucune notification récente."
    notifications.dismiss_all()
    assert "makoctl dismiss --all" in fake_system.joined_calls()
    fake_system.outputs["makoctl mode"] = "do-not-disturb"
    assert notifications.do_not_disturb(True) is True
    assert "makoctl mode -a do-not-disturb" in fake_system.joined_calls()


# ---------------------------------------------------------------- sessions
@pytest.fixture
def manager(journal, fake_system):
    fake_system.available |= {"hyprctl", "kdenlive", "ghostty"}
    sessions = [
        Session(
            "video",
            ["ma session vidéo", "session montage"],
            [SessionApp("kdenlive", 3), SessionApp("ghostty", 4)],
        )
    ]
    return SessionManager(sessions, journal, AppResolver())


def test_session_find(manager):
    assert manager.find("video").name == "video"
    assert manager.find("session montage").name == "video"
    assert manager.find("ma session video").name == "video"  # flou / sans accent
    assert manager.find("inconnue") is None
    assert manager.names() == ["video"]


def test_session_open(manager, fake_system):
    name, n = manager.open("session montage")
    assert (name, n) == ("video", 2)
    calls = fake_system.joined_calls()
    assert "hyprctl dispatch workspace 3" in calls and "hyprctl dispatch workspace 4" in calls
    assert ["kdenlive"] in fake_system.launched and ["ghostty"] in fake_system.launched
    with pytest.raises(RuntimeError, match="inconnue"):
        manager.open("truc")


def test_session_save_and_reopen(manager, fake_system, journal):
    fake_system.outputs["hyprctl -j clients"] = json.dumps(
        [
            {"class": "kdenlive", "workspace": {"id": 3}},
            {"class": "com.mitchellh.ghostty", "workspace": {"id": 1}},
            {"class": "kdenlive", "workspace": {"id": 3}},  # doublon ignoré
            {"class": "", "workspace": {"id": 2}},
        ]
    )
    assert manager.save("montage du soir") == 2
    saved = journal.get_pref("session.montage du soir")
    assert saved == [{"exec": "kdenlive", "workspace": 3}, {"exec": "ghostty", "workspace": 1}]
    session = manager.find("montage du soir")
    assert session is not None and [a.exec for a in session.apps] == ["kdenlive", "ghostty"]
    assert "montage du soir" in manager.names()
