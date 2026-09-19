from fastapi import APIRouter, HTTPException
from typing import Optional, List, Dict
import time
import uuid
import hashlib

from ..models import (
    SessionStartRequest, IngestRequest, ExportCheckRequest,
    SessionDocument, EventBatch, PieceTable, TypedIndex,
    IntegrityResponse, ExportCheckResponse, Event
)
from ..services.piece_table import PieceTableManager
from ..services.classify import ContentClassifier
from ..services.scoring import ScoringEngine


router = APIRouter(prefix="/api/integrity", tags=["integrity"])


# In-memory state for active sessions (in production, use Redis)
active_sessions: Dict[str, dict] = {}


def get_session_state(session_id: str) -> dict:
    """Get or create session state"""
    if session_id not in active_sessions:
        active_sessions[session_id] = {
            "piece_table": PieceTableManager(),
            "classifier": ContentClassifier(),
            "cursor_pos": 0,
            "recent_pastes": [],
            "last_event_time": time.time()
        }
    return active_sessions[session_id]


@router.post("/session/start")
async def start_session(request: SessionStartRequest) -> dict:
    """Start a new integrity tracking session"""
    session_id = str(uuid.uuid4())
    doc_id = request.doc_id or str(uuid.uuid4())
    
    # Create session document
    session_doc = SessionDocument(
        session_id=session_id,
        doc_id=doc_id,
        settings={"strict_mode": request.strict_mode}
    )
    
    # Initialize session state
    active_sessions[session_id] = {
        "piece_table": PieceTableManager(),
        "classifier": ContentClassifier(),
        "cursor_pos": 0,
        "recent_pastes": [],
        "last_event_time": time.time(),
        "doc_id": doc_id,
        "strict_mode": request.strict_mode
    }
    
    return {"session_id": session_id, "doc_id": doc_id}


@router.post("/ingest")
async def ingest_events(request: IngestRequest) -> IntegrityResponse:
    """Process document events and update integrity scores"""
    
    state = get_session_state(request.session_id)
    piece_table: PieceTableManager = state["piece_table"]
    classifier: ContentClassifier = state["classifier"]
    cursor_pos = state["cursor_pos"]
    
    # Clear old paste tracking
    current_time = time.time()
    state["recent_pastes"] = [
        (length, ts) for length, ts in state["recent_pastes"] 
        if current_time - ts < 60  # Keep pastes from last minute
    ]
    
    # Track if we just had a copy event
    last_copy_time = None
    
    # Process events
    for event in request.events:
        ts = event.ts
        
        if event.t == "key":
            # Single character typed
            piece_table.insert_typed(cursor_pos, 1, ts)
            cursor_pos += 1
            
        elif event.t == "enter":
            # Enter key (newline)
            piece_table.insert_typed(cursor_pos, 1, ts)
            cursor_pos += 1
            
        elif event.t == "backspace":
            # Backspace
            if cursor_pos > 0:
                piece_table.handle_backspace(cursor_pos, ts)
                cursor_pos -= 1
                
        elif event.t == "delete":
            # Delete key
            piece_table.handle_delete(cursor_pos, ts)
            
        elif event.t == "paste":
            # Paste event
            length = event.len or len(event.snippet or "")
            snippet = event.snippet or ""
            
            # Check if this is from a recent copy
            is_from_copy = last_copy_time and (ts - last_copy_time < 1.0)
            copy_is_internal = piece_table.is_last_copy_internal() if is_from_copy else False
            
            # Classify the paste
            origin = classifier.classify_paste(snippet, is_from_copy, copy_is_internal)
            
            # Generate source ID for tracking
            source_id = hashlib.md5(f"{ts}:{snippet[:100]}".encode()).hexdigest()[:8]
            
            # Insert the paste
            piece_table.insert_paste(cursor_pos, length, origin, source_id, ts)
            
            # Update classifier index if internal
            if origin == "INT":
                classifier.add_internal_content(snippet, cursor_pos)
            
            # Track paste for flags
            if origin == "EXT":
                state["recent_pastes"].append((length, ts))
            
            cursor_pos += length
            
        elif event.t == "copy":
            # Copy event
            if event.from_pos is not None and event.to_pos is not None:
                piece_table.record_copy(event.from_pos, event.to_pos)
                last_copy_time = ts
                
        elif event.t == "cut":
            # Cut event (copy + delete)
            if event.from_pos is not None and event.to_pos is not None:
                piece_table.record_copy(event.from_pos, event.to_pos)
                piece_table.delete_range(event.from_pos, event.to_pos)
                cursor_pos = event.from_pos
                last_copy_time = ts
                
        elif event.t == "sel":
            # Selection change
            if event.from_pos is not None:
                cursor_pos = event.from_pos
                
        elif event.t == "update":
            # Document update (for detecting large inserts)
            new_len = event.len or request.content_len
            old_len = piece_table.text_len
            
            if new_len > old_len:
                insert_len = new_len - old_len
                # Check if this is a large insert without paste event
                if insert_len >= 80 and (ts - state.get("last_event_time", ts)) <= 1.0:
                    # Classify as potential external paste
                    # In production, we'd need the actual inserted text
                    origin = "EXT"  # Conservative assumption
                    source_id = hashlib.md5(f"large:{ts}".encode()).hexdigest()[:8]
                    piece_table.insert_paste(cursor_pos, insert_len, origin, source_id, ts)
                    state["recent_pastes"].append((insert_len, ts))
                    cursor_pos += insert_len
    
    # Update state
    state["cursor_pos"] = cursor_pos
    state["last_event_time"] = current_time
    
    # Calculate composition
    typed, internal, external = piece_table.get_composition()
    
    # Get external spans
    ext_spans = piece_table.get_external_spans()
    
    # Compute scores
    result = ScoringEngine.compute_scores(
        typed, internal, external,
        request.events,
        state["recent_pastes"],
        ext_spans
    )
    
    # Database storage removed for now (works in-memory)
    
    return IntegrityResponse(**result)


