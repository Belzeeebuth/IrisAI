"""Interface en ligne de commande d'Iris."""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
from pathlib import Path

from iris import __version__, paths
from iris.config import Config, load_config, write_default_config

log = logging.getLogger("iris")


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="iris", description="Iris — assistant vocal pour Omarchy OS")
    ap.add_argument(
        "--config", type=Path, help="fichier de configuration (défaut : ~/.config/iris/config.toml)"
    )
    ap.add_argument("-v", "--verbose", action="store_true", help="logs détaillés")
    ap.add_argument("--version", action="version", version=f"iris {__version__}")
    sub = ap.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="boucle vocale complète (utilisée par le service systemd)")
    run.add_argument(
        "--no-wake",
        action="store_true",
        help="pas de mot d'activation : chaque phrase est une commande",
    )
    run.add_argument("--print-only", action="store_true", help="réponses affichées, pas prononcées")

    repl = sub.add_parser("repl", help="mode texte interactif (sans micro)")
    repl.add_argument("--speak", action="store_true", help="prononcer les réponses")

    ask = sub.add_parser("ask", help='exécuter une commande texte, ex. : iris ask "monte le son"')
    ask.add_argument("text", nargs="+")
    ask.add_argument("--speak", action="store_true")

    say = sub.add_parser("say", help="tester la voix")
    say.add_argument("text", nargs="+")
    say.add_argument(
        "--backend", default=None, help="kokoro | openai | piper | elevenlabs | espeak"
    )
    say.add_argument("--lang", default=None, help="fr | en")
    say.add_argument("--voice", default=None, help="nom ou id de voix (selon le backend)")

    listen = sub.add_parser(
        "listen", help="enregistrer quelques secondes et transcrire (test micro + STT)"
    )
    listen.add_argument("--seconds", type=float, default=5.0)
    listen.add_argument("--execute", action="store_true", help="exécuter la commande transcrite")

    sub.add_parser("doctor", help="vérifier l'installation")
    sub.add_parser("intents", help="lister les intentions reconnues")

    cfg = sub.add_parser("config", help="gérer la configuration")
    cfg_sub = cfg.add_subparsers(dest="config_cmd", required=True)
    cfg_init = cfg_sub.add_parser("init", help="créer ~/.config/iris/config.toml")
    cfg_init.add_argument("--force", action="store_true")
    cfg_sub.add_parser("path")
    cfg_sub.add_parser("show", help="afficher la configuration effective")
    cfg_sub.add_parser("edit", help="ouvrir dans $EDITOR")

    voices = sub.add_parser("voices", help="voix Piper")
    voices_sub = voices.add_subparsers(dest="voices_cmd", required=True)
    vl = voices_sub.add_parser("list", help="voix disponibles pour un moteur")
    vl.add_argument("--lang", default=None, help="filtre : fr, en (Piper : fr_FR, en_US)")
    vl.add_argument(
        "--engine",
        default="elevenlabs",
        choices=("elevenlabs", "cartesia", "openai", "kokoro", "piper"),
    )
    vlib = voices_sub.add_parser(
        "library", help="bibliothèque communautaire ElevenLabs (voix natives par langue)"
    )
    vlib.add_argument("--lang", default="fr")
    vlib.add_argument("--search", default=None)
    vlib.add_argument("--gender", default=None, help="female | male")
    vlib.add_argument("--limit", type=int, default=20)
    vlib.add_argument("--featured", action="store_true")
    vlib.add_argument(
        "--preview",
        type=int,
        default=None,
        metavar="N",
        help="écouter l'extrait de la N-ième voix listée",
    )
    vadd = voices_sub.add_parser(
        "add", help="ajouter une voix de la bibliothèque ElevenLabs à ton compte"
    )
    vadd.add_argument("public_owner_id")
    vadd.add_argument("voice_id")
    vadd.add_argument(
        "--name", required=True, help="nom sous lequel l'utiliser (tts.elevenlabs_voice)"
    )
    vcache = voices_sub.add_parser("cache", help="cache des synthèses")
    vcache.add_argument("--clear", action="store_true")
    vd = voices_sub.add_parser("download", help="voix Piper (nom) ou « kokoro » (voix IA locale)")
    vd.add_argument("voice", nargs="?", default=None)
    vd.add_argument(
        "--model",
        default=None,
        help="kokoro : kokoro-v1.0.onnx | kokoro-v1.0.int8.onnx | kokoro-v1.0.fp16.onnx",
    )
    vd.add_argument("--force", action="store_true")

    models = sub.add_parser("models", help="modèles Whisper")
    models_sub = models.add_subparsers(dest="models_cmd", required=True)
    md = models_sub.add_parser("download")
    md.add_argument("model", nargs="?", default=None)

    wake = sub.add_parser("wakeword", help="openWakeWord")
    wake_sub = wake.add_subparsers(dest="wake_cmd", required=True)
    wake_sub.add_parser("setup", help="télécharger les modèles de base openWakeWord")

    journal = sub.add_parser("journal", help="journal des actions")
    journal.add_argument("--last", type=int, default=20)
    journal.add_argument("--clear", action="store_true")
    journal.add_argument("--stats", action="store_true")

    status = sub.add_parser("status", help="état courant (fichier pour Waybar / Quickshell)")
    status.add_argument("--waybar", action="store_true", help="JSON Waybar sur une ligne")
    status.add_argument("--follow", action="store_true", help="réaffiche à chaque changement")

    trigger = sub.add_parser(
        "trigger", help="push-to-talk : réveille l'instance en cours (SIGUSR1)"
    )
    trigger.add_argument("--pause", action="store_true", help="bascule pause/reprise (SIGUSR2)")

    llm = sub.add_parser("llm", help="cerveau LLM (OpenCode Zen / Go, Ollama…)")
    llm_sub = llm.add_subparsers(dest="llm_cmd", required=True)
    lt = llm_sub.add_parser("test", help="envoie une question au modèle configuré")
    lt.add_argument("text", nargs="*")
    ld = llm_sub.add_parser(
        "decide", help="montre la décision du LLM pour une phrase (action / réponse / rien)"
    )
    ld.add_argument("text", nargs="+")
    llm_sub.add_parser("models", help="liste les modèles disponibles chez le provider")
    llm_sub.add_parser("info", help="provider, URL, modèle, clé présente ?")

    tasks = sub.add_parser("tasks", help="historique des tâches et agents lancés")
    tasks.add_argument("--last", type=int, default=15)

    memory = sub.add_parser("memory", help="mémoire persistante (faits)")
    memory_sub = memory.add_subparsers(dest="memory_cmd", required=False)
    memory_sub.add_parser("list")
    mf = memory_sub.add_parser("forget")
    mf.add_argument("fact", nargs="+")
    mr = memory_sub.add_parser("remember")
    mr.add_argument("fact", nargs="+")
    memory_sub.add_parser("clear")

    sub.add_parser("agents", help="agents IA disponibles (claude, opencode, codex, gemini)")
    projects = sub.add_parser("projects", help="projets connus (config + dossiers de projets)")
    projects.add_argument("query", nargs="?", default=None)

    automations = sub.add_parser("automations", help="automatisations et rappels programmés")
    auto_sub = automations.add_subparsers(dest="auto_cmd", required=False)
    auto_sub.add_parser("list")
    ad = auto_sub.add_parser("delete")
    ad.add_argument("query", nargs="+")
    ar = auto_sub.add_parser("run", help="exécuter maintenant (test)")
    ar.add_argument("query", nargs="+")
    aa = auto_sub.add_parser(
        "add", help='ex. iris automations add "chaque matin à 9 h lance spotify"'
    )
    aa.add_argument("text", nargs="+")

    sub.add_parser("habits", help="habitudes détectées (routines horaires, enchaînements)")

    prefs = sub.add_parser(
        "prefs", help="préférences apprises à la voix (ton, voix, alias, activation…)"
    )
    prefs_sub = prefs.add_subparsers(dest="prefs_cmd", required=False)
    prefs_sub.add_parser("list")
    prefs_sub.add_parser("reset")

    service = sub.add_parser("service", help="service systemd utilisateur")
    service_sub = service.add_subparsers(dest="service_cmd", required=True)
    si = service_sub.add_parser("install")
    si.add_argument("--no-start", action="store_true")
    service_sub.add_parser("uninstall")
    service_sub.add_parser("status")
    service_sub.add_parser("show", help="afficher l'unité générée")
    sr = service_sub.add_parser("restart", help="relancer le service et attendre qu'Iris écoute")
    sr.add_argument("--timeout", type=float, default=30.0, help="attente maximale (s)")

    restart = sub.add_parser("restart", help="relancer Iris quand elle ne répond plus")
    restart.add_argument("--timeout", type=float, default=30.0, help="attente maximale (s)")
    return ap


