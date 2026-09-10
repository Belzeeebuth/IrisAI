# Vie privée et sécurité

## Ce qui reste sur la machine (toujours)

- **Audio du micro** : capturé en mémoire par trames de 30 ms, découpé en phrases, transcrit, puis libéré. Aucun fichier audio n'est écrit (`iris listen` non plus). Iris ignore le micro pendant qu'elle parle.
- **Transcription** : faster-whisper en local. Modèle téléchargé une fois depuis Hugging Face (`~/.cache/huggingface`), puis utilisé hors-ligne.
- **Synthèse** : Piper en local (voix dans `~/.local/share/iris/voices`).
- **Compréhension** : règles locales, aucun modèle distant.

## Ce qui est écrit sur le disque

| Donnée | Emplacement | Contrôle |
|---|---|---|
| Journal des actions (intention, paramètres, résultat, durée, horodatage) | `~/.local/state/iris/iris.db` | `privacy.journal_actions = false` ; `iris journal --clear` |
| Texte des phrases entendues | même base, table `utterances` | **désactivé par défaut** (`privacy.store_transcripts`) |
| Préférences apprises (phases 3-4) | même base, table `prefs` | idem |
| Log technique (niveau INFO : ce qu'Iris entend et fait) | `~/.local/state/iris/iris.log` + journald | `journalctl --user -u iris` ; rotation 2 Mo × 3 |

Note : le log INFO contient le texte entendu (« Entendu [idle] : … ») pour le diagnostic. Lance le service avec `iris run` sans `-v` pour rester à ce niveau, ou réduis le niveau dans `iris/log.py` si tu veux un log muet.

## Ce qui peut sortir de la machine (opt-in explicite)

| Fonction | Condition | Ce qui est envoyé |
|---|---|---|
| Cerveau LLM (OpenCode Zen / Go, OpenAI, OpenRouter) | `privacy.allow_cloud = true`, `llm.enabled = true`, clé | Le texte des phrases non reconnues et des questions, la personnalité, la liste des capacités, et si `llm.context` : heure, classe + titre de la fenêtre active, workspace, batterie, trois dernières actions. Jamais l'audio. Avec `provider = "ollama"` (localhost), rien ne sort. |
| Voix OpenAI (`tts.backend = "openai"`) | `privacy.allow_cloud = true`, `OPENAI_API_KEY` | Le texte des réponses d'Iris (pas pour un serveur `localhost`). |
| ElevenLabs (voix) | `privacy.allow_cloud = true`, `tts.backend = "elevenlabs"`, `ELEVENLABS_API_KEY` | Le texte des réponses d'Iris. |
| API Whisper OpenAI (repli STT) | `privacy.allow_cloud = true`, `stt.cloud_fallback = true`, `OPENAI_API_KEY` | L'audio de la phrase, uniquement si le moteur local échoue. |
| Claude Code (phase 3) | `agents.claude_code_enabled = true` + `claude login` | Le texte après « demande à Claude … », via ton abonnement claude.ai. Jamais l'audio. |
| Téléchargement des voix / modèles | commandes `iris voices download`, `iris models download` | Rien de personnel (simple téléchargement). |

`privacy.allow_cloud = false` (défaut) rend inopérants le LLM distant, les voix cloud et le repli Whisper même s'ils sont configurés ; les URL `localhost` restent permises.

## Sécurité des actions

- Les actions destructrices (fermer tout, veille, extinction, redémarrage) exigent une confirmation orale ; le délai sans réponse annule.
- Les commandes personnalisées sont exécutées avec les droits de ta session (comme un raccourci clavier). Marque `confirm = true` celles qui ont un impact.
- Iris n'exécute jamais de shell arbitraire dicté à la voix : seules les phrases déclarées dans `[[commands]]` déclenchent un script. Le LLM ne peut proposer que des intentions de la liste des capacités (jamais `custom`, jamais de shell), et ses propositions critiques passent par la confirmation vocale.
- La dictée tape ce que tu dis dans la fenêtre active : en mode dictée, seule « fin de dictée » (ou « stop ») est interprétée.
- Le service tourne sans privilèges, dans `background.slice`, et ne fait pas tomber la session s'il plante (`Restart=on-failure`).

## À venir (phase 5)

Chiffrement du journal, rétention automatique, mode « sans trace », liste blanche des commandes.
