# Ember Signal — Agent Map

> Tagline: "Signals to Evidence"
> Role: Governance Layer for Terminal Operations

## What is Ember?

Ember is a local-first governance layer that watches terminal
operations, detects changes, suggests actions, and enforces policies
— all with cryptographically signed evidence.

- Ember is NOT: A chatbot, automation tool, or decision maker.
- Ember IS: A Provenance Keeper, Safety Guardian, Audit Witness.

## Quick Start

    python3 ember_agent.py

## Architecture Layers

| Layer | Module | Purpose |
|---|---|---|
| P1 | perception/layer.py | Observe system |
| P2 | perception/triggers.py | Suggest actions |
| P3 | perception/orchestrator.py | Multi-agent |
| P4 | perception/bridge_*.py | Terminal transport |
| P5 | perception/release_gate.py | Release decision |
| P6 | perception/governance.py | Policy enforcement |

## Key Commands

| Command | Purpose |
|---|---|
| perceive | Observe system |
| analyze | LLM analysis |
| suggest | Get suggestions |
| orchestrate <task> | Multi-agent task |
| @ / T <cmd> | Route to terminal |
| graph | Signed evidence graph |
| gate | Release evaluation |
| govern | Governance status |
| policy | Policy check |
| ask <q> | Talk to Ember |
| lessons | Self-learning log |
| help | Show help |
| exit | Quit |

## Core Principles

1. Evidence-first — No claim without proof
2. Human-in-Control — Ember proposes, humans decide
3. Cryptographic — Ed25519 signed everything
4. Local-first — Runs on Tab A 2017 (2GB RAM)
5. Progressive Disclosure — Details in docs/

## File Structure

    ember-lite/
    ├── AGENTS.md          ← You are here
    ├── README.md          ← User intro
    ├── ember_agent.py     ← Main entry
    ├── perception/        ← P1-P6 modules
    ├── docs/              ← Detailed docs
    └── scripts/           ← Utilities

## Philosophy

"No record, no evidence. No evidence, no decision.
No decision, no governance."

## Learn More

- docs/guides/QUICKSTART.md
- docs/architecture/OVERVIEW.md
- docs/design-docs/DECISIONS.md
