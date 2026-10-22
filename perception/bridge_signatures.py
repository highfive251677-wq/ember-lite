"""
Ember Bridge Signatures — Ed25519
==================================
Premium: Cryptographic Provenance
- Ed25519 (ATP Standard)
- Key Persistence
- Sign / Verify API

Evidence-hash contract (docs/EVIDENCE_HASH_CONTRACT.md):
- NEW signatures are made over the canonical serialization
  (perception.canonical.canonical_bytes — compact, sorted, UTF-8).
- Verification accepts the canonical form AND the legacy v2.0 form
  (default separators) so historical signatures stay verifiable.
- key_id (sha256 of the public key, 16-hex prefix) is BINDING: a verifier
  that knows the expected key_id refuses a signature made by any other key,
  even a cryptographically valid one.
- Identity is fail-closed: a missing key file raises IdentityNotProvisioned.
  Nothing ever mints a new identity silently; provisioning is an explicit
  generate_keypair() call.
"""

import os
import base64
import hashlib
import stat
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

from perception.canonical import canonical_bytes, legacy_bytes


KEY_DIR = os.path.join(os.path.dirname(__file__), "keys")


class IdentityNotProvisioned(RuntimeError):
    """No signing identity exists for this terminal.

    Raised instead of silently minting a key: a service that lost its key
    file must not continue as a brand-new identity without anyone noticing.
    Provision explicitly with generate_keypair(terminal).
    """


def _ensure_key_dir():
    os.makedirs(KEY_DIR, exist_ok=True)


def _key_paths(terminal: str):
    return (
        os.path.join(KEY_DIR, f"{terminal}_private.key"),
        os.path.join(KEY_DIR, f"{terminal}_public.key")
    )


def generate_keypair(terminal: str) -> dict:
    """Explicitly create an Ed25519 keypair for a terminal.

    This is the ONLY path that ever creates a key. Private key material is
    written 0600, public key 0644.
    """
    _ensure_key_dir()
    priv_path, pub_path = _key_paths(terminal)
    
    if os.path.exists(priv_path):
        return {"status": "exists", "terminal": terminal}
    
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    
    with open(priv_path, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        ))
    os.chmod(priv_path, stat.S_IRUSR | stat.S_IWUSR)  # 0600
    
    with open(pub_path, "wb") as f:
        f.write(public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        ))
    os.chmod(pub_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IROTH | stat.S_IRGRP)  # 0644
    
    return {"status": "created", "terminal": terminal}


def _load_private(terminal: str):
    # NOTE: _key_paths returns (private, public) — the private path comes
    # FIRST. The v2.0 code destructured this as `_, priv_path = ...` and
    # silently loaded the PUBLIC key file as a private seed (both are 32
    # bytes), so nothing was ever signed by the persisted identity. Loading
    # the real private file is a contract fix, not a refactor.
    priv_path, _ = _key_paths(terminal)
    if not os.path.exists(priv_path):
        raise IdentityNotProvisioned(
            f"no signing identity for terminal {terminal!r}; "
            f"call generate_keypair({terminal!r}) explicitly"
        )
    with open(priv_path, "rb") as f:
        return ed25519.Ed25519PrivateKey.from_private_bytes(f.read())


def _load_public(terminal: str):
    _, pub_path = _key_paths(terminal)
    if not os.path.exists(pub_path):
        raise IdentityNotProvisioned(
            f"no public key for terminal {terminal!r}; "
            f"call generate_keypair({terminal!r}) explicitly"
        )
    with open(pub_path, "rb") as f:
        return ed25519.Ed25519PublicKey.from_public_bytes(f.read())


def key_id_for(public_key_b64: str) -> str:
    """The stable 16-hex key fingerprint carried in receipts and chain rows."""
    pub_bytes = base64.b64decode(public_key_b64)
    return base64.b64encode(hashlib.sha256(pub_bytes).digest()).decode()[:16]