@router.get("/status")
async def get_status(
    session_id: Optional[str] = None,
    doc_id: Optional[str] = None
) -> IntegrityResponse:
    """Get current integrity status for a session or document"""
    
    if not session_id and not doc_id:
        raise HTTPException(status_code=400, detail="session_id or doc_id required")
    
    # Find session
    if not session_id and doc_id:
        # Look up session by doc_id
        for sid, state in active_sessions.items():
            if state.get("doc_id") == doc_id:
                session_id = sid
                break
    
    if not session_id or session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    state = active_sessions[session_id]
    piece_table: PieceTableManager = state["piece_table"]
    
    # Calculate current composition
    typed, internal, external = piece_table.get_composition()
    ext_spans = piece_table.get_external_spans()
    
    # Compute scores
    result = ScoringEngine.compute_scores(
        typed, internal, external,
        [],  # No new events
        state["recent_pastes"],
        ext_spans
    )
    
    return IntegrityResponse(**result)


@router.post("/export/check")
async def check_export(request: ExportCheckRequest) -> ExportCheckResponse:
    """Check if export is allowed based on trust score"""
    
    if request.session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    state = active_sessions[request.session_id]
    piece_table: PieceTableManager = state["piece_table"]
    
    # Calculate current trust
    typed, internal, external = piece_table.get_composition()
    trust = ScoringEngine.calculate_trust_score(typed, internal, external)
    
    # Check if export is allowed
    ok = trust >= request.min_trust
    
    # Generate reason if blocked
    reason = None
    if not ok:
        total = max(typed + internal + external, 1)
        external_ratio = round(100 * external / total)
        ext_spans = piece_table.get_external_spans()
        reason = f"External paste {external_ratio}% ({len(ext_spans)} spans)"
    
    return ExportCheckResponse(ok=ok, trust=trust, reason=reason)
