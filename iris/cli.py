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
    vl.add_argument("--engine", default="piper", choices=("piper", "kokoro"))
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

    if args.voices_cmd == "list":
        if args.engine == "kokoro":
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
        for name, desc in voices.list_remote_voices(lang):
            installed = "✓ " if voices.voice_files(name, cfg.tts.piper_voices_dir) else "  "
            print(f"{installed}{name:32} {desc}")
        return 0
    voice = args.voice or cfg.tts.piper_voice
    if voice == "kokoro":
        model, _ = voices.download_kokoro(
            args.model or cfg.tts.kokoro_model, cfg.tts.kokoro_models_dir, force=args.force
        )
        print(f"Voix IA Kokoro prête : {model}")
        return 0
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
    "status": cmd_status,
    "trigger": cmd_trigger,
    "llm": cmd_llm,
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
