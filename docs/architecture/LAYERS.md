# Layer Specifications

## P1: Perception

Purpose: Observe system without mutating.

Files:
- perception/base_observer.py
- perception/observers.py
- perception/analysis.py
- perception/layer.py

Observers:
| Observer | Source | What |
|---|---|---|
| Backend | HTTP | /api/health |
| Repo | Git | git status |
| Evidence | SQLite | Provenance DB |
| Local | System | Disk/User |

Commands: perceive, analyze

## P2: Proactive

Purpose: Generate suggestions.

Files:
- perception/triggers.py
- perception/suggestion.py
- perception/monitor.py

Triggers:
- status_change
- confidence_drop
- error_appeared
- correlation_alert

Commands: suggest, monitor, stats, suggestions

## P3: Orchestration

Purpose: Multi-agent coordination.

Files:
- perception/orchestrator.py
- perception/evidence_graph.py

Agents:
- researcher
- coder
- reviewer

Commands: agents, orchestrate <task>

## P4: Bridge

Purpose: Cross-terminal transport.

Files:
- perception/bridge_transport.py
- perception/bridge_signatures.py
- perception/bridge_router.py
- perception/bridge_mcp.py

Features:
- WAL mode
- Idempotency keys
- Lamport clocks
- Dead letter queue
- Heartbeats
- Ed25519 signatures

Commands: @ <cmd>, T <cmd>, bridge, sign, graph, mcp

## P5: Release Gate

Purpose: 6-dimension decision.

Gates:
| Gate | Weight | Threshold |
|---|---|---|
| Security | 25% | 0 CRITICAL |
| Performance | 20% | >= 85% |
| Evidence | 20% | 100% valid |
| Regression | 15% | >= -2% |
| Cost | 10% | <= 5% |
| Governance | 10% | <= 3 pending |

Decisions: SHIP, HOLD, REVIEW, NO_SHIP

Commands: gate, gate history

## P6: Governance

Purpose: Policy + Approval + Capability.

Files:
- perception/governance.py

Policies (5 default):
- POL-SEC-001: No CRITICAL
- POL-CONF-001: Min confidence 85
- POL-EVID-001: Evidence integrity
- POL-GOV-001: Approval backlog <= 3
- POL-COST-001: Error rate <= 5%

Commands: govern, policy

## Related

- OVERVIEW.md
- ../guides/COMMANDS.md
