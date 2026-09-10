"""Exécution de commandes : synchrone (``run``) ou détachée (``launch``).

Le lancement détaché utilise, dans l'ordre : ``uwsm app --`` (Omarchy/UWSM : l'application
vit dans son propre scope systemd et survit à un redémarrage d'Iris), ``systemd-run --user``,
puis un simple ``Popen`` dans une nouvelle session.
"""

from __future__ import annotations

import logging
import os
import shlex
import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass, field

log = logging.getLogger(__name__)


@dataclass
class CmdResult:
    ok: bool
    code: int
    out: str = ""
    err: str = ""
    argv: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.ok


def which(name: str) -> str | None:
    return shutil.which(name)


def run(
    argv: Sequence[str] | str,
    *,
    timeout: float = 15,
    shell: bool = False,
    env: dict[str, str] | None = None,
    input_text: str | None = None,
) -> CmdResult:
    """Exécute et attend. Ne lève jamais : le résultat porte ``ok`` et ``err``."""
    display = argv if isinstance(argv, str) else " ".join(shlex.quote(a) for a in argv)
    try:
        proc = subprocess.run(
            argv,
            shell=shell,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, **env} if env else None,
            input=input_text,
        )
    except FileNotFoundError:
        log.debug("Commande introuvable : %s", display)
        return CmdResult(False, 127, "", f"commande introuvable : {display}", _argv_list(argv))
    except subprocess.TimeoutExpired:
        log.warning("Commande trop longue (> %ss) : %s", timeout, display)
        return CmdResult(False, 124, "", "délai dépassé", _argv_list(argv))
    except OSError as exc:
        return CmdResult(False, 1, "", str(exc), _argv_list(argv))
    result = CmdResult(
        proc.returncode == 0,
        proc.returncode,
        proc.stdout.strip(),
        proc.stderr.strip(),
        _argv_list(argv),
    )
    log.debug("run %s → %d", display, proc.returncode)
    return result


def launch(argv: Sequence[str] | str, *, launcher: str = "auto", shell: bool = False) -> bool:
    """Lance une application détachée d'Iris. Retourne True si le lancement a été émis."""
    if isinstance(argv, str):
        argv_list = ["sh", "-c", argv] if shell else shlex.split(argv)
    else:
        argv_list = list(argv)
    if not argv_list:
        return False

    wrappers: list[list[str]] = []
    in_session = bool(os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY"))
    if launcher in ("auto", "uwsm") and in_session and which("uwsm"):
        wrappers.append(["uwsm", "app", "--"])
    if launcher in ("auto", "systemd-run") and which("systemd-run"):
        wrappers.append(["systemd-run", "--user", "--quiet", "--collect", "--same-dir", "--"])
    wrappers.append([])  # direct

    for wrapper in wrappers:
        full = [*wrapper, *argv_list]
        try:
            subprocess.Popen(
                full,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            log.info("Lancé : %s", " ".join(shlex.quote(a) for a in full))
            return True
        except FileNotFoundError:
            if not wrapper:
                log.warning("Exécutable introuvable : %s", argv_list[0])
                return False
            continue
        except OSError as exc:
            log.warning("Lancement impossible (%s) : %s", exc, full)
            continue
    return False


def expand(command: str) -> list[str]:
    """Développe les variables d'environnement puis découpe la commande."""
    return shlex.split(os.path.expandvars(os.path.expanduser(command)))


def _argv_list(argv: Sequence[str] | str) -> list[str]:
    return shlex.split(argv) if isinstance(argv, str) else list(argv)
