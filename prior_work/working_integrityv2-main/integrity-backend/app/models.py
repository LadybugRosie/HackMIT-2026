from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Literal, Any
from datetime import datetime
import uuid


# ============================================================================
# INTEGRITY MODELS (Existing)
# ============================================================================

class Event(BaseModel):
    t: Literal["key", "backspace", "paste", "copy", "cut", "sel", "update", "enter", "delete"]
    ts: float
    k: Optional[str] = None  # key for key events
    len: Optional[int] = None  # length for paste/update
    snippet: Optional[str] = None  # snippet for paste (capped at 4KB)
    from_pos: Optional[int] = Field(None, alias="from")  # selection start
    to_pos: Optional[int] = Field(None, alias="to")  # selection end
    
    class Config:
        populate_by_name = True


class IngestRequest(BaseModel):
    session_id: str
    doc_id: str
    content_len: int
    content_sha256: str
    current_text: Optional[str] = None  # Actual current editor content
    events: List[Event]


class SessionStartRequest(BaseModel):
    strict_mode: bool = False
    doc_id: Optional[str] = None


class ExportCheckRequest(BaseModel):
    session_id: str
    doc_id: str
    min_trust: int = 60


class Piece(BaseModel):
    start: int
    end: int
    origin: Literal["T", "INT", "EXT"]  # Typed, Internal, External
    source_id: Optional[str] = None  # ID of paste/copy source
    ts_created: float