# ---------------------------------------------------------------------------- commandes
def cmd_run(cfg: Config, args: argparse.Namespace) -> int:
    from iris.app import build_assistant
    from iris.audio.capture import AudioCapture
    from iris.audio.vad import VadSegmenter

    if args.no_wake:
        cfg.wake.backend = "none"
    assistant = build_assistant(cfg, speak=not args.print_only, with_stt=True, with_status=True)
    if cfg.wake.backend == "none":
        assistant.wake = None
    _write_pid()

    audio_wake = None
    if cfg.wake.backend == "openwakeword":
        from iris.wakeword.openwakeword import OpenWakeWord

        try:
            audio_wake = OpenWakeWord(cfg.wake.openwakeword_model, cfg.wake.openwakeword_threshold)
        except Exception as exc:  # noqa: BLE001
            log.error(
                "openWakeWord indisponible (%s) : repli sur la détection par transcription", exc
            )

    # préchargement du modèle STT pour ne pas rater la première phrase
    if hasattr(assistant.stt, "load"):
        assistant.stt.load()

    capture = AudioCapture(cfg.audio)
    capture.start()
    segmenter = VadSegmenter(cfg.audio)

    def _stop(signum, _frame) -> None:  # noqa: ANN001
        log.info("Arrêt demandé (signal %s)", signum)
        assistant.stop()
        capture.stop()

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGUSR1, lambda *_: assistant.request_wake())
    signal.signal(signal.SIGUSR2, lambda *_: assistant.request_toggle_pause())
    try:
        assistant.run_forever(capture, segmenter, audio_wake)
    finally:
        capture.stop()
        _remove_pid()
    return 0


