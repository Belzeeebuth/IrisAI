<div align="center">

# Iris

**L'assistante vocale native d'Omarchy OS**

*« Hey Iris, ouvre mon workspace de dev. »*

[![Phase](https://img.shields.io/badge/phase-2%20%C2%B7%20int%C3%A9gration%20syst%C3%A8me-8b5cf6)](#roadmap)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776ab)](pyproject.toml)
[![Licence](https://img.shields.io/badge/licence-MIT-green)](LICENSE)
[![Local](https://img.shields.io/badge/donn%C3%A9es-locales%20par%20d%C3%A9faut-0ea5e9)](docs/PRIVACY.md)
[![Voix](https://img.shields.io/badge/voix-Kokoro%20%C2%B7%20OpenAI%20%C2%B7%20ElevenLabs-f472b6)](docs/VOICE.md)
[![LLM](https://img.shields.io/badge/cerveau-OpenCode%20Zen%20%2F%20Go-f59e0b)](docs/LLM.md)

</div>

Iris est un assistant vocal conçu pour [Omarchy](https://omarchy.org) (Arch Linux + Hyprland). Elle se lance avec ta session, écoute en arrière-plan le mot d'activation **« Hey Iris »**, comprend ce que tu dis en français ou en anglais, agit sur le système (applications, workspaces et écrans Hyprland, volume, luminosité, thèmes Omarchy, musique, Bluetooth, Wi-Fi, notifications, dictée…) et te répond avec une **vraie voix IA** (Kokoro en local, ou OpenAI / ElevenLabs). Quand une phrase sort de ses règles, un **cerveau LLM** (OpenCode Zen ou OpenCode Go, ou n'importe quel endpoint OpenAI-compatible) décide de l'action à faire ou répond à ta question. Par défaut tout tourne **en local** ; le cloud est un choix explicite.

> **État du projet — Phase 2 (intégration système) livrée, cerveau LLM branché.** Le cœur est couvert par 260 tests sans matériel. La voix Kokoro a été testée pour de vrai (synthèse française fonctionnelle, [échantillon](docs/VOICE.md)). Le client OpenCode Zen / Go est testé contre des réponses simulées : pas d'appel réel effectué faute de clé. La chaîne micro → Whisper **n'a pas encore été validée sur une machine Omarchy physique** : les premiers retours serviront à calibrer les seuils. Voir [Limitations connues](#limitations-connues).

---

## Sommaire

- [Ce qu'Iris sait faire](#ce-quiris-sait-faire)
- [Ce qu'Iris ne sait pas (encore) faire](#ce-quiris-ne-sait-pas-encore-faire)
- [Exemple de session](#exemple-de-session)
- [Comment ça marche](#comment-ça-marche)
- [Installation sur Omarchy](#installation-sur-omarchy)
- [Utilisation](#utilisation)
- [Configuration](#configuration)
- [Lancement automatique](#lancement-automatique)
- [Vie privée et mode local](#vie-privée-et-mode-local)
- [Architecture du code](#architecture-du-code)
- [Roadmap](#roadmap)
- [Idées pour la suite](#idées-pour-la-suite)
- [Limitations connues](#limitations-connues)
- [Dépannage](#dépannage)
- [Développement](#développement)

---

## Ce qu'Iris sait faire

Toutes les phrases ci-dessous fonctionnent en français et en anglais, avec ou sans formule de politesse (« peux-tu… s'il te plaît »). Liste complète : [docs/COMMANDS.md](docs/COMMANDS.md).

| Domaine | Exemples | Détails |
|---|---|---|
| **Activation** | « Hey Iris » · « Iris, ouvre le terminal » · « ouvre le terminal, Iris » | Mot d'activation seul → « Oui ? » puis commande ; ou tout dans une phrase. Tolère les variantes de transcription (« Irisse », « Irish »). |
| **Applications** | « ouvre le terminal » · « lance mon navigateur » · « ouvre Obsidian » · « ferme Firefox » · « ferme tout » | Alias parlés (terminal, navigateur, éditeur, fichiers, musique…) + n'importe quelle appli ayant un fichier `.desktop`. Web-apps Omarchy (YouTube, GitHub, Claude, WhatsApp…). Lancement via `uwsm app` pour survivre aux redémarrages d'Iris. |
| **Workspaces Hyprland** | « va sur le workspace 3 » · « bureau suivant » · « envoie cette fenêtre sur le workspace 2 » · « ferme cette fenêtre » · « plein écran » | Via `hyprctl` ; l'instance Hyprland est retrouvée automatiquement même depuis un service systemd. |
| **Audio** | « monte le son » · « baisse le volume de 20 » · « volume à 50 % » · « coupe le son » · « remets le son » | `wpctl` (WirePlumber) avec repli `pactl`. Réponse avec le volume réel. |
| **Écran** | « luminosité à 40 » · « monte la luminosité » · « mode nuit » | `brightnessctl` (repli `light`), `omarchy-toggle-nightlight`. |
| **Musique** | « pause » · « musique suivante » · « piste précédente » | `playerctl` (MPRIS) — Spotify, navigateur, VLC… Annonce le titre suivant. |
| **Omarchy** | « change de thème » · « mets le thème tokyo night » · « prends une capture d'écran » · « verrouille l'écran » | Scripts `omarchy-*` natifs, avec repli (`hyprlock`, `hyprshot`, `grim`). Correspondance floue sur le nom du thème. |
| **Alimentation** | « mets en veille » · « éteins l'ordinateur » · « redémarre le pc » | **Toujours confirmé** : « Veux-tu vraiment éteindre l'ordinateur ? » → oui / non. |
| **Web** | « cherche des recettes de crêpes sur internet » · « ouvre github.com » · « ouvre github point com » | Moteur de recherche configurable (DuckDuckGo par défaut). |
| **Infos** | « quelle heure est-il ? » · « quel jour sommes-nous ? » · « qu'est-ce que tu sais faire ? » · « dis bonjour à tout le monde » | |
| **Commandes personnalisées** | « lance mon workspace de dev » → *ton script shell* | Déclarées dans la config (`[[commands]]`), avec confirmation optionnelle. C'est le moyen le plus simple d'étendre Iris. |
| **Dictée** | « écris : bonjour à tous » · « mode dictée » … « fin de dictée » | Tape dans la fenêtre active (`wtype`, repli `ydotool` ou presse-papiers). En mode dictée, chaque phrase est tapée telle quelle, sans réponse vocale. |
| **Écrans** | « envoie cette fenêtre sur l'écran de droite » · « va sur l'écran de gauche » | `hyprctl movewindow mon:r` / `focusmonitor`. |
| **Périphériques** | « active le bluetooth » · « connecte mes écouteurs » · « coupe le wifi » · « mode avion » · « niveau de batterie » · « change de sortie audio » | `bluetoothctl` (alias `[bluetooth]` + correspondance floue sur les noms), `rfkill`/`nmcli`, `/sys/class/power_supply`, `omarchy-cmd-audio-switch` ou `wpctl`. |
| **Notifications** | « lis mes notifications » · « efface les notifications » · « ne pas déranger » | `makoctl history` résumé à voix haute, `makoctl dismiss`, mode `do-not-disturb` de mako. |
| **Sessions** | « ouvre ma session vidéo » · « sauvegarde la session sous montage » | Ensembles d'applications par workspace (`[[sessions]]`), ou instantané des fenêtres ouvertes enregistré dans le journal. |
| **Plusieurs commandes** | « ouvre le terminal et va sur le workspace 2 » · « ouvre firefox et spotify » | Découpage sur « et / puis / and then », y compris les formes elliptiques. |
| **Contrôle** | « stop » · « mets-toi en pause pendant 10 minutes » · « reprends l'écoute » · touche push-to-talk (`iris trigger`) | |
| **Cerveau LLM** | « pourquoi le ciel est bleu ? » · « explique-moi les workspaces » · *toute phrase hors règles* : « c'est beaucoup trop silencieux ici » → *baisse… non, monte le son* | Via **OpenCode Go / Zen** (ou OpenAI, OpenRouter, Ollama local). Le modèle reçoit ta personnalité, la liste des capacités et le contexte (heure, fenêtre active, workspace, dernières actions) et renvoie soit une action Iris (repasse par les confirmations), soit une réponse parlée, soit rien (bruit ambiant). |
| **Agent IA** *(expérimental)* | « demande à Claude d'écrire un haïku » | Délègue au CLI **Claude Code** authentifié avec ton abonnement claude.ai (`claude login`), **pas de clé API**. Désactivé par défaut. |

Après chaque commande, une courte fenêtre (5 s) permet d'enchaîner sans répéter « Hey Iris ». Une phrase non reconnue dans cette fenêtre est ignorée silencieusement (conversation ambiante) ; après un « Hey Iris » explicite, Iris te dit qu'elle n'a pas compris.

## Ce qu'Iris ne sait pas (encore) faire

| Pas encore | Prévu en |
|---|---|
| Comprendre une demande en langage libre hors des règles (« ouvre-moi un truc pour prendre des notes ») | Phase 3 (LLM local ou Claude Code) |
| Se souvenir du contexte entre deux sessions (« reprends ma session d'hier ») | Phase 3 (mémoire contextuelle) |
| Proposer des automatisations d'elle-même (« chaque matin à 9 h… ») | Phase 4 (apprentissage des habitudes) |
| Dicter du texte dans l'application active (style BridgeVoice) | Phase 2 |
| Surveiller une tâche longue et notifier à la fin | Phase 3 (agents) |
| Réagir à un profil de personnalité libre (« parle comme un coach ») au-delà des tons intégrés | Phase 4 |
| Interrompre Iris pendant qu'elle parle (*barge-in*) | Phase 5 |
| Détection du mot d'activation sur l'audio brut sans modèle à entraîner | Phase 5 (modèle « hey iris » openWakeWord fourni) |
| Widget d'état (Waybar / Quickshell) | Phase 2 |
| Plusieurs langues dans la même session | Phase 4 |

## Exemple de session

```
toi   : Hey Iris
iris  : Oui ?
toi   : va sur le workspace 2 et ouvre le terminal        ← (deux commandes : dis-les l'une après l'autre)
iris  : Workspace 2.
toi   : ouvre le terminal                                  ← enchaînement sans « Hey Iris »
iris  : ghostty est lancé.
toi   : Iris, mets le volume à cinquante pour cent
iris  : Volume à 50 pour cent.
toi   : Iris, ferme tout
iris  : Veux-tu vraiment fermer toutes les applications ?
toi   : non
iris  : Annulé.
toi   : Iris, lance mon workspace de dev                   ← commande personnalisée de ta config
iris  : Workspace de dev lancé.
toi   : Iris, ouvre le terminal et le navigateur          ← plusieurs commandes
iris  : ghostty est lancé. chromium est lancé.
toi   : Iris, écris : Bonjour Alice, je te confirme pour 18 h.   ← dictée dans la fenêtre active
iris  : C'est écrit.
toi   : Iris, il fait trop sombre là                        ← hors règles → cerveau LLM
iris  : Luminosité à 60 pour cent.
toi   : Iris, c'est quoi la différence entre Wayland et X11 ?
iris  : Wayland est un protocole moderne où le compositeur gère tout directement ; X11 est l'ancien serveur d'affichage… (réponse du modèle, parlée)
```

Le même dialogue fonctionne au clavier avec `iris repl` (pratique pour tester sans micro).

## Comment ça marche

```
   micro (parec / sounddevice / pw-record / arecord)
     │  trames 16 kHz, 30 ms
     ▼
   VAD  ── webrtcvad ou seuil d'énergie adaptatif ──▶ découpe en phrases
     │
     ▼
   STT  ── faster-whisper (local, int8) ──▶ « hé iris, monte le son »
     │
     ▼
   Wake word ── correspondance floue sur le texte ──▶ commande : « monte le son »
     │            (ou openWakeWord sur l'audio, optionnel)
     ▼
   NLU  ── règles fr/en + commandes perso ──▶ Intent(volume_up)
     │            └── phrase inconnue ──▶ LLM (OpenCode Zen/Go) ──▶ action Iris | réponse | silence
     ▼
   Routeur ── confirmation si critique ──▶ Action (wpctl / hyprctl / uwsm / omarchy-* / wtype / bluetoothctl…)
     │                                          │
     ▼                                          ▼
   Journal SQLite (traçabilité)            Réponse ──▶ voix IA (Kokoro / OpenAI / ElevenLabs) ──▶ pw-play
                                                └──▶ état Waybar ($XDG_RUNTIME_DIR/iris/state.json)
```

Machine à états : `IDLE` → (« Hey Iris ») → `ACTIVE` → (commande) → exécution → `ACTIVE` (fenêtre d'enchaînement) ou `IDLE`. Les intentions critiques passent par `CONFIRMING` (oui / non / délai de 12 s), y compris quand c'est le LLM qui les propose. « Mets-toi en pause » bascule en `PAUSED`, « mode dictée » en `DICTATING`. Pendant qu'Iris parle, le micro est ignoré pour qu'elle ne s'entende pas elle-même. La voix est jouée phrase par phrase pendant que la suivante se synthétise. Détails : [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Installation sur Omarchy

### En une commande

```bash
git clone https://github.com/belzeeebuth/irisai.git ~/.local/src/irisai
cd ~/.local/src/irisai
./scripts/install.sh
```

Le script : installe les paquets système manquants (`pacman`, dont `wtype` pour la dictée), crée un environnement Python isolé (`uv`, Python 3.12) dans `~/.local/share/iris/venv`, installe Iris avec `faster-whisper`, `kokoro-onnx` (voix IA), `piper-tts` (secours) et `sounddevice`, télécharge la voix Kokoro, la voix Piper `fr_FR-siwis-medium` et le modèle Whisper `base`, crée `~/.config/iris/config.toml`, installe et démarre le service systemd, puis lance `iris doctor`.

Options : `--no-service`, `--no-voice`, `--no-pacman`, `--extras=stt,tts,voice,audio,wakeword`. Variables : `IRIS_VOICE`, `IRIS_KOKORO_MODEL` (`kokoro-v1.0.onnx` par défaut, `kokoro-v1.0.int8.onnx` pour un CPU modeste), `IRIS_WHISPER_MODEL`, `IRIS_PYTHON`.

Pour le cerveau LLM, ajoute ta clé OpenCode (voir [Cerveau LLM](#cerveau-llm-opencode-zen--go)) :

```bash
echo 'OPENCODE_API_KEY=sk-...' >> ~/.config/environment.d/iris.conf   # lu par systemd --user (UWSM)
systemctl --user import-environment OPENCODE_API_KEY                    # pour la session en cours
```

### Premier test

```bash
iris say "Bonjour, je suis Iris."     # la voix
iris listen --seconds 5 --execute     # parle : « monte le son »
iris ask "quelle heure est-il"        # sans micro
iris doctor                           # tout est vert ?
journalctl --user -u iris -f          # ce qu'Iris entend et fait
```

### Installation manuelle

```bash
sudo pacman -S --needed python uv pipewire wireplumber libpulse brightnessctl playerctl libnotify espeak-ng
uv venv --python 3.12 ~/.local/share/iris/venv
uv pip install --python ~/.local/share/iris/venv/bin/python "/chemin/vers/irisai[stt,tts,audio]"
ln -sf ~/.local/share/iris/venv/bin/iris ~/.local/bin/iris
iris config init
iris voices download kokoro          # voix IA locale (325 Mo ; --model kokoro-v1.0.int8.onnx : 114 Mo)
iris voices download fr_FR-siwis-medium   # voix Piper de secours
iris models download base            # ou small (meilleur en français, ~2× plus lent)
iris service install
```

Extras disponibles : `stt` (faster-whisper), `voice` (kokoro-onnx), `tts` (piper-tts), `audio` (sounddevice + webrtcvad), `wakeword` (openWakeWord), `cloud` (requests, pour ElevenLabs / fallback Whisper API), `all`. Sans `audio`, Iris capture le micro avec `parec` (livré avec `libpulse`). Sans voix installée, elle se rabat sur `espeak-ng` puis sur l'affichage console.

## Utilisation

| Commande | Rôle |
|---|---|
| `iris run` | Boucle vocale complète (ce que lance le service). `--no-wake` : sans mot d'activation ; `--print-only` : réponses affichées. |
| `iris repl` | Mode texte interactif, sans micro. `--speak` pour entendre les réponses. |
| `iris ask "…"` | Une commande texte, puis quitte. Code de retour 1 si non comprise. |
| `iris say "…"` | Tester la voix. |
| `iris listen [--seconds N] [--execute]` | Enregistrer, transcrire, éventuellement exécuter. Test micro + Whisper. |
| `iris doctor` | Diagnostic : binaires, modules, voix, modèles, session Hyprland. |
| `iris intents` | Intentions reconnues + commandes personnalisées chargées. |
| `iris config init / path / show / edit` | Gérer `~/.config/iris/config.toml`. |
| `iris voices list [--lang fr_FR] / download NOM` | Voix Piper. |
| `iris models download [tiny\|base\|small\|medium\|large-v3]` | Modèles Whisper. |
| `iris journal [--last N] [--stats] [--clear]` | Journal des actions exécutées. |
| `iris service install / uninstall / status / show` | Service systemd utilisateur. |
| `iris status [--waybar] [--follow]` | État courant (idle, active, thinking, speaking, dictating…) ; format JSON pour Waybar. |
| `iris trigger [--pause]` | Push-to-talk : réveille l'instance en cours (comme « Hey Iris ») ; `--pause` bascule pause/reprise. |
| `iris llm info / test "…" / decide "…" / models` | Cerveau LLM : configuration effective, question de test, décision brute pour une phrase, modèles du provider. |
| `iris voices download kokoro [--model …]` · `iris voices list --engine kokoro` | Voix IA locale. |
| `iris say --backend openai "…"` | Tester un backend de voix précis. |
| `iris wakeword setup` | Modèles de base openWakeWord (si tu utilises un modèle « hey iris »). |

## Configuration

Fichier : `~/.config/iris/config.toml` (créé par `iris config init`, toutes les clés commentées ; référence complète dans [docs/CONFIGURATION.md](docs/CONFIGURATION.md)). Extraits utiles :

```toml
[assistant]
language = "fr"          # ou "en"
verbosity = "normal"     # concise | normal | chatty
tone = "warm"            # warm | direct | coach      ← « Sois plus directe »

[wake]
phrases = ["hey iris", "iris", "ok iris", "salut iris"]
fuzzy_threshold = 0.76   # baisse à 0.70 si Whisper écorche souvent « Iris »

personality = "Tutoie-moi, sois directe et un peu taquine."   # transmis au LLM

[stt]
model = "small"          # base par défaut ; small = nettement mieux en français

[tts]
backend = "auto"         # kokoro (voix IA locale) → piper → espeak. Ou "openai", "elevenlabs".
kokoro_speed = 1.05

[llm]
enabled = true
provider = "opencode-go" # ou "opencode-zen", "openai", "openrouter", "ollama"
model = "glm-5.3-flash"  # clé dans OPENCODE_API_KEY

[privacy]
allow_cloud = true       # requis pour OpenCode / OpenAI / ElevenLabs (localhost toujours permis)

[apps]                   # alias parlés supplémentaires
"mon éditeur" = "zed"
"mes mails" = "webapp:https://mail.proton.me"

[[commands]]             # tes automatisations
name = "workspace-dev"
phrases = ["lance mon workspace de dev", "ouvre mon environnement de dev"]
exec = "hyprctl dispatch workspace 2 && uwsm app -- ghostty -e nvim ~/projets"
reply = "Workspace de dev lancé."

[[commands]]
name = "nettoyage"
phrases = ["nettoie les paquets"]
exec = "paru -Sc --noconfirm"
confirm = true           # « Veux-tu vraiment lancer nettoyage ? »
wait = true              # attend la fin avant de répondre
```

## Voix IA

Piper est une voix de synthèse correcte mais reconnaissable ; Iris parle maintenant avec des voix neuronales expressives. Guide complet : [docs/VOICE.md](docs/VOICE.md).

| Backend | Où | Qualité | Latence | Configuration |
|---|---|---|---|---|
| **Kokoro** (défaut) | local, CPU, 24 kHz | naturelle, voix `ff_siwis` en français, 50+ voix anglaises | plus rapide que le temps réel sur un CPU de bureau ; ~2,5× plus lent sur un vCPU bridé | `iris voices download kokoro` |
| **OpenAI** `gpt-4o-mini-tts` | cloud (ou serveur local compatible : Kokoro-FastAPI, Speaches) | très expressive, **pilotable par instructions** (« voix chaleureuse, léger sourire ») dérivées du ton | ~1 s | `tts.backend = "openai"`, `OPENAI_API_KEY`, `privacy.allow_cloud = true` |
| **ElevenLabs** | cloud | référence en expressivité | ~1 s | `tts.backend = "elevenlabs"`, `ELEVENLABS_API_KEY`, `tts.elevenlabs_voice_id` |
| Piper | local | correcte, robotique | instantanée | repli automatique |

La lecture est **en pipeline** : la première phrase est jouée pendant que la suivante se synthétise. Un serveur Kokoro-FastAPI sur GPU (`tts.backend = "openai"`, `openai_base_url = "http://localhost:8880/v1"`) donne la qualité Kokoro sans charge CPU.

## Cerveau LLM (OpenCode Zen / Go)

Le moteur de règles reste le premier réflexe (instantané, hors-ligne, prévisible). Le LLM intervient pour tout le reste : phrases hors règles, questions, conversation, personnalité. Guide complet : [docs/LLM.md](docs/LLM.md).

1. **Clé** : connecte-toi sur [opencode.ai/auth](https://opencode.ai/auth). *OpenCode Go* (10 $/mois) donne accès à des modèles ouverts (GLM, Kimi, MiniMax, Qwen, DeepSeek…) ; *OpenCode Zen* (paiement à l'usage, sans marge) ajoute Claude, GPT, Gemini, Grok. La clé fonctionne hors de l'outil OpenCode.
2. **Environnement** : `OPENCODE_API_KEY=…` dans `~/.config/environment.d/iris.conf` (systemd --user) ou `llm.api_key` dans la config.
3. **Config** : `[llm] enabled = true`, `provider = "opencode-go"` (URL `https://opencode.ai/zen/go/v1`) ou `"opencode-zen"` (`https://opencode.ai/zen/v1`), `model = "glm-5.3-flash"` (rapide et économique ; `kimi-k2.6`, `minimax-m3`, `qwen3.7-plus`, ou sur Zen `claude-haiku-4-5`, `gpt-5.4-mini`…), et `[privacy] allow_cloud = true`.
4. **Test** : `iris llm info`, `iris llm test "présente-toi"`, `iris llm decide "il fait trop sombre"`.

Iris parle aux modèles GPT / GLM / Kimi / MiniMax / DeepSeek via `/chat/completions` et aux modèles Claude / Qwen via `/messages` (choix automatique). Tout endpoint OpenAI-compatible marche aussi : `provider = "ollama"` pour un modèle local (aucune donnée ne sort), `"openrouter"`, `"openai"`, ou `"custom"` avec `base_url`.

Ce que le modèle reçoit : ta phrase (texte, jamais l'audio), la personnalité et le ton configurés, la liste des capacités d'Iris, et si `llm.context = true` l'heure, la fenêtre active, le workspace, la batterie et les trois dernières actions du journal. Il répond en JSON : `{"action": "brightness_set", "slots": {"n": 60}}`, `{"reply": "…"}` ou `{"ignore": true}`. Une action proposée par le modèle passe par les mêmes confirmations qu'une commande vocale : le LLM ne peut pas éteindre la machine sans ton « oui ».

## Lancement automatique

`iris service install` écrit `~/.config/systemd/user/iris.service` et l'active. L'unité est liée à `graphical-session.target`, qu'Omarchy active via UWSM au démarrage d'Hyprland : Iris démarre avec ta session, s'arrête avec elle, et **redémarre seule en cas de plantage** (`Restart=on-failure`). Elle tourne dans `background.slice` avec une priorité réduite pour ne jamais gêner le bureau.

```bash
systemctl --user status iris      # état
journalctl --user -u iris -f      # logs en direct (ce qu'elle entend, ce qu'elle fait)
systemctl --user restart iris     # après un changement de config
```

Alternative sans systemd : `hypr/iris-autostart.conf` (`exec-once = uwsm app -- ~/.local/bin/iris run`).

**Widget Waybar** : `contrib/waybar/iris.jsonc` ajoute un module `custom/iris` (icône micro qui change de couleur : écoute, réflexion, parole, dictée, pause ; clic = push-to-talk, clic droit = pause) avec son CSS `contrib/waybar/iris.css`. Mets `waybar_signal = 8` dans `[system]` pour un rafraîchissement instantané.

**Push-to-talk** : `contrib/hypr/iris.conf` propose `SUPER + ALT + Espace` → `iris trigger` (équivaut à « Hey Iris ») et `SUPER + ALT + P` → pause/reprise. À inclure depuis `~/.config/hypr/bindings.conf`.

## Vie privée et mode local

- **Par défaut, rien ne quitte la machine.** Transcription (faster-whisper) et synthèse (Piper) sont locales ; `privacy.allow_cloud = false` bloque tout backend réseau même s'il est configuré par erreur.
- **L'audio du micro n'est jamais écrit sur le disque** : il vit en mémoire le temps de la transcription, puis disparaît.
- **Le journal des actions** (`~/.local/state/iris/iris.db`) trace *ce qu'Iris a fait* (intention, paramètres, résultat, durée) pour la traçabilité demandée aux assistants qui pilotent un système. Il ne contient pas le texte de tes phrases sauf si `privacy.store_transcripts = true`. `iris journal --clear` l'efface ; `privacy.journal_actions = false` le désactive.
- Les modèles sont téléchargés une fois (Hugging Face) puis lus hors-ligne.
- Options cloud, toutes en opt-in explicite (`privacy.allow_cloud = true`) : cerveau LLM OpenCode / OpenAI / OpenRouter (texte des phrases hors règles et questions, plus le contexte listé ci-dessus), voix OpenAI ou ElevenLabs (texte des réponses), API Whisper d'OpenAI (repli STT). Les URL `localhost` (Ollama, Kokoro-FastAPI) restent permises sans ce drapeau. Le pont Claude Code envoie à Claude *uniquement* le texte de la demande « demande à Claude … », via ton abonnement.

Détails : [docs/PRIVACY.md](docs/PRIVACY.md).

## Architecture du code

```
iris/
├── cli.py            commandes `iris …`             ├── core/
├── app.py            assemblage des composants      │   ├── assistant.py   machine à états + boucle vocale
├── config.py         config TOML → dataclasses      │   ├── router.py      intention → action → réponse
├── doctor.py         diagnostic                     │   ├── phrasebook.py  réponses fr/en, ton, verbosité
├── service.py        unité systemd                  │   └── journal.py     SQLite : actions, prefs, transcriptions
├── audio/            capture, VAD, lecture, bips    │   └── status.py      état JSON pour Waybar + pid
├── wakeword/         transcript (flou) / openWakeWord├── actions/
├── stt/              faster-whisper, fallback cloud  │   ├── system.py      run / launch (uwsm, systemd-run)
├── tts/              kokoro, openai_speech, piper,   │   ├── hyprland.py, monitors.py
│                     elevenlabs, espeak, streaming   │   ├── apps.py, sessions.py
├── llm/              client (OpenAI/Anthropic-compat)│   ├── audio_ctl.py, brightness.py, media.py
│                     + brain (décision, contexte)    │   ├── devices.py     bluetooth, wifi, batterie, sortie audio
├── nlu/              normalisation, nombres, règles, │   ├── notifications.py (mako), typing.py (dictée)
│                     découpage multi-commandes        │   ├── power.py, web.py, notify.py
├── agents/           pont Claude Code (expérimental) │   └── omarchy.py     thèmes, lock, screenshot, webapps
└── data/             config par défaut, alias apps
tests/                260 tests (NLU, wake, routeur, machine à états, LLM, VAD, config, journal, CLI)
scripts/install.sh    installation Omarchy            systemd/iris.service   hypr/   contrib/waybar/
```

Principes : dépendances lourdes importées à la demande (le cœur ne requiert que numpy) ; chaque backend a un repli ; toute interaction système passe par `actions/system.py` (donc simulable dans les tests) ; toute erreur d'action devient une réponse parlée, jamais un plantage.

## Roadmap

Détail par phase, avec les tâches : [docs/ROADMAP.md](docs/ROADMAP.md).

- [x] **Phase 1 — Prototype vocal** (v0.1) : activation « Hey Iris » (transcription floue, openWakeWord optionnel), transcription locale Whisper, VAD, commandes simples fr/en, voix Piper, confirmations, journal SQLite, mode texte, CLI, diagnostic, service systemd, script d'installation Omarchy, README.
  - [ ] Validation sur machine Omarchy réelle et calibration des seuils (à faire avec les premiers retours).
  - [ ] Modèle openWakeWord « hey iris » pré-entraîné fourni dans le dépôt.
- [x] **Phase 2 — Intégration système** *(cette version, v0.2)* : dictée (`wtype`, mode dictée continue), multi-écrans, Bluetooth / Wi-Fi / mode avion / batterie / sortie audio, notifications mako (lecture, effacement, ne pas déranger), sessions de workspaces, plusieurs commandes par phrase, push-to-talk (`iris trigger` + raccourci Hyprland), état pour Waybar, langue de réponse automatique.
  - [x] **Voix IA** : Kokoro local (défaut), OpenAI `gpt-4o-mini-tts` et serveurs OpenAI-compatibles, ElevenLabs ; lecture phrase par phrase.
  - [x] **Cerveau LLM** (avancé depuis la phase 3) : OpenCode Go / Zen, OpenAI, OpenRouter, Ollama ; repli sur phrase inconnue, questions ouvertes, personnalité, contexte, historique de conversation.
  - [ ] Widget Quickshell (module Waybar livré).
- [ ] **Phase 3 — Agents + mémoire** : agents en arrière-plan avec surveillance et notification à la fin (« surveille la compilation »), pont Claude Code asynchrone (abonnement claude.ai, pas d'API), mémoire contextuelle persistante (projets ouverts, tâches en cours), proposition de reprise (« reprendre ta session d'hier ? »), transcription voix → prompt dans le terminal actif.
- [ ] **Phase 4 — Personnalisation + apprentissage** : profil de personnalité libre, apprentissage des habitudes depuis le journal, suggestions d'automatisations récurrentes, planificateur (« chaque matin à 9 h… »).
- [ ] **Phase 5 — Mode privé + performances** : chiffrement du journal, effacement automatique, *barge-in*, streaming STT, front-end audio en Rust (VAD + wake word), support Parakeet / whisper.cpp / GPU.

## Idées pour la suite

- Voix « émotionnelle » : choisir le ton de la voix (Piper multi-locuteurs, styles ElevenLabs) selon le contexte (erreur, succès, matin).
- « Iris, résume mes notifications de la matinée » (lecture de l'historique mako).
- Mode réunion : coupe le micro, active *ne pas déranger*, bascule le thème.
- Raccourci clavier *push-to-talk* (Super + espace) en complément du mot d'activation.
- Profils par contexte (travail / maison) qui changent apps, verbosité et ton.
- Réponses contextuelles au workspace actif (« ferme ça » = la fenêtre active).
- Intégration Walker : ouvrir le lanceur avec la requête pré-remplie quand l'app est inconnue.
- Plugins : dossier `~/.config/iris/plugins/` de scripts déclarant leurs phrases.
- Retour visuel : bulle Quickshell « j'écoute / je réfléchis / j'exécute ».
- Synchronisation optionnelle et chiffrée des préférences entre machines.

## Limitations connues

- **Non validé sur matériel réel** : les seuils du VAD énergie (`audio.energy_threshold`) et la tolérance du mot d'activation (`wake.fuzzy_threshold`) sont des valeurs raisonnables, pas calibrées. `webrtcvad` (extra `audio`) est plus robuste au bruit.
- Le mot d'activation par transcription implique que **chaque phrase entendue est transcrite** (localement) : coût CPU modéré avec `tiny`/`base`, sensible avec `small` sur un portable. openWakeWord règle ça (Phase 5) mais nécessite un modèle « hey iris » entraîné.
- Whisper hallucine parfois sur le silence ; les artefacts connus sont filtrés (`stt/base.py`), d'autres peuvent passer.
- Pas d'interruption pendant qu'Iris parle (le micro est volontairement ignoré).
- Deux commandes dans une phrase (« ouvre A et ferme B ») ne sont pas découpées.
- `piper-tts` sur PyPI ne fournit pas toujours de roue pour la toute dernière version de Python d'Arch : le script utilise Python 3.12 via `uv`. Alternative : paquet AUR `piper-tts-bin` (Iris utilise le binaire `piper` s'il est dans le PATH).
- Kokoro sur un CPU lent (ou dans une VM bridée) peut être plus lent que le temps réel : prendre le modèle `int8`, raccourcir les réponses (`verbosity = "concise"`), ou passer par un serveur Kokoro-FastAPI / OpenAI.
- Le LLM et le pont Claude Code sont synchrones : Iris attend la réponse (quelques secondes, jusqu'à `llm.timeout_s`). Le widget affiche « réfléchit » pendant ce temps.
- Le client OpenCode Zen / Go est validé par des tests à réponses simulées, pas encore par un appel réel (aucune clé disponible pendant le développement). Les endpoints et modèles viennent de la documentation OpenCode de septembre 2026 ; `iris llm models` liste ce que ton compte voit vraiment.
- Kokoro v1.0 n'a qu'une voix française (`ff_siwis`) ; pour d'autres timbres en français, utiliser OpenAI ou ElevenLabs.
- Sauvegarder une session capture les classes de fenêtres et tente d'en déduire la commande : les applications lancées par un script exotique peuvent être manquées.

## Dépannage

| Symptôme | Piste |
|---|---|
| `iris doctor` : « parec introuvable » | `sudo pacman -S libpulse` ou `uv pip install sounddevice` dans le venv. |
| Iris n'entend rien | `iris listen --seconds 5` ; vérifier la source par défaut (`wpctl status`) ; baisser `audio.energy_threshold` ou passer `vad_backend = "webrtc"`. |
| Elle se déclenche sur d'autres mots | Monter `wake.fuzzy_threshold` (0.85) ou retirer « iris » seul des `phrases`. |
| Elle ne reconnaît pas « Iris » | Baisser `fuzzy_threshold` (0.70), ajouter les variantes entendues (`journalctl --user -u iris`) dans `phrases`, passer `stt.model = "small"`. |
| Pas de voix | `iris say test` ; `iris voices download fr_FR-siwis-medium` ; vérifier `pw-play` ; `tts.backend = "espeak"` en secours. |
| « Je n'arrive pas à parler à Hyprland » | Le service n'a pas l'environnement de session : Omarchy (UWSM) l'importe normalement ; sinon `systemctl --user import-environment WAYLAND_DISPLAY HYPRLAND_INSTANCE_SIGNATURE` dans `autostart.conf`. |
| Le service ne démarre pas au boot | `systemctl --user is-active graphical-session.target` doit être `active` ; sinon utiliser `hypr/iris-autostart.conf`. |
| Whisper très lent | `stt.model = "tiny"` ou `base` ; `compute_type = "int8"` ; sur GPU NVIDIA : `device = "cuda"`, `compute_type = "float16"`. |
| « Library libcublas.so.12 is not found » | faster-whisper a tenté CUDA sans les bibliothèques NVIDIA. Depuis 0.2.1 Iris bascule seule sur CPU ; pour le GPU : `sudo pacman -S cuda cudnn` (ou `uv pip install nvidia-cublas-cu12 nvidia-cudnn-cu12` dans le venv + `LD_LIBRARY_PATH`), sinon `stt.device = "cpu"`. |
| « Je n'ai pas de modèle de langage configuré » | `[llm] enabled = true` + `[privacy] allow_cloud = true` + clé exportée ; `iris llm info` montre ce qui manque. |
| LLM : « clé API refusée » | Clé Go utilisée avec `provider = "opencode-zen"` (ou l'inverse) : les URL diffèrent (`/zen/go/v1` vs `/zen/v1`). |
| LLM : « modèle introuvable (404) » | Le modèle n'est pas dans ton plan ; `iris llm models` liste les identifiants disponibles. |
| Voix Kokoro hachée / lente | `kokoro_model = "kokoro-v1.0.int8.onnx"` ; ou `tts.backend = "openai"` avec un serveur Kokoro-FastAPI local. |
| Dictée : rien ne s'écrit | `sudo pacman -S wtype` ; sinon le texte est copié (Ctrl+V). Certaines applis XWayland ignorent wtype : `typing_tool = "ydotool"`. |

## Développement

```bash
uv venv .venv && uv pip install --python .venv/bin/python -e ".[dev]"
.venv/bin/pytest            # 260 tests, ~2 s, aucun matériel requis
.venv/bin/ruff check iris tests && .venv/bin/ruff format iris tests
.venv/bin/iris repl         # tester la compréhension au clavier
```

Ajouter une commande : une `Rule` dans `iris/nlu/intents.py`, un `_h_<nom>` dans `iris/core/router.py`, ses phrases dans `iris/core/phrasebook.py` (fr **et** en), un test dans `tests/`. Ajouter un alias d'application : `iris/data/apps.toml`.

Contributions bienvenues — voir [CONTRIBUTING.md](CONTRIBUTING.md). Licence [MIT](LICENSE).
