"""Détection sur l'audio brut avec openWakeWord (modèle personnalisé « hey iris »).

Nécessite ``pip install openwakeword`` et un modèle entraîné (voir docs/WAKEWORD.md).
Fonctionne sur des trames 16 kHz mono int16 ; openWakeWord préfère des blocs de 80 ms (1280 échantillons).
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

CHUNK = 1280


class OpenWakeWord:
    def __init__(self, model_path: str, threshold: float = 0.5) -> None:
        try:
            from openwakeword.model import Model
        except ImportError as exc:  # pragma: no cover - dépend de l'environnement
            raise RuntimeError(
                "openwakeword n'est pas installé : pip install 'iris-assistant[wakeword]'"
            ) from exc
        path = Path(model_path).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"Modèle wake word introuvable : {path}")
        framework = "onnx" if path.suffix == ".onnx" else "tflite"
        self.model = Model(wakeword_models=[str(path)], inference_framework=framework)
        self.threshold = threshold
        self._buffer = np.zeros(0, dtype=np.int16)
        log.info("openWakeWord chargé : %s (%s)", path.name, framework)

    def process(self, frame: np.ndarray) -> bool:
        """Retourne True dès qu'un score dépasse le seuil ; réinitialise le modèle ensuite."""
        self._buffer = np.concatenate([self._buffer, frame.astype(np.int16, copy=False)])
        detected = False
        while len(self._buffer) >= CHUNK:
            chunk, self._buffer = self._buffer[:CHUNK], self._buffer[CHUNK:]
            scores = self.model.predict(chunk)
            if any(score >= self.threshold for score in scores.values()):
                detected = True
        if detected:
            self.model.reset()
            self._buffer = np.zeros(0, dtype=np.int16)
        return detected


def setup_base_models() -> str:
    """Télécharge les modèles de features (mel + embedding) requis par openWakeWord."""
    try:
        import openwakeword.utils
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("openwakeword n'est pas installé") from exc
    openwakeword.utils.download_models()
    return "Modèles openWakeWord téléchargés."