def _write_pid() -> None:
    from iris.core.status import pid_file

    try:
        path = pid_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(os.getpid()), encoding="utf-8")
    except OSError as exc:
        log.debug("pid non écrit : %s", exc)


def _remove_pid() -> None:
    from iris.core.status import pid_file

    try:
        pid_file().unlink(missing_ok=True)
    except OSError:
        pass


def cmd_repl(cfg: Config, args: argparse.Namespace) -> int:
    from iris.app import build_assistant

    assistant = build_assistant(cfg, text_mode=True, speak=args.speak)
    print(
        "Iris — mode texte (Ctrl-D pour quitter). Mot d'activation facultatif. Ex. : « monte le son »"
    )
    while True:
        try:
            line = input("> ")
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        assistant.tick()
        assistant.handle_text(line)


def cmd_ask(cfg: Config, args: argparse.Namespace) -> int:
    from iris.app import build_assistant

    assistant = build_assistant(cfg, text_mode=True, speak=args.speak)
    reply = assistant.handle_text(" ".join(args.text))
    return 0 if reply is None or reply.ok else 1


def cmd_say(cfg: Config, args: argparse.Namespace) -> int:
    import inspect

    from iris.tts.factory import build_tts

    if args.backend:
        cfg.tts.backend = args.backend
    if args.lang:
        cfg.assistant.language = args.lang
    if args.voice:
        backend = cfg.tts.backend if cfg.tts.backend != "auto" else "elevenlabs"
        setattr(
            cfg.tts,
            {
                "elevenlabs": "elevenlabs_voice",
                "openai": "openai_voice",
                "cartesia": "cartesia_voice",
                "kokoro": "kokoro_voice",
                "piper": "piper_voice",
            }.get(backend, "elevenlabs_voice"),
            args.voice,
        )
        cfg.tts.backend = backend
    tts = build_tts(cfg)
    print(f"[{tts.name}]", file=sys.stderr)
    text = " ".join(args.text)
    if "language" in inspect.signature(tts.speak).parameters:
        return 0 if tts.speak(text, language=cfg.reply_language) else 1
    return 0 if tts.speak(text) else 1


