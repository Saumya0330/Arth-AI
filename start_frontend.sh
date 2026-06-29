#!/bin/bash
# अर्थAI — Start React frontend
# Run from anywhere: ./start_frontend.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/frontend"

export PATH="/opt/homebrew/bin:$PATH"
echo "Starting अर्थAI frontend at http://localhost:5173"
npm run dev
