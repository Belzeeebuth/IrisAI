import iris.stt.faster_whisper as fw
from iris.config import STTConfig


def test_resolve_device_without_cuda(monkeypatch):
    monkeypatch.setattr(fw, "cuda_usable", lambda: False)
    assert fw.resolve_device("auto") == ("cpu", None)
    assert fw.resolve_device("cpu") == ("cpu", None)
    device, reason = fw.resolve_device("cuda")
    assert device == "cpu" and "libcublas" in reason


def test_resolve_device_with_cuda(monkeypatch):
    monkeypatch.setattr(fw, "cuda_usable", lambda: True)
    assert fw.resolve_device("auto") == ("cuda", None)
    assert fw.resolve_device("cuda") == ("cuda", None)


def test_cuda_error_detection():
    assert fw._is_cuda_error(
        RuntimeError("Library libcublas.so.12 is not found or cannot be loaded")
    )
    assert fw._is_cuda_error(RuntimeError("Unable to load libcudnn_ops.so.9"))
    assert not fw._is_cuda_error(RuntimeError("model file not found"))


class FakeSegment:
    def __init__(self, text: str, no_speech_prob: float = 0.0) -> None:
        self.text = text
        self.no_speech_prob = no_speech_prob


class FakeInfo:
    language = "fr"
    language_probability = 0.99


def test_transcribe_falls_back_to_cpu_after_cuda_failure(monkeypatch):
    import sys
    import types

    import numpy as np

    created: list[tuple[str, str]] = []

    class FakeWhisperModel:
        def __init__(self, model, device="auto", compute_type="default"):
            created.append((device, compute_type))
            self.device = device

        def transcribe(self, samples, **kwargs):
            if self.device == "cuda":
                raise RuntimeError("Library libcublas.so.12 is not found or cannot be loaded")
            return [FakeSegment(" monte le son ")], FakeInfo()

    monkeypatch.setitem(
        sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=FakeWhisperModel)
    )
    monkeypatch.setattr(fw, "cuda_usable", lambda: True)  # libs chargeables mais inférence en échec
    stt = fw.FasterWhisperSTT(STTConfig(device="auto", compute_type="float16"))
    text = stt.transcribe(np.zeros(16000, dtype=np.int16), 16000, "fr")
    assert text == "monte le son"
    assert created == [("cuda", "float16"), ("cpu", "int8")]
    assert stt.device == "cpu" and stt.last_language == "fr"


def test_load_uses_cpu_directly_without_cuda_libs(monkeypatch):
    import sys
    import types

    created: list[tuple[str, str]] = []

    class FakeWhisperModel:
        def __init__(self, model, device="auto", compute_type="default"):
            created.append((device, compute_type))

    monkeypatch.setitem(
        sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=FakeWhisperModel)
    )
    monkeypatch.setattr(fw, "cuda_usable", lambda: False)
    fw.FasterWhisperSTT(STTConfig(device="auto", compute_type="float16")).load()
    assert created == [("cpu", "int8")]