def cmd_listen(cfg: Config, args: argparse.Namespace) -> int:
    from iris.audio.capture import record_seconds
    from iris.stt.factory import build_stt

    stt = build_stt(cfg)
    if hasattr(stt, "load"):
        stt.load()
    print(f"Parle maintenant ({args.seconds:.0f} s)…", file=sys.stderr)
    audio = record_seconds(cfg.audio, args.seconds)
    text = stt.transcribe(audio, cfg.audio.sample_rate, cfg.stt_language)
    print(text or "(rien d'exploitable)")
    if text and args.execute:
        from iris.app import build_assistant

        build_assistant(cfg, text_mode=True).handle_text(text)
    return 0


def cmd_doctor(cfg: Config, args: argparse.Namespace) -> int:
    from iris.doctor import report

    text, ok = report(cfg)
    print(text)
    return 0 if ok else 1


def cmd_intents(cfg: Config, args: argparse.Namespace) -> int:
    from iris.nlu.intents import RULES

    for rule in RULES:
        flag = " (confirmation)" if rule.confirm else ""
        print(f"{rule.name}{flag}")
    if cfg.commands:
        print("\nCommandes personnalisées :")
        for c in cfg.commands:
            print(f"  {c.name}: {', '.join(c.phrases)}  →  {c.exec}")
    return 0


def cmd_config(cfg: Config, args: argparse.Namespace) -> int:
    if args.config_cmd == "init":
        path = write_default_config(args.config, force=args.force)
        print(path)
    elif args.config_cmd == "path":
        print(args.config or paths.config_file())
    elif args.config_cmd == "show":
        from dataclasses import asdict
        from pprint import pprint

        data = {k: v for k, v in asdict(cfg).items() if k != "source"}
        pprint(data, sort_dicts=False, width=110)
    elif args.config_cmd == "edit":
        path = write_default_config(args.config)
        editor = os.environ.get("VISUAL") or os.environ.get("EDITOR") or "nano"
        os.execvp(editor, [editor, str(path)])
    return 0


