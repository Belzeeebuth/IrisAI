import json

from iris.core.status import StatusWriter, default_status_file, pid_file


def test_status_write_and_read(tmp_path, fake_system):
    path = tmp_path / "run" / "state.json"
    writer = StatusWriter(path, waybar_signal=8)
    fake_system.available.add("pkill")
    writer.write("active", "à l'écoute")
    data = json.loads(path.read_text())
    assert data["alt"] == "active" and data["class"] == "active" and "à l'écoute" in data["tooltip"]
    assert StatusWriter.read(path)["state"] == "active"
    assert ["pkill", "-RTMIN+8", "waybar"] in fake_system.calls
    assert StatusWriter.read(tmp_path / "nope.json") is None


def test_default_paths(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    assert default_status_file() == tmp_path / "iris" / "state.json"
    assert pid_file() == tmp_path / "iris" / "iris.pid"
