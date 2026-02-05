#!/usr/bin/env bash
# Start the Hospital Dashboard API (run after schema + seed are done).
# Usage: ./run.sh   or:  bash run.sh

set -e
cd "$(dirname "$0")"

# Use .env if present
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

# Default DB URL for local Mac (no password)
export DATABASE_URL="${DATABASE_URL:-postgresql://$(whoami)@localhost:5432/hospital_analytics}"

# Activate venv if it exists
if [ -d venv ]; then
  source venv/bin/activate
fi

echo "Starting API at http://localhost:8000 (docs: http://localhost:8000/docs)"
exec uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
