"""Capture du micro en trames int16 mono.

Backends (ordre « auto ») :
1. ``sounddevice`` (PortAudio) si le module est installé ;
2. ``parec`` (libpulse, fonctionne avec pipewire-pulse) ;
3. ``pw-record`` (PipeWire natif) ;
4. ``arecord`` (ALSA).

Chaque trame est horodatée (``time.monotonic()``) pour pouvoir ignorer ce qui a été
capté pendant qu'Iris parlait.
"""

from __future__ import annotations

import logging
import queue
import shutil
import subprocess
import threading
import time
from collections.abc import Iterator

import numpy as np

from iris.config import AudioConfig

log = logging.getLogger(__name__)


class CaptureError(RuntimeError):
    pass


class AudioCapture:
    def __init__(self, cfg: AudioConfig) -> None:
        self.cfg = cfg
        self.backend = "none"
        self._queue: queue.Queue[tuple[float, np.ndarray]] = queue.Queue(maxsize=2000)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._proc: subprocess.Popen[bytes] | None = None
        self._stream = None

    # ------------------------------------------------------------------ cycle de vie
    def start(self) -> None:
        order = (
            ["sounddevice", "parec", "pw-record", "arecord"]
            if self.cfg.backend == "auto"
            else [self.cfg.backend]
        )
        errors: list[str] = []
        for backend in order:
            try:
                getattr(self, f"_start_{backend.replace('-', '_')}")()
                self.backend = backend
                log.info(
                    "Capture audio : %s @ %d Hz, trames de %d ms",
                    backend,
                    self.cfg.sample_rate,
                    self.cfg.frame_ms,
                )
                return
            except Exception as exc:
                errors.append(f"{backend}: {exc}")
        raise CaptureError("Aucun backend de capture audio disponible — " + " | ".join(errors))

    def stop(self) -> None:
        self._stop.set()
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        if self._proc is not None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=2)
            except Exception:
                self._proc.kill()
            self._proc = None

    def frames(self, timeout: float = 0.5) -> Iterator[tuple[float, np.ndarray]]:
        """Itère sur (horodatage, trame). Se termine quand ``stop()`` est appelé."""
        while not self._stop.is_set():
            try:
                yield self._queue.get(timeout=timeout)
            except queue.Empty:
                if self._proc is not None and self._proc.poll() is not None:
                    raise CaptureError(
                        f"Le processus de capture ({self.backend}) s'est arrêté"
                    ) from None
                continue

    def _put(self, frame: np.ndarray) -> None:
        try:
            self._queue.put_nowait((time.monotonic(), frame))
        except queue.Full:
            # on préfère perdre de l'audio que bloquer la capture
            try:
                self._queue.get_nowait()
                self._queue.put_nowait((time.monotonic(), frame))
            except queue.Empty:
                pass

    # ------------------------------------------------------------------ backends
    def _start_sounddevice(self) -> None:
        import sounddevice as sd

        device: int | str | None = None
        if self.cfg.device:
            device = int(self.cfg.device) if self.cfg.device.isdigit() else self.cfg.device

        def callback(indata, frames, _time, status) -> None:  # noqa: ANN001
            if status:
                log.debug("sounddevice status: %s", status)
            self._put(np.frombuffer(bytes(indata), dtype=np.int16).copy())

        self._stream = sd.RawInputStream(
            samplerate=self.cfg.sample_rate,
            blocksize=self.cfg.frame_samples,
            channels=1,
            dtype="int16",
            device=device,
            callback=callback,
        )
        self._stream.start()

    def _start_subprocess(self, argv: list[str]) -> None:
        if shutil.which(argv[0]) is None:
            raise CaptureError(f"{argv[0]} introuvable")
        self._proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        frame_bytes = self.cfg.frame_samples * 2

        def reader() -> None:
            assert self._proc is not None and self._proc.stdout is not None
            stream = self._proc.stdout
            while not self._stop.is_set():
                data = stream.read(frame_bytes)
                if not data:
                    break
                if len(data) < frame_bytes:
                    data = data + b"\x00" * (frame_bytes - len(data))
                self._put(np.frombuffer(data, dtype=np.int16).copy())

        self._thread = threading.Thread(target=reader, name="iris-capture", daemon=True)
        self._thread.start()
        time.sleep(0.2)
        if self._proc.poll() is not None:
            raise CaptureError(
                f"{argv[0]} s'est arrêté immédiatement (code {self._proc.returncode})"
            )

    def _start_parec(self) -> None:
        argv = [
            "parec",
            "--raw",
            f"--rate={self.cfg.sample_rate}",
            "--channels=1",
            "--format=s16le",
            f"--latency-msec={self.cfg.frame_ms}",
        ]
        if self.cfg.device:
            argv.append(f"--device={self.cfg.device}")
        self._start_subprocess(argv)

    def _start_pw_record(self) -> None:
        argv = [
            "pw-record",
            "--raw",
            f"--rate={self.cfg.sample_rate}",
            "--channels=1",
            "--format=s16",
        ]
        if self.cfg.device:
            argv.append(f"--target={self.cfg.device}")
        argv.append("-")
        self._start_subprocess(argv)

    def _start_arecord(self) -> None:
        argv = [
            "arecord",
            "-q",
            "-t",
            "raw",
            "-f",
            "S16_LE",
            "-r",
            str(self.cfg.sample_rate),
            "-c",
            "1",
        ]
        if self.cfg.device:
            argv += ["-D", self.cfg.device]
        self._start_subprocess(argv)


def record_seconds(cfg: AudioConfig, seconds: float) -> np.ndarray:
    """Enregistre ``seconds`` secondes (utilisé par ``iris listen``)."""
    cap = AudioCapture(cfg)
    cap.start()
    needed = int(seconds * cfg.sample_rate)
    chunks: list[np.ndarray] = []
    total = 0
    try:
        for _, frame in cap.frames():
            chunks.append(frame)
            total += frame.shape[0]
            if total >= needed:
                break
    finally:
        cap.stop()
    return np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.int16)
