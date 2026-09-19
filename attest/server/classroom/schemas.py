from __future__ import annotations

import re
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

Role = Literal["student", "teacher"]
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class UserOut(BaseModel):
    user_id: str
    email: str
    name: str
    role: Role


class SignupRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=120)
    role: Role = "student"
    class_code: Optional[str] = None

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("invalid email address")
        return v

    @field_validator("class_code")
    @classmethod
    def _code(cls, v: Optional[str]) -> Optional[str]:
        v = (v or "").strip().upper()
        return v or None


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return v.strip().lower()


class AuthResponse(BaseModel):
    token: str
    user: UserOut


# ---- classes / assignments / submissions -------------------------------------------------

class ClassCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class JoinRequest(BaseModel):
    class_code: str

    @field_validator("class_code")
    @classmethod
    def _code(cls, v: str) -> str:
        return v.strip().upper()


class ClassOut(BaseModel):
    class_id: str
    name: str
    class_code: Optional[str] = None  # teachers only
    teacher_id: str
    teacher_name: str
    student_count: int = 0
    assignment_count: int = 0
    created_ms: int


class AssignmentSettings(BaseModel):
    factcheck: bool = True
    similarity: bool = True
    allow_paste: bool = True
    min_trust: int = Field(default=0, ge=0, le=100)


class AssignmentCreate(BaseModel):
    class_id: str
    title: str = Field(min_length=1, max_length=200)
    instructions: str = ""
    due_ms: Optional[int] = None
    points: int = Field(default=100, ge=0, le=10_000)
    published: bool = True
    settings: AssignmentSettings = Field(default_factory=AssignmentSettings)


class AssignmentUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    instructions: Optional[str] = None
    due_ms: Optional[int] = None
    points: Optional[int] = Field(default=None, ge=0, le=10_000)
    published: Optional[bool] = None
    settings: Optional[AssignmentSettings] = None


class AssignmentOut(BaseModel):
    assignment_id: str
    class_id: str
    class_name: Optional[str] = None
    title: str
    instructions: str
    due_ms: Optional[int]
    points: int
    published: bool
    settings: AssignmentSettings
    created_ms: int
    my_submission: Optional[Dict[str, Any]] = None   # students: {submission_id, status, grade}
    submission_counts: Optional[Dict[str, int]] = None  # teachers


class StartSubmissionRequest(BaseModel):
    assignment_id: str


class DraftRequest(BaseModel):
    content: str = Field(max_length=500_000)


class SubmitRequest(BaseModel):
    session_id: str
    text: str = Field(max_length=500_000)
    certificate: Optional[Dict[str, Any]] = None


class GradeRequest(BaseModel):
    grade: float = Field(ge=0)
    feedback: str = Field(default="", max_length=20_000)


class SubmissionOut(BaseModel):
    submission_id: str
    assignment_id: str
    student_id: str
    student_name: Optional[str] = None
    content: str
    status: str
    ledger_session_id: Optional[str]
    certificate: Optional[Dict[str, Any]] = None
    integrity: Optional[Dict[str, Any]] = None
    factcheck_status: str
    factcheck: Optional[Dict[str, Any]] = None
    similarity_status: str
    similarity: Optional[Dict[str, Any]] = None
    submitted_ms: Optional[int]
    grade: Optional[float]
    feedback: Optional[str]
    graded_ms: Optional[int]
    updated_ms: int
    assignment: Optional[AssignmentOut] = None


class LedgerInfo(BaseModel):
    session_id: str
    genesis: str
    chain_head: str
    event_count: int
    text: str
    finalized: bool
