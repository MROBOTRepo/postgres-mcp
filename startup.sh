#!/bin/bash
set -e

echo "Installing Python dependencies..."
pip install --no-cache-dir -r /home/site/wwwroot/requirements.txt

echo "Starting MCP server on port 8000..."
cd /home/site/wwwroot
exec python server.py
