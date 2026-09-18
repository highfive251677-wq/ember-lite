# Ember Signal

> "Signals to Evidence"

A local-first governance layer for terminal operations.

## Features

- Perception — Observe backend, repo, evidence, local
- Proactive — Triggers + Suggestions + Monitor
- Orchestration — Multi-agent coordination
- Bridge — Cross-terminal transport with Ed25519
- Release Gate — 6-dimension decision
- Governance — Policy + Approval + Capability

## Quick Start

    git clone https://github.com/highfive251677-wq/ember-lite.git
    cd ember-lite
    pip install rich cryptography
    export OPENROUTER_API_KEY="sk-or-v1-..."
    python3 ember_agent.py

## Documentation

| Doc | Purpose |
|---|---|
| AGENTS.md | Agent map (start here) |
| docs/guides/QUICKSTART.md | 5-min setup |
| docs/guides/COMMANDS.md | Command reference |
| docs/architecture/OVERVIEW.md | System design |
| docs/design-docs/DECISIONS.md | Why we built it |

## Architecture

    User → Agent → Safety → Provenance
              ↓
        P1 → P2 → P3 → P4 → P5 → P6
              ↓
        Signed Evidence Bundle

## License

MIT
