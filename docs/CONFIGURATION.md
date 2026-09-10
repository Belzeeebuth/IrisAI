# Configuration

Fichier : `~/.config/iris/config.toml` (`iris config path`). Créé avec toutes les clés commentées par `iris config init` ; toute clé absente prend la valeur par défaut embarquée (`iris/data/config.default.toml`). `iris config show` affiche la configuration effective. Après modification : `systemctl --user restart iris`.

## `[assistant]`

| Clé | Défaut | Rôle |
|---|---|---|
| `name` | `"Iris"` | Nom (notifications). |
| `language` | `"fr"` | Langue des réponses et de la transcription (`fr` / `en`). |
| `verbosity` | `"normal"` | `concise` · `normal` · `chatty` (ajoute « Autre chose ? »). |
| `tone` | `"warm"` | `warm` · `direct` · `coach`. |
| `active_window_s` | `8.0` | Après « Hey Iris » seul, secondes d'attente d'une commande. |
| `follow_up_window_s` | `5.0` | Après une commande, secondes pour enchaîner sans mot d'activation (`0` pour désactiver). |
| `confirm_timeout_s` | `12.0` | Délai de réponse à une demande de confirmation. |
| `ack_sound` | `true` | Bip d'activation (sinon « Oui ? » parlé). |

## `[wake]`

| Clé | Défaut | Rôle |
|---|---|---|
| `backend` | `"transcript"` | `transcript` (dans le texte, aucun modèle) · `openwakeword` (audio brut, modèle requis) · `none` (chaque phrase est une commande). |
| `phrases` | `["hey iris", "iris", "ok iris", "salut iris", "dis iris", "hé iris"]` | Phrases d'activation. Ajoute les variantes que Whisper produit chez toi. |
| `fuzzy_threshold` | `0.76` | Similarité minimale (0-1). Plus bas = plus tolérant, plus de faux positifs. |
| `openwakeword_model` | `""` | Chemin du modèle `.onnx` / `.tflite` (voir WAKEWORD.md). |
| `openwakeword_threshold` | `0.5` | Score de détection. |

## `[audio]`

| Clé | Défaut | Rôle |
|---|---|---|
| `backend` | `"auto"` | `sounddevice` · `parec` · `pw-record` · `arecord`. |
| `device` | `""` | Périphérique/source (nom ou index sounddevice, nom de source PipeWire pour parec). |
| `player` | `"auto"` | Lecture des réponses : `pw-play` · `paplay` · `aplay` · `ffplay` · `mpv` · `sounddevice`. |
| `sample_rate` / `frame_ms` | `16000` / `30` | Fréquence et taille de trame. |
| `vad_backend` | `"auto"` | `webrtc` (si installé) sinon `energy`. |
| `vad_aggressiveness` | `2` | webrtc : 0 (permissif) à 3 (strict). |
| `energy_threshold` | `0.010` | VAD énergie : seuil RMS (0-1). Baisse si Iris n'entend pas, monte si elle se déclenche sur le bruit. |
| `silence_ms` | `800` | Silence marquant la fin d'une phrase. |
| `min_speech_ms` | `250` | Durée minimale de parole. |
| `max_utterance_s` | `15.0` | Coupe les phrases trop longues. |
| `pre_roll_ms` | `300` | Audio conservé avant la détection de parole. |

## `[stt]`

| Clé | Défaut | Rôle |
|---|---|---|
| `backend` | `"faster-whisper"` | `faster-whisper` · `openai` (cloud) · `none`. |
| `model` | `"base"` | `tiny` · `base` · `small` · `medium` · `large-v3` ou chemin CTranslate2. **`small` recommandé en français** si le CPU suit. |
| `device` | `"auto"` | `cpu` · `cuda`. |
| `compute_type` | `"int8"` | `int8` (CPU) · `float16` (GPU) · `default`. |
| `language` | `""` | Vide = `assistant.language` ; `auto` = détection. |
| `beam_size` | `1` | 1 = rapide ; 5 = plus précis, plus lent. |
| `cloud_fallback` | `false` | API Whisper OpenAI si le local échoue (nécessite `privacy.allow_cloud` et `OPENAI_API_KEY`). |

## `[tts]`

| Clé | Défaut | Rôle |
|---|---|---|
| `backend` | `"auto"` | `piper` → `espeak` → `console` ; ou `elevenlabs`, `none`. |
| `piper_voice` | `"fr_FR-siwis-medium"` | `iris voices list --lang fr_FR`. |
| `piper_voices_dir` | `""` | Vide = `~/.local/share/iris/voices`. |
| `piper_length_scale` | `1.0` | < 1 plus rapide, > 1 plus lent. |
| `piper_sentence_silence` | `0.15` | Pause entre phrases (s). |
| `elevenlabs_voice_id` / `elevenlabs_model` | `""` / `eleven_multilingual_v2` | Nécessite `ELEVENLABS_API_KEY`. |
| `espeak_voice` | `"fr"` | Voix de secours. |
| `max_spoken_chars` | `600` | Troncature des réponses longues à l'oral. |

## `[privacy]`

| Clé | Défaut | Rôle |
|---|---|---|
| `allow_cloud` | `false` | Interrupteur général des backends réseau. |
| `store_transcripts` | `false` | Conserver le texte des phrases entendues dans le journal. |
| `journal_actions` | `true` | Tracer les actions exécutées. |

## `[system]`

| Clé | Défaut | Rôle |
|---|---|---|
| `terminal` / `browser` / `editor` | `""` | Forcer l'application ; vide = `$TERMINAL`, `omarchy-launch-browser`, `omarchy-launch-editor`… |
| `launcher` | `"auto"` | `uwsm` · `systemd-run` · `direct`. |
| `volume_step` / `brightness_step` | `5` / `10` | Pas pour « monte / baisse ». |
| `search_url` | DuckDuckGo | `{q}` est remplacé par la requête encodée. |
| `notify` | `true` | Notification bureau pour les réponses longues (agent). |

## `[agents]`

| Clé | Défaut | Rôle |
|---|---|---|
| `claude_code_enabled` | `false` | Active « demande à Claude … » via le CLI Claude Code (abonnement claude.ai). |
| `claude_bin` | `"claude"` | Binaire. |
| `claude_timeout_s` | `180` | Délai maximal. |
| `claude_workdir` | `""` | Dossier de travail (vide = home). |

## `[apps]`

Alias parlés supplémentaires : `"nom prononcé" = "commande"` ou `"webapp:URL"`. Priorité sur les alias embarqués (`iris/data/apps.toml`). Les variables d'environnement sont développées (`"$TERMINAL -e btop"`).

## `[[commands]]`

```toml
[[commands]]
name = "workspace-dev"                          # nom (journal, confirmation)
phrases = ["lance mon workspace de dev"]        # une ou plusieurs phrases (correspondance floue ≥ 85 %)
exec = "hyprctl dispatch workspace 2 && uwsm app -- ghostty"   # shell (sh -c)
confirm = false                                 # demander confirmation
wait = false                                    # attendre la fin (≤ 120 s) ; l'échec devient une réponse
reply = "Workspace de dev lancé."               # réponse parlée (défaut : « <name> : c'est fait. »)
```

Les commandes personnalisées sont testées **avant** les règles intégrées : elles peuvent donc redéfinir une phrase standard.
