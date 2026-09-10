#!/usr/bin/env bash
# Installation d'Iris sur Omarchy OS (Arch Linux + Hyprland).
#
#   ./scripts/install.sh              # installation complète (venv, voix, config, service)
#   ./scripts/install.sh --no-service # sans le service systemd
#   ./scripts/install.sh --no-voice   # sans télécharger la voix Piper
#   ./scripts/install.sh --no-pacman  # ne pas toucher aux paquets système
#   ./scripts/install.sh --kokoro     # ajouter la voix locale Kokoro (facultative, 325 Mo)
#
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${IRIS_VENV:-$HOME/.local/share/iris/venv}"
BIN_DIR="$HOME/.local/bin"
PYTHON_VERSION="${IRIS_PYTHON:-3.12}"
VOICE="${IRIS_VOICE:-fr_FR-siwis-medium}"
WHISPER_MODEL="${IRIS_WHISPER_MODEL:-base}"
WITH_SERVICE=1
WITH_VOICE=1
WITH_PACMAN=1
EXTRAS="${IRIS_EXTRAS:-stt,tts,audio}"
KOKORO_MODEL="${IRIS_KOKORO_MODEL:-kokoro-v1.0.onnx}"
WITH_KOKORO=0

for arg in "$@"; do
  case "$arg" in
    --no-service) WITH_SERVICE=0 ;;
    --no-voice) WITH_VOICE=0 ;;
    --no-pacman) WITH_PACMAN=0 ;;
    --kokoro) WITH_KOKORO=1; EXTRAS="$EXTRAS,voice" ;;
    --extras=*) EXTRAS="${arg#--extras=}" ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) echo "option inconnue : $arg" >&2; exit 2 ;;
  esac
done

say() { printf '\033[1;35m[iris]\033[0m %s\n' "$*"; }

# 1. Paquets système ---------------------------------------------------------
if [[ $WITH_PACMAN -eq 1 ]] && command -v pacman >/dev/null; then
  say "Paquets système (pacman)…"
  sudo pacman -S --needed --noconfirm \
    python uv pipewire wireplumber libpulse brightnessctl playerctl libnotify espeak-ng wtype
else
  say "Paquets système ignorés (pas de pacman ou --no-pacman)."
fi

# 2. Environnement Python ---------------------------------------------------
if ! command -v uv >/dev/null; then
  say "uv introuvable : installation via pip…"
  python3 -m pip install --user uv
fi
say "Environnement Python ($VENV, Python $PYTHON_VERSION)…"
mkdir -p "$(dirname "$VENV")" "$BIN_DIR"
uv venv --quiet --python "$PYTHON_VERSION" "$VENV"
say "Installation d'Iris + extras [$EXTRAS]…"
uv pip install --quiet --python "$VENV/bin/python" --upgrade "$REPO_DIR[$EXTRAS]"
ln -sf "$VENV/bin/iris" "$BIN_DIR/iris"
if ! echo "$PATH" | tr ':' '\n' | grep -qx "$BIN_DIR"; then
  say "⚠ $BIN_DIR n'est pas dans ton PATH (Omarchy l'ajoute normalement)."
fi

# 3. Configuration -------------------------------------------------------------
"$BIN_DIR/iris" config init >/dev/null
say "Configuration : $("$BIN_DIR/iris" config path)"

# 4. Voix + modèle ---------------------------------------------------------------
if [[ $WITH_VOICE -eq 1 ]]; then
  say "Voix Piper de secours $VOICE…"
  "$BIN_DIR/iris" voices download "$VOICE" || true
  if [[ $WITH_KOKORO -eq 1 ]]; then
    say "Voix locale Kokoro ($KOKORO_MODEL)…"
    "$BIN_DIR/iris" voices download kokoro --model "$KOKORO_MODEL" || say "⚠ téléchargement Kokoro impossible (réseau ?)"
  fi
fi
say "Modèle Whisper « $WHISPER_MODEL » (téléchargé au premier lancement si absent)…"
"$BIN_DIR/iris" models download "$WHISPER_MODEL" || say "⚠ téléchargement du modèle impossible pour l'instant (réseau ?)"

# 5. Service ------------------------------------------------------------------------
if [[ $WITH_SERVICE -eq 1 ]]; then
  say "Service systemd utilisateur…"
  "$BIN_DIR/iris" service install
fi

say "Diagnostic :"
"$BIN_DIR/iris" doctor || true
say "Terminé. Essaie : iris say \"Bonjour, je suis Iris\"   puis   iris listen --execute"
say "Voix IA : ELEVENLABS_API_KEY dans ~/.config/environment.d/iris.conf + [privacy] allow_cloud = true, puis iris voices library --lang fr (voir docs/VOICE.md)."
say "Cerveau LLM (OpenCode Go/Zen) : clé sur https://opencode.ai/auth → OPENCODE_API_KEY, puis [llm] enabled = true (voir docs/LLM.md)."