def cmd_voices(cfg: Config, args: argparse.Namespace) -> int:
    from iris.tts import voices

    if args.voices_cmd == "cache":
        from iris.tts.cache import TTSCache

        cache = TTSCache(max_mb=cfg.tts.cache_max_mb)
        if args.clear:
            print(f"{cache.clear()} fichier(s) supprimé(s).")
        else:
            print(
                f"{cache.dir} : {cache.size_bytes() / 1_048_576:.1f} Mo (max {cfg.tts.cache_max_mb} Mo)"
            )
        return 0

    if args.voices_cmd == "library":
        tts = _elevenlabs(cfg)
        found = tts.library(args.lang, args.search, args.gender, args.limit, args.featured or None)
        if not found:
            print("Aucune voix trouvée.")
            return 1
        for i, v in enumerate(found, 1):
            print(f"{i:2d}. {v.summary()}")
            print(f"     owner={v.public_owner_id}  {v.description[:90]}")
        print(
            '\nAjouter : iris voices add <owner> <voice_id> --name "Nom"   puis   tts.elevenlabs_voice = "Nom"'
        )
        if args.preview:
            return _preview(found, args.preview)
        return 0

    if args.voices_cmd == "add":
        tts = _elevenlabs(cfg)
        voice_id = tts.add_from_library(args.public_owner_id, args.voice_id, args.name)
        print(
            f'Voix ajoutée : {args.name} ({voice_id}). Dans la config : elevenlabs_voice = "{args.name}"'
        )
        return 0

    if args.voices_cmd == "list":
        engine = args.engine
        if engine == "elevenlabs":
            tts = _elevenlabs(cfg)
            for v in tts.voices(refresh=True):
                if (
                    args.lang
                    and (v.labels or {}).get("language")
                    and (v.labels or {}).get("language", "").lower()[:2] != args.lang[:2]
                ):
                    continue
                print(v.summary())
            print("\nVoix natives par langue : iris voices library --lang fr")
            return 0
        if engine == "cartesia":
            from iris.tts.cartesia import CartesiaTTS

            for v in CartesiaTTS(cfg.tts, cfg.reply_language).voices(args.lang or None):
                print(
                    f"{v['name']:24} {v['id']}  {v['language']:3} {v['gender']:7} {v['description'][:60]}"
                )
            return 0
        if engine == "openai":
            for name in (
                "alloy",
                "ash",
                "ballad",
                "coral",
                "echo",
                "fable",
                "nova",
                "onyx",
                "sage",
                "shimmer",
                "verse",
                "marin",
                "cedar",
            ):
                print(name)
            return 0
        if engine == "kokoro":
            files = voices.kokoro_files(cfg.tts.kokoro_model, cfg.tts.kokoro_models_dir)
            print(
                f"Modèle Kokoro : {files[0] if files else 'non installé (iris voices download kokoro)'}"
            )
            names: list[str] = []
            if files:
                try:
                    from iris.tts.kokoro import KokoroTTS

                    names = KokoroTTS(cfg.tts, cfg.reply_language).voices()
                except Exception as exc:  # noqa: BLE001
                    print(f"(liste indisponible : {exc})", file=sys.stderr)
            for name in names or voices.KOKORO_KNOWN_VOICES:
                if args.lang and not name.startswith(args.lang[:1].lower()):
                    continue
                print(f"{name:14} {voices.KOKORO_KNOWN_VOICES.get(name, '')}")
            return 0
        lang = args.lang or (
            cfg.assistant.language[:2] + "_" if cfg.assistant.language != "auto" else None
        )
        if lang and len(lang) == 2:
            lang = lang + "_"
        for name, desc in voices.list_remote_voices(lang):
            installed = "✓ " if voices.voice_files(name, cfg.tts.piper_voices_dir) else "  "
            print(f"{installed}{name:32} {desc}")
        return 0

    voice = args.voice or cfg.tts.piper_voice
    if voice == "kokoro":
        model, _ = voices.download_kokoro(
            args.model or cfg.tts.kokoro_model, cfg.tts.kokoro_models_dir, force=args.force
        )
        print(f"Voix Kokoro prête : {model}")
        return 0
    model, _ = voices.download_voice(voice, cfg.tts.piper_voices_dir, force=args.force)
    print(f"Voix prête : {model}")
    return 0


def _elevenlabs(cfg: Config):
    from iris.tts.elevenlabs import ElevenLabsTTS

    return ElevenLabsTTS(cfg.tts, cfg.reply_language, cfg.audio.player)


def _preview(found, index: int) -> int:
    import shutil
    import subprocess
    import tempfile

    from iris.tts.elevenlabs import preview_to_file

    if not 1 <= index <= len(found):
        print(f"--preview attend un numéro entre 1 et {len(found)}", file=sys.stderr)
        return 2
    voice = found[index - 1]
    if not voice.preview_url:
        print("Pas d'extrait pour cette voix.", file=sys.stderr)
        return 1
    player = next((p for p in ("mpv", "ffplay", "pw-play") if shutil.which(p)), None)
    if player is None:
        print(f"Extrait : {voice.preview_url} (installe mpv pour l'écouter ici)")
        return 0
    with tempfile.TemporaryDirectory(prefix="iris-preview-") as tmp:
        path = preview_to_file(voice.preview_url, Path(tmp) / "preview.mp3")
        argv = {
            "mpv": ["mpv", "--no-terminal", "--no-video"],
            "ffplay": ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"],
            "pw-play": ["pw-play"],
        }[player]
        print(f"▶ {voice.name}")
        subprocess.run([*argv, str(path)], check=False)
    return 0


