#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PROJECT_DIR="$(CDPATH= cd -- "${SCRIPT_DIR}/.." && pwd)"
RECIPIENT="${1:-${RECIPIENT:-root}}"

export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="${PROJECT_DIR}/src${PYTHONPATH:+:${PYTHONPATH}}"

exec python3 -m system_inspection_report.main "$RECIPIENT"
