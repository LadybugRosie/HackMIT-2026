from typing import List

from fastapi import APIRouter, Depends, HTTPException

from ..db import Db
from ..deps import class_member_or_404, class_teacher_or_404, current_user, get_db, require_role
from ..ids import new_class_code, new_id, now_ms
from ..schemas import ClassCreate, ClassOut, JoinRequest
from ..views import assignment_out, class_out

router = APIRouter(prefix="/api/classes", tags=["classes"])


def _unique_code(db: Db) -> str:
    for _ in range(50):
        code = new_class_code()
        if db.one("SELECT 1 FROM classes WHERE class_code = ?", (code,)) is None:
            return code
    raise HTTPException(500, "could not allocate a class code")


@router.post("", response_model=ClassOut, status_code=201)
def create_class(payload: ClassCreate, db: Db = Depends(get_db), user: dict = Depends(require_role("teacher"))) -> ClassOut:
    class_id, now, code = new_id(), now_ms(), _unique_code(db)
    with db.tx() as conn:
        conn.execute("INSERT INTO classes (class_id, name, class_code, teacher_id, created_ms) VALUES (?,?,?,?,?)",
                     (class_id, payload.name.strip(), code, user["user_id"], now))
        conn.execute("INSERT INTO class_members (class_id, user_id, role, joined_ms) VALUES (?,?,?,?)",
                     (class_id, user["user_id"], "teacher", now))
    return class_out(db, db.one("SELECT * FROM classes WHERE class_id = ?", (class_id,)), True)


@router.get("", response_model=List[ClassOut])
def list_classes(db: Db = Depends(get_db), user: dict = Depends(current_user)) -> List[ClassOut]:
    if user["role"] == "teacher":
        rows = db.all("SELECT * FROM classes WHERE teacher_id = ? ORDER BY created_ms DESC", (user["user_id"],))
    else:
        rows = db.all("SELECT c.* FROM classes c JOIN class_members m ON m.class_id = c.class_id "
                      "WHERE m.user_id = ? ORDER BY m.joined_ms DESC", (user["user_id"],))
    return [class_out(db, r, user["role"] == "teacher") for r in rows]


@router.get("/{class_id}")
def get_class(class_id: str, db: Db = Depends(get_db), user: dict = Depends(current_user)) -> dict:
    if user["role"] == "teacher":
        class_teacher_or_404(db, class_id, user)
        assignments = db.all(
            "SELECT a.*, c.name AS class_name, c.teacher_id FROM assignments a JOIN classes c ON c.class_id = a.class_id "
            "WHERE a.class_id = ? ORDER BY COALESCE(a.due_ms, 9e15), a.created_ms", (class_id,))
        roster = db.all(
            "SELECT u.user_id, u.name, u.email, m.joined_ms FROM class_members m JOIN users u ON u.user_id = m.user_id "
            "WHERE m.class_id = ? AND m.role = 'student' ORDER BY u.name", (class_id,))
        klass = db.one("SELECT * FROM classes WHERE class_id = ?", (class_id,))
        return {"class": class_out(db, klass, True), "assignments": [assignment_out(db, a, user) for a in assignments],
                "roster": [dict(r) for r in roster]}

    klass = class_member_or_404(db, class_id, user)
    assignments = db.all(
        "SELECT a.*, c.name AS class_name, c.teacher_id FROM assignments a JOIN classes c ON c.class_id = a.class_id "
        "WHERE a.class_id = ? AND a.published = 1 ORDER BY COALESCE(a.due_ms, 9e15), a.created_ms", (class_id,))
    return {"class": class_out(db, klass, False), "assignments": [assignment_out(db, a, user) for a in assignments]}


@router.post("/join", response_model=ClassOut)
def join_class(payload: JoinRequest, db: Db = Depends(get_db), user: dict = Depends(require_role("student"))) -> ClassOut:
    row = db.one("SELECT * FROM classes WHERE class_code = ?", (payload.class_code,))
    if row is None:
        raise HTTPException(404, "invalid class code")
    db.exec("INSERT OR IGNORE INTO class_members (class_id, user_id, role, joined_ms) VALUES (?,?,?,?)",
            (row["class_id"], user["user_id"], "student", now_ms()))
    return class_out(db, row, False)


@router.post("/{class_id}/regenerate-code")
def regenerate_code(class_id: str, db: Db = Depends(get_db), user: dict = Depends(require_role("teacher"))) -> dict:
    class_teacher_or_404(db, class_id, user)
    code = _unique_code(db)
    db.exec("UPDATE classes SET class_code = ? WHERE class_id = ?", (code, class_id))
    return {"class_code": code}
