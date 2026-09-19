import json
import secrets

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request

from attest.certificate import build_certificate, verify_certificate
from attest.chain import genesis_hash, sha256_hex
from attest.models import Certificate
from attest.replay import replay
from attest.storage.base import SessionRecord

from ..db import Db
from ..deps import class_member_or_404, current_user, get_db, get_store, require_role, submission_or_404
from ..ids import new_id, now_ms
from ..schemas import DraftRequest, GradeRequest, LedgerInfo, StartSubmissionRequest, SubmissionOut, SubmitRequest
from ..tasks import run_post_submit
from ..views import assignment_row, loads, submission_out

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


@router.post("/{submission_id}/ledger", response_model=LedgerInfo)
def ledger(submission_id: str, db: Db = Depends(get_db), store=Depends(get_store),
           user: dict = Depends(require_role("student"))) -> LedgerInfo:
    """Create (once) or resume the attest ledger session bound to this submission. The session's
    doc_id is the submission_id, which is what `submit` later checks — a session started any other
    way can never certify a submission."""
    row = submission_or_404(db, submission_id, user)
    if row["student_id"] != user["user_id"]:
        raise HTTPException(404, "submission not found")
    session_id = row["ledger_session_id"]
    if session_id is None:
        if row["status"] != "draft":
            raise HTTPException(409, {"code": "not_draft", "detail": "submission is no longer editable"})
        session_id, nonce = new_id(), secrets.token_hex(16)
        genesis = genesis_hash(session_id, nonce)
        store.create(SessionRecord(session_id=session_id, server_nonce=nonce, genesis=genesis, created_ms=now_ms(),
                                   doc_id=submission_id, head=genesis, owner=user["user_id"]))
        db.exec("UPDATE submissions SET ledger_session_id = ?, updated_ms = ? WHERE submission_id = ? AND ledger_session_id IS NULL",
                (session_id, now_ms(), submission_id))
        session_id = db.one("SELECT ledger_session_id FROM submissions WHERE submission_id = ?", (submission_id,))["ledger_session_id"]
    rec = store.get(session_id)
    return LedgerInfo(session_id=rec.session_id, genesis=rec.genesis, chain_head=rec.head, event_count=rec.event_count,
                      text=replay(rec.events), finalized=rec.certificate is not None)


@router.post("/{submission_id}/submit")
def submit(submission_id: str, payload: SubmitRequest, background: BackgroundTasks, request: Request,
           db: Db = Depends(get_db), store=Depends(get_store), user: dict = Depends(require_role("student"))) -> dict:
    """The hard guarantee: the certificate is rebuilt from the server's own ledger copy and must bind
    to exactly the submitted text. The client's certificate is compared, never stored."""
    row = submission_or_404(db, submission_id, user)
    if row["student_id"] != user["user_id"]:
        raise HTTPException(404, "submission not found")
    if row["status"] != "draft":
        raise HTTPException(409, {"code": "not_draft", "detail": "already submitted"})
    if row["ledger_session_id"] is None or payload.session_id != row["ledger_session_id"]:
        raise HTTPException(409, {"code": "wrong_session", "detail": "session is not the ledger bound to this submission"})
    rec = store.get(payload.session_id)
    if rec is None or rec.doc_id != submission_id:
        raise HTTPException(409, {"code": "wrong_session", "detail": "session is not the ledger bound to this submission"})

    if rec.certificate is None:
        cert, reason = build_certificate(rec, payload.text, request.app.state.attestors,
                                         request.app.state.attest_settings.HID_TRUSTED_CDHASHES)
        if cert is None:
            raise HTTPException(409, {"code": "not_bound", "detail": reason})
        cert_dict = cert.model_dump()
        store.set_certificate(rec.session_id, cert_dict)
    else:
        cert_dict = rec.certificate
        if cert_dict["doc_sha256"] != sha256_hex(payload.text):
            raise HTTPException(409, {"code": "hash_mismatch",
                                      "detail": "the text differs from the ledger that was finalized — reload and submit again"})
    ok, level, checks = verify_certificate(Certificate(**cert_dict), payload.text, rec.events)
    if not ok:  # cannot happen if the store is consistent; refuse loudly rather than certify garbage
        raise HTTPException(500, {"code": "verify_failed", "checks": [c.model_dump() for c in checks]})

    a = assignment_row(db, row["assignment_id"])
    settings = loads(a["settings_json"], {})
    now = now_ms()
    db.exec(
        "UPDATE submissions SET content = ?, status = 'submitted', submitted_ms = ?, certificate_json = ?, integrity_json = ?, "
        "factcheck_status = ?, similarity_status = ?, updated_ms = ? WHERE submission_id = ?",
        (payload.text, now, json.dumps(cert_dict), json.dumps(cert_dict["claims"].get("integrity")),
         "pending" if settings.get("factcheck", True) else "skipped",
         "pending" if settings.get("similarity", True) else "skipped", now, submission_id))
    background.add_task(run_post_submit, db, store, submission_id, request.app.state.resolver)

    return {
        "submission": submission_out(db, db.one("SELECT * FROM submissions WHERE submission_id = ?", (submission_id,)), user),
        "certificate": cert_dict,
        "verify": {"ok": ok, "assurance_level": level, "checks": [c.model_dump() for c in checks]},
        "client_certificate_matches": (payload.certificate or {}).get("chain_root") == cert_dict["chain_root"] if payload.certificate else None,
    }


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
