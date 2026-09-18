"""
Ember Lessons System
Ember က သူ့အမှားတွေကနေ သင်ယူခြင်း

Philosophy: "မှတ်တမ်းမရှိရင် သက်သေမရှိဘူး"
→ "အမှားမှတ်တမ်းမရှိရင် တိုးတက်မှုမရှိဘူး"
"""

import sqlite3
import os
from datetime import datetime


DB_PATH = os.path.join(os.path.dirname(__file__), "lessons.db")


def init_lessons_db():
    """Lessons Database ဖန်တီးခြင်း"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS lessons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lesson_type TEXT NOT NULL,
            trigger_pattern TEXT,
            mistake TEXT NOT NULL,
            root_cause TEXT,
            fix TEXT NOT NULL,
            prevention TEXT,
            severity TEXT DEFAULT 'medium',
            learned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            times_encountered INTEGER DEFAULT 1
        )
    """)
    conn.commit()
    conn.close()
    return DB_PATH


def record_lesson(lesson_type, mistake, fix, root_cause=None,
                  prevention=None, trigger_pattern=None, severity="medium"):
    """
    သင်ခန်းစာ တစ်ခုကို မှတ်တမ်းတင်ခြင်း
    
    Args:
        lesson_type: "syntax_error", "logic_error", "runtime_error", "process_error"
        mistake: ဘာမှားခဲ့လဲ
        fix: ဘယ်လို ပြင်ခဲ့လဲ
        root_cause: အမြစ်အကြောင်းရင်း
        prevention: နောက်တစ်ခါ ဘယ်လို ရှောင်မလဲ
        trigger_pattern: ဘယ် pattern မြင်ရင် သတိထားမလဲ
        severity: "low", "medium", "high", "critical"
    """
    init_lessons_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # တူတူ ရှိပြီးသားလား စစ်ဆေးခြင်း
    c.execute("""
        SELECT id, times_encountered FROM lessons
        WHERE mistake = ? AND fix = ?
    """, (mistake, fix))
    existing = c.fetchone()
    
    if existing:
        # ရှိပြီးသားဆိုရင် count ကို တိုးခြင်း
        c.execute("""
            UPDATE lessons
            SET times_encountered = times_encountered + 1
            WHERE id = ?
        """, (existing[0],))
        lesson_id = existing[0]
        print(f"📚 Lesson #{lesson_id} reinforced (encountered {existing[1] + 1} times)")
    else:
        # အသစ် ထည့်ခြင်း
        c.execute("""
            INSERT INTO lessons
            (lesson_type, trigger_pattern, mistake, root_cause, fix, prevention, severity)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            lesson_type, trigger_pattern, mistake,
            root_cause, fix, prevention, severity
        ))
        lesson_id = c.lastrowid
        print(f"📚 Lesson #{lesson_id} recorded")
    
    conn.commit()
    conn.close()
    return lesson_id


def get_lessons(lesson_type=None, severity=None, limit=20):
    """Lessons တွေကို ရယူခြင်း"""
    init_lessons_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    query = "SELECT * FROM lessons WHERE 1=1"
    params = []
    
    if lesson_type:
        query += " AND lesson_type = ?"
        params.append(lesson_type)
    
    if severity:
        query += " AND severity = ?"
        params.append(severity)
    
    query += " ORDER BY times_encountered DESC, learned_at DESC LIMIT ?"
    params.append(limit)
    
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    
    return [
        {
            "id": r[0],
            "type": r[1],
            "trigger_pattern": r[2],
            "mistake": r[3],
            "root_cause": r[4],
            "fix": r[5],
            "prevention": r[6],
            "severity": r[7],
            "learned_at": r[8],
            "times_encountered": r[9]
        }
        for r in rows
    ]


def check_for_pattern(code_or_command: str) -> list:
    """
    Code / Command ကို ကြည့်ပြီး ဖြစ်နိုင်တဲ့ ပြဿနာတွေကို သတိပေးခြင်း
    (Ember က Command run ခင်မှာ သုံးနိုင်တယ်)
    """
    init_lessons_db()
    warnings = []
    
    lessons = get_lessons(limit=100)
    for lesson in lessons:
        pattern = lesson.get("trigger_pattern")
        if not pattern:
            continue
        
        # Simple substring matching
        if pattern.lower() in code_or_command.lower():
            warnings.append({
                "lesson_id": lesson["id"],
                "pattern": pattern,
                "warning": lesson["mistake"],
                "fix": lesson["fix"],
                "severity": lesson["severity"]
            })
    
    return warnings


def summary() -> str:
    """Lessons တွေရဲ့ Summary"""
    init_lessons_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM lessons")
    total = c.fetchone()[0]
    
    c.execute("""
        SELECT lesson_type, COUNT(*) 
        FROM lessons GROUP BY lesson_type
    """)
    by_type = c.fetchall()
    
    c.execute("""
        SELECT SUM(times_encountered) FROM lessons
    """)
    total_encounters = c.fetchone()[0] or 0
    
    conn.close()
    
    lines = [
        "=" * 60,
        "  📚 Ember Lessons Summary",
        "=" * 60,
        f"",
        f"  Total Lessons:      {total}",
        f"  Total Encounters:   {total_encounters}",
        f"",
        f"  By Type:",
    ]
    
    for lesson_type, count in by_type:
        lines.append(f"    • {lesson_type}: {count}")
    
    lines.append("")
    lines.append("=" * 60)
    
    return "\n".join(lines)


# =========================================================
# SEED: ဒီနေ့ ဖြစ်ခဲ့တဲ့ အမှားတွေကို မှတ်တမ်းတင်ခြင်း
# =========================================================

def seed_initial_lessons():
    """ပထမဆုံး သင်ခန်းစာတွေ ထည့်ခြင်း"""
    
    # Lesson 1: Python Reserved Keyword
    record_lesson(
        lesson_type="syntax_error",
        trigger_pattern="from=context.get",
        mistake="Python Reserved Keyword 'from' ကို keyword argument အနေနဲ့ သုံးမိ",
        root_cause="'from' ဟာ Python ရဲ့ reserved keyword ဖြစ်တဲ့အတွက် keyword argument အနေနဲ့ သုံးလို့ မရ",
        fix="'from' ကို 'from_val' လို့ ပြောင်းပြီး template ထဲက placeholder ကိုပါ update လုပ်ပါ",
        prevention="Variable / Argument နာမည် ပေးတိုင်း Python Reserved Keywords စာရင်းနဲ့ တိုက်စစ်ပါ",
        severity="high"
    )
    
    # Lesson 2: Copy/Paste Duplicate Lines
    record_lesson(
        lesson_type="process_error",
        trigger_pattern="duplicate_lines",
        mistake="Termux မှာ Code ရှည်တွေ copy/paste လုပ်တဲ့အခါ လိုင်းတွေ ထပ်သွားပြီး syntax error တက်",
        root_cause="Termux ရဲ့ Terminal က multi-line paste ကို တစ်ခါတစ်ရံ မှားယွင်းစွာ handle လုပ်တယ်",
        fix="Script ဖိုင်ကို 'cat > file << ENDOFFILE' pattern နဲ့ တစ်ခါတည်း ရေးပါ၊ 'EOF' အစား 'ENDOFFILE' ကို သုံးပါ",
        prevention="Code ရေးပြီးတိုင်း 'python3 -m py_compile file.py' နဲ့ syntax စစ်ပါ",
        severity="high"
    )
    
    # Lesson 3: Heredoc Delimiter Collision
    record_lesson(
        lesson_type="process_error",
        trigger_pattern="<< 'EOF'",
        mistake="File content ထဲမှာ 'EOF' ပါနေတဲ့အခါ heredoc က စောစော ပိတ်သွားတယ်",
        root_cause="Heredoc delimiter က unique မဖြစ်လို့ content ထဲက 'EOF' နဲ့ ရောသွားတယ်",
        fix="Delimiter ကို 'ENDOFFILE' လို unique စာလုံးအဖြစ် ပြောင်းပါ",
        prevention="Heredoc သုံးတိုင်း 'EOF' အစား unique delimiter သုံးပါ",
        severity="medium"
    )
    
    print("✅ Seed lessons recorded.")


if __name__ == "__main__":
    print("=" * 60)
    print("  Testing Lessons System")
    print("=" * 60)
    print()
    
    init_lessons_db()
    seed_initial_lessons()
    
    print()
    print(summary())
    
    print("\n🔍 Testing pattern check:")
    test_code = """
    message = rule["template"].format(
        from=context.get("from", "?"),
        to=context.get("to", "?")
    )
    """
    warnings = check_for_pattern(test_code)
    
    if warnings:
        for w in warnings:
            print(f"   ⚠️  [{w['severity'].upper()}] Lesson #{w['lesson_id']}")
            print(f"      Mistake: {w['warning']}")
            print(f"      Fix: {w['fix']}")
    else:
        print("   ✅ No issues detected.")
    
    print("\n✅ Lessons test complete.")
