#!/bin/bash
# अर्थAI — Start FastAPI backend
# Run from anywhere: ./start_backend.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

source .venv/bin/activate
export TOKENIZERS_PARALLELISM=false
export PYTHONPATH="$SCRIPT_DIR"

echo "Starting अर्थAI backend at http://localhost:8000"
echo "API docs: http://localhost:8000/docs"
uvicorn backend.main:app --reload --port 8000
