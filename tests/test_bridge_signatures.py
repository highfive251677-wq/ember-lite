"""
Bridge signature round-trip (perception/bridge_signatures.py).

Ed25519 must reject tampered payloads and accept authentic ones.
Evidence-hash contract (docs/EVIDENCE_HASH_CONTRACT.md) enforcement:
canonical signing, dual-form verification, binding key_id, and fail-closed
identity. The autouse `provisioned_identity` fixture provisions terminal "T"
in an isolated KEY_DIR (see tests/conftest.py).
"""

import base64
import hashlib
import json
import os

import pytest

from perception import bridge_signatures as bs
from perception.canonical import canonical_bytes, legacy_bytes


def test_sign_verify_roundtrip():
    payload = {"command": "git status", "channel": "termux"}
    signed = bs.sign(payload, terminal="T")
    assert signed["algorithm"] == "Ed25519"
    assert bs.verify(payload, signed["signature"], signed["public_key"]) is True


def test_tampered_payload_rejected():
    payload = {"command": "git status"}
    signed = bs.sign(payload, terminal="T")
    tampered = {"command": "rm -rf /"}
    assert bs.verify(tampered, signed["signature"], signed["public_key"]) is False


def test_malformed_signature_rejected():
    assert bs.verify({"a": 1}, "not-base64!!", "also-bad") is False


def test_sign_returns_truthful_key_id_and_payload_hash():
    payload = {"a": 1, "b": [2, 3]}
    out = bs.sign(payload, terminal="T")

    # payload_hash is the real sha256 of the CANONICAL signed bytes
    # (contract rule 1/2 — no spaced form for new signatures).
    assert out["payload_hash"] == hashlib.sha256(canonical_bytes(payload)).hexdigest()
    assert out["payload_hash"] != hashlib.sha256(legacy_bytes(payload)).hexdigest()
    assert len(out["payload_hash"]) == 64

    # key_id is a stable fingerprint of the public key; the old "lib" field is gone.
    assert len(out["key_id"]) == 16
    assert "lib" not in out


def test_key_id_is_stable_and_key_specific(tmp_path, monkeypatch):
    # Contract rule 4: identity is fail-closed — provision explicitly.
    monkeypatch.setattr(bs, "KEY_DIR", str(tmp_path / "keys"))
    bs.generate_keypair("A")
    bs.generate_keypair("B")
    a = bs.sign({"x": 1}, terminal="A")
    a2 = bs.sign({"x": 2}, terminal="A")
    b = bs.sign({"x": 1}, terminal="B")
    assert a["key_id"] == a2["key_id"]   # same key -> same id
    assert a["key_id"] != b["key_id"]    # different key -> different id


# ── Contract rule 1/2: canonical form is what gets signed ───────────


def test_signature_verifies_against_canonical_and_legacy_forms():
    """
    New signatures are canonical; verification accepts canonical AND legacy.
    Proven by constructing a v2.0-style (spaced) signature manually and
    checking verify() accepts BOTH serializations for that artifact.
    """
    from cryptography.hazmat.primitives.asymmetric import ed25519

    payload = {"cmd": "status", "n": 1}

    # Legacy-style signature over spaced bytes (what v2.0 produced).
    legacy_data = json.dumps(payload, sort_keys=True).encode()
    signed = bs.sign(payload, terminal="T")
    # Re-sign the legacy bytes with the provisioned key by hand.
    priv_path = os.path.join(bs.KEY_DIR, "T_private.key")
    with open(priv_path, "rb") as f:
        key = ed25519.Ed25519PrivateKey.from_private_bytes(f.read())
    legacy_sig = base64.b64encode(key.sign(legacy_data)).decode()

    detail = bs.verify_signature(payload, legacy_sig, signed["public_key"])
    assert detail["valid"] is True
    assert detail["form"] == "legacy"

    # The canonical signature verifies in the canonical form.
    detail = bs.verify_signature(payload, signed["signature"], signed["public_key"])
    assert detail["valid"] is True
    assert detail["form"] == "canonical"


# ── Contract rule 3: key_id is binding ──────────────────────────────


def test_key_id_binding_refuses_a_different_valid_key(tmp_path, monkeypatch):
    """A cryptographically valid signature from ANY other key must fail when
    the verifier pins the expected key_id."""
    # Pinned signature first: made by the fixture-provisioned terminal "T".
    pinned = bs.sign({"action": "release"}, terminal="T")

    # Attacker identity in an isolated key dir (fail-closed provisioning).
    monkeypatch.setattr(bs, "KEY_DIR", str(tmp_path / "other"))
    bs.generate_keypair("attacker")
    attacker_signed = bs.sign({"steal": True}, terminal="attacker")
    # Attacker signature IS valid against its own key...
    assert bs.verify({"steal": True}, attacker_signed["signature"],
                     attacker_signed["public_key"]) is True
    # ...but refused the moment the pinned key_id is enforced.
    assert bs.verify({"steal": True}, attacker_signed["signature"],
                     attacker_signed["public_key"],
                     expected_key_id=pinned["key_id"]) is False
    detail = bs.verify_signature({"steal": True}, attacker_signed["signature"],
                                 attacker_signed["public_key"],
                                 expected_key_id=pinned["key_id"])
    assert detail["reason"] == "key_id_mismatch"
    assert detail["key_id_ok"] is False

    # The correctly-pinned signature verifies.
    assert bs.verify({"action": "release"}, pinned["signature"],
                     pinned["public_key"],
                     expected_key_id=pinned["key_id"]) is True


# ── Contract rule 4: identity is fail-closed ────────────────────────


def test_missing_identity_raises_instead_of_minting_a_key(tmp_path, monkeypatch):
    monkeypatch.setattr(bs, "KEY_DIR", str(tmp_path / "fresh-empty"))
    with pytest.raises(bs.IdentityNotProvisioned):
        bs.sign({"x": 1}, terminal="ghost")
    # And nothing was silently written:
    assert not os.path.exists(os.path.join(str(tmp_path / "fresh-empty"),
                                           "ghost_private.key"))


def test_generate_keypair_file_permissions(tmp_path, monkeypatch):
    monkeypatch.setattr(bs, "KEY_DIR", str(tmp_path / "perm"))
    bs.generate_keypair("T2")
    priv = os.path.join(str(tmp_path / "perm"), "T2_private.key")
    pub = os.path.join(str(tmp_path / "perm"), "T2_public.key")
    assert (os.stat(priv).st_mode & 0o777) == 0o600
    assert (os.stat(pub).st_mode & 0o777) == 0o644
