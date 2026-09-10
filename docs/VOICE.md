# Voix IA

Iris parle avec une voix neuronale expressive. `tts.backend = "auto"` prend la meilleure voix disponible selon tes clés :
**ElevenLabs** (si `ELEVENLABS_API_KEY` et `privacy.allow_cloud = true`) → **OpenAI** → **Cartesia** → Kokoro (local, si installé) → Piper → espeak-ng → console.

Toutes les voix cloud bénéficient :
- du **cache disque** (`~/.cache/iris/tts`, `tts.cache = true`, 200 Mo max) : « Oui ? », « Workspace 2. », « Volume à 50 pour cent. » ne sont synthétisés qu'une fois ;
- de la lecture **phrase par phrase** (la phrase N est jouée pendant que N+1 se synthétise).

## ElevenLabs (recommandé)

La référence en naturel et en expressivité, avec des voix françaises natives dans la bibliothèque communautaire.

```bash
# 1. clé : https://elevenlabs.io → Profile → API keys
echo 'ELEVENLABS_API_KEY=sk_…' >> ~/.config/environment.d/iris.conf
systemctl --user import-environment ELEVENLABS_API_KEY

# 2. choisir une voix
iris voices list --engine elevenlabs              # voix de ton compte (prédéfinies + ajoutées)
iris voices library --lang fr                     # voix françaises natives de la bibliothèque
iris voices library --lang fr --gender female --search chaleureuse --preview 2   # écouter la 2e
iris voices add <owner> <voice_id> --name "Léa"   # l'ajouter à ton compte

# 3. essayer sans toucher à la config
iris say --backend elevenlabs --voice "Léa" "Bonjour, je suis Iris. Workspace de dev lancé, veux-tu que je lance aussi les agents ?"
```

```toml
[tts]
backend = "elevenlabs"                  # ou "auto"
elevenlabs_voice = "Léa"                # nom (résolu via /v1/voices) ou identifiant
elevenlabs_model = "eleven_multilingual_v2"
elevenlabs_stability = 0.45             # ↓ plus expressif, ↑ plus régulier
elevenlabs_similarity = 0.8
elevenlabs_style = 0.15                 # exagération du style (multilingual_v2 / flash)
elevenlabs_speed = 1.0                  # 0.7 → 1.2
elevenlabs_speaker_boost = true

[privacy]
allow_cloud = true
```

| Modèle | Pour | Notes |
|---|---|---|
| `eleven_multilingual_v2` | qualité de référence, français natif | défaut ; `language_code` non supporté (la langue est déduite du texte) |
| `eleven_flash_v2_5` | latence minimale (~75 ms), moitié prix | envoie `language_code = fr` pour verrouiller la langue |
| `eleven_turbo_v2_5` | compromis qualité / latence | |
| `eleven_v3` | le plus expressif | balises dans le texte des réponses (`[laughs]`, `[whispers]`, `[excited]`) ; `stability` arrondie à 0.0 / 0.5 / 1.0 ; `style` ignoré |

Iris transmet `previous_text` entre les phrases d'une même réponse pour une prosodie continue, demande du PCM 24 kHz (`elevenlabs_output_format`, `pcm_44100` selon le plan), et gère les erreurs de clé/quota par une réponse parlée de repli (console ou Piper), jamais un plantage.

Coût : la facturation est au caractère. Un usage assistant (≈ 50 réponses courtes par jour, ≈ 2 000 caractères) représente ≈ 60 000 caractères par mois **avant cache** ; avec le cache, une fraction. Le plan Starter (30 000 caractères) peut suffire, Creator (100 000) est confortable ; `eleven_flash_v2_5` compte moitié.

## OpenAI `gpt-4o-mini-tts`

Voix pilotables par **instructions** (Iris les dérive du ton : chaleureuse / directe / coach, ou `tts.openai_instructions`). Voix : `alloy, ash, ballad, coral, echo, fable, nova, onyx, sage, shimmer, verse, marin, cedar`. Le même backend pilote un serveur local compatible (Kokoro-FastAPI, Speaches : `openai_base_url = "http://localhost:8880/v1"`, sans clé ni `allow_cloud`).

```toml
[tts]
backend = "openai"
openai_voice = "coral"
openai_instructions = "Voix chaleureuse et posée, léger sourire, rythme naturel."
```

## Cartesia Sonic

Latence très faible et **émotions** contrôlables (`sonic-3`) : `content`, `calm`, `enthusiastic`, `curious`, `apologetic`…

```bash
# clé : https://play.cartesia.ai → API keys → CARTESIA_API_KEY
iris voices list --engine cartesia --lang fr
iris say --backend cartesia --voice <id> "Bonjour, je suis Iris."
```

```toml
[tts]
backend = "cartesia"
cartesia_voice = "<identifiant>"
cartesia_model = "sonic-3"
cartesia_emotion = "content"
cartesia_speed = 1.0
```

## Kokoro (local, facultatif)

Voix neuronale locale (Apache 2.0, 24 kHz). Testée : fonctionnelle en français (`ff_siwis`) mais jugée trop synthétique pour Iris ; elle reste disponible pour un usage 100 % hors-ligne. `iris voices download kokoro` (325 Mo, `--model kokoro-v1.0.int8.onnx` : 114 Mo). Sur un CPU lent elle peut être plus lente que le temps réel.

## Piper (secours)

Voix locale rapide mais synthétique, utilisée automatiquement si rien d'autre n'est disponible : `iris voices download fr_FR-siwis-medium`.

## Comparer et dépanner

```bash
iris say --backend elevenlabs "Workspace de dev lancé. Veux-tu que je lance aussi les agents ?"
iris say --backend openai     "…"
iris say --backend cartesia   "…"
iris say --backend piper      "…"
iris voices cache             # taille du cache ; --clear pour le vider (après un changement de voix, inutile : la clé inclut la voix)
iris doctor                   # « voix (ordre auto) » montre ce qui sera utilisé
```

`journalctl --user -u iris` affiche la voix choisie au démarrage (« Voix : elevenlabs ») et les erreurs (clé refusée, quota).
