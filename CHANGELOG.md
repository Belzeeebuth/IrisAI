# Changelog

## Non publié

- **N'importe quelle application installée** : quand le nom entendu ne correspond à rien d'exact, Iris cherche la meilleure correspondance dans tout le catalogue `.desktop` et dans ses alias, et tolère une transcription approximative — « prismenscher », « prism lensure » ou « lanceur prism » ouvrent Prism Launcher. Sont désormais indexés le nom français (`Name[fr]`), les mots-clés (« minecraft » → Prism Launcher), la commande et la classe de fenêtre (`StartupWMClass`, qui fiabilise aussi la fermeture). Un nom court ne capte plus un mot plus long (« obs » ne répond pas pour « obsidienne »), et faute de correspondance crédible Iris préfère dire qu'elle n'a pas trouvé. L'application est annoncée sous son vrai nom (« Prism Launcher » plutôt que « prismlauncher »).
- **Mémoire** : `MALLOC_TRIM_THRESHOLD_=131072` dans l'unité systemd. Les allocations de CTranslate2 fragmentent le tas, et la glibc conservait par défaut plusieurs centaines de mégaoctets déjà libérés au lieu de les rendre au système. Mesuré après vingt transcriptions : 1263 Mo → 942 Mo, sans toucher au modèle ni à la qualité.
- **Claude Code** : « lance Claude Code » ouvre la CLI dans un terminal. La phrase était auparavant comprise comme « demande à Claude de faire *code* » (règle `ask_agent`), et la transcription fréquente « cloud code » finissait par ouvrir l'éditeur. Le rapprochement approximatif exige maintenant la **même forme** — autant de mots, longueur voisine — donc plus aucun mot de la demande ne peut rester inexpliqué par le nom retenu.
- **« Lance le jeu … »** : les mots jeu / jeux / game sont ignorés devant un nom d'application, comme application / logiciel / programme.
- **Navigateurs nommés** : « ouvre Firefox / Chrome / Brave / Zen » lance ce navigateur-là ; seuls « le navigateur », « internet », « le web »… passent par le navigateur par défaut (`omarchy-launch-browser`).
- **« Lance-moi une page Firefox »**, « un nouvel onglet Firefox », « open a new Firefox window » : les mots page / onglet / fenêtre / tab / window (et nouvelle / new) sont ignorés devant un nom d'application ; « ferme cette page / cet onglet » ferme la fenêtre active.
- **Hyprland ≥ 0.56** : `hyprctl dispatch` évalue désormais du Lua (`hl.dsp.window.close()`…) et l'ancienne syntaxe `closewindow address:0x…` échoue. Iris détecte le mode Lua au premier échec et traduit ses dispatchers (fermer / focaliser une fenêtre, workspaces, plein écran, flottant, moniteurs). Avant ce correctif, « ferme Spotify » retombait sur `pkill`, ce qui tuait l'application au lieu de la fermer proprement.

## 0.4.0 — Phase 4 : personnalisation, habitudes, automatisations

- **Style à la voix** : « sois plus directe / taquine / pro / zen / motivante / chaleureuse », « sois plus concise / bavarde », « réponses normales », « parle en anglais / français » ; trois nouveaux tons (`playful`, `pro`, `zen`) avec variantes de réponses. Les préférences dites à la voix sont **mémorisées** (table `prefs`) et réappliquées au démarrage par-dessus `config.toml` ; `iris prefs [list|reset]`.
- **Voix à la voix** : « parle plus vite / plus lentement / vitesse normale » (tous moteurs, mémorisé), « change de voix », « utilise la voix de Léa » (ElevenLabs par nom, OpenAI, Kokoro), mémorisée par moteur. La personnalité (`assistant.personality`) alimente aussi les instructions de la voix OpenAI.
- **Nom d'activation appris** : « appelle-toi Nova » (rechargé à chaud, persistant).
- **Alias appris** : « quand je dis mes mails, ouvre Thunderbird » (cible résolue en commande réelle ou `webapp:`), « quels sont mes alias ».
- **Habitudes** (`[habits]`) : routines horaires et enchaînements détectés dans le journal (14 jours, 3 jours distincts) ; suggestions proactives avec accord explicite (« Tu fais souvent … vers 9 h, je m'en occupe ? », « Veux-tu aussi … ? »), refus définitif mémorisé, cooldown, jamais pour une action à confirmation ; « quelles sont mes habitudes », « arrête de me proposer des suggestions », `iris habits`.
- **Automatisations** (`[automations]`, table `automations`) : « chaque matin à 9 h lance spotify », « en semaine à 8 h 30 … », « tous les vendredis à 17 h … », « every weekday at 8:30 … » ; liste / suppression à la voix ; exécution par la boucle vocale (« Comme prévu : … »), refus des actions à confirmation ; `iris automations [list|add|delete|run]`.
- **Rappels** : « rappelle-moi de … à 20 h », « dans 25 minutes rappelle-moi … », « demain à 9 h rappelle-moi … » → voix + notification critique, rattrapés après un redémarrage.
- **Heures calmes** (`assistant.quiet_hours`) : réponses concises, aucune suggestion. **Phrases personnalisées** (`[phrases]`) pour remplacer n'importe quelle réplique.
- **Widget Quickshell** (`contrib/quickshell/Iris.qml`).
- Intégré depuis les retours de terrain : `iris say --voice`, alias `opencode` (TUI dans le terminal), annonce du programme lancé dans le terminal plutôt que de l'émulateur, en-tête `x-opencode-session` et `User-Agent` versionné exigés par OpenCode Go.
- 92 intentions, 370 tests.

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
