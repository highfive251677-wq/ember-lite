"""
Ember Migration Verifier (Strict, Fail-Closed)
================================================
Copilot Requirement: Exact equality, fail-closed.

Rules:
    - source_count == target_count (exact)
    - source_pk_set == target_pk_set (no missing, no extra)
    - every source row exists in target
    - every digest matches
    - every crypto field identical
    - any error → status = "error"

KPI #1 (Evidence-First), KPI #3 (Cryptographic Integrity).
Pure Python stdlib only.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3


def _canonical(v) -> str:
    return json.dumps(v, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, default=str)


def _digest(v) -> str:
    return hashlib.sha256(_canonical(v).encode("utf-8")).hexdigest()


def verify_table(source_conn, target_conn, source_table, target_table,
                 pk_column, digest_columns, crypto_columns=None):
    """
    Strict verification. Any mismatch → status = "issues_found".
    Any query/schema error → status = "error".
    """
    report = {
        "source_table": source_table,
        "target_table": target_table,
        "status": "unknown",
        "row_counts": {},
        "pk_comparison": {},
        "content_digest": {},
        "crypto_check": {},
        "errors": [],
    }

    # ===== Row counts (EXACT match required) =====
    try:
        s_count = source_conn.execute(
            f"SELECT COUNT(*) FROM {source_table}"
        ).fetchone()[0]
    except sqlite3.OperationalError as exc:
        report["status"] = "error"
        report["errors"].append(f"source_count_error: {exc}")
        return report

    try:
        t_count = target_conn.execute(
            f"SELECT COUNT(*) FROM {target_table}"
        ).fetchone()[0]
    except sqlite3.OperationalError as exc:
        report["status"] = "error"
        report["errors"].append(f"target_count_error: {exc}")
        return report

    report["row_counts"] = {
        "source": s_count,
        "target": t_count,
        "match": s_count == t_count,   # ✅ exact equality
        "delta": t_count - s_count,
    }

    # ===== PK sets (EXACT equality) =====
    try:
        s_pks = {str(r[0]) for r in source_conn.execute(
            f"SELECT {pk_column} FROM {source_table}"
        )}
        t_pks = {str(r[0]) for r in target_conn.execute(
            f"SELECT {pk_column} FROM {target_table}"
        )}
    except sqlite3.OperationalError as exc:
        report["status"] = "error"
        report["errors"].append(f"pk_query_error: {exc}")
        return report

    missing = sorted(s_pks - t_pks)
    extra = sorted(t_pks - s_pks)

    report["pk_comparison"] = {
        "source_count": len(s_pks),
        "target_count": len(t_pks),
        "missing_in_target": missing[:10],
        "extra_in_target": extra[:10],
        "missing_count": len(missing),
        "extra_count": len(extra),
        "all_present": len(missing) == 0 and len(extra) == 0,  # ✅ both zero
    }

    # ===== Content digests (EVERY source row must exist in target) =====
    try:
        s_digests = {}
        for row in source_conn.execute(
            f"SELECT {pk_column}, {', '.join(digest_columns)} "
            f"FROM {source_table}"
        ):
            s_digests[str(row[0])] = _digest(list(row[1:]))
    except sqlite3.OperationalError as exc:
        report["status"] = "error"
        report["errors"].append(f"source_digest_error: {exc}")
        return report

    mismatches = []
    missing_in_target = []

    for pk, s_digest in s_digests.items():
        try:
            row = target_conn.execute(
                f"SELECT {', '.join(digest_columns)} "
                f"FROM {target_table} WHERE {pk_column} = ?",
                (pk,),
            ).fetchone()
        except sqlite3.OperationalError as exc:
            report["status"] = "error"
            report["errors"].append(f"target_digest_error: {exc}")
            return report

        if row is None:
            # ✅ Missing target row = failure, NOT skip
            missing_in_target.append(pk)
            continue

        if _digest(list(row)) != s_digest:
            mismatches.append(pk)

    report["content_digest"] = {
        "checked": len(s_digests),
        "mismatches": mismatches[:10],
        "mismatch_count": len(mismatches),
        "missing_in_target": missing_in_target[:10],
        "missing_count": len(missing_in_target),
    }

    # ===== Crypto preservation (strict — pre-check columns) =====
    if crypto_columns:
        crypto_ok = 0
        crypto_fail = 0
        crypto_errors = []

        # Pre-check: every crypto column must exist in BOTH tables
        for col in crypto_columns:
            for tbl, conn in [(source_table, source_conn),
                              (target_table, target_conn)]:
                try:
                    conn.execute(
                        f"SELECT {col} FROM {tbl} LIMIT 1"
                    ).fetchone()
                except sqlite3.OperationalError as exc:
                    crypto_errors.append(
                        f"missing_column_{col}_in_{tbl}: {exc}"
                    )
                    report["errors"].append(
                        f"missing_column_{col}_in_{tbl}"
                    )

        # Only proceed if all columns exist
        if not crypto_errors:
            for col in crypto_columns:
                try:
                    s_vals = {
                        str(r[0]): r[1]
                        for r in source_conn.execute(
                            f"SELECT {pk_column}, {col} "
                            f"FROM {source_table} WHERE {col} IS NOT NULL"
                        )
                    }
                except sqlite3.OperationalError as exc:
                    crypto_errors.append(f"source_col_{col}_error: {exc}")
                    report["errors"].append(f"source_col_{col}_error")
                    continue

                for pk, s_val in s_vals.items():
                    try:
                        row = target_conn.execute(
                            f"SELECT {col} FROM {target_table} "
                            f"WHERE {pk_column} = ?", (pk,),
                        ).fetchone()
                    except sqlite3.OperationalError as exc:
                        crypto_errors.append(f"target_col_{col}_error: {exc}")
                        crypto_fail += 1
                        report["errors"].append(f"target_col_{col}_error")
                        continue

                    if row is None:
                        crypto_fail += 1
                    elif row[0] == s_val:
                        crypto_ok += 1
                    else:
                        crypto_fail += 1

        # ===== NULL asymmetry check =====
        # For every source row where crypto col is NULL,
        # target must also be NULL. Otherwise target injected extra data.
        null_asymmetry = 0
        null_asymmetry_pks = []
        if not crypto_errors:
            for col in crypto_columns:
                try:
                    s_null_pks = {
                        str(r[0]) for r in source_conn.execute(
                            f"SELECT {pk_column} FROM {source_table} "
                            f"WHERE {col} IS NULL"
                        )
                    }
                    for pk in s_null_pks:
                        row = target_conn.execute(
                            f"SELECT {col} FROM {target_table} "
                            f"WHERE {pk_column} = ?", (pk,),
                        ).fetchone()
                        if row is None:
                            continue
                        if row[0] is not None:
                            null_asymmetry += 1
                            if len(null_asymmetry_pks) < 10:
                                null_asymmetry_pks.append(pk)
                except sqlite3.OperationalError as exc:
                    crypto_errors.append(
                        f"null_check_{col}_error: {exc}"
                    )
                    report["errors"].append(f"null_check_{col}_error")

        report["crypto_check"] = {
            "columns": crypto_columns,
            "preserved": crypto_ok,
            "failed": crypto_fail,
            "errors": crypto_errors,
            "null_asymmetry": null_asymmetry,
            "null_asymmetry_pks": null_asymmetry_pks,
        }

    # ===== Overall status (FAIL-CLOSED) =====
    issues = 0
    if not report["row_counts"].get("match", False):
        issues += 1
    if not report["pk_comparison"].get("all_present", False):
        issues += 1
    if report["content_digest"].get("mismatch_count", 0) > 0:
        issues += 1
    if report["content_digest"].get("missing_count", 0) > 0:
        issues += 1
    if report.get("crypto_check", {}).get("failed", 0) > 0:
        issues += 1
    if report.get("crypto_check", {}).get("null_asymmetry", 0) > 0:
        issues += 1
    if report["errors"]:
        issues += 1

    if report["errors"]:
        report["status"] = "error"
    elif issues == 0:
        report["status"] = "ok"
    else:
        report["status"] = "issues_found"

    report["total_issues"] = issues
    return report


def format_report(report):
    lines = [
        "=" * 60,
        f"  VERIFY: {report['source_table']} → {report['target_table']}",
        "=" * 60,
        f"  Status: {report['status'].upper()}", "",
    ]
    rc = report.get("row_counts", {})
    lines.append(f"  Row counts: source={rc.get('source', 0)}, "
                 f"target={rc.get('target', 0)}, "
                 f"match={rc.get('match', False)}")
    pkc = report.get("pk_comparison", {})
    lines.append(f"  PKs: source={pkc.get('source_count', 0)}, "
                 f"target={pkc.get('target_count', 0)}, "
                 f"missing={pkc.get('missing_count', 0)}, "
                 f"extra={pkc.get('extra_count', 0)}")
    cd = report.get("content_digest", {})
    lines.append(f"  Content: checked={cd.get('checked', 0)}, "
                 f"mismatches={cd.get('mismatch_count', 0)}, "
                 f"missing={cd.get('missing_count', 0)}")
    cc = report.get("crypto_check", {})
    if cc:
        lines.append(f"  Crypto: preserved={cc.get('preserved', 0)}, "
                     f"failed={cc.get('failed', 0)}")
    if report.get("errors"):
        lines.append(f"  Errors: {report['errors'][:3]}")
    lines.append(f"  Total issues: {report.get('total_issues', 0)}")
    lines.append("=" * 60)
    return "\n".join(lines)


# =========================================================
# SELF-TEST — 6 CASES
# =========================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  MIGRATION VERIFIER — STRICT SELF TEST")
    print("=" * 60)
    print()

    def fresh_pair():
        src = sqlite3.connect(":memory:")
        dst = sqlite3.connect(":memory:")
        for c in (src, dst):
            c.execute("""
                CREATE TABLE decisions (
                    decision_id TEXT PRIMARY KEY, assessment TEXT,
                    severity TEXT, confidence REAL, evidence_hash TEXT
                )
            """)
        rows = [
            ("d1", "possible_smoke", "high", 0.75, "h1" * 20),
            ("d2", "normal", "info", 0.10, "h2" * 20),
            ("d3", "corroborated_event", "critical", 0.92, "h3" * 20),
        ]
        for r in rows:
            src.execute("INSERT INTO decisions VALUES (?, ?, ?, ?, ?)", r)
            dst.execute("INSERT INTO decisions VALUES (?, ?, ?, ?, ?)", r)
        src.commit()
        dst.commit()
        return src, dst

    def check(report, expected_status, label):
        got = report["status"]
        ok = got == expected_status
        icon = "✅" if ok else "❌"
        print(f"{icon} {label}: status={got} (expected={expected_status})")
        return ok

    passed = 0
    total = 0

    # Case 1: Perfect match → ok
    src, dst = fresh_pair()
    r = verify_table(src, dst, "decisions", "decisions", "decision_id",
                     ["assessment", "severity", "confidence"],
                     ["evidence_hash"])
    total += 1
    if check(r, "ok", "Case 1 (perfect match)"):
        passed += 1

    # Case 2: Tampered → issues_found
    src, dst = fresh_pair()
    dst.execute("UPDATE decisions SET assessment='tampered' WHERE decision_id='d2'")
    dst.commit()
    r = verify_table(src, dst, "decisions", "decisions", "decision_id",
                     ["assessment", "severity", "confidence"],
                     ["evidence_hash"])
    total += 1
    if check(r, "issues_found", "Case 2 (tampered)"):
        passed += 1

    # Case 3: Missing row → issues_found
    src, dst = fresh_pair()
    dst.execute("DELETE FROM decisions WHERE decision_id='d3'")
    dst.commit()
    r = verify_table(src, dst, "decisions", "decisions", "decision_id",
                     ["assessment", "severity", "confidence"])
    total += 1
    if check(r, "issues_found", "Case 3 (missing row)"):
        passed += 1

    # Case 4: Extra target row → issues_found (STRICT!)
    src, dst = fresh_pair()
    dst.execute("INSERT INTO decisions VALUES ('extra', 'x', 'y', 0.0, 'zh')")
    dst.commit()
    r = verify_table(src, dst, "decisions", "decisions", "decision_id",
                     ["assessment", "severity", "confidence"])
    total += 1
    if check(r, "issues_found", "Case 4 (extra target row)"):
        passed += 1

    # Case 5: Missing crypto column → error
    src, dst = fresh_pair()
    dst.execute("ALTER TABLE decisions DROP COLUMN evidence_hash")
    dst.commit()
    r = verify_table(src, dst, "decisions", "decisions", "decision_id",
                     ["assessment", "severity", "confidence"],
                     ["evidence_hash"])
    total += 1
    if check(r, "error", "Case 5 (missing crypto column)"):
        passed += 1

    # Case 6: Missing source table → error
    src, dst = fresh_pair()
    r = verify_table(src, dst, "nonexistent", "decisions", "decision_id",
                     ["assessment"])
    total += 1
    if check(r, "error", "Case 6 (missing source table)"):
        passed += 1

    # Case 7: NULL asymmetry (target injected extra crypto value)
    src, dst = fresh_pair()
    src.execute("UPDATE decisions SET evidence_hash=NULL WHERE decision_id='d1'")
    src.commit()
    dst.execute("UPDATE decisions SET evidence_hash='injected' WHERE decision_id='d1'")
    dst.commit()
    r = verify_table(src, dst, "decisions", "decisions", "decision_id",
                     ["assessment", "severity", "confidence"],
                     ["evidence_hash"])
    total += 1
    if check(r, "issues_found", "Case 7 (NULL asymmetry)"):
        passed += 1

    print()
    print(f"📊 Passed: {passed}/{total}")

    if passed == total:
        print("🎉 MIGRATION VERIFIER STRICT — READY")
    else:
        print("❌ SOME TESTS FAILED")
