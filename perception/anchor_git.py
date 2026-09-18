"""
Ember Git-Based Anchoring (Phase 6)
====================================
Copilot: "Use Tab A as a light client or signer, not as a validator."

Strategy:
    - Local anchor file (always, no network)
    - Git commit as the "remote anchor"
    - The Git commit SHA is itself the external timestamp

Why Git:
    - No blockchain node required
    - Git already has cryptographic integrity (SHA-1/SHA-256)
    - GitHub/Codeberg act as the "transparency log"
    - Tab A can commit offline and push when online

Pure Python stdlib only (subprocess).
"""

from __future__ import annotations

import os
import json
import subprocess
from datetime import datetime, timezone
from typing import Any


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANCHOR_DIR = os.path.join(REPO_ROOT, "anchors")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run(cmd: list[str], cwd: str) -> dict:
    try:
        r = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=15,
        )
        return {
            "ok": r.returncode == 0,
            "stdout": r.stdout.strip(),
            "stderr": r.stderr.strip(),
            "code": r.returncode,
        }
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def anchor_to_git(anchor_dict: dict, message: str | None = None) -> dict:
    """
    Write an anchor commitment file and commit it to Git.

    Returns the commit SHA — the external anchor.
    """
    os.makedirs(ANCHOR_DIR, exist_ok=True)

    anchor_id = anchor_dict.get("anchor_id", "unknown")
    anchor_file = os.path.join(ANCHOR_DIR, f"{anchor_id}.json")

    with open(anchor_file, "w") as f:
        json.dump(anchor_dict, f, indent=2, sort_keys=True)

    # Stage
    add = _run(["git", "add", anchor_file], REPO_ROOT)
    if not add["ok"]:
        return {"anchored": False, "stage": "add", "error": add}

    # Commit
    msg = message or f"Anchor: {anchor_id} @ {_now_iso()}"
    commit = _run(["git", "commit", "-m", msg], REPO_ROOT)

    # Empty commit still counts as anchor attempt
    if not commit["ok"]:
        if "nothing to commit" in (commit.get("stdout", "") + commit.get("stderr", "")):
            sha = _run(["git", "rev-parse", "HEAD"], REPO_ROOT)
            return {
                "anchored": True,
                "commit_sha": sha.get("stdout", "")[:40],
                "note": "no_changes",
            }
        return {"anchored": False, "stage": "commit", "error": commit}

    # Get SHA
    sha = _run(["git", "rev-parse", "HEAD"], REPO_ROOT)
    commit_sha = sha.get("stdout", "")[:40] if sha["ok"] else None

    return {
        "anchored": True,
        "anchor_id": anchor_id,
        "commit_sha": commit_sha,
        "anchor_file": anchor_file,
        "anchored_at": _now_iso(),
    }


def remote_anchor(anchor_dict: dict, push: bool = False) -> dict:
    """
    Commit locally, and optionally push to the remote.
    Remote push is the "external anchor".
    """
    result = anchor_to_git(anchor_dict)
    if not result.get("anchored"):
        return result

    if push:
        p = _run(["git", "push"], REPO_ROOT)
        result["pushed"] = p["ok"]
        result["push_stdout"] = p.get("stdout", "")[:200]
        if not p["ok"]:
            result["push_error"] = p.get("stderr", "")[:200]

    return result


def read_anchor_file(anchor_id: str) -> dict | None:
    path = os.path.join(ANCHOR_DIR, f"{anchor_id}.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def list_anchor_files() -> list[str]:
    if not os.path.isdir(ANCHOR_DIR):
        return []
    return sorted(
        f for f in os.listdir(ANCHOR_DIR) if f.endswith(".json")
    )


if __name__ == "__main__":
    print("Git anchor module ready.")
    print("Anchor dir:", ANCHOR_DIR)
    print("Existing anchors:", len(list_anchor_files()))
