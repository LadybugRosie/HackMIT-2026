from fastapi import APIRouter, Depends

from ..db import Db
from ..deps import current_user, get_db
from ..views import class_out

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
def dashboard(db: Db = Depends(get_db), user: dict = Depends(current_user)) -> dict:
    uid = user["user_id"]
    if user["role"] == "student":
        classes = db.all("SELECT c.* FROM classes c JOIN class_members m ON m.class_id = c.class_id "
                         "WHERE m.user_id = ? ORDER BY m.joined_ms DESC", (uid,))
        due = db.all(
            "SELECT a.assignment_id, a.title, a.due_ms, a.points, c.class_id, c.name AS class_name, s.status, s.submission_id "
            "FROM assignments a JOIN classes c ON c.class_id = a.class_id "
            "JOIN class_members m ON m.class_id = a.class_id AND m.user_id = ? "
            "LEFT JOIN submissions s ON s.assignment_id = a.assignment_id AND s.student_id = ? "
            "WHERE a.published = 1 AND (s.status IS NULL OR s.status = 'draft') "
            "ORDER BY COALESCE(a.due_ms, 9e15), a.created_ms LIMIT 10", (uid, uid))
        return {
            "role": "student",
            "classes": [class_out(db, c, False) for c in classes],
            "due_soon": [dict(r) | {"status": r["status"] or "not_started"} for r in due],
        }

    classes = db.all("SELECT * FROM classes WHERE teacher_id = ? ORDER BY created_ms DESC", (uid,))
    tiles = {
        "classes": len(classes),
        "students": db.one("SELECT COUNT(DISTINCT m.user_id) AS c FROM class_members m JOIN classes c ON c.class_id = m.class_id "
                           "WHERE c.teacher_id = ? AND m.role = 'student'", (uid,))["c"],
        "assignments": db.one("SELECT COUNT(*) AS c FROM assignments a JOIN classes c ON c.class_id = a.class_id "
                              "WHERE c.teacher_id = ?", (uid,))["c"],
        "to_grade": db.one("SELECT COUNT(*) AS c FROM submissions s JOIN assignments a ON a.assignment_id = s.assignment_id "
                           "JOIN classes c ON c.class_id = a.class_id WHERE c.teacher_id = ? AND s.status = 'submitted'", (uid,))["c"],
    }
    recent = db.all(
        "SELECT s.submission_id, s.status, s.submitted_ms, u.name AS student_name, a.title, a.assignment_id, c.name AS class_name "
        "FROM submissions s JOIN assignments a ON a.assignment_id = s.assignment_id JOIN classes c ON c.class_id = a.class_id "
        "JOIN users u ON u.user_id = s.student_id WHERE c.teacher_id = ? AND s.status != 'draft' "
        "ORDER BY s.submitted_ms DESC LIMIT 10", (uid,))
    return {"role": "teacher", "tiles": tiles, "classes": [class_out(db, c, True) for c in classes],
            "recent": [dict(r) for r in recent]}
