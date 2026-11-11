#!/usr/bin/env bash
set -euo pipefail
if [[ -z "${ISAAC_SIM_PATH:-}" ]]; then
    echo 'Set ISAAC_SIM_PATH to your Isaac Sim 5.1 installation folder.' >&2
    exit 1
fi
if [[ ! -f "$ISAAC_SIM_PATH/python.sh" ]]; then
    echo "Isaac Sim python.sh was not found in $ISAAC_SIM_PATH" >&2
    exit 1
fi
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec "$ISAAC_SIM_PATH/python.sh" "$SCRIPT_DIR/app.py" "$@"
