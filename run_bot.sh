#!/bin/bash
# Quick Python detection and bot runner
set -e

# Find Python command
PYTHON_CMD=""
for cmd in python3 python python3.11 python3.12; do
    if command -v "$cmd" >/dev/null 2>&1; then
        PYTHON_CMD="$cmd"
        break
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "❌ Error: Python not found. Please install Python 3.11+ first."
    exit 1
fi

# Activate virtual environment if it exists
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

# Run the bot with detected Python command
"$PYTHON_CMD" -m src.main "$@"