#!/usr/bin/env python3
"""Deterministic Ember Signal release verification."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "EMBER-SIGNAL-RELEASE.json"
REQUIRED_FILES = (
    "ember_agent.py",
    "perception/release_gate.py",
    "perception/evidence_chain.py",
    "LICENSE",
    "README.md",
    "pyproject.toml",
)
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
EMBEDDED_MANIFEST = {
    "product": "Ember Signal",
    "tagline": "Signals to Evidence",
    "release": "0.1.0",
    "sourceCommit": "2bb64e184c5618cf5d7fef2f4755975b6041b535",
    "sourceLicenseObserved": "MIT",
    "humanControl": True,
    "signedEvidenceRequired": True,
    "commercialStatus": "PENDING — evidence incomplete",
}


def check() -> dict:
    checks: list[dict] = []

    def add(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "status": "PASS" if passed else "FAIL", "detail": detail})

    source_checkout = (ROOT / "pyproject.toml").exists()
    add("manifest_exists", MANIFEST.exists() or not source_checkout, "source manifest or embedded package manifest")
    manifest = EMBEDDED_MANIFEST.copy()
    if MANIFEST.exists():
        try:
            manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
            add("manifest_json", isinstance(manifest, dict), "valid JSON object")
        except json.JSONDecodeError as exc:
            add("manifest_json", False, str(exc))

    if source_checkout:
        for relative in REQUIRED_FILES:
            path = ROOT / relative
            add(f"file:{relative}", path.is_file(), "present" if path.is_file() else "missing")

    commit = str(manifest.get("sourceCommit", ""))
    add("source_commit", bool(SHA_RE.fullmatch(commit)), "40-character immutable commit recorded")
    add("commercial_boundary", manifest.get("commercialStatus") == "PENDING — evidence incomplete", "commercial clearance remains explicitly pending")
    add("human_control", manifest.get("humanControl") is True, "human approval boundary recorded")
    add("signed_evidence", manifest.get("signedEvidenceRequired") is True, "signed evidence requirement recorded")

    for module in ("perception.release_gate", "perception.evidence_chain", "ember_agent"):
        try:
            importlib.import_module(module)
            add(f"import:{module}", True, "importable")
        except Exception as exc:  # pragma: no cover
            add(f"import:{module}", False, f"{type(exc).__name__}: {exc}")

    digest = hashlib.sha256(MANIFEST.read_bytes()).hexdigest() if MANIFEST.exists() else hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    passed = all(item["status"] == "PASS" for item in checks)
    return {
        "product": "Ember Signal",
        "release": manifest.get("release"),
        "status": "PASS" if passed else "FAIL",
        "commercialStatus": manifest.get("commercialStatus"),
        "manifestSha256": digest,
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the Ember Signal release boundary")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args()
    result = check()
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"{result['product']} {result.get('release')}: {result['status']}")
        for item in result["checks"]:
            print(f"[{item['status']}] {item['name']}: {item['detail']}")
        print(f"Commercial status: {result['commercialStatus']}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
