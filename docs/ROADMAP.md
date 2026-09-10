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
- [x] Widget d'état Waybar (`iris status --waybar`, `contrib/waybar`, signal de rafraîchissement) — [x] variante Quickshell (`contrib/quickshell`, phase 4)
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

## Phase 3 — Agents IA + mémoire contextuelle ✅ (v0.3)

Objectif : Iris agit dans la durée et se souvient.

- [x] Tâches en arrière-plan (`[[tasks]]`) avec annonce vocale et notification à la fin ; surveillance d'un processus existant (`pgrep -f`) ; état, annulation, lecture du résultat ; historique dans le journal (`iris tasks`)
- [x] Agents lancés à la voix en arrière-plan : Claude Code (`claude -p`, abonnement claude.ai, **pas d'API**), OpenCode (`opencode run`), Codex (`codex exec`), Gemini CLI ; dossier du projet déduit de « … dans le projet X » ; résumé parlé + notification ; `iris agents`
- [x] Projets : « ouvre le projet X » → éditeur + terminal dans le dossier ; `[projects]` + `system.project_dirs` ; `iris projects`
- [x] Voix → terminal : « envoie : … » / « dis au terminal … » (texte + Entrée), « mode terminal » (dictée avec Entrée)
- [x] Mémoire persistante : faits (« retiens que… », « oublie… », « que sais-tu de moi ? »), injectés dans le prompt du LLM ; historique de conversation LLM persistant ; `iris memory`
- [x] Instantanés de session (fenêtres par workspace, toutes les 10 min et à l'arrêt) ; « reprends ma session d'hier » ; proposition de reprise au démarrage (opt-in `assistant.resume_prompt`)
- [x] Réponses LLM en streaming (SSE) lues phrase par phrase
- [x] Outils du modèle : `calc`, `clipboard`, `read_file` (dossier personnel), `recall`, `tasks` (un appel par décision)
- [x] Texte d'origine (accents, majuscules) conservé pour la dictée, les prompts d'agents, la mémoire et les recherches
- [ ] Dialogue suivi avec un agent interactif (relire ses questions, répondre à la voix)
- [ ] Restauration des fichiers ouverts dans l'éditeur lors d'une reprise de session

## Phase 4 — Personnalisation + apprentissage ✅ (v0.4)

Objectif : Iris s'adapte à toi, à la voix, et te propose des raccourcis sans jamais agir sans ton accord. Guides : [PERSONALIZATION.md](PERSONALIZATION.md), [AUTOMATIONS.md](AUTOMATIONS.md).

- [x] Style à la voix : « sois plus directe / taquine / pro / zen / motivante / chaleureuse », « sois plus concise / bavarde », « parle en anglais » — six tons (`warm`, `direct`, `coach`, `playful`, `pro`, `zen`) avec variantes de réponses, mémorisés dans le journal et réappliqués au démarrage par-dessus `config.toml` (`iris prefs`)
- [x] Profil de personnalité libre (`assistant.personality`) transmis au LLM **et** aux instructions de la voix OpenAI ; phrases personnalisées `[phrases]` pour remplacer n'importe quelle réplique
- [x] Voix à la voix : « parle plus vite / plus lentement / vitesse normale » (tous moteurs), « change de voix », « utilise la voix de Léa » (ElevenLabs par nom, OpenAI, Kokoro), mémorisées par moteur
- [x] Nom d'activation appris : « appelle-toi Nova » (détecteur rechargé à chaud, persistant)
- [x] Alias appris : « quand je dis mes mails, ouvre Thunderbird » (cible résolue en commande réelle ou web-app), « quels sont mes alias »
- [x] Apprentissage des habitudes depuis le journal (14 jours, 3 jours distincts minimum) : routines horaires par demi-heure, enchaînements à moins de deux minutes ; « quelles sont mes habitudes », `iris habits`
- [x] Suggestions proactives avec accord explicite : « Tu fais souvent ouvrir spotify vers 9 h, je m'en occupe chaque jour à 9 h ? » dans un moment calme, « Veux-tu aussi activer ne pas déranger ? » après une action ; refus définitif mémorisé, cooldown, jamais pour une action à confirmation ; « arrête de me proposer des suggestions »
- [x] Planificateur intégré (sans systemd timer : les automatisations vivent dans la session graphique et peuvent refuser les actions critiques) : « chaque matin à 9 h, lance mon workspace de dev », « en semaine à 8 h 30 … », « tous les vendredis à 17 h … », « every weekday at 8:30 … » ; liste, suppression, exécution à l'heure dite avec « Comme prévu : … » ; `iris automations`
- [x] Rappels : « rappelle-moi de sortir les poubelles à 20 h », « dans 25 minutes rappelle-moi … », « demain à 9 h … » → voix + notification critique ; rattrapés si Iris était éteinte
- [x] Heures calmes (`assistant.quiet_hours = "22:00-07:00"`) : réponses concises, aucune suggestion
- [x] Widget Quickshell (`contrib/quickshell/Iris.qml`) lisant le même état JSON que Waybar
- [ ] Planning avancé (« toutes les 2 heures », « le 1er du mois »), automatisation multi-actions
- [ ] Profils par contexte (travail / maison) changeant apps, ton et verbosité d'un mot

## Phase 5 — Mode privé + performances

- [ ] Chiffrement du journal et des préférences (clé dans le trousseau)
- [ ] Effacement automatique (rétention configurable) et mode « sans journal »
- [ ] *Barge-in* : interrompre Iris en parlant (annulation de la lecture + écho)
- [ ] STT en streaming (résultats partiels) pour une latence < 500 ms
- [ ] Front-end audio en Rust : capture, VAD, wake word, ring buffer — 0 % CPU au repos
- [ ] Moteurs alternatifs : whisper.cpp, Parakeet (NeMo), GPU (CUDA / ROCm)
- [ ] Modèle wake word « hey iris » de qualité (jeu de données + entraînement reproductible)
- [ ] Audit sécurité : liste blanche des commandes shell, sandbox des commandes perso
- [ ] Effacement automatique des habitudes / préférences apprises avec la rétention du journal
