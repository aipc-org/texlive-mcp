#!/bin/sh
set -eu
if [ "$#" -eq 0 ]; then
    set -- --workspace "$PWD"
fi
PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$PROJECT_DIR"
exec "$PROJECT_DIR/.venv/bin/python" -m latex_mcp_server.local "$@"
