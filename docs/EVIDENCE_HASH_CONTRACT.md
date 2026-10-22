# Evidence-Hash Contract (pinned)

**Status:** Pinned as of this commit. **Owner:** ember-lite `perception/`.
**Reference implementation:** `perception/canonical.py`.

This document resolves the findings from the OpenHands independent
re-verification and the BRIDGE-001 cross-check (Oct 2026): the canonicalization
split, the persisted-but-ignored `key_id`, the silently regenerated identity,
the empty-chain honesty inversion, and the inconsistent tip formats. Every rule
below is enforced by tests, not by convention.

## 1. One canonical serialization

Every hash and every NEW signature is computed over exactly:

```
json.dumps(payload, sort_keys=True, separators=(",", ":"),
           ensure_ascii=False, default=str).encode("utf-8")
```

Implemented once in `perception/canonical.py:canonical_bytes()`. All modules
hash through it (`evidence_chain._hash`, and by extension observation hashes,
block hashes, receipt hashes, and policy hashes that already used the identical
formula). Nothing else defines a competing canonical form.

Properties: deterministic across processes/platforms; no whitespace ambiguity;
stable Unicode; non-JSON types degrade explicitly via `str()` instead of
raising mid-hash.

## 2. Legacy form is verification-only

`bridge_signatures` v2.0 signed over a DIFFERENT serialization (default
separators, `ensure_ascii=True` — "spaced"). Historical signatures made over
that form MUST remain verifiable, so:

- Verification accepts **canonical first, legacy second**
  (`canonical_bytes` → `legacy_bytes`), and reports which form matched.
- Nothing NEW is ever produced in the legacy form. `sign()` uses only
  `canonical_bytes`.

This makes the v2.0 → contract transition non-breaking: existing chains and
receipts keep verifying; all new artifacts are canonical.

## 3. `key_id` is binding

`key_id` = `base64(sha256(raw_public_key))[:16]`. It is persisted with every
signature (chain rows, receipts) and is now ENFORCED:

- `verify_signature(payload, sig, pub, expected_key_id=...)` refuses any
  signature whose public key does not fingerprint to `expected_key_id`,
  even if the signature is cryptographically valid.
- `verify_chain()` passes each row's stored `key_id`. Swapping in an attacker
  key plus a re-signed block therefore fails attribution (counted as
  `unverified`) instead of passing as verified.
- Chain validity (hash/link integrity) and signature assurance
  (`verified`/`unverified`) remain separate axes: a key swap does not break
  the chain; it breaks the attribution.

## 4. Identity is fail-closed — and the signer IS the persisted identity

A missing key file raises `IdentityNotProvisioned`. Nothing in the signing
path ever mints a key silently — a service that loses its identity must stop
being a new anonymous identity and instead provision explicitly:

```
from perception.bridge_signatures import generate_keypair
generate_keypair(terminal)   # the ONLY key-creation path
```

Callers of `sign()` already record failures honestly (`sign_error`,
`signed: False`), so unprovisioned operation degrades to visible unsigned
state, never to a silently re-keyed identity. Private keys are written `0600`,
public keys `0644`.

**Resolved defect (found during contract implementation):** v2.0's
`_load_private` destructured `_key_paths()` backwards and loaded the
**public** key file as a private seed (both files are 32 raw bytes, so the
deserialization never complained). Consequently every v2.0 signature was made
by a phantom key derived from public material, and the persisted private key
signed nothing — "key persistence" was effectively decorative, and the real
signing seed was exactly as public as the public key. From this commit the
signer is the persisted private key. Historical artifacts still verify: their
embedded `public_key` is self-consistent with their signatures, and
verification never reads key files. Any verifier that pinned the on-disk
identity (rather than the row `key_id`) must re-pin — that re-pin is exactly
the auditability rule 3 provides.

## 5. Empty chain semantics

An empty chain is **vacuously valid but explicitly marked**:

- `verify_chain()` on zero blocks → `{"valid": true, "status": "empty",
  "blocks": 0, "tip": null, ...}` — never a fabricated zero tip.
- `get_chain_summary()` on zero blocks → `tip_hash: null`.
- `tip` / `tip_hash` for non-empty chains is ALWAYS the 16-hex prefix of the
  head block hash.

This resolves the observed production inconsistency (16-zero `tip_hash` vs
64-zero `verify.tip` on `ember-signal-web.onrender.com`) and the honesty
inversion where an empty chain was indistinguishable from a healthy one.
Consumers MUST treat `tip is null` (or `status == "empty"`) as "no evidence
recorded yet", not as a failure and not as a healthy chain.

## 6. Enforcement

- `tests/test_bridge_signatures.py` — round-trip, dual-form (legacy accepted,
  canonical required for new), key_id binding, fail-closed identity,
  payload_hash = sha256(canonical bytes), key file permissions.
- `tests/test_evidence_chain.py` — empty-chain status/tip, key_id-bound chain
  verification, legacy-block compat inside the chain, tamper detection.

## 7. Non-goals (out of scope here)

- Merkle inclusion-proof complexity (O(n) indexing) — performance, not
  contract.
- `wave3_verify.py` positional row canonicalization — different object type
  (list rows, not dict payloads).
- Key rotation ceremony — `key_id` binding is the precondition that makes
  rotation auditable; the ceremony itself is a separate decision.
