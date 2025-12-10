#!/bin/bash
# Quick start script for OSS Engagement Analyzer

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "Installing dependencies..."
    venv/bin/pip install -r requirements.txt
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo ""
    echo "⚠️  Please edit .env and add your GITHUB_TOKEN before running the analyzer"
    echo ""
    exit 1
fi

# Check if GITHUB_TOKEN is set
if ! grep -q "GITHUB_TOKEN=ghp_\|GITHUB_TOKEN=github_pat_" .env 2>/dev/null; then
    echo "⚠️  GITHUB_TOKEN not configured in .env file"
    echo "Please edit .env and add your GitHub Personal Access Token"
    echo ""
    exit 1
fi

# Run the analyzer
echo "Running analyzer..."
venv/bin/python analyzer.py "$@"