def cmd_models(cfg: Config, args: argparse.Namespace) -> int:
    from iris.stt.faster_whisper import FasterWhisperSTT

    if args.model:
        cfg.stt.model = args.model
    print(f"Téléchargement / vérification du modèle Whisper « {cfg.stt.model} »…", file=sys.stderr)
    FasterWhisperSTT(cfg.stt).load()
    print("Modèle prêt.")
    return 0


def cmd_wakeword(cfg: Config, args: argparse.Namespace) -> int:
    from iris.wakeword.openwakeword import setup_base_models

    print(setup_base_models())
    return 0


def cmd_journal(cfg: Config, args: argparse.Namespace) -> int:
    from iris.app import build_journal

    journal = build_journal(cfg)
    if args.clear:
        journal.clear()
        print("Journal effacé.")
        return 0
    if args.stats:
        for intent, n in journal.intent_counts().items():
            print(f"{n:6d}  {intent}")
        return 0
    records = journal.recent(args.last)
    if not records:
        print("Journal vide.")
    for rec in reversed(records):
        mark = "✓" if rec.ok else "✗"
        slots = f" {rec.slots}" if rec.slots else ""
        print(f"{rec.when} {mark} {rec.intent}{slots} — {rec.result} ({rec.duration_ms} ms)")
    return 0


def cmd_status(cfg: Config, args: argparse.Namespace) -> int:
    import json
    import time

    from iris.core.status import StatusWriter

    path = cfg.system.status_file or None
    last = None
    while True:
        data = StatusWriter.read(path) or {
            "text": "󰍭",
            "alt": "off",
            "class": "off",
            "tooltip": "Iris : arrêtée",
            "state": "off",
        }
        if args.waybar:
            line = json.dumps(
                {k: data.get(k, "") for k in ("text", "alt", "tooltip", "class")},
                ensure_ascii=False,
            )
        else:
            line = f"{data.get('state', 'off')}" + (
                f" — {data['detail']}" if data.get("detail") else ""
            )
        if line != last:
            print(line, flush=True)
            last = line
        if not args.follow:
            return 0
        time.sleep(0.5)


def cmd_trigger(cfg: Config, args: argparse.Namespace) -> int:
    from iris.core.status import pid_file

    sig = signal.SIGUSR2 if args.pause else signal.SIGUSR1
    try:
        pid = int(pid_file().read_text().strip())
        os.kill(pid, sig)
        return 0
    except (OSError, ValueError):
        pass
    from iris.actions import system

    res = system.run(["pkill", f"-{sig.name}", "-f", "iris run"], timeout=3)
    if not res.ok:
        print("Iris ne tourne pas (iris run / systemctl --user start iris).", file=sys.stderr)
        return 1
    return 0


