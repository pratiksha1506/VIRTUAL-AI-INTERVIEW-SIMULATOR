import sqlite3
import hashlib
import os
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from .config import DB_PATH

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password: str, salt: Optional[str] = None) -> str:
    if not salt:
        salt = os.urandom(16).hex()
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
    return f"{salt}${dk.hex()}"

def verify_password(password: str, hashed_str: str) -> bool:
    if not hashed_str or "$" not in hashed_str:
        return False
    salt, dk_hex = hashed_str.split("$", 1)
    test_dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
    return test_dk.hex() == dk_hex

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Users
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'job_seeker', -- 'job_seeker' or 'admin'
        created_at TEXT NOT NULL
    )
    """)

    # Interviews
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS interviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        candidate_id INTEGER NOT NULL,
        admin_id INTEGER,
        job_role TEXT NOT NULL,
        experience_level TEXT NOT NULL DEFAULT 'Mid-Level',
        interview_type TEXT NOT NULL DEFAULT 'Technical',
        difficulty TEXT NOT NULL DEFAULT 'Medium',
        question_count INTEGER NOT NULL DEFAULT 5,
        duration_minutes INTEGER NOT NULL DEFAULT 15,
        camera_enabled INTEGER NOT NULL DEFAULT 0,
        resume_text TEXT,
        scheduled_date TEXT,
        scheduled_time TEXT,
        status TEXT NOT NULL DEFAULT 'in_progress', -- 'scheduled', 'in_progress', 'completed', 'cancelled'
        started_at TEXT,
        completed_at TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (candidate_id) REFERENCES users(id)
    )
    """)

    # Questions asked during the interview
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        interview_id INTEGER NOT NULL,
        sequence_num INTEGER NOT NULL,
        question_text TEXT NOT NULL,
        question_type TEXT NOT NULL,
        topic TEXT,
        difficulty TEXT NOT NULL,
        expected_keywords TEXT,
        context_notes TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (interview_id) REFERENCES interviews(id)
    )
    """)

    # Candidate responses per question
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        interview_id INTEGER NOT NULL,
        question_id INTEGER NOT NULL,
        transcript TEXT NOT NULL,
        duration_seconds REAL NOT NULL DEFAULT 0,
        content_score INTEGER,
        technical_score INTEGER,
        communication_score INTEGER,
        problem_solving_score INTEGER,
        facial_score INTEGER,
        overall_score INTEGER,
        feedback_json TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (interview_id) REFERENCES interviews(id),
        FOREIGN KEY (question_id) REFERENCES questions(id)
    )
    """)

    # Final comprehensive report
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        interview_id INTEGER UNIQUE NOT NULL,
        overall_score INTEGER NOT NULL,
        content_score INTEGER NOT NULL,
        technical_score INTEGER NOT NULL,
        communication_score INTEGER NOT NULL,
        problem_solving_score INTEGER NOT NULL,
        scoring_engine TEXT NOT NULL,
        strengths_json TEXT,
        weaknesses_json TEXT,
        recommendations_json TEXT,
        practice_exercises_json TEXT,
        model_answers_json TEXT,
        presentation_obs_json TEXT,
        overall_feedback TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (interview_id) REFERENCES interviews(id)
    )
    """)

    # Settings table for persistent admin configuration
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """)

    conn.commit()

    # Seed default question count if not present
    cursor.execute("SELECT key FROM settings WHERE key = 'default_question_count'")
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO settings (key, value, updated_at) VALUES ('default_question_count', '10', ?)",
            (datetime.utcnow().isoformat(),)
        )
        conn.commit()

    # Seed demo admin if not present
    cursor.execute("SELECT id FROM users WHERE email = 'admin@demo.com'")
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO users (name, email, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
            ("Demo Admin", "admin@demo.com", hash_password("admin123"), "admin", datetime.utcnow().isoformat())
        )
        conn.commit()

    conn.close()

# User helpers
def create_user(name: str, email: str, password: str, role: str = "job_seeker") -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    created_at = datetime.utcnow().isoformat()
    try:
        cursor.execute(
            "INSERT INTO users (name, email, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
            (name.strip(), email.lower().strip(), hash_password(password), role, created_at)
        )
        conn.commit()
        user_id = cursor.lastrowid
        return {"id": user_id, "name": name.strip(), "email": email.lower().strip(), "role": role, "createdAt": created_at}
    finally:
        conn.close()

