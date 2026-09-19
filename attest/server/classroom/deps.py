from __future__ import annotations

from typing import Callable, Optional

from fastapi import Depends, Header, HTTPException, Request

from .db import Db
from .ids import now_ms
from .schemas import Role
from .security import hash_token


def get_db(request: Request) -> Db:
    return request.app.state.db


def get_store(request: Request):
    return request.app.state.store


def _token_from_header(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        return None
    return value.strip()


def optional_user(request: Request, authorization: Optional[str] = Header(default=None)) -> Optional[dict]:
    token = _token_from_header(authorization)
    if token is None:
        return None
    db: Db = request.app.state.db
    row = db.one(
        "SELECT u.user_id, u.email, u.name, u.role FROM auth_tokens t JOIN users u ON u.user_id = t.user_id "
        "WHERE t.token_hash = ? AND t.expires_ms > ?",
        (hash_token(token), now_ms()),
    )
    return dict(row) if row else None


def current_user(user: Optional[dict] = Depends(optional_user)) -> dict:
    if user is None:
        raise HTTPException(401, "not signed in")
    return user


def require_role(role: Role) -> Callable[..., dict]:
    def dep(user: dict = Depends(current_user)) -> dict:
        if user["role"] != role:
            raise HTTPException(403, f"{role}s only")
        return user
    return dep


def class_teacher_or_404(db: Db, class_id: str, user: dict) -> dict:
    row = db.one("SELECT * FROM classes WHERE class_id = ?", (class_id,))
    if row is None or row["teacher_id"] != user["user_id"]:
        raise HTTPException(404, "class not found")
    return dict(row)


def class_member_or_404(db: Db, class_id: str, user: dict) -> dict:
    row = db.one(
        "SELECT c.* FROM classes c JOIN class_members m ON m.class_id = c.class_id "
        "WHERE c.class_id = ? AND m.user_id = ?", (class_id, user["user_id"]))
    if row is None:
        raise HTTPException(404, "class not found")
    return dict(row)


def submission_for_session(db: Db, session_id: str) -> Optional[dict]:
    row = db.one(
        "SELECT s.submission_id, s.student_id, s.status, c.teacher_id FROM submissions s "
        "JOIN assignments a ON a.assignment_id = s.assignment_id JOIN classes c ON c.class_id = a.class_id "
        "WHERE s.ledger_session_id = ?", (session_id,))
    return dict(row) if row else None


def guard_session_path(request: Request, user: Optional[dict] = Depends(optional_user)) -> None:
    """Engine routes with a {session_id}: sessions bound to a submission are visible only to its
    owner or the class teacher. Unbound sessions (the public engine demo) stay open."""
    session_id = request.path_params.get("session_id")
    if not session_id:
        return
    bound = submission_for_session(request.app.state.db, session_id)
    if bound is None:
        return
    if user is None:
        raise HTTPException(401, "not signed in")
    if user["user_id"] not in (bound["student_id"], bound["teacher_id"]):
        raise HTTPException(404, "unknown session")


def guard_session_owner(request: Request, user: Optional[dict] = Depends(optional_user)) -> None:
    """Device enrolment and head signing on a bound session: the owning student only, while the
    draft is open. Teachers can *read* everything else about a session but never sign for it."""
    session_id = request.path_params.get("session_id")
    if not session_id:
        return
    bound = submission_for_session(request.app.state.db, session_id)
    if bound is None:
        return
    if user is None:
        raise HTTPException(401, "not signed in")
    if bound["student_id"] != user["user_id"]:
        raise HTTPException(404, "unknown session")
    if bound["status"] != "draft" and request.method != "GET":
        raise HTTPException(409, {"code": "not_draft", "detail": "submission is no longer editable"})


async def guard_ingest_body(request: Request, user: Optional[dict] = Depends(optional_user)) -> None:
    """Only the owning student may append to a bound ledger, and only while the draft is open."""
    try:
        body = await request.json()  # cached by Starlette; the endpoint re-reads the same bytes
    except ValueError:
        return  # let the endpoint's own validation produce the 422
    session_id = body.get("session_id") if isinstance(body, dict) else None
    if not session_id:
        return
    bound = submission_for_session(request.app.state.db, session_id)
    if bound is None:
        return
    if user is None:
        raise HTTPException(401, "not signed in")
    if bound["student_id"] != user["user_id"]:
        raise HTTPException(404, "unknown session")
    if bound["status"] != "draft":
        raise HTTPException(409, {"code": "not_draft", "detail": "submission is no longer editable"})


def submission_or_404(db: Db, submission_id: str, user: dict) -> dict:
    """Owner or the teacher of the class; 404 either way so ids cannot be enumerated."""
    row = db.one(
        "SELECT s.*, a.class_id, c.teacher_id FROM submissions s "
        "JOIN assignments a ON a.assignment_id = s.assignment_id "
        "JOIN classes c ON c.class_id = a.class_id WHERE s.submission_id = ?", (submission_id,))
    if row is None or (row["student_id"] != user["user_id"] and row["teacher_id"] != user["user_id"]):
        raise HTTPException(404, "submission not found")
    return dict(row)
