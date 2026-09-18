"""
Ember Bridge Signatures — Ed25519
==================================
Premium: Cryptographic Provenance
- Ed25519 (ATP Standard)
- Key Persistence
- Sign / Verify API
"""

import os
import json
import base64
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization


KEY_DIR = os.path.join(os.path.dirname(__file__), "keys")


def _ensure_key_dir():
    os.makedirs(KEY_DIR, exist_ok=True)


def _key_paths(terminal: str):
    return (
        os.path.join(KEY_DIR, f"{terminal}_private.key"),
        os.path.join(KEY_DIR, f"{terminal}_public.key")
    )


def generate_keypair(terminal: str) -> dict:
    """Terminal အတွက် Ed25519 Keypair ဖန်တီးခြင်း"""
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
    
    with open(pub_path, "wb") as f:
        f.write(public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        ))
    
    return {"status": "created", "terminal": terminal}


def _load_private(terminal: str):
    _, priv_path = _key_paths(terminal)
    if not os.path.exists(priv_path):
        generate_keypair(terminal)
    with open(priv_path, "rb") as f:
        return ed25519.Ed25519PrivateKey.from_private_bytes(f.read())


def _load_public(terminal: str):
    _, pub_path = _key_paths(terminal)
    if not os.path.exists(pub_path):
        generate_keypair(terminal)
    with open(pub_path, "rb") as f:
        return ed25519.Ed25519PublicKey.from_public_bytes(f.read())


def sign(payload, terminal: str = "T") -> dict:
    """Payload ကို Sign လုပ်ခြင်း"""
    if isinstance(payload, (dict, list)):
        data = json.dumps(payload, sort_keys=True).encode()
    else:
        data = str(payload).encode()
    
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
        "payload_hash": data.hex()[:16]
    }


def verify(payload, signature_b64: str, public_key_b64: str) -> bool:
    """Signature ကို Verify လုပ်ခြင်း"""
    try:
        if isinstance(payload, (dict, list)):
            data = json.dumps(payload, sort_keys=True).encode()
        else:
            data = str(payload).encode()
        
        signature = base64.b64decode(signature_b64)
        pub_bytes = base64.b64decode(public_key_b64)
        public_key = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
        public_key.verify(signature, data)
        return True
    except Exception:
        return False


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
    
    valid = verify(msg, signed["signature"], signed["public_key"])
    print(f"✓ Verify (correct): {valid}")
    
    tampered = dict(msg)
    tampered["command"] = "rm -rf /"
    invalid = verify(tampered, signed["signature"], signed["public_key"])
    print(f"✗ Verify (tampered): {invalid}")
    print()
    print("✅ P4.2 Signatures complete.")
