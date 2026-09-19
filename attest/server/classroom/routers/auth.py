import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Header, Request

from ..db import Db
from ..deps import current_user, get_db
from ..ids import new_id, now_ms
from ..schemas import AuthResponse, LoginRequest, SignupRequest, UserOut
from ..security import hash_password, hash_token, mint_token, verify_password
from ..settings import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])


def issue_token(db: Db, user_id: str) -> str:
    token, digest = mint_token()
    now = now_ms()
    db.exec("INSERT INTO auth_tokens (token_hash, user_id, created_ms, expires_ms) VALUES (?,?,?,?)",
            (digest, user_id, now, now + settings.TOKEN_TTL_DAYS * 86_400_000))
    return token


@router.post("/signup", response_model=AuthResponse, status_code=201)
def signup(payload: SignupRequest, db: Db = Depends(get_db)) -> AuthResponse:
    klass = None
    if payload.class_code:
        if payload.role != "student":
            raise HTTPException(400, "only students join classes with a code")
        klass = db.one("SELECT class_id FROM classes WHERE class_code = ?", (payload.class_code,))
        if klass is None:
            raise HTTPException(404, "invalid class code")

    user_id, now = new_id(), now_ms()
    try:
        with db.tx() as conn:
            conn.execute("INSERT INTO users (user_id, email, password_hash, name, role, created_ms) VALUES (?,?,?,?,?,?)",
                         (user_id, payload.email, hash_password(payload.password, settings.SCRYPT_N),
                          payload.name.strip(), payload.role, now))
            if klass is not None:
                conn.execute("INSERT INTO class_members (class_id, user_id, role, joined_ms) VALUES (?,?,?,?)",
                             (klass["class_id"], user_id, "student", now))
    except sqlite3.IntegrityError:
        raise HTTPException(409, "an account with this email already exists")

    return AuthResponse(token=issue_token(db, user_id),
                        user=UserOut(user_id=user_id, email=payload.email, name=payload.name.strip(), role=payload.role))


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Db = Depends(get_db)) -> AuthResponse:
    row = db.one("SELECT * FROM users WHERE email = ?", (payload.email,))
    if row is None or not verify_password(payload.password, row["password_hash"]):
        raise HTTPException(401, "incorrect email or password")
    return AuthResponse(token=issue_token(db, row["user_id"]),
                        user=UserOut(user_id=row["user_id"], email=row["email"], name=row["name"], role=row["role"]))


@router.post("/logout")
def logout(authorization: str = Header(default=""), db: Db = Depends(get_db), _: dict = Depends(current_user)) -> dict:
    token = authorization.partition(" ")[2].strip()
    db.exec("DELETE FROM auth_tokens WHERE token_hash = ?", (hash_token(token),))
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(user: dict = Depends(current_user)) -> UserOut:
    return UserOut(**user)
