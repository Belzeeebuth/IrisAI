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

## Phase 2 — Intégration système

Objectif : Iris devient un citoyen du bureau Omarchy.

- [ ] Dictée : « Iris, écris : … » tape le texte dans la fenêtre active (`wtype` / `ydotool`), mode « commande » vs « dictée »
- [ ] Widget d'état Waybar (module custom : idle / écoute / réflexion / parle) et variante Quickshell
- [ ] Notifications riches (icône, actions cliquables) et lecture des notifications récentes (mako)
- [ ] Sessions de workspaces nommées : « ouvre ma session vidéo » (apps + positions), sauvegarde/restauration via `hyprctl clients`
- [ ] Multi-écrans : « envoie ça sur l'écran de droite »
- [ ] Périphériques : Bluetooth (`bluetuith`/`bluetoothctl`), Wi-Fi (`iwctl`/`nmcli`), sortie audio (`omarchy-cmd-audio-switch`)
- [ ] Raccourci push-to-talk (Super + espace) via keybinding Hyprland → `iris listen --execute`
- [ ] Découpage de plusieurs commandes dans une phrase (« ouvre A et ferme B »)
- [ ] Localisation : détection auto fr/en par phrase

## Phase 3 — Agents IA + mémoire contextuelle

Objectif : au-delà des règles, avec Claude via l'abonnement claude.ai (**pas l'API**).

- [ ] Pont Claude Code (`claude -p`) asynchrone : Iris répond « je demande à Claude » et notifie la réponse
- [ ] Repli NLU → LLM : une phrase non reconnue par les règles est envoyée à Claude avec la liste des outils d'Iris (schéma JSON), qui renvoie l'intention à exécuter
- [ ] Lancement d'agents en arrière-plan (`claude`, `codex`, scripts) avec suivi : « surveille la compilation » → notification à la fin, résumé vocal
- [ ] Mémoire contextuelle SQLite : projets ouverts, dernier workspace, tâches en cours, préférences apprises
- [ ] « Veux-tu reprendre ta session de codage d'hier ? » au démarrage (opt-in)
- [ ] Transcription voix → prompt pour Claude Code dans le terminal actif (style BridgeVoice)
- [ ] LLM local optionnel (Ollama) pour rester 100 % hors-ligne

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
