# Ember Lite

Provenance-first Terminal Agent for Android/Termux.

## What is Ember Lite?

Ember Lite is a lightweight AI agent that:
- Logs every terminal action with SHA-256 provenance hashes
- Classifies commands by safety level (SAFE / MEDIUM / HIGH / CRITICAL)
- Requires human approval for risky actions
- Maintains an immutable action history

## Project Structure


## Installation

```bash
pkg install python sqlite git jq -y
pip install rich requests
cd ~/ember-lite
python ember_agent.py
