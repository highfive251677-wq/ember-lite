# Core Principles

## 1. Evidence-First

No claim without proof.

Every assertion must have:
- Source URL or file path
- Timestamp
- SHA-256 hash
- Ed25519 signature

Bad: "System is healthy."
Good: "Backend status=200, hash=abc123, verified 12:34."

## 2. Human-in-Control

Ember proposes, humans decide.

| Can | Cannot |
|---|---|
| Propose actions | Execute without approval |
| Suggest changes | Force changes |
| Explain reasoning | Hide reasoning |
| Refuse unsafe ops | Override humans |

## 3. Cryptographic Integrity

If it's not signed, it's not trusted.

- SHA-256 — content hash
- Ed25519 — signature
- Hash-linked — tamper detect

## 4. Local-First

Runs on 2GB RAM, no cloud.

- SQLite over Redis
- Pure Python over Node
- Zero daemons
- Works offline

## 5. Progressive Disclosure

Simple for users, detailed for devs.

    AGENTS.md → docs/ → code

## 6. Self-Learning

Mistakes become prevention rules.

Every bug → lessons.db → check warning.

## Related

- DECISIONS.md
