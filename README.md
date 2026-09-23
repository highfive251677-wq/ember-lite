# Ember Signal

> "Signals to Evidence"

Ember Signal is a local-first governance layer for terminal operations. It observes changes, keeps signed evidence, surfaces bounded suggestions, and evaluates release readiness while keeping people in control.

## What the first product release provides

- **Perception:** observe backend, repository, evidence, and local system signals.
- **Proactive review:** triggers, suggestions, and monitoring without autonomous decision authority.
- **Evidence chain:** signed, traceable observations and verification tools.
- **Release Gate:** six-dimension release evaluation for security, performance, evidence, regression, cost, and governance.
- **Governance:** policy, approval, and capability boundaries.
- **Bridge:** cross-terminal transport with Ed25519 signatures where configured.
- **Reproducible CLI:** install with `pip`, then use the `ember-signal` command.

Ember Signal is **not a chatbot, autonomous decision maker, or unrestricted automation agent**. It is a provenance keeper, safety guardian, and audit witness.

## Installation

```bash
python3 -m venv .venv
.venv/bin/pip install .
.venv/bin/ember-signal
```

The runtime requires Python 3.11 or newer. Optional language-model features require provider configuration described in the command documentation; the evidence and release-gate paths remain deterministic and local-first.

## Release verification

Run the deterministic product contract check before packaging or deployment:

```bash
.venv/bin/ember-signal verify --json
# or
.venv/bin/python scripts/verify_release.py --json
```

The verifier checks required files, importability, the immutable source commit recorded in the release manifest, signed-evidence requirements, and the human-control boundary. A `PASS` result is a technical release check only. It does **not** mean that copyright, asset licensing, contributor rights, counsel review, or commercial clearance has been completed.

## First five commands

```text
ember: whoami       # Meet Ember
ember: perceive     # Observe system
ember: gate         # Evaluate release
ember: govern       # Check governance
ember: exit         # Leave
```

## Luma Foundry integration boundary

Luma Foundry consumes a **read-only, sanitized evidence bundle** through an independently written adapter. The adapter does not import this Python runtime into the Luma Node application and does not treat a source commit as proof of ownership or commercial permission. Imported observations remain traceable to the exact Ember Signal source commit and are rejected when bundles are malformed, unsigned, unverified, credential-like, or missing provenance.

The current operational source is the Ember Signal Render service, while the Luma public route may use a bounded local fallback if the remote source is unavailable. Operator B must separately approve the catalogue Product ID, Drive register mapping, contributor-rights evidence, asset licences, dependency notices, and counsel-review record before any commercial claim or purchase flow is enabled.

## Architecture

```text
User → Agent → Safety → Provenance
              ↓
        P1 → P2 → P3 → P4 → P5 → P6
              ↓
        Signed Evidence Bundle → Luma read-only adapter
```

## Repository map

| Area | Purpose |
|---|---|
| `ember_agent.py` | Interactive CLI entry point |
| `perception/` | Observation, safety, bridge, governance, and release-gate layers |
| `scripts/verify_release.py` | Deterministic technical release verifier |
| `tests/` | Standard-library product contract tests |
| `EMBER-SIGNAL-RELEASE.json` | Release identity and explicit evidence boundary |
| `docs/` | Detailed operating and architecture documentation |

## License

MIT. Preserve the repository copyright and licence notice when redistributing source. Generated observation data and Luma product clearance remain separate questions.
