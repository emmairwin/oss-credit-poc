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
fi

# Check if GITHUB_TOKEN is set (optional - only needed for org member lookup)
if ! grep -q "GITHUB_TOKEN=ghp_\|GITHUB_TOKEN=github_pat_" .env 2>/dev/null; then
    echo "Note: GITHUB_TOKEN not configured in .env file"
    echo "Issue/PR attribution by org membership will not be available"
    echo "Commit attribution by email domain will still work"
    echo ""
fi

# Run the analyzer
echo "Running analyzer..."
venv/bin/python analyzer.py "$@"
