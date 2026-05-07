#!/bin/bash
# Claude Context Patcher - One-liner patch script
# Usage: curl -sSL https://raw.githubusercontent.com/2ndelement/claude-context-patcher/main/scripts/patch.sh | bash

set -e

echo "Claude Context Patcher"
echo "====================="
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not installed."
    exit 1
fi

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Run the patcher
echo "Searching for Claude Code installation..."
cd "$PROJECT_DIR"
python3 -m src.main --auto

echo ""
echo "Done! Please restart Claude Code."
