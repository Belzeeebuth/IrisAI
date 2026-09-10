# Changelog

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
