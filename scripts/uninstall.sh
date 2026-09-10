#!/usr/bin/env bash
# Désinstalle Iris (service, venv, lien). Conserve la configuration et le journal sauf --purge.
set -euo pipefail
VENV="${IRIS_VENV:-$HOME/.local/share/iris/venv}"
if command -v iris >/dev/null; then iris service uninstall || true; fi
rm -f "$HOME/.local/bin/iris"
rm -rf "$VENV"
if [[ "${1:-}" == "--purge" ]]; then
  rm -rf "$HOME/.config/iris" "$HOME/.local/share/iris" "$HOME/.local/state/iris" "$HOME/.cache/iris"
  echo "Iris désinstallée, données supprimées."
else
  echo "Iris désinstallée (config et journal conservés ; --purge pour tout supprimer)."
fi