class SessionDocument(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    doc_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    settings: Dict[str, Any] = Field(default_factory=dict)


class EventBatch(BaseModel):
    session_id: str
    batch_ts: float
    events: List[Dict[str, Any]]


class PieceTable(BaseModel):
    session_id: str
    doc_id: str
    pieces: List[Piece] = Field(default_factory=list)
    text_len: int = 0


class TypedIndex(BaseModel):
    session_id: str
    ngrams: Dict[str, List[int]] = Field(default_factory=dict)  # ngram -> positions


class IntegrityScores(BaseModel):
    trust: int  # 0-100
    composition: int  # 0-100


class ContentMix(BaseModel):
    typed: float  # 0-1
    internal: float  # 0-1
    external: float  # 0-1


class ExternalSpan(BaseModel):
    start: int
    end: int


class IntegrityResponse(BaseModel):
    scores: IntegrityScores
    mix: ContentMix
    flags: List[str]
    ext_spans: List[ExternalSpan]


class ExportCheckResponse(BaseModel):
    ok: bool
    trust: int
    reason: Optional[str] = None


# ============================================================================
# CLASSROOM MODELS (New)
# ============================================================================

# --- Class Models ---

class ClassCreate(BaseModel):
    """Request model for creating a new class"""
    name: str = Field(..., min_length=1, max_length=200)
    section: Optional[str] = Field(None, max_length=50)
    subject: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    color: Optional[str] = Field("#1a73e8", pattern=r'^#[0-9a-fA-F]{6}$')


class ClassUpdate(BaseModel):
    """Request model for updating a class"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    section: Optional[str] = Field(None, max_length=50)
    subject: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    color: Optional[str] = Field(None, pattern=r'^#[0-9a-fA-F]{6}$')


class ClassJoin(BaseModel):
    """Request model for joining a class"""
    class_code: str = Field(..., min_length=6, max_length=8)


class ClassSettings(BaseModel):
    """Default settings for assignments in this class"""
    default_face_verification: bool = True
    default_face_check_interval: int = 600000  # 10 minutes
    default_strict_mode: bool = False
    default_minimum_trust: int = 60
    allow_late_submissions: bool = True


class ClassResponse(BaseModel):
    """Response model for class data"""
    class_id: str
    name: str
    section: Optional[str]
    subject: str
    description: Optional[str]
    color: str
    class_code: str
    teacher_id: str
    teacher_name: str
    student_count: int
    assignment_count: int
    created_at: datetime
    archived: bool = False


# --- Assignment Models ---

class RubricLevel(BaseModel):
    """A scoring level within a rubric criterion"""
    name: str = Field(..., min_length=1, max_length=50)  # "Excellent", "Good", etc.
    points: int = Field(..., ge=0)
    description: str = Field(..., min_length=1, max_length=500)


class RubricCriteria(BaseModel):
    """A criterion in an assignment rubric"""
    criteria_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., min_length=1, max_length=100)  # "Thesis Statement"
    description: str = Field(..., min_length=1, max_length=500)
    points: int = Field(..., ge=1)  # Max points for this criterion
    levels: List[RubricLevel] = Field(..., min_length=2)  # At least 2 levels


class AssignmentSettings(BaseModel):
    """Settings for an individual assignment"""
    # Integrity Tool Toggles — teacher chooses which tools are active
    analyze_integrity_enabled: bool = True   # Content authenticity (copy/paste tracking)
    gptzero_enabled: bool = True             # AI detection via GPTZero
    stylometry_enabled: bool = True          # Forensic authorship verification (V3)
    face_verification_enabled: bool = True   # Periodic face identity checks
    check_plagiarism: bool = True            # Plagiarism database (internal + scholarly + web)

    # Face Verification Config
    face_check_interval: int = 600000  # 10 minutes in ms
    face_max_warnings: int = 3
    strict_mode: bool = False  # Block external paste
    minimum_trust_score: int = 60

    # Submission Settings
    allow_late: bool = True
    late_penalty_percent: int = 10  # Per day
    max_attempts: int = 1

    # Plagiarism Settings
    plagiarism_threshold: int = 40  # Flag above this %

    # Auto-Grading Settings
    auto_grade_enabled: bool = False

    # Education level — adjusts AI grading expectations
    education_level: Literal["high_school", "university", "graduate"] = "university"


class AssignmentCreate(BaseModel):
    """Request model for creating an assignment"""
    class_id: str
    title: str = Field(..., min_length=1, max_length=200)
    instructions: str = Field(..., min_length=1, max_length=10000)
    due_date: datetime
    points: int = Field(..., ge=1, le=1000)
    settings: AssignmentSettings = Field(default_factory=AssignmentSettings)
    rubric: Optional[List[RubricCriteria]] = None
    type: Literal["regular", "stylometry_enrollment"] = "regular"


class AssignmentUpdate(BaseModel):
    """Request model for updating an assignment"""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    instructions: Optional[str] = Field(None, min_length=1, max_length=10000)
    due_date: Optional[datetime] = None
    points: Optional[int] = Field(None, ge=1, le=1000)
    settings: Optional[AssignmentSettings] = None
    rubric: Optional[List[RubricCriteria]] = None


class AssignmentResponse(BaseModel):
    """Response model for assignment data"""
    assignment_id: str
    class_id: str
    class_name: str
    teacher_id: str
    title: str
    instructions: str
    due_date: datetime
    points: int
    settings: AssignmentSettings
    rubric: Optional[List[RubricCriteria]]
    created_at: datetime
    published: bool
    submission_count: int
    graded_count: int
    # Assignment kind (regular | stylometry_enrollment) + enrollment prompts.
    # WITHOUT these here FastAPI's response_model silently STRIPS them (and the
    # student enrichment below) from the JSON — which made every assignment
    # render "Missing"/"Not Started" even after submission.
    type: str = "regular"
    stylometry_prompts: Optional[Any] = None
    # Student-only enrichment (the caller's own submission state)
    status: Optional[str] = None
    submitted: Optional[bool] = None
    grade: Optional[int] = None
    graded_at: Optional[datetime] = None
    submission_id: Optional[str] = None
    trust_score: Optional[int] = None


# --- Submission Models ---

class PlagiarismMatch(BaseModel):
    """A plagiarism match between submissions"""
    matched_submission_id: str
    matched_student_id: str
    matched_student_name: str
    similarity_score: float  # 0-100
    matching_segments: List[Dict[str, Any]]  # [{start, end, text, matched_text}]


class FaceVerificationLog(BaseModel):
    """Log entry for face verification during session"""
    timestamp: datetime
    result: Literal["verified", "warning", "failed"]
    confidence: Optional[float] = None
    message: Optional[str] = None


class CriteriaScore(BaseModel):
    """Score for a single rubric criterion"""
    criteria_id: str
    criteria_name: Optional[str] = None
    score: int
    max_score: Optional[int] = None
    level_name: Optional[str] = None
    explanation: Optional[str] = None
    evidence: Optional[str] = None


class AutoGradeResult(BaseModel):
    """Result from auto-grading system"""
    total_score: int
    max_score: int
    criteria_scores: List[CriteriaScore]
    overall_feedback: str
    confidence: float  # 0-1, how confident the AI is
    graded_at: datetime


class SubmissionCreate(BaseModel):
    """Request model for creating/updating a submission draft"""
    assignment_id: str
    content: str
    content_html: Optional[str] = None


class SubmissionSubmit(BaseModel):
    """Request model for final submission"""
    content: str
    content_html: Optional[str] = None
    session_id: str
    integrity_data: Optional[Dict[str, Any]] = None
    report_html: Optional[str] = None


class GradeSubmission(BaseModel):
    """Request model for grading a submission"""
    grade: int = Field(..., ge=0)
    feedback: Optional[str] = Field(None, max_length=5000)
    criteria_scores: Optional[List[CriteriaScore]] = None


class SubmissionResponse(BaseModel):
    """Response model for submission data"""
    submission_id: str
    assignment_id: str
    assignment_title: str
    student_id: str
    student_name: str
    class_id: str
    
    # Content
    content: str
    content_html: Optional[str]
    word_count: int
    
    # Integrity Data
    trust_score: int
    content_mix: ContentMix
    integrity_flags: List[str]
    face_verification_log: List[FaceVerificationLog]
    
    # Plagiarism Results
    plagiarism_score: int
    plagiarism_matches: List[PlagiarismMatch]
    
    # AI Detection (None = detector never ran; live value lives under ai_detection)
    ai_probability: Optional[float] = None
    
    # Grading
    status: Literal["draft", "submitted", "graded", "returned"]
    submitted_at: Optional[datetime]
    grade: Optional[int]
    max_grade: int
    grade_breakdown: Optional[List[CriteriaScore]]
    feedback: Optional[str]
    graded_by: Optional[str]  # "auto" or teacher name
    graded_at: Optional[datetime]
    
    # Auto-grade suggestion (if available)
    auto_grade_suggestion: Optional[AutoGradeResult] = None


# --- Analytics Models ---

class ClassAnalytics(BaseModel):
    """Analytics for a class"""
    class_id: str
    total_students: int
    total_assignments: int
    average_trust_score: float
    average_grade: float
    submission_rate: float  # % of assignments submitted on time
    plagiarism_incidents: int
    trust_distribution: Dict[str, int]  # {"high": 10, "medium": 5, "low": 2}


class AssignmentAnalytics(BaseModel):
    """Analytics for an assignment"""
    assignment_id: str
    total_submissions: int
    graded_count: int
    average_grade: float
    average_trust_score: float
    average_plagiarism_score: float
    late_submissions: int
    flagged_submissions: int
    grade_distribution: Dict[str, int]  # {"A": 10, "B": 15, etc.}


# --- Document Fingerprint for Plagiarism ---

class DocumentFingerprint(BaseModel):
    """Fingerprint data for plagiarism detection"""
    submission_id: str
    assignment_id: str
    class_id: str
    student_id: str
    fingerprint: List[int]  # Winnowing fingerprints
    ngram_hashes: Dict[str, List[int]]  # For quick lookup
    word_count: int
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# STYLOMETRY V3 (Per-Course) MODELS
# ============================================================================

class StylometryV3EnrollRequest(BaseModel):
    """Submit 3 writing samples for per-course stylometry enrollment"""
    class_id: str
    samples: List[str] = Field(..., min_length=3, max_length=10)

class StylometryV3VerifyRequest(BaseModel):
    """Verify a submission against the student's per-course profile"""
    class_id: str
    submission_text: str = Field(..., min_length=50)

class StylometryV3CourseStatus(BaseModel):
    """Per-course enrollment status for a student"""
    class_id: str
    enrolled: bool = False
    profile_strength: Optional[str] = None
    samples_count: int = 0
    enrolled_at: Optional[datetime] = None

