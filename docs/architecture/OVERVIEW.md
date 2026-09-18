# Architecture Overview

## System Diagram

    User → Agent → Safety → Provenance
              ↓
        P1 → P2 → P3 → P4 → P5 → P6
              ↓
        Signed Evidence Bundle

## Components

| Component | File | Purpose |
|---|---|---|
| Agent | ember_agent.py | Entry point |
| Brain | ember_brain.py | LLM integration |
| Identity | ember_identity.py | Self-awareness |
| Safety | safety.py | Command classify |
| Provenance | provenance.py | Audit trail |
| Perception | perception/layer.py | Observe system |
| Governance | perception/governance.py | Policy enforce |

## Data Flow

1. User input → Safety check
2. SAFE: auto-execute
3. MEDIUM/HIGH: require approval
4. CRITICAL: blocked

## Cryptographic Layers

| Layer | Algorithm | Purpose |
|---|---|---|
| Hash | SHA-256 | Provenance |
| Signature | Ed25519 | Non-repudiation |
| Chain | Hash-linked | Tamper detect |
| Idempotency | UUID | Duplicate prevent |

## Storage

| DB | File | Purpose |
|---|---|---|
| Provenance | provenance.db | Actions |
| Perception | perception/perception.db | Observations |
| Lessons | perception/lessons.db | Learning |
| Bridge | perception/bridge.db | Messages |
| Graph | perception/bridge_graph.db | Signed nodes |
| Gate | perception/release_gate.db | Evaluations |
| Governance | perception/governance.db | Policies |

## Related

- LAYERS.md — Detailed specs
- ../design-docs/DECISIONS.md — Why
