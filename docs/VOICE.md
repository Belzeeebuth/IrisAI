# Voix IA

Iris dispose de quatre backends de synthèse. `tts.backend = "auto"` prend le premier disponible dans l'ordre Kokoro → Piper → espeak-ng → console.

## Kokoro (local, défaut)

[Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) est un modèle neuronal open-source (Apache 2.0) au rendu très naturel, exécuté en local via `kokoro-onnx` (ONNX Runtime, CPU, 24 kHz). Aucune donnée ne sort de la machine.

```bash
uv pip install --python ~/.local/share/iris/venv/bin/python kokoro-onnx   # ou extra [voice]
iris voices download kokoro                       # kokoro-v1.0.onnx (fp32, 325 Mo) + voices-v1.0.bin (28 Mo)
iris voices download kokoro --model kokoro-v1.0.int8.onnx   # variante légère (114 Mo)
iris voices list --engine kokoro
iris say "Bonjour, je suis Iris."
```

```toml
[tts]
backend = "kokoro"
kokoro_model = "kokoro-v1.0.onnx"
kokoro_voice = ""        # vide = ff_siwis (fr) / af_heart (en)
kokoro_speed = 1.0       # 1.05-1.1 pour un débit plus vif
kokoro_lang = ""         # vide = suit la langue ; "fr-fr", "en-us", "en-gb"
```

Voix : français `ff_siwis` (la seule voix française de v1.0) ; anglais `af_heart` (recommandée), `af_bella`, `af_nicole`, `am_michael`, `am_fenrir`, `bf_emma`, `bm_george`… (54 voix). Le modèle reste chargé en mémoire après le premier appel (~1 s de chargement).

Performance mesurée : sur un vCPU Xeon bridé (4 cœurs, conteneur), modèle int8, facteur temps réel ≈ 2,7 (7,9 s d'audio en 19 s à froid, 5,7 s en 15 s à chaud). Sur un CPU de bureau ou de portable récent, Kokoro est généralement plus rapide que le temps réel (RTF 0,2-0,5). La lecture en pipeline (phrase N jouée pendant que N+1 se synthétise) masque une bonne partie de la latence. Si c'est trop lent : `kokoro-v1.0.int8.onnx`, `verbosity = "concise"`, ou un serveur Kokoro-FastAPI sur GPU (ci-dessous).

Échantillon généré pendant le développement : `Bonjour ! Je suis Iris, l'assistante vocale d'Omarchy…` (voix `ff_siwis`, int8).

## OpenAI-compatible `/audio/speech`

Un seul backend pour :

- **OpenAI** `gpt-4o-mini-tts` : voix expressives et **pilotables par instructions** ; Iris dérive l'instruction du ton (`warm` : « voix chaleureuse, naturelle et posée, léger sourire » ; `direct` ; `coach`) ou utilise `tts.openai_instructions`. Voix : `alloy, ash, ballad, coral, echo, fable, nova, onyx, sage, shimmer, verse, marin, cedar`.
- **Serveurs locaux** exposant la même API : [Kokoro-FastAPI](https://github.com/remsky/Kokoro-FastAPI) (`http://localhost:8880/v1`, GPU), [Speaches](https://github.com/speaches-ai/speaches), LM Studio… Aucune clé nécessaire pour une URL `localhost`, et `privacy.allow_cloud` n'est pas requis.

```toml
[tts]
backend = "openai"
openai_base_url = "https://api.openai.com/v1"    # ou http://localhost:8880/v1
openai_model = "gpt-4o-mini-tts"                 # Kokoro-FastAPI : "kokoro"
openai_voice = "coral"                           # Kokoro-FastAPI : "ff_siwis"
openai_instructions = ""                         # ex. "Voix douce et complice, rythme calme."
openai_speed = 1.0
openai_api_key_env = "OPENAI_API_KEY"

[privacy]
allow_cloud = true                               # pour api.openai.com
```

Le flux est demandé en PCM 24 kHz (`response_format = "pcm"`) ; si le serveur ne le supporte pas, Iris redemande en WAV.

## ElevenLabs

```toml
[tts]
backend = "elevenlabs"
elevenlabs_voice_id = "…"                        # ID de la voix (console ElevenLabs)
elevenlabs_model = "eleven_multilingual_v2"      # ou eleven_v3 / eleven_flash_v2_5
[privacy]
allow_cloud = true
```

Clé : `ELEVENLABS_API_KEY`. Sortie PCM 22,05 kHz. Nécessite l'extra `cloud` (`requests`).

## Piper (secours)

Voix locale rapide mais synthétique : `iris voices download fr_FR-siwis-medium`. Utilisée automatiquement si Kokoro n'est pas installé.

## Comparer

```bash
iris say --backend kokoro "Workspace de dev lancé. Veux-tu que je lance aussi les agents ?"
iris say --backend openai "Workspace de dev lancé. Veux-tu que je lance aussi les agents ?"
iris say --backend piper  "Workspace de dev lancé. Veux-tu que je lance aussi les agents ?"
iris say --lang en "Hello, I'm Iris."
```

## Pistes (roadmap)

Kyutai TTS (français natif, streaming, GPU), Chatterbox multilingue (émotion contrôlable), Orpheus, XTTS ; voix « émotionnelle » selon le contexte (erreur, succès, matin) ; cache des réponses fréquentes.