def sign(payload, terminal: str = "T") -> dict:
    """Sign a payload over the canonical serialization.

    Raises IdentityNotProvisioned (and never mints a key) when the terminal
    has no identity yet — callers record that honestly instead of silently
    continuing under a brand-new identity.
    """
    data = canonical_bytes(payload)
    
    private_key = _load_private(terminal)
    signature = private_key.sign(data)
    public_key = private_key.public_key()
    pub_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    
    return {
        "terminal": terminal,
        "signature": base64.b64encode(signature).decode(),
        "public_key": base64.b64encode(pub_bytes).decode(),
        "algorithm": "Ed25519",
        # A stable fingerprint of the signing key, so a receipt identifies WHICH
        # key signed it (for rotation/revocation). Not a hash of the payload.
        "key_id": base64.b64encode(hashlib.sha256(pub_bytes).digest()).decode()[:16],
        # Full sha256 of the exact signed (canonical) bytes, so a verifier can
        # re-derive it.
        "payload_hash": hashlib.sha256(data).hexdigest(),
    }


def verify_signature(payload, signature_b64: str, public_key_b64: str,
                     expected_key_id: str = None) -> dict:
    """Verify a signature and report WHY it failed.

    Contract rules:
    - The signature must authenticate the canonical serialization OR, for
      historical artifacts, the legacy v2.0 serialization.
    - If expected_key_id is given, the supplied public key must fingerprint
      to exactly that key_id — a valid signature from any other key is a
      failure (the pinned identity signed this, nobody else).
    """
    result = {
        "valid": False,
        "form": None,
        "key_id": None,
        "key_id_ok": None,
        "reason": None,
    }
    try:
        signature = base64.b64decode(signature_b64)
        pub_bytes = base64.b64decode(public_key_b64)
        public_key = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
    except Exception as exc:
        result["reason"] = f"malformed_key_or_signature: {type(exc).__name__}"
        return result

    result["key_id"] = key_id_for(public_key_b64)
    if expected_key_id is not None:
        result["key_id_ok"] = result["key_id"] == expected_key_id
        if not result["key_id_ok"]:
            result["reason"] = "key_id_mismatch"
            return result

    # Canonical form first; legacy v2.0 form accepted for historical blocks.
    for form, serializer in (("canonical", canonical_bytes), ("legacy", legacy_bytes)):
        try:
            data = serializer(payload)
            public_key.verify(signature, data)
            result["valid"] = True
            result["form"] = form
            return result
        except Exception:
            continue

    result["reason"] = "signature_invalid_for_both_serializations"
    return result


def verify(payload, signature_b64: str, public_key_b64: str,
           expected_key_id: str = None) -> bool:
    """Backward-compatible boolean verification (see verify_signature)."""
    return verify_signature(payload, signature_b64, public_key_b64,
                            expected_key_id=expected_key_id)["valid"]


if __name__ == "__main__":
    print("=" * 60)
    print("  Testing Bridge Signatures (P4.2)")
    print("=" * 60)
    print()
    
    r1 = generate_keypair("T")
    r2 = generate_keypair("@")
    print(f"✅ Keypair T: {r1['status']}")
    print(f"✅ Keypair @: {r2['status']}")
    print()
    
    msg = {"command": "git status", "channel": "termux"}
    signed = sign(msg, terminal="T")
    print(f"🔐 Signed: {signed['signature'][:32]}...")
    print(f"   Algorithm: {signed['algorithm']}")
    print()
    
    valid = verify(msg, signed["signature"], signed["public_key"],
                   expected_key_id=signed["key_id"])
    print(f"✓ Verify (correct, key_id bound): {valid}")
    
    tampered = dict(msg)
    tampered["command"] = "rm -rf /"
    invalid = verify(tampered, signed["signature"], signed["public_key"])
    print(f"✗ Verify (tampered): {invalid}")
    print()
    print("✅ P4.2 Signatures complete.")
