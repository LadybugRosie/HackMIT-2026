from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request

from ..db import Db
from ..deps import current_user, get_db, get_store, require_role, submission_or_404
from ..tasks import run_post_submit
from ..views import loads

router = APIRouter(prefix="/api/factcheck", tags=["factcheck"])


@router.get("/submissions/{submission_id}")
def get_factcheck(submission_id: str, db: Db = Depends(get_db), user: dict = Depends(current_user)) -> dict:
    row = submission_or_404(db, submission_id, user)
    return {"status": row["factcheck_status"], "result": loads(row["factcheck_json"])}


@router.post("/submissions/{submission_id}/run")
def rerun_factcheck(submission_id: str, background: BackgroundTasks, request: Request, db: Db = Depends(get_db),
                    store=Depends(get_store), user: dict = Depends(require_role("teacher"))) -> dict:
    row = submission_or_404(db, submission_id, user)
    if row["teacher_id"] != user["user_id"]:
        raise HTTPException(404, "submission not found")
    if row["status"] == "draft":
        raise HTTPException(409, {"code": "not_submitted", "detail": "nothing to check yet"})
    db.exec("UPDATE submissions SET factcheck_status = 'pending' WHERE submission_id = ?", (submission_id,))
    background.add_task(run_post_submit, db, store, submission_id, request.app.state.resolver)
    return {"status": "pending"}