def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email.lower().strip(),))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, email, role, created_at FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_candidates() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT u.id, u.name, u.email, u.role, u.created_at,
           COUNT(i.id) as interview_count,
           SUM(CASE WHEN i.status = 'completed' THEN 1 ELSE 0 END) as completed_count
    FROM users u
    LEFT JOIN interviews i ON i.candidate_id = u.id
    WHERE u.role = 'job_seeker'
    GROUP BY u.id
    ORDER BY u.id DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    res = []
    for r in rows:
        d = dict(r)
        d["account_status"] = "Active"
        res.append(d)
    return res

def clear_all_interview_history() -> Dict[str, int]:
    """Clears all historical interview attempts, questions, responses, and reports."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM reports")
    del_reports = cursor.rowcount
    cursor.execute("DELETE FROM responses")
    del_responses = cursor.rowcount
    cursor.execute("DELETE FROM questions")
    del_questions = cursor.rowcount
    cursor.execute("DELETE FROM interviews")
    del_interviews = cursor.rowcount
    conn.commit()
    conn.close()
    return {
        "interviews_cleared": del_interviews,
        "questions_cleared": del_questions,
        "responses_cleared": del_responses,
        "reports_cleared": del_reports
    }

def delete_user_and_data(user_id: int) -> bool:
    """Safely cascades and deletes all associated records for a user."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM interviews WHERE candidate_id = ?", (user_id,))
    int_ids = [r[0] for r in cursor.fetchall()]
    if int_ids:
        placeholders = ','.join('?' for _ in int_ids)
        cursor.execute(f"DELETE FROM reports WHERE interview_id IN ({placeholders})", int_ids)
        cursor.execute(f"DELETE FROM responses WHERE interview_id IN ({placeholders})", int_ids)
        cursor.execute(f"DELETE FROM questions WHERE interview_id IN ({placeholders})", int_ids)
        cursor.execute(f"DELETE FROM interviews WHERE id IN ({placeholders})", int_ids)
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return True

