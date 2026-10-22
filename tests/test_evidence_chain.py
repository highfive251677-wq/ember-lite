"""
Evidence chain integrity (perception/evidence_chain.py).

The chain's whole promise ("no record, no evidence") rests on verify_chain
recomputing hashes and refusing to trust stored values.

Evidence-hash contract (docs/EVIDENCE_HASH_CONTRACT.md) enforcement:
empty-chain semantics (status/tip), key_id-bound signature verification,
and legacy-block compatibility inside one chain.
"""

import base64
import json
import sqlite3

from perception import bridge_signatures as bs
from perception import evidence_chain as ec


def test_empty_chain_is_valid(isolated_dbs):
    result = ec.verify_chain()
    assert result["valid"] is True
    assert result["blocks"] == 0
    # Contract rule 5: an empty chain is explicitly marked, never faked.
    assert result["status"] == "empty"
    assert result["tip"] is None

    summary = ec.get_chain_summary()
    assert summary["blocks"] == 0
    assert summary["tip_hash"] is None


def test_append_then_verify(isolated_dbs):
    first = ec.add_observation({"a": 1}, terminal="T")
    second = ec.add_observation({"a": 2}, terminal="T")

    assert first["recorded"] is True
    assert first["signed"] is True
    assert second["previous_hash"] == first["block_hash"]

    result = ec.verify_chain()
    assert result["valid"] is True
    assert result["blocks"] == 2
    assert result["verified"] == 2
    assert result["unverified"] == 0


def test_summary_reports_true_flags(isolated_dbs):
    ec.add_observation({"a": 1}, terminal="T")
    ec.add_observation({"a": 2}, terminal="T")

    summary = ec.get_chain_summary()
    assert summary["blocks"] == 2
    assert summary["signed"] == 2
    assert summary["anchored"] == 0  # nothing was anchored yet
    assert summary["tip_hash"] != "0" * 16


def test_tampered_payload_is_detected(isolated_dbs):
    ec.add_observation({"a": 1}, terminal="T")

    conn = sqlite3.connect(str(isolated_dbs["chain"]))
    payload = json.loads(
        conn.execute("SELECT canonical_payload FROM chain").fetchone()[0]
    )
    payload["created_at"] = "1999-01-01T00:00:00+00:00"
    conn.execute(
        "UPDATE chain SET canonical_payload = ?",
        (json.dumps(payload, sort_keys=True, separators=(",", ":")),),
    )
    conn.commit()
    conn.close()

    result = ec.verify_chain()
    assert result["valid"] is False
    assert result["broken_reason"] == "hash_mismatch_at_1"


def test_broken_chain_link_is_detected(isolated_dbs):
    ec.add_observation({"a": 1}, terminal="T")
    ec.add_observation({"a": 2}, terminal="T")

    conn = sqlite3.connect(str(isolated_dbs["chain"]))
    conn.execute("UPDATE chain SET previous_hash = ? WHERE block_index = 2", ("f" * 64,))
    conn.commit()
    conn.close()

    result = ec.verify_chain()
    assert result["valid"] is False
    assert result["broken_reason"] == "broken_link_at_2"


# ── Contract rule 3: key_id-bound verification ──────────────────────


def test_stored_key_id_matches_signing_key(isolated_dbs):
    """The invariant that makes external key pinning possible: every row
    stores the fingerprint of the key that actually signed it."""
    from perception.bridge_signatures import key_id_for

    ec.add_observation({"a": 1}, terminal="T")

    conn = sqlite3.connect(str(isolated_dbs["chain"]))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT public_key, key_id FROM chain WHERE block_index = 1").fetchone()
    conn.close()

    assert row["key_id"] == key_id_for(row["public_key"])
    assert len(row["key_id"]) == 16


def test_signature_key_id_disagreement_is_unverified(isolated_dbs):
    """The row-level binding: a signature whose key does not fingerprint to
    the row's stored key_id counts as unverified."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from perception.canonical import canonical_bytes

    ec.add_observation({"a": 1}, terminal="T")

    attacker_key = ed25519.Ed25519PrivateKey.generate()
    pub_bytes = attacker_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    attacker_pub_b64 = base64.b64encode(pub_bytes).decode()

    conn = sqlite3.connect(str(isolated_dbs["chain"]))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT canonical_payload, key_id FROM chain WHERE block_index = 1").fetchone()
    payload = json.loads(row["canonical_payload"])
    forged_sig = base64.b64encode(attacker_key.sign(canonical_bytes(payload))).decode()
    # Attacker swaps signature + public_key but CANNOT fake the stored key_id
    # (they do not control it): signature is valid, key_id binding refuses it.
    conn.execute(
        "UPDATE chain SET signature = ?, public_key = ? WHERE block_index = 1",
        (forged_sig, attacker_pub_b64),
    )
    conn.commit()
    conn.close()

    result = ec.verify_chain()
    assert result["valid"] is True          # hash/link integrity intact
    assert result["verified"] == 0
    assert result["unverified"] == 1        # attribution refused


# ── Contract rule 2: legacy blocks stay verifiable inside the chain ──


def test_legacy_spaced_signature_still_verifies_in_chain(isolated_dbs):
    """A v2.0-era block (signature over spaced serialization) still counts as
    verified — the dual-form acceptance keeps historical chains valid."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519

    ec.add_observation({"legacy": True}, terminal="T")

    # Rewrite the signature as a v2.0-style (spaced-bytes) signature made by
    # the SAME provisioned key — exactly what old rows look like.
    priv_path = str(__import__("pathlib").Path(bs.KEY_DIR) / "T_private.key")
    with open(priv_path, "rb") as f:
        key = ed25519.Ed25519PrivateKey.from_private_bytes(f.read())

    conn = sqlite3.connect(str(isolated_dbs["chain"]))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT canonical_payload, public_key, key_id FROM chain WHERE block_index = 1").fetchone()
    payload = json.loads(row["canonical_payload"])
    legacy_sig = base64.b64encode(
        key.sign(json.dumps(payload, sort_keys=True).encode())
    ).decode()
    conn.execute(
        "UPDATE chain SET signature = ? WHERE block_index = 1",
        (legacy_sig,),
    )
    conn.commit()
    conn.close()

    result = ec.verify_chain()
    assert result["valid"] is True
    assert result["verified"] == 1
    assert result["unverified"] == 0
