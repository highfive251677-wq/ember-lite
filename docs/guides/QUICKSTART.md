# Quick Start

## Prerequisites

- Termux (Android) or Linux
- Python 3.11+
- 500 MB free space

## Installation

    git clone https://github.com/highfive251677-wq/ember-lite.git
    cd ember-lite
    pip install rich cryptography
    export OPENROUTER_API_KEY="sk-or-v1-..."
    python3 ember_agent.py

## First 5 Commands

    ember: whoami       # Meet Ember
    ember: perceive     # Observe system
    ember: gate         # Evaluate release
    ember: govern       # Check governance
    ember: exit         # Leave

## Common Workflows

Workflow 1: Daily Check

    perceive → gate → govern

Workflow 2: Cross-Terminal

    @ curl https://api.example.com/health
    T git status --short
    bridge inbox

Workflow 3: Multi-Agent

    orchestrate build a login page

## Troubleshooting

| Problem | Fix |
|---|---|
| Brain offline | Set OPENROUTER_API_KEY |
| Import error | pip install rich cryptography |
| No output | python3 -m py_compile ember_agent.py |

## Next

- COMMANDS.md — Full reference
- ../architecture/OVERVIEW.md — How it works
