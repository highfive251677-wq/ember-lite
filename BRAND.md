---
title: Ember Signal — Brand Identity
version: 1.0.0
last_updated: 2026-09-18
---

# 🌸 Ember Signal — Brand Identity

## Core Identity

| Field | Value |
|---|---|
| **Name** | Ember Signal |
| **Product** | Ember AI (Wildfire Intelligence Layer) |
| **Tagline** | *"Signals to Evidence"* |
| **Category** | Evidence & Audit Layer for Wildfire Operations |
| **Domain** | lumafoundry.live |

## What We Are NOT

- ❌ General chatbot
- ❌ Automation tool
- ❌ Decision maker
- ❌ Emergency authority

## What We ARE

- ✅ Provenance Keeper
- ✅ Safety Guardian
- ✅ Audit Trail Witness
- ✅ Evidence Analyst

## Our Six Sacred KPIs

| # | KPI | Rule |
|---|---|---|
| 1 | **Evidence-First** | No claim without proof. Missing data = `unknown`, not default. |
| 2 | **Human-in-Control** | Ember proposes. Operators decide. Physical actions ALWAYS require approval. |
| 3 | **Cryptographic Integrity** | Ed25519 signed everything. Hash-linked evidence chain. |
| 4 | **Local-First** | Runs on Samsung Tab A 2017 (2GB RAM). No heavy frameworks. |
| 5 | **Progressive Disclosure** | Simple for operators, detailed for developers. |
| 6 | **Self-Learning** | Every mistake becomes a prevention rule (lessons.db). |

## Architecture: P1-P6 Layers (Do NOT Merge or Rename)

| Layer | Module | Purpose |
|---|---|---|
| **P1** Perception | `perception/layer.py` | Observe system state |
| **P2** Proactive | `perception/triggers.py` | Generate suggestions |
| **P3** Orchestration | `perception/orchestrator.py` | Multi-agent coordination |
| **P4** Bridge | `perception/bridge_*.py` | Terminal transport + Ed25519 |
| **P5** Release Gate | `perception/release_gate.py` | 6-dimension decision |
| **P6** Governance | `perception/governance.py` | Policy + Approval + Capability |

## Supporting Infrastructure (Do NOT Duplicate)

| Module | Purpose |
|---|---|
| `perception/evidence_chain.py` | Hash-linked evidence chain |
| `perception/lessons.py` | Self-learning prevention rules |
| `perception/database.py` | Observation storage |
| `provenance.py` | Audit trail |
| `safety.py` | Command safety classification |

## Our Voice

- **Tone**: Calm, factual, evidence-based
- **Style**: Concise, traceable, human-readable
- **Avoid**: Hype, exaggeration, black-box claims
- **Embrace**: Transparency, traceability, human oversight

## Our Weaknesses → Our Strengths

| Weakness | Strength |
|---|---|
| No heavy frameworks | Zero-dependency architecture |
| Slow device | Edge-optimized for 2GB RAM |
| Manual approval | Safety-by-design |
| JSON-only output | Machine-readable by default |
| Niche domain | Mission-critical vertical |
| No ML/LLM scoring | Explainable AI by design |

## Our Philosophy

> *"မှတ်တမ်းမရှိရင် သက်သေမရှိဘူး။*
> *သက်သေမရှိရင် ဆုံးဖြတ်ချက်မရှိဘူး။*
> *ဆုံးဖြတ်ချက်မရှိရင် Governance မရှိဘူး။"*

## Tech Stack

- **Language**: Python 3.11+
- **Storage**: SQLite (local-first)
- **AI**: OpenRouter API (`openrouter/free` model)
- **Crypto**: Ed25519 via `cryptography` or pure Python `ed25519`
- **Device**: Samsung Tab A 2017 (2GB RAM, Termux)
