import json
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from ..db import Db
from ..deps import class_member_or_404, class_teacher_or_404, current_user, get_db, require_role
from ..ids import new_id, now_ms
from ..schemas import AssignmentCreate, AssignmentOut, AssignmentUpdate
from ..views import assignment_out, assignment_row, submission_metrics

router = APIRouter(prefix="/api/assignments", tags=["assignments"])


def _owned_assignment_or_404(db: Db, assignment_id: str, user: dict):
    row = assignment_row(db, assignment_id)
    if row is None or row["teacher_id"] != user["user_id"]:
        raise HTTPException(404, "assignment not found")
    return row


@router.post("", response_model=AssignmentOut, status_code=201)
def create_assignment(payload: AssignmentCreate, db: Db = Depends(get_db), user: dict = Depends(require_role("teacher"))) -> AssignmentOut:
    class_teacher_or_404(db, payload.class_id, user)
    assignment_id = new_id()
    db.exec(
        "INSERT INTO assignments (assignment_id, class_id, title, instructions, due_ms, points, published, settings_json, created_ms) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (assignment_id, payload.class_id, payload.title.strip(), payload.instructions, payload.due_ms, payload.points,
         int(payload.published), json.dumps(payload.settings.model_dump()), now_ms()))
    return assignment_out(db, assignment_row(db, assignment_id), user)


@router.get("/{assignment_id}", response_model=AssignmentOut)
def get_assignment(assignment_id: str, db: Db = Depends(get_db), user: dict = Depends(current_user)) -> AssignmentOut:
    if user["role"] == "teacher":
        return assignment_out(db, _owned_assignment_or_404(db, assignment_id, user), user)
    row = assignment_row(db, assignment_id)
    if row is None:
        raise HTTPException(404, "assignment not found")
    class_member_or_404(db, row["class_id"], user)
    if not row["published"]:
        raise HTTPException(404, "assignment not found")
    return assignment_out(db, row, user)


@router.put("/{assignment_id}", response_model=AssignmentOut)
def update_assignment(assignment_id: str, payload: AssignmentUpdate, db: Db = Depends(get_db),
                      user: dict = Depends(require_role("teacher"))) -> AssignmentOut:
    _owned_assignment_or_404(db, assignment_id, user)
    fields = payload.model_dump(exclude_unset=True)
    if not fields:
        return assignment_out(db, assignment_row(db, assignment_id), user)
    sets, params = [], []
    for key, value in fields.items():
        if key == "settings":
            sets.append("settings_json = ?"); params.append(json.dumps(payload.settings.model_dump()))
        elif key == "published":
            sets.append("published = ?"); params.append(int(value))
        elif key == "title":
            sets.append("title = ?"); params.append(value.strip())
        else:
            sets.append(f"{key} = ?"); params.append(value)
    params.append(assignment_id)
    db.exec(f"UPDATE assignments SET {', '.join(sets)} WHERE assignment_id = ?", params)
    return assignment_out(db, assignment_row(db, assignment_id), user)


@router.get("/{assignment_id}/submissions")
def list_submissions(assignment_id: str, db: Db = Depends(get_db), user: dict = Depends(require_role("teacher"))) -> List[dict]:
    """One row per enrolled student, whether or not they have started."""
    a = _owned_assignment_or_404(db, assignment_id, user)
    rows = db.all(
        "SELECT u.user_id, u.name, u.email, s.* FROM class_members m JOIN users u ON u.user_id = m.user_id "
        "LEFT JOIN submissions s ON s.assignment_id = ? AND s.student_id = u.user_id "
        "WHERE m.class_id = ? AND m.role = 'student' ORDER BY u.name", (assignment_id, a["class_id"]))
    out = []
    for r in rows:
        item = {
            "student": {"user_id": r["user_id"], "name": r["name"], "email": r["email"]},
            "submission_id": r["submission_id"], "status": r["status"] or "not_started",
            "submitted_ms": r["submitted_ms"], "grade": r["grade"], "graded_ms": r["graded_ms"],
        }
        if r["submission_id"]:
            item.update(submission_metrics(r))
        out.append(item)
    return out
