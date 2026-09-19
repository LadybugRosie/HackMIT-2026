from fastapi import APIRouter, Depends, HTTPException

from ..db import Db
from ..deps import class_member_or_404, current_user, get_db, require_role, submission_or_404
from ..ids import new_id, now_ms
from ..schemas import DraftRequest, GradeRequest, StartSubmissionRequest, SubmissionOut
from ..views import assignment_row, submission_out

router = APIRouter(prefix="/api/submissions", tags=["submissions"])


def _teacher_submission_or_404(db: Db, submission_id: str, user: dict) -> dict:
    row = submission_or_404(db, submission_id, user)
    if row["teacher_id"] != user["user_id"]:
        raise HTTPException(404, "submission not found")
    return row


@router.post("/start", response_model=SubmissionOut)
def start_submission(payload: StartSubmissionRequest, db: Db = Depends(get_db),
                     user: dict = Depends(require_role("student"))) -> SubmissionOut:
    """Get-or-create the student's draft for an assignment (one per student per assignment)."""
    a = assignment_row(db, payload.assignment_id)
    if a is None:
        raise HTTPException(404, "assignment not found")
    class_member_or_404(db, a["class_id"], user)
    if not a["published"]:
        raise HTTPException(404, "assignment not found")
    now = now_ms()
    db.exec("INSERT OR IGNORE INTO submissions (submission_id, assignment_id, student_id, content, status, updated_ms) "
            "VALUES (?,?,?,?, 'draft', ?)", (new_id(), payload.assignment_id, user["user_id"], "", now))
    row = db.one("SELECT * FROM submissions WHERE assignment_id = ? AND student_id = ?", (payload.assignment_id, user["user_id"]))
    return submission_out(db, row, user)


@router.get("/{submission_id}", response_model=SubmissionOut)
def get_submission(submission_id: str, db: Db = Depends(get_db), user: dict = Depends(current_user)) -> SubmissionOut:
    return submission_out(db, submission_or_404(db, submission_id, user), user)


@router.put("/{submission_id}/draft")
def save_draft(submission_id: str, payload: DraftRequest, db: Db = Depends(get_db),
               user: dict = Depends(require_role("student"))) -> dict:
    row = submission_or_404(db, submission_id, user)
    if row["student_id"] != user["user_id"]:
        raise HTTPException(404, "submission not found")
    if row["status"] != "draft":
        raise HTTPException(409, {"code": "not_draft", "detail": "submission is no longer editable"})
    db.exec("UPDATE submissions SET content = ?, updated_ms = ? WHERE submission_id = ?", (payload.content, now_ms(), submission_id))
    return {"ok": True}


@router.post("/{submission_id}/grade", response_model=SubmissionOut)
def grade_submission(submission_id: str, payload: GradeRequest, db: Db = Depends(get_db),
                     user: dict = Depends(require_role("teacher"))) -> SubmissionOut:
    row = _teacher_submission_or_404(db, submission_id, user)
    if row["status"] == "draft":
        raise HTTPException(409, {"code": "not_submitted", "detail": "cannot grade a draft"})
    a = assignment_row(db, row["assignment_id"])
    if payload.grade > a["points"]:
        raise HTTPException(422, f"grade exceeds the assignment's {a['points']} points")
    now = now_ms()
    db.exec("UPDATE submissions SET grade = ?, feedback = ?, graded_ms = ?, status = 'graded', updated_ms = ? WHERE submission_id = ?",
            (payload.grade, payload.feedback, now, now, submission_id))
    return submission_out(db, db.one("SELECT * FROM submissions WHERE submission_id = ?", (submission_id,)), user)


@router.post("/{submission_id}/return", response_model=SubmissionOut)
def return_submission(submission_id: str, db: Db = Depends(get_db), user: dict = Depends(require_role("teacher"))) -> SubmissionOut:
    row = _teacher_submission_or_404(db, submission_id, user)
    if row["status"] != "graded":
        raise HTTPException(409, {"code": "not_graded", "detail": "grade the submission before returning it"})
    db.exec("UPDATE submissions SET status = 'returned', updated_ms = ? WHERE submission_id = ?", (now_ms(), submission_id))
    return submission_out(db, db.one("SELECT * FROM submissions WHERE submission_id = ?", (submission_id,)), user)
