# Command Reference

## Perception (P1)

- `perceive` — Observe all sources
- `perceive backend` — Observe single source
- `analyze` — LLM analysis of last perception

## Proactive (P2)

- `suggest` — Generate suggestions
- `monitor` — Run 3 iterations
- `monitor <n>` — Run n iterations
- `stats` — Monitor statistics
- `suggestions` — Suggestion history

## Orchestration (P3)

- `agents` — List registered agents
- `orchestrate <task>` — Run multi-agent task

## Bridge (P4)

- `@ <cmd>` — Route to a-Shell (iOS)
- `T <cmd>` — Route to Termux (Android)
- `bridge` — Bridge statistics
- `bridge inbox` — Pending messages
- `sign <text>` — Ed25519 sign
- `graph` — Signed graph summary
- `graph verify` — Verify integrity
- `mcp` — MCP interface info

## Release Gate (P5)

- `gate` — Run 6-dimension evaluation
- `gate history` — Evaluation history

## Governance (P6)

- `govern` — Governance summary
- `policy` — Policy check

## Identity

- `ask <q>` — Ask Ember
- `whoami` — Ember identity
- `identity` — Full identity
- `history` — Action history
- `lessons` — Self-learning log
- `check <code>` — Check against lessons
- `help` — Help panel
- `exit` — Quit

## Terminal Commands

Any unrecognized command is a shell command.

Safety levels:
- SAFE → auto-run
- MEDIUM → approval
- HIGH → approval + warning
- CRITICAL → blocked