# Interview helpers
def create_interview(candidate_id: int, job_role: str, experience_level: str, interview_type: str,
                     difficulty: str, question_count: int, duration_minutes: int, camera_enabled: bool,
                     resume_text: Optional[str] = None, status: str = "in_progress",
                     scheduled_date: Optional[str] = None, scheduled_time: Optional[str] = None,
                     admin_id: Optional[int] = None) -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()

    # Validate that candidate exists and is a registered job seeker
    cursor.execute("SELECT id, role FROM users WHERE id = ?", (candidate_id,))
    cand = cursor.fetchone()
    if not cand or cand["role"] != "job_seeker":
        conn.close()
        raise ValueError(f"Cannot create interview: candidate ID {candidate_id} does not exist or is not a registered job seeker.")

    now = datetime.utcnow().isoformat()
    started_at = now if status == "in_progress" else None

    cursor.execute("""
    INSERT INTO interviews (candidate_id, admin_id, job_role, experience_level, interview_type,
                            difficulty, question_count, duration_minutes, camera_enabled,
                            resume_text, scheduled_date, scheduled_time, status, started_at, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (candidate_id, admin_id, job_role, experience_level, interview_type,
          difficulty, question_count, duration_minutes, 1 if camera_enabled else 0,
          resume_text, scheduled_date, scheduled_time, status, started_at, now))
    conn.commit()
    interview_id = cursor.lastrowid
    conn.close()
    return get_interview_by_id(interview_id)

def get_interview_by_id(interview_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM interviews WHERE id = ?", (interview_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["camera_enabled"] = bool(d["camera_enabled"])
    return d

def update_interview_status(interview_id: int, status: str, completed_at: Optional[str] = None, started_at: Optional[str] = None):
    conn = get_connection()
    cursor = conn.cursor()
    if completed_at:
        cursor.execute("UPDATE interviews SET status = ?, completed_at = ? WHERE id = ?", (status, completed_at, interview_id))
    elif status == "in_progress":
        now = started_at or datetime.utcnow().isoformat()
        cursor.execute("UPDATE interviews SET status = ?, started_at = COALESCE(started_at, ?) WHERE id = ?", (status, now, interview_id))
    else:
        cursor.execute("UPDATE interviews SET status = ? WHERE id = ?", (status, interview_id))
    conn.commit()
    conn.close()

def get_interviews_for_candidate(candidate_id: int) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM interviews WHERE candidate_id = ? ORDER BY id DESC", (candidate_id,))
    rows = cursor.fetchall()
    conn.close()
    res = []
    for r in rows:
        d = dict(r)
        d["camera_enabled"] = bool(d["camera_enabled"])
        res.append(d)
    return res

def get_all_interviews() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT i.*, u.name as candidate_name, u.email as candidate_email,
           r.overall_score, r.technical_score, r.communication_score,
           r.problem_solving_score, r.content_score, r.scoring_engine,
           r.overall_feedback
    FROM interviews i 
    JOIN users u ON i.candidate_id = u.id 
    LEFT JOIN reports r ON r.interview_id = i.id
    ORDER BY i.id DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    res = []
    for r in rows:
        d = dict(r)
        d["camera_enabled"] = bool(d["camera_enabled"])
        if d.get("overall_score") is not None:
            d["report"] = {
                "overall_score": d["overall_score"],
                "technical_score": d["technical_score"],
                "communication_score": d["communication_score"],
                "problem_solving_score": d["problem_solving_score"],
                "content_score": d["content_score"],
                "scoring_engine": d["scoring_engine"],
                "overall_feedback": d["overall_feedback"]
            }
        else:
            d["report"] = None
        res.append(d)
    return res

def get_interview_audit_detail(interview_id: int) -> Optional[Dict[str, Any]]:
    """Fetches full interview audit details: candidate info, questions, transcripts, scores, and report."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT i.*, u.name as candidate_name, u.email as candidate_email
    FROM interviews i
    JOIN users u ON i.candidate_id = u.id
    WHERE i.id = ?
    """, (interview_id,))
    int_row = cursor.fetchone()
    if not int_row:
        conn.close()
        return None
    interview = dict(int_row)
    interview["camera_enabled"] = bool(interview["camera_enabled"])

    # Questions
    cursor.execute("SELECT * FROM questions WHERE interview_id = ? ORDER BY sequence_num ASC", (interview_id,))
    questions = [dict(q) for q in cursor.fetchall()]

    # Responses
    cursor.execute("""
    SELECT r.*, q.question_text, q.topic, q.difficulty, q.sequence_num
    FROM responses r
    JOIN questions q ON r.question_id = q.id
    WHERE r.interview_id = ?
    ORDER BY q.sequence_num ASC
    """, (interview_id,))
    responses = []
    for r in cursor.fetchall():
        rd = dict(r)
        if rd.get("feedback_json"):
            try:
                rd["feedback"] = json.loads(rd["feedback_json"])
            except Exception:
                rd["feedback"] = rd["feedback_json"]
        responses.append(rd)

    conn.close()

    report = get_report_by_interview_id(interview_id)

    return {
        "interview": interview,
        "questions": questions,
        "responses": responses,
        "report": report
    }

# Question helpers
def add_question(interview_id: int, sequence_num: int, question_text: str, question_type: str,
                 topic: str, difficulty: str, expected_keywords: str = "", context_notes: str = "") -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    cursor.execute("""
    INSERT INTO questions (interview_id, sequence_num, question_text, question_type, topic, difficulty, expected_keywords, context_notes, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (interview_id, sequence_num, question_text, question_type, topic, difficulty, expected_keywords, context_notes, now))
    conn.commit()
    qid = cursor.lastrowid
    conn.close()
    return {
        "id": qid,
        "interview_id": interview_id,
        "sequence_num": sequence_num,
        "question_text": question_text,
        "question_type": question_type,
        "topic": topic,
        "difficulty": difficulty,
        "expected_keywords": expected_keywords,
        "context_notes": context_notes,
    }

def get_questions_for_interview(interview_id: int) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM questions WHERE interview_id = ? ORDER BY sequence_num ASC", (interview_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_question_by_id(question_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM questions WHERE id = ?", (question_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

# Response helpers
def add_response(interview_id: int, question_id: int, transcript: str, duration_seconds: float,
                 content_score: int, technical_score: int, communication_score: int,
                 problem_solving_score: int, facial_score: Optional[int], overall_score: int,
                 feedback: Dict[str, Any]) -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    feedback_str = json.dumps(feedback)
    cursor.execute("""
    INSERT INTO responses (interview_id, question_id, transcript, duration_seconds,
                           content_score, technical_score, communication_score,
                           problem_solving_score, facial_score, overall_score, feedback_json, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (interview_id, question_id, transcript, duration_seconds,
          content_score, technical_score, communication_score, problem_solving_score,
          facial_score, overall_score, feedback_str, now))
    conn.commit()
    rid = cursor.lastrowid
    conn.close()
    return {
        "id": rid,
        "interview_id": interview_id,
        "question_id": question_id,
        "transcript": transcript,
        "duration_seconds": duration_seconds,
        "content_score": content_score,
        "technical_score": technical_score,
        "communication_score": communication_score,
        "problem_solving_score": problem_solving_score,
        "facial_score": facial_score,
        "overall_score": overall_score,
        "feedback": feedback
    }

def get_responses_for_interview(interview_id: int) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT r.*, q.question_text, q.question_type, q.topic, q.difficulty 
    FROM responses r 
    JOIN questions q ON r.question_id = q.id 
    WHERE r.interview_id = ? 
    ORDER BY r.id ASC
    """, (interview_id,))
    rows = cursor.fetchall()
    conn.close()
    res = []
    for r in rows:
        d = dict(r)
        if d.get("feedback_json"):
            try:
                d["feedback"] = json.loads(d["feedback_json"])
            except Exception:
                d["feedback"] = {}
        res.append(d)
    return res

# Report helpers
def save_report(interview_id: int, overall_score: int, content_score: int,
                technical_score: int, communication_score: int, problem_solving_score: int,
                scoring_engine: str, strengths: List[str], weaknesses: List[str],
                recommendations: List[str], practice_exercises: List[str],
                model_answers: List[Dict[str, Any]], presentation_obs: Dict[str, Any],
                overall_feedback: str) -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    cursor.execute("""
    INSERT OR REPLACE INTO reports (interview_id, overall_score, content_score, technical_score,
                                    communication_score, problem_solving_score, scoring_engine,
                                    strengths_json, weaknesses_json, recommendations_json,
                                    practice_exercises_json, model_answers_json, presentation_obs_json,
                                    overall_feedback, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (interview_id, overall_score, content_score, technical_score,
          communication_score, problem_solving_score, scoring_engine,
          json.dumps(strengths), json.dumps(weaknesses), json.dumps(recommendations),
          json.dumps(practice_exercises), json.dumps(model_answers), json.dumps(presentation_obs),
          overall_feedback, now))
    conn.commit()
    conn.close()
    return get_report_by_interview_id(interview_id)

def get_report_by_interview_id(interview_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reports WHERE interview_id = ?", (interview_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["strengths"] = json.loads(d["strengths_json"] or "[]")
    d["weaknesses"] = json.loads(d["weaknesses_json"] or "[]")
    d["recommendations"] = json.loads(d["recommendations_json"] or "[]")
    d["practice_exercises"] = json.loads(d["practice_exercises_json"] or "[]")
    d["model_answers"] = json.loads(d["model_answers_json"] or "[]")
    d["presentation_observations"] = json.loads(d["presentation_obs_json"] or "{}")
    return d

# Settings helpers
def get_setting(key: str, default: str = "") -> str:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row["value"] if row else default

def set_setting(key: str, value: str):
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    cursor.execute("""
    INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)
    ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
    """, (key, str(value), now))
    conn.commit()
    conn.close()

def get_all_settings() -> Dict[str, str]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM settings")
    rows = cursor.fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}

def get_configured_question_count(job_role: Optional[str] = None) -> int:
    if job_role:
        role_key = f"question_count_{job_role.lower().replace(' ', '_')}"
        role_val = get_setting(role_key)
        if role_val and role_val.isdigit():
            cnt = int(role_val)
            if 1 <= cnt <= 50:
                return cnt
    val = get_setting("default_question_count", "10")
    try:
        cnt = int(val)
        return max(1, min(50, cnt))
    except (ValueError, TypeError):
        return 10

# Initialize database schema on load
init_db()
