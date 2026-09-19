"""Row -> response helpers shared by the routers."""
from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict, Optional

from .db import Db
from .schemas import AssignmentOut, AssignmentSettings, ClassOut, SubmissionOut


def loads(text: Optional[str], default: Any = None) -> Any:
    if not text:
        return default
    try:
        return json.loads(text)
    except ValueError:
        return default


def class_out(db: Db, row: sqlite3.Row | dict, include_code: bool) -> ClassOut:
    teacher = db.one("SELECT name FROM users WHERE user_id = ?", (row["teacher_id"],))
    students = db.one("SELECT COUNT(*) AS c FROM class_members WHERE class_id = ? AND role = 'student'", (row["class_id"],))
    assignments = db.one("SELECT COUNT(*) AS c FROM assignments WHERE class_id = ?", (row["class_id"],))
    return ClassOut(
        class_id=row["class_id"], name=row["name"], class_code=row["class_code"] if include_code else None,
        teacher_id=row["teacher_id"], teacher_name=teacher["name"] if teacher else "",
        student_count=students["c"], assignment_count=assignments["c"], created_ms=row["created_ms"],
    )


def assignment_row(db: Db, assignment_id: str) -> Optional[sqlite3.Row]:
    return db.one(
        "SELECT a.*, c.name AS class_name, c.teacher_id FROM assignments a "
        "JOIN classes c ON c.class_id = a.class_id WHERE a.assignment_id = ?", (assignment_id,))


def assignment_out(db: Db, row: sqlite3.Row | dict, user: dict) -> AssignmentOut:
    keys = row.keys() if isinstance(row, sqlite3.Row) else row
    class_name = row["class_name"] if "class_name" in keys else None
    out = AssignmentOut(
        assignment_id=row["assignment_id"], class_id=row["class_id"], class_name=class_name,
        title=row["title"], instructions=row["instructions"], due_ms=row["due_ms"], points=row["points"],
        published=bool(row["published"]), settings=AssignmentSettings(**loads(row["settings_json"], {})),
        created_ms=row["created_ms"],
    )
    if user["role"] == "student":
        sub = db.one("SELECT submission_id, status, grade, submitted_ms FROM submissions WHERE assignment_id = ? AND student_id = ?",
                     (row["assignment_id"], user["user_id"]))
        out.my_submission = dict(sub) if sub else None
    else:
        counts = {"draft": 0, "submitted": 0, "graded": 0, "returned": 0}
        for r in db.all("SELECT status, COUNT(*) AS c FROM submissions WHERE assignment_id = ? GROUP BY status", (row["assignment_id"],)):
            counts[r["status"]] = r["c"]
        out.submission_counts = counts
    return out


def submission_metrics(row: sqlite3.Row | dict) -> Dict[str, Any]:
    """The chips a teacher sees in the submissions table; all None until the analyses ran."""
    integ = loads(row["integrity_json"])
    sim = loads(row["similarity_json"])
    fc = loads(row["factcheck_json"])
    return {
        "trust": integ["scores"]["trust"] if integ else None,
        "verdict": integ["verdict"] if integ else None,
        "external_pct": round(integ["mix"]["external"] * 100) if integ else None,
        "assurance_level": (loads(row["certificate_json"]) or {}).get("assurance_level"),
        "similarity_max": sim.get("max_score") if sim else None,
        "similarity_status": row["similarity_status"],
        "factcheck_summary": fc.get("summary") if fc else None,
        "factcheck_status": row["factcheck_status"],
    }


def submission_out(db: Db, row: sqlite3.Row | dict, user: dict, with_assignment: bool = True) -> SubmissionOut:
    student = db.one("SELECT name FROM users WHERE user_id = ?", (row["student_id"],))
    out = SubmissionOut(
        submission_id=row["submission_id"], assignment_id=row["assignment_id"], student_id=row["student_id"],
        student_name=student["name"] if student else None, content=row["content"], status=row["status"],
        ledger_session_id=row["ledger_session_id"], certificate=loads(row["certificate_json"]),
        integrity=loads(row["integrity_json"]), factcheck_status=row["factcheck_status"],
        factcheck=loads(row["factcheck_json"]), similarity_status=row["similarity_status"],
        similarity=loads(row["similarity_json"]), submitted_ms=row["submitted_ms"], grade=row["grade"],
        feedback=row["feedback"], graded_ms=row["graded_ms"], updated_ms=row["updated_ms"],
    )
    if with_assignment:
        a = assignment_row(db, row["assignment_id"])
        if a is not None:
            out.assignment = assignment_out(db, a, user)
    return out
