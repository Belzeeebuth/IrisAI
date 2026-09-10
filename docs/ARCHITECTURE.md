# Architecture

## Vue d'ensemble

Iris est un pipeline de composants remplaçables, orchestrés par une machine à états (`iris/core/assistant.py`).

```
AudioCapture ──▶ VadSegmenter ──▶ STT ──▶ Assistant.on_utterance ──▶ TranscriptWake ──▶ IntentParser ──▶ Router ──▶ actions/*
    (thread)        (main)        (main)                                                                     │
                                                                                          Journal ◀──────────┤
                                                                                          TTS.speak ◀────────┘
```

- **Capture** (`audio/capture.py`) : un thread pousse des trames int16 horodatées dans une file. Backends : sounddevice, parec, pw-record, arecord.
- **VAD** (`audio/vad.py`) : `VadSegmenter.push(frame)` renvoie une phrase complète quand un silence suit la parole (pré-roll, durée min/max).
- **STT** (`stt/`) : protocole `transcribe(audio, rate, language) -> str`. `FasterWhisperSTT` charge le modèle à la demande ; `FallbackSTT` chaîne local → cloud.
- **Wake** (`wakeword/`) : `TranscriptWake.match(text) -> WakeMatch(remainder)` ; `OpenWakeWord.process(frame) -> bool`.
- **NLU** (`nlu/`) : `canonical()` normalise ; `IntentParser.parse()` teste d'abord les commandes perso (flou), puis les `Rule` ordonnées (spécifiques avant génériques). `parse_yes_no()` pour les confirmations.
- **Routeur** (`core/router.py`) : `_h_<intent>` → `Reply(text, ok, keep_listening, control)`. Erreurs `RuntimeError` = attendues (outil absent) → réponse parlée. Journalise chaque exécution. `intent_from_decision()` convertit une proposition du LLM en intention ordinaire (nom vérifié, confirmations conservées).
- **LLM** (`llm/client.py`, `llm/brain.py`) : client urllib pour `/chat/completions` (OpenAI-compatible) et `/messages` (Anthropic-compatible) avec presets OpenCode Go / Zen, OpenAI, OpenRouter, Ollama ; `Brain.decide()` (JSON : action / réponse / ignore) et `Brain.converse()`, prompt système = persona + capacités + contexte, historique borné.
- **Découpage** (`nlu/split.py`) : plusieurs commandes par phrase, formes elliptiques pour les verbes d'application.
- **Statut** (`core/status.py`) : fichier JSON `$XDG_RUNTIME_DIR/iris/state.json` (format Waybar) + signal, fichier pid pour `iris trigger`.
- **Assistant** (`core/assistant.py`) : états `IDLE / ACTIVE / CONFIRMING / PAUSED`, fenêtres temporelles via un `clock` injectable (testable), suppression de l'écho (trames antérieures à `_ignore_before` ignorées).
- **Actions** (`actions/`) : toute commande système passe par `system.run` / `system.launch` / `system.which`, remplacés par un faux dans les tests.
- **TTS** (`tts/`) : `speak(text[, language]) -> bool`. Kokoro (kokoro-onnx, modèle en mémoire), OpenAI-compatible `/audio/speech` (OpenAI, Kokoro-FastAPI…), Piper (API Python persistante ou CLI), ElevenLabs, espeak-ng, console. `speak_streaming()` synthétise la phrase N+1 pendant la lecture de la phrase N.
- **Journal** (`core/journal.py`) : SQLite WAL, tables `actions`, `utterances`, `prefs`.

## Choix de conception

- **Local d'abord, cloud en opt-in** : `privacy.allow_cloud` court-circuite tout backend réseau.
- **Dégradation gracieuse** : chaque brique a un repli (parec → pw-record → arecord ; piper → espeak → console ; wpctl → pactl ; omarchy-* → outils génériques). Un outil manquant produit une réponse, pas un crash.
- **Imports paresseux** : numpy est la seule dépendance dure ; faster-whisper, piper, sounddevice, openwakeword, requests sont importés à l'usage.
- **Testabilité** : 260 tests sans matériel — NLU (table de phrases), wake word, routeur (commandes émises), machine à états (horloge simulée), VAD (signal synthétique), config, journal, CLI.
- **Séparation texte / voix** : `handle_text()` et `on_utterance()` partagent `process_command()` ; `iris repl` exerce exactement la logique du mode vocal.
- **Lancement d'apps détaché** : `uwsm app --` (scope systemd propre, survit au redémarrage d'Iris) → `systemd-run --user` → `Popen` en nouvelle session.
- **Service systemd** dans `graphical-session.target` : démarre/arrête avec Hyprland (UWSM), `Restart=on-failure`, `background.slice`.

## Étendre Iris

| Besoin | Où |
|---|---|
| Nouvelle phrase pour une intention existante | `iris/nlu/intents.py` (pattern) + `tests/test_intents.py` |
| Nouvelle intention | `Rule` + `_h_<nom>` dans `router.py` + phrases fr/en dans `phrasebook.py` + tests |
| Nouvel alias d'application | `iris/data/apps.toml` (ou `[apps]` utilisateur) |
| Nouveau backend STT/TTS/capture | un module implémentant le protocole + branchement dans `*/factory.py` ou `capture.py` |
| Automatisation utilisateur sans code | `[[commands]]` dans la config |

## Rust ?

La spec cible « Python + Rust pour les performances critiques ». En phase 1, aucun goulot ne justifie Rust : la capture et le VAD coûtent < 2 % CPU, Whisper (C++ via CTranslate2) et Piper (ONNX Runtime) sont déjà natifs. Le front-end audio Rust (capture + VAD + wake word en un binaire, 0 % au repos) est prévu en phase 5, exposé à Python via un flux de trames sur stdout — le même contrat que `parec` aujourd'hui, donc sans changement d'architecture.
