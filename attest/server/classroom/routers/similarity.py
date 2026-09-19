import json

from fastapi import APIRouter, Depends, HTTPException

from ..db import Db
from ..deps import current_user, get_db, require_role, submission_or_404
from ..settings import settings
from ..similarity import run_similarity
from ..views import assignment_row, loads

router = APIRouter(prefix="/api/similarity", tags=["similarity"])


@router.get("/submissions/{submission_id}")
def get_similarity(submission_id: str, db: Db = Depends(get_db), user: dict = Depends(current_user)) -> dict:
    row = submission_or_404(db, submission_id, user)
    return {"status": row["similarity_status"], "result": loads(row["similarity_json"])}


@router.post("/assignments/{assignment_id}/recompute")
def recompute(assignment_id: str, db: Db = Depends(get_db), user: dict = Depends(require_role("teacher"))) -> dict:
    """Re-fingerprint and re-compare every non-draft submission of the assignment (small classes: synchronous)."""
    a = assignment_row(db, assignment_id)
    if a is None or a["teacher_id"] != user["user_id"]:
        raise HTTPException(404, "assignment not found")
    ids = [r["submission_id"] for r in db.all(
        "SELECT submission_id FROM submissions WHERE assignment_id = ? AND status != 'draft' ORDER BY submitted_ms", (assignment_id,))]
    for sid in ids:
        result = run_similarity(db, sid, settings.SIMILARITY_K, settings.SIMILARITY_W)
        db.exec("UPDATE submissions SET similarity_status = 'done', similarity_json = ? WHERE submission_id = ?",
                (json.dumps(result), sid))
    return {"count": len(ids)}
