# Roadmap d'Iris

Cinq phases, chacune livrable et utile seule. Les cases cochées sont dans le dépôt.

## Phase 1 — Prototype vocal ✅ (v0.1)

Objectif : dire « Hey Iris, monte le son » et que ça marche, en local.

- [x] Capture micro multi-backend (sounddevice, parec, pw-record, arecord) avec horodatage
- [x] VAD : webrtcvad ou seuil d'énergie adaptatif ; découpage en phrases avec pré-roll
- [x] Transcription locale faster-whisper (int8, CPU/GPU), filtrage des hallucinations, `hotwords="Iris"`
- [x] Mot d'activation par correspondance floue sur la transcription (préfixe, suffixe, mots parasites)
- [x] Backend openWakeWord optionnel (audio brut) — modèle « hey iris » à fournir
- [x] NLU à règles fr/en : 42 intentions, nombres en lettres, formules de politesse, URLs dictées
- [x] Actions : Hyprland, volume, luminosité, applications (alias + .desktop + web-apps), Omarchy (thèmes, lock, screenshot, nightlight), médias, alimentation, web, heure/date
- [x] Confirmations pour les actions critiques (fermer tout, veille, extinction, redémarrage, commandes perso marquées)
- [x] Machine à états : activation, fenêtre d'enchaînement, pause, reprise, délais
- [x] Voix Piper (API Python ou binaire) ; repli espeak-ng ; repli console ; ElevenLabs en opt-in
- [x] Journal SQLite des actions + préférences (fondation mémoire)
- [x] Commandes personnalisées `[[commands]]` (phrases → shell, confirm, wait, reply)
- [x] Ton (warm / direct / coach) et verbosité (concise / normal / chatty)
- [x] CLI complète, `iris doctor`, service systemd, script d'installation Omarchy, autostart Hyprland
- [x] 186 tests unitaires sans matériel
- [ ] Calibration terrain des seuils VAD / wake word sur Omarchy
- [ ] Modèle openWakeWord « hey iris » pré-entraîné livré dans `iris/data/`
- [ ] Paquet AUR `iris-assistant`

## Phase 2 — Intégration système ✅ (v0.2)

Objectif : Iris devient un citoyen du bureau Omarchy.

- [x] Dictée : « écris : … » tape dans la fenêtre active (`wtype` → `ydotool` → presse-papiers) ; mode dictée continue jusqu'à « fin de dictée »
- [x] Widget d'état Waybar (`iris status --waybar`, `contrib/waybar`, signal de rafraîchissement) — [ ] variante Quickshell
- [x] Notifications mako : lecture résumée de l'historique, effacement, ne pas déranger
- [x] Sessions de workspaces nommées (`[[sessions]]`) + sauvegarde des fenêtres ouvertes
- [x] Multi-écrans : « envoie ça sur l'écran de droite », « va sur l'écran de gauche »
- [x] Périphériques : Bluetooth (`bluetoothctl`, alias, correspondance floue), Wi-Fi (`nmcli`/`rfkill`), mode avion, batterie, sortie audio (`omarchy-cmd-audio-switch`/`wpctl`)
- [x] Push-to-talk : `iris trigger` (SIGUSR1) + raccourci Hyprland (`contrib/hypr/iris.conf`), pause par SIGUSR2
- [x] Découpage de plusieurs commandes dans une phrase, formes elliptiques comprises
- [x] Langue automatique : réponses dans la langue détectée par Whisper (`assistant.language = "auto"`)
- [x] **Voix IA** : Kokoro local (défaut), OpenAI-compatible (`gpt-4o-mini-tts`, Kokoro-FastAPI, Speaches), ElevenLabs ; lecture en pipeline phrase par phrase
- [x] **Cerveau LLM** (avancé depuis la phase 3) : OpenCode Go / Zen, OpenAI, OpenRouter, Ollama, custom ; repli NLU avec liste des capacités en JSON, questions ouvertes, personnalité, contexte, historique
- [ ] Notifications riches émises par Iris (icône, actions cliquables)
- [ ] Widget Quickshell

## Phase 3 — Agents IA + mémoire contextuelle

Objectif : Iris agit dans la durée et se souvient.

- [ ] Pont Claude Code (`claude -p`, abonnement claude.ai, **pas d'API**) asynchrone : « je demande à Claude » puis notification et résumé vocal
- [ ] Agents en arrière-plan (`claude`, `opencode`, `codex`, scripts) avec suivi : « surveille la compilation » → notification à la fin
- [ ] Mémoire contextuelle SQLite : projets ouverts, dernier workspace, tâches en cours, préférences apprises ; historique LLM persistant
- [ ] « Veux-tu reprendre ta session de codage d'hier ? » au démarrage (opt-in)
- [ ] Transcription voix → prompt dans le terminal actif (style BridgeVoice)
- [ ] Réponses LLM en streaming (phrase par phrase vers la voix)
- [ ] Outils LLM avancés : lecture d'un fichier, résumé de la fenêtre active, calculs

## Phase 4 — Personnalisation + apprentissage

- [ ] Profil de personnalité libre (`assistant.personality = "Sois directe, tutoie, pas de blabla"`) appliqué aux réponses générées
- [ ] Apprentissage des habitudes depuis le journal : fréquences par heure / jour → suggestions (« Tu lances souvent Spotify à 9 h, je le fais automatiquement ? »)
- [ ] Planificateur : « chaque matin à 9 h, lance mon workspace de dev » → unité systemd timer générée
- [ ] Alias appris : « quand je dis "mon éditeur", c'est Zed » sans éditer la config
- [ ] Voix : choix du locuteur, vitesse, réglages par contexte
- [ ] Multi-langue dans la session

## Phase 5 — Mode privé + performances

- [ ] Chiffrement du journal et des préférences (clé dans le trousseau)
- [ ] Effacement automatique (rétention configurable) et mode « sans journal »
- [ ] *Barge-in* : interrompre Iris en parlant (annulation de la lecture + écho)
- [ ] STT en streaming (résultats partiels) pour une latence < 500 ms
- [ ] Front-end audio en Rust : capture, VAD, wake word, ring buffer — 0 % CPU au repos
- [ ] Moteurs alternatifs : whisper.cpp, Parakeet (NeMo), GPU (CUDA / ROCm)
- [ ] Modèle wake word « hey iris » de qualité (jeu de données + entraînement reproductible)
- [ ] Audit sécurité : liste blanche des commandes shell, sandbox des commandes perso
