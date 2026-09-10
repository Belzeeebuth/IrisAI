# Changelog

## 0.3.0 — Phase 3 : tâches, agents, projets, mémoire

- **Tâches en arrière-plan** (`[[tasks]]`) : lancement, surveillance d'un processus existant, état, annulation, lecture du résultat ; annonce vocale et notification à la fin, différées pendant une confirmation ou une dictée ; historique `iris tasks`.
- **Agents IA** lancés à la voix : Claude Code (`claude -p`), OpenCode (`opencode run`), Codex (`codex exec`), Gemini CLI, dans le dossier du projet (« … dans le projet X ») ; résumé parlé + notification ; `iris agents`. Remplace l'ancien pont Claude synchrone (clés `claude_code_*` toujours acceptées).
- **Projets** : « ouvre le projet X » (éditeur + terminal dans le dossier), `[projects]`, `system.project_dirs`, `iris projects`.
- **Voix → terminal** : « envoie : … », « dis au terminal … », « mode terminal » (dictée avec Entrée).
- **Mémoire persistante** : faits (« retiens que … », « oublie … », « que sais-tu de moi ? »), injectés dans le prompt du LLM ; historique de conversation LLM persistant ; instantanés de session et « reprends ma session d'hier » ; proposition de reprise au démarrage (`assistant.resume_prompt`) ; `iris memory`.
- **LLM** : réponses en streaming (SSE, phrase par phrase), outils du modèle (`calc`, `clipboard`, `read_file`, `recall`, `tasks`).
- Les slots libres (dictée, prompts, mémoire, recherches) conservent le texte d'origine (accents, majuscules).
- Mot d'activation en fin de phrase : « ouvre le projet iris » n'est plus tronqué.
- 77 intentions, 336 tests.

## 0.2.1 — Voix cloud premium, repli CPU

- **ElevenLabs** devient la voix de référence : backend réécrit sans dépendance (`xi-api-key`, PCM 24 kHz), voix par **nom** résolue via `/v1/voices`, exploration de la **bibliothèque** communautaire par langue (`iris voices library --lang fr --preview N`) et ajout au compte (`iris voices add`), réglages `stability / similarity / style / speed / speaker_boost`, `language_code` pour flash/turbo/v3, `previous_text` pour la continuité entre phrases, arrondi de `stability` pour `eleven_v3`.
- **Cartesia Sonic** : nouveau backend (`sonic-3`, émotions, `Cartesia-Version 2026-08-14`), `iris voices list --engine cartesia`.
- **Cache disque** des synthèses cloud (`tts.cache`, `iris voices cache [--clear]`).
- `tts.backend = "auto"` choisit la meilleure voix disponible selon les clés et `privacy.allow_cloud` ; Kokoro n'est plus installée par défaut (`install.sh --kokoro`).
- `iris say --voice`, `iris voices list --engine elevenlabs|cartesia|openai`.
- **STT** : bascule automatique sur CPU quand les bibliothèques CUDA manquent (`libcublas.so.12`), `iris doctor` affiche le périphérique effectif.

## 0.2.0 — Phase 2 : intégration système, voix IA, cerveau LLM

- **Voix IA** : Kokoro-82M en local (backend par défaut, `iris voices download kokoro`), endpoint OpenAI-compatible `/audio/speech` (OpenAI `gpt-4o-mini-tts` avec instructions de style selon le ton, Kokoro-FastAPI, Speaches), lecture phrase par phrase en pipeline. Piper reste en secours.
- **Cerveau LLM** : client OpenAI / Anthropic-compatible sans dépendance (OpenCode Go `https://opencode.ai/zen/go/v1`, OpenCode Zen `https://opencode.ai/zen/v1`, OpenAI, OpenRouter, Ollama, custom) ; repli sur phrase inconnue (action Iris / réponse / silence), questions ouvertes (`ask_llm`), personnalité libre, contexte (heure, fenêtre, workspace, batterie, dernières actions), historique de conversation ; `iris llm info|test|decide|models`.
- **Dictée** : `type_text` (« écris : … »), mode dictée continue (`wtype` → `ydotool` → presse-papiers).
- **Écrans** : déplacer une fenêtre / le focus vers l'écran voisin.
- **Périphériques** : Bluetooth (on/off, connexion par nom, alias `[bluetooth]`), Wi-Fi, mode avion, batterie, sortie audio.
- **Notifications** mako : lecture résumée, effacement, ne pas déranger.
- **Sessions** de workspaces : `[[sessions]]` + sauvegarde des fenêtres ouvertes.
- **Plusieurs commandes** par phrase (« … et … », formes elliptiques).
- **Push-to-talk** : `iris trigger` (SIGUSR1/SIGUSR2), raccourci Hyprland ; **état Waybar** (`iris status --waybar`, module `contrib/waybar`).
- **Langue automatique** (`assistant.language = "auto"`) : réponses dans la langue détectée par Whisper.
- 22 nouvelles intentions (64 au total), 260 tests.

## 0.1.0 — Phase 1 : prototype vocal

Première version. Activation « Hey Iris » (transcription floue, openWakeWord optionnel), transcription locale faster-whisper, VAD, ~45 intentions fr/en (applications, Hyprland, volume, luminosité, médias, thèmes Omarchy, alimentation avec confirmation, web, heure/date), commandes personnalisées, voix Piper avec replis, machine à états (activation, enchaînement, confirmation, pause), journal SQLite, CLI complète (`run`, `repl`, `ask`, `say`, `listen`, `doctor`, `config`, `voices`, `models`, `journal`, `service`), service systemd, script d'installation Omarchy, 186 tests.
