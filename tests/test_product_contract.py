import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ProductContractTests(unittest.TestCase):
    def test_manifest_is_explicitly_not_commercially_cleared(self):
        manifest = json.loads((ROOT / "EMBER-SIGNAL-RELEASE.json").read_text())
        self.assertEqual(manifest["product"], "Ember Signal")
        self.assertEqual(manifest["commercialStatus"], "PENDING — evidence incomplete")
        self.assertTrue(manifest["humanControl"])
        self.assertTrue(manifest["signedEvidenceRequired"])

    def test_release_verifier_passes(self):
        result = subprocess.run(
            [sys.executable, "scripts/verify_release.py", "--json"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "PASS")
        self.assertTrue(all(item["status"] == "PASS" for item in payload["checks"]))

    def test_release_gate_is_importable(self):
        result = subprocess.run(
            [sys.executable, "-c", "import perception.release_gate; import perception.evidence_chain"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
