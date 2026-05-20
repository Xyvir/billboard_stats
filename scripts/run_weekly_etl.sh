#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "${ROOT_DIR}"

echo "Bypassing Postgres checks. Running local JSON ETL..."

# We stripped out the entire block checking for required_vars.
# Now it just blindly runs the Python updater.
python -m billboard_stats.etl.updater "$@"
