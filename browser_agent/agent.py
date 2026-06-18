"""
agent.py — Main entry point for the Browser Agent CLI.
Usage: python agent.py [COMMAND] [OPTIONS]
"""
import sys
import os

# Add the browser_agent package directory to sys.path
sys.path.insert(0, os.path.dirname(__file__))

# Fix Windows encoding issues for Rich emojis
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

from cli import cli

if __name__ == "__main__":
    cli()
