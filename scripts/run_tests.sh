#!/usr/bin/env bash
# scripts/run_tests.sh
# Runs the isolation level test suite against the local Postgres instance.
#
# Usage:
#   ./scripts/run_tests.sh
#
# Prerequisites:
#   - Docker running:  docker compose up -d
#   - Dependencies installed:  uv sync

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "-- pgisolations isolation test runner --"
echo ""

# Verify docker compose service is healthy before running
if ! docker compose ps --status running | grep -q "pgisolations_db"; then
  echo "[ERROR] Postgres container is not running."
  echo "        Start it first with:  docker compose up -d"
  exit 1
fi

echo "[INFO] Postgres container is up. Running tests..."
echo ""

uv run python -m tests.test_isolation
