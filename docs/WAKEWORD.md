# Mot d'activation

## Mode `transcript` (défaut)

Chaque phrase détectée par le VAD est transcrite localement, puis comparée aux `wake.phrases` par correspondance floue (`difflib`) sur les premiers ou les derniers mots. Avantages : rien à entraîner, fonctionne avec n'importe quel prénom, tolère « Irisse », « Irish », « Hé Iris ». Inconvénient : toute phrase entendue est transcrite (CPU), et la réactivité dépend de la vitesse de Whisper (~0,3-1 s avec `base` sur CPU).

Réglages : `wake.fuzzy_threshold` (0.76 : « Irish » passe, « gris »/« pris » non), `wake.phrases` (ajoute les variantes vues dans `journalctl --user -u iris`).

## Mode `openwakeword`

[openWakeWord](https://github.com/dscripka/openWakeWord) détecte le mot sur l'audio brut, en continu, sans transcrire. Il faut un modèle « hey iris » :

1. `uv pip install --python ~/.local/share/iris/venv/bin/python openwakeword`
2. `iris wakeword setup` (télécharge les modèles de features mel/embedding)
3. Entraîner un modèle avec le [notebook d'entraînement automatique](https://github.com/dscripka/openWakeWord/blob/main/notebooks/automatic_model_training.ipynb) (phrase cible : `hey iris`, ~1 h sur un GPU Colab gratuit), récupérer `hey_iris.onnx` ou `.tflite`
4. Copier le modèle dans `~/.local/share/iris/wakeword/` et configurer :

```toml
[wake]
backend = "openwakeword"
openwakeword_model = "~/.local/share/iris/wakeword/hey_iris.onnx"
openwakeword_threshold = 0.5
```

Dans ce mode, la détection déclenche le bip d'activation ; la phrase suivante est transcrite comme commande. « Iris, … » dans une même phrase reste aussi reconnu par la transcription.

Un modèle « hey iris » pré-entraîné sera fourni dans le dépôt (roadmap phase 1/5).

## Mode `none`

Pas de mot d'activation : chaque phrase est une commande. Utile pour un mode push-to-talk (`iris listen --execute` sur un raccourci Hyprland) ou pour tester.