def cmd_llm(cfg: Config, args: argparse.Namespace) -> int:
    import json
    import urllib.request

    from iris.llm import LLMError, build_client

    if args.llm_cmd == "info":
        from iris.llm import PROVIDERS

        preset = PROVIDERS.get(cfg.llm.provider, {})
        key_env = cfg.llm.api_key_env or preset.get("key_env", "")
        print(f"activé      : {cfg.llm.enabled}")
        print(f"provider    : {cfg.llm.provider}")
        print(f"base_url    : {cfg.llm.base_url or preset.get('base_url', '')}")
        print(f"modèle      : {cfg.llm.model}")
        print(
            f"clé ({key_env or 'llm.api_key'}) : {'présente' if (cfg.llm.api_key or os.environ.get(key_env or '', '')) else 'ABSENTE'}"
        )
        print(f"allow_cloud : {cfg.privacy.allow_cloud}")
        return 0
    try:
        client = build_client(cfg.llm, cfg.privacy.allow_cloud)
    except LLMError as exc:
        print(f"LLM non utilisable : {exc}", file=sys.stderr)
        return 1
    if args.llm_cmd == "models":
        req = urllib.request.Request(
            f"{client.base_url}/models",
            headers={"Authorization": f"Bearer {client.api_key}", "User-Agent": "iris-assistant"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310
            data = json.load(resp)
        for item in data.get("data", data if isinstance(data, list) else []):
            print(item.get("id") if isinstance(item, dict) else item)
        return 0
    from iris.app import build_journal
    from iris.llm import Brain

    brain = Brain(cfg, client)
    text = " ".join(args.text) or "Présente-toi en une phrase."
    if args.llm_cmd == "decide":
        decision = brain.decide(text, cfg.reply_language)
        print(decision)
        return 0
    build_journal(cfg)
    print(brain.converse(text, cfg.reply_language))
    return 0


def cmd_tasks(cfg: Config, args: argparse.Namespace) -> int:
    import time

    from iris.app import build_journal

    rows = build_journal(cfg).recent_tasks(args.last)
    if not rows:
        print("Aucune tâche enregistrée.")
        return 0
    for r in reversed(rows):
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(r["started"]))
        mark = {"done": "✓", "failed": "✗", "cancelled": "–"}.get(r["status"], "…")
        dur = f"{int((r['finished'] or time.time()) - r['started'])}s"
        print(f"{when} {mark} [{r['kind']}] {r['name']} ({dur}) — {r['output'][-120:].strip()!s}")
    return 0


def cmd_memory(cfg: Config, args: argparse.Namespace) -> int:
    from iris.app import build_journal
    from iris.core.memory import Memory

    memory = Memory(build_journal(cfg), cfg.memory.max_facts)
    cmd = args.memory_cmd or "list"
    if cmd == "list":
        facts = memory.facts()
        if not facts:
            print('Mémoire vide. Dis « Iris, retiens que … » ou : iris memory remember "…"')
        for f in facts:
            print(f"- {f.sentence()}")
    elif cmd == "remember":
        print(f"Noté : {memory.remember(' '.join(args.fact), source='cli').sentence()}")
    elif cmd == "forget":
        removed = memory.forget(" ".join(args.fact))
        print(f"Oublié : {removed.sentence()}" if removed else "Rien trouvé.")
    elif cmd == "clear":
        print(f"{memory.forget_all()} fait(s) effacé(s).")
    return 0


def cmd_agents(cfg: Config, args: argparse.Namespace) -> int:
    from iris.agents.runner import PRESETS, AgentRunner
    from iris.core.tasks import TaskManager

    runner = AgentRunner(cfg.agents, TaskManager())
    print(f"agents.enabled = {runner.enabled} ; défaut : {cfg.agents.default}")
    for name in PRESETS:
        ok = runner.available(name)
        print(
            f"  {'✓' if ok else '✗'} {name:10} {PRESETS[name]['bin']:10} {'prêt' if ok else 'CLI introuvable'}"
        )
    return 0


def cmd_projects(cfg: Config, args: argparse.Namespace) -> int:
    from iris.actions.projects import ProjectResolver

    resolver = ProjectResolver(cfg.projects, cfg.system.project_dirs)
    if args.query:
        path = resolver.resolve(args.query)
        print(path or "introuvable")
        return 0 if path else 1
    for name, path in sorted(resolver.candidates().items()):
        print(f"{name:30} {path}")
    return 0


def cmd_automations(cfg: Config, args: argparse.Namespace) -> int:
    from iris.app import build_assistant
    from iris.core.habits import describe

    assistant = build_assistant(cfg, text_mode=True, speak=False)
    router = assistant.router
    scheduler = router.scheduler
    cmd = args.auto_cmd or "list"
    if cmd == "list":
        items = scheduler.list()
        if not items:
            print("Aucune automatisation.")
        for a in items:
            action = (
                a.name
                if a.intent == "reminder_fire"
                else describe(a.intent, a.slots, cfg.reply_language)
            )
            print(f"{a.id:3d}. {a.describe(cfg.reply_language, action)}  [{a.source}]")
        return 0
    if cmd == "add":
        reply = assistant.handle_text(" ".join(args.text))
        return 0 if reply is not None and reply.ok else 1
    query = " ".join(args.query)
    auto = scheduler.find(query)
    if auto is None:
        print("Automatisation introuvable.", file=sys.stderr)
        return 1
    if cmd == "delete":
        scheduler.delete(str(auto.id))
        print(f"Supprimé : {auto.name}")
    elif cmd == "run":
        reply = router.run_automation(auto)
        print(reply.text)
        return 0 if reply.ok else 1
    return 0


def cmd_habits(cfg: Config, args: argparse.Namespace) -> int:
    from iris.app import build_journal
    from iris.core.habits import Habits, describe, key_to_intent

    habits = Habits(build_journal(cfg), cfg.habits.window_days, cfg.habits.min_occurrences)
    routines = habits.routines()
    follow_ups = habits.follow_ups()
    if not routines and not follow_ups:
        print("Aucune habitude détectée pour l'instant (il faut plusieurs jours d'utilisation).")
        return 0
    for r in routines:
        days = "en semaine" if r.weekdays_only else "tous les jours"
        print(
            f"routine      {r.hour:2d}:{r.minute:02d} {days:14} {describe(r.intent, r.slots)}  ({r.count} jours)"
        )
    for key, fu in follow_ups.items():
        first_intent, first_slots = key_to_intent(key)
        print(
            f"enchaînement {describe(first_intent, first_slots)} → {describe(fu.intent, fu.slots)}"
            f"  ({fu.count} fois, {int(fu.ratio * 100)} %)"
        )
    return 0


def cmd_prefs(cfg: Config, args: argparse.Namespace) -> int:
    from iris.app import build_journal
    from iris.core.prefs import Prefs

    prefs = Prefs(build_journal(cfg))
    if (args.prefs_cmd or "list") == "reset":
        print(f"{prefs.reset()} préférence(s) effacée(s).")
        return 0
    items = prefs.all()
    if not items:
        print(
            "Aucune préférence apprise (dis « sois plus directe », « parle plus vite », « appelle-toi Nova »…)."
        )
    for key, value in items.items():
        print(f"{key:26} {value}")
    return 0


def cmd_restart(cfg: Config, args: argparse.Namespace) -> int:
    """« iris restart » : le geste de secours quand Iris n'entend plus rien."""
    from iris import service

    ok, messages = service.restart(wait_s=args.timeout)
    for line in messages:
        print(line, file=sys.stdout if ok else sys.stderr)
    return 0 if ok else 1


def cmd_service(cfg: Config, args: argparse.Namespace) -> int:
    from iris import service

    if args.service_cmd == "restart":
        return cmd_restart(cfg, args)
    if args.service_cmd == "install":
        for line in service.install(start=not args.no_start):
            print(line)
    elif args.service_cmd == "uninstall":
        for line in service.uninstall():
            print(line)
    elif args.service_cmd == "status":
        print(service.status())
    elif args.service_cmd == "show":
        print(service.render_unit(), end="")
    return 0


COMMANDS = {
    "run": cmd_run,
    "repl": cmd_repl,
    "ask": cmd_ask,
    "say": cmd_say,
    "listen": cmd_listen,
    "doctor": cmd_doctor,
    "intents": cmd_intents,
    "config": cmd_config,
    "voices": cmd_voices,
    "models": cmd_models,
    "wakeword": cmd_wakeword,
    "journal": cmd_journal,
    "service": cmd_service,
    "restart": cmd_restart,
    "status": cmd_status,
    "trigger": cmd_trigger,
    "llm": cmd_llm,
    "tasks": cmd_tasks,
    "memory": cmd_memory,
    "agents": cmd_agents,
    "projects": cmd_projects,
    "automations": cmd_automations,
    "habits": cmd_habits,
    "prefs": cmd_prefs,
}


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    from iris.log import setup_logging

    level = "DEBUG" if args.verbose else ("INFO" if args.command == "run" else "WARNING")
    paths.ensure_dirs()
    setup_logging(level, file=paths.log_file() if args.command == "run" else None)
    cfg = load_config(args.config)
    try:
        return COMMANDS[args.command](cfg, args)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # noqa: BLE001
        if args.verbose:
            raise
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
