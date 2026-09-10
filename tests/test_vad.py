import numpy as np

from iris.audio.vad import EnergyVad, VadSegmenter
from iris.config import AudioConfig


def synth(cfg: AudioConfig, silence_s: float, speech_s: float, tail_s: float) -> np.ndarray:
    rate = cfg.sample_rate
    rng = np.random.default_rng(0)
    quiet = lambda s: (rng.normal(0, 40, int(rate * s))).astype(np.int16)  # noqa: E731
    t = np.arange(int(rate * speech_s)) / rate
    voice = (np.sin(2 * np.pi * 220 * t) * 6000 + rng.normal(0, 300, t.size)).astype(np.int16)
    return np.concatenate([quiet(silence_s), voice, quiet(tail_s)])


def frames(audio: np.ndarray, n: int):
    for i in range(0, len(audio) - n + 1, n):
        yield audio[i : i + n]


def test_segmenter_extracts_one_utterance() -> None:
    cfg = AudioConfig(vad_backend="energy", silence_ms=600, pre_roll_ms=300, min_speech_ms=200)
    seg = VadSegmenter(cfg, EnergyVad(cfg.energy_threshold))
    audio = synth(cfg, 1.0, 1.2, 1.5)
    utterances = [
        u for u in (seg.push(f) for f in frames(audio, cfg.frame_samples)) if u is not None
    ]
    assert len(utterances) == 1
    duration = len(utterances[0]) / cfg.sample_rate
    assert 1.2 <= duration <= 2.2  # parole + pré-roll + ~200 ms de silence


def test_short_noise_is_dropped() -> None:
    cfg = AudioConfig(vad_backend="energy", min_speech_ms=400)
    seg = VadSegmenter(cfg, EnergyVad(cfg.energy_threshold))
    audio = synth(cfg, 0.5, 0.12, 1.5)  # 120 ms de « parole »
    utterances = [
        u for u in (seg.push(f) for f in frames(audio, cfg.frame_samples)) if u is not None
    ]
    assert utterances == []


def test_max_utterance_cuts_long_speech() -> None:
    cfg = AudioConfig(vad_backend="energy", max_utterance_s=1.0, silence_ms=500)
    seg = VadSegmenter(cfg, EnergyVad(cfg.energy_threshold))
    audio = synth(cfg, 0.3, 3.0, 1.0)
    utterances = [
        u for u in (seg.push(f) for f in frames(audio, cfg.frame_samples)) if u is not None
    ]
    assert len(utterances) >= 2
    assert all(len(u) / cfg.sample_rate <= 1.05 for u in utterances)


def test_energy_vad_adapts_to_noise_floor() -> None:
    vad = EnergyVad(threshold=0.01)
    quiet = np.zeros(480, dtype=np.int16)
    assert vad.is_speech(quiet) is False
    loud = (np.sin(np.linspace(0, 50, 480)) * 8000).astype(np.int16)
    assert vad.is_speech(loud) is True
