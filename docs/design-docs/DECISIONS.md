# Design Decisions

## ADR-001: SQLite over Redis

Status: Accepted

Context: Cross-terminal bus on 2GB RAM.

Decision: SQLite with WAL mode.

Rationale:
| Criterion | SQLite | Redis |
|---|---|---|
| RAM | ~0 MB | 50-100 MB |
| Infra | Zero | Daemon |
| Precedent | Claude Bridge | Enterprise |

## ADR-002: Ed25519 over RSA

Status: Accepted

Decision: Ed25519 via cryptography library.

Rationale:
- 64-byte signatures
- NIST approved
- ATP Standard
- Pure Python fallback

## ADR-003: Transport != Orchestration

Status: Accepted

Decision: Bridge is transport only.

Rationale (Claude Bridge):
"A bridge is a transport, not an autonomous orchestrator."

## ADR-004: 6-Dimension Gate

Status: Accepted

Decision: Security + Performance + Evidence + Regression + Cost + Governance.

Rationale (Industry):
- Cerberus: Security + Performance + Cost
- 5-Dimension: + Groundedness + Safety
- BDP: PASS/REVIEW/BLOCKED

## ADR-005: Documentation-First Repo

Status: Accepted

Decision: AGENTS.md + docs/ + CI.

Rationale (agentic-engine):
"A single AGENTS.md works for humans and agents."

## Related

- PRINCIPLES.md
