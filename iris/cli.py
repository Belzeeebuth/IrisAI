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
    vl = voices_sub.add_parser("list")
    vl.add_argument("--lang", default=None, help="filtre, ex. fr_FR, en_US")
    vd = voices_sub.add_parser("download")
    vd.add_argument("voice", nargs="?", default=None)
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

    service = sub.add_parser("service", help="service systemd utilisateur")
    service_sub = service.add_subparsers(dest="service_cmd", required=True)
    si = service_sub.add_parser("install")
    si.add_argument("--no-start", action="store_true")
    service_sub.add_parser("uninstall")
    service_sub.add_parser("status")
    service_sub.add_parser("show", help="afficher l'unité générée")
    return ap


# ---------------------------------------------------------------------------- commandes
def cmd_run(cfg: Config, args: argparse.Namespace) -> int:
    from iris.app import build_assistant
    from iris.audio.capture import AudioCapture
    from iris.audio.vad import VadSegmenter

    if args.no_wake:
        cfg.wake.backend = "none"
    assistant = build_assistant(cfg, speak=not args.print_only, with_stt=True)
    if cfg.wake.backend == "none":
        assistant.wake = None

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
    try:
        assistant.run_forever(capture, segmenter, audio_wake)
    finally:
        capture.stop()
    return 0


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
    from iris.tts.factory import build_tts

    tts = build_tts(cfg)
    print(f"[{tts.name}]", file=sys.stderr)
    return 0 if tts.speak(" ".join(args.text)) else 1


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

    if args.voices_cmd == "list":
        lang = args.lang or (cfg.assistant.language + "_" if cfg.assistant.language else None)
        for name, desc in voices.list_remote_voices(lang):
            installed = "✓ " if voices.voice_files(name, cfg.tts.piper_voices_dir) else "  "
            print(f"{installed}{name:32} {desc}")
        return 0
    voice = args.voice or cfg.tts.piper_voice
    model, _ = voices.download_voice(voice, cfg.tts.piper_voices_dir, force=args.force)
    print(f"Voix prête : {model}")
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


def cmd_service(cfg: Config, args: argparse.Namespace) -> int:
    from iris import service

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
