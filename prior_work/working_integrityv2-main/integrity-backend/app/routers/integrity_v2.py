from fastapi import APIRouter, HTTPException
from typing import Optional, List, Dict
import time
import uuid
import hashlib

from ..models import (
    SessionStartRequest, IngestRequest, 
    IntegrityResponse, Event
)
from ..services.content_tracker import ContentTracker
from ..services.scoring_v2 import ScoringEngine


router = APIRouter(prefix="/api/integrity", tags=["integrity"])


# In-memory state for active sessions
active_sessions: Dict[str, dict] = {}


def get_session_state(session_id: str) -> dict:
    """Get or create session state"""
    if session_id not in active_sessions:
        active_sessions[session_id] = {
            "tracker": ContentTracker(),
            "cursor_pos": 0,
            "last_copy": None,  # Track last copied text
            "strict_mode": False,
            "doc_id": None,
            "created_at": time.time()
        }
    return active_sessions[session_id]


@router.post("/session/start")
async def start_session(request: SessionStartRequest) -> dict:
    """Start a new integrity tracking session"""
    session_id = str(uuid.uuid4())
    
    state = get_session_state(session_id)
    state["doc_id"] = request.doc_id
    state["strict_mode"] = request.strict_mode
    
    return {
        "session_id": session_id,
        "doc_id": request.doc_id
    }


@router.post("/ingest")
async def ingest_events(request: IngestRequest) -> IntegrityResponse:
    """Process document events and return integrity scores"""
    
    state = get_session_state(request.session_id)
    tracker = state["tracker"]
    
    print(f"\n{'='*70}")
    print(f"INGEST REQUEST")
    print(f"  Session: {request.session_id[:8]}...")
    print(f"  Events: {len(request.events)}")
    print(f"  Current text length: {len(request.current_text) if request.current_text else 'N/A'}")
    print(f"{'='*70}\n")
    
    # Store all paste events for comparison
    if "paste_history" not in state:
        state["paste_history"] = []
    
    # Store typed characters count
    if "typed_chars" not in state:
        state["typed_chars"] = 0
    
    # Process each event - store paste info
    for event in request.events:
        try:
            if event.t == "key" or event.t == "enter":
                state["typed_chars"] += 1
                
            elif event.t == "paste" and event.snippet:
                # Store paste event
                state["paste_history"].append({
                    "text": event.snippet,
                    "type": "unknown",  # Will classify as internal/external later
                    "timestamp": event.ts
                })
                print(f"📋 Stored paste event: {len(event.snippet)} chars")
                
            elif event.t == "copy" and event.snippet:
                # Store copy for internal paste detection
                state["last_copy"] = {
                    "text": event.snippet,
                    "timestamp": event.ts
                }
                print(f"📄 Stored copy event: {len(event.snippet)} chars")
            
            # Still process in tracker for backward compatibility
            process_event(tracker, event, state)
        except Exception as e:
            print(f"Error processing event: {e}")
            continue
    
    # NOW THE KEY PART: Compare paste history with current text
    if request.current_text is not None:
        current_text = request.current_text
        print(f"\n🔍 ANALYZING CURRENT CONTENT:")
        print(f"   Current text: {len(current_text)} chars")
        print(f"   Typed chars accumulated: {state['typed_chars']}")
        print(f"   Paste events: {len(state['paste_history'])}")
        
        # Check which pastes are still in the document
        external_chars_remaining = 0
        internal_chars_remaining = 0
        
        for paste_event in state["paste_history"]:
            paste_text = paste_event["text"]
            
            # Classify as internal or external
            last_copy = state.get("last_copy")
            is_internal = False
            if last_copy and abs(paste_event["timestamp"] - last_copy["timestamp"]) < 30:
                if paste_text.strip() in last_copy["text"].strip():
                    is_internal = True
            
            # Check if paste text is still in current document
            if paste_text in current_text:
                if is_internal:
                    internal_chars_remaining += len(paste_text)
                    print(f"   ✓ Internal paste still present: {len(paste_text)} chars")
                else:
                    external_chars_remaining += len(paste_text)
                    print(f"   ✓ External paste still present: {len(paste_text)} chars")
            else:
                print(f"   ✗ Paste was deleted: {len(paste_text)} chars ({'internal' if is_internal else 'external'})")
        
        # Calculate composition from ACTUAL current state
        total_chars = len(current_text)
        if total_chars > 0:
            typed_ratio = max(0, (total_chars - external_chars_remaining - internal_chars_remaining)) / total_chars
            internal_ratio = internal_chars_remaining / total_chars
            external_ratio = external_chars_remaining / total_chars
            
            composition = {
                'typed': typed_ratio,
                'internal': internal_ratio,
                'external': external_ratio
            }
            
            print(f"\n📊 CALCULATED COMPOSITION FROM CURRENT CONTENT:")
            print(f"   Typed: {typed_ratio*100:.1f}%")
            print(f"   Internal: {internal_ratio*100:.1f}%")
            print(f"   External: {external_ratio*100:.1f}%")
        else:
            composition = {'typed': 1.0, 'internal': 0.0, 'external': 0.0}
    else:
        # Fallback to tracker if no current text provided
        composition = tracker.get_composition()
    
    # Calculate scores based on composition
    scoring_engine = ScoringEngine(strict=state.get("strict_mode", False))
    scores = scoring_engine.calculate_scores(composition)
    
    print(f"\n💯 FINAL SCORES:")
    print(f"  Trust: {scores['trust']:.1f}")
    print(f"  Composition: {scores['composition']:.1f}")
    print(f"{'='*70}\n")
    
    # Get external spans for highlighting
    ext_spans_tuples = tracker.get_external_spans()
    # Convert tuples to dicts for Pydantic
    ext_spans = [{"start": start, "end": end} for start, end in ext_spans_tuples]
    
    # Detect integrity flags
    flags = []
    if composition['external'] > 0.3:
        flags.append(f"High external content: {composition['external']*100:.1f}%")
    if composition['external'] > 0.5:
        flags.append("Majority of content is from external sources")
    if composition['typed'] < 0.2:
        flags.append(f"Low typed content: {composition['typed']*100:.1f}%")
    
    return IntegrityResponse(
        scores=scores,
        mix=composition,
        flags=flags,
        ext_spans=ext_spans
    )


def process_event(tracker: ContentTracker, event: Event, state: dict) -> None:
    """Process a single event"""
    
    # Use cursor position from event if available, otherwise use state
    cursor_pos = event.from_pos if event.from_pos is not None else state.get("cursor_pos", 0)
    
    print(f"Processing event: {event.t}, cursor_pos: {cursor_pos}")
    
    if event.t == "key":
        # Single character typed
        char = event.k or " "
        tracker.insert_typed(char, cursor_pos)
        state["cursor_pos"] = cursor_pos + 1
        print(f"  Typed '{char}' at pos {cursor_pos}, new cursor: {state['cursor_pos']}")
        
    elif event.t == "enter":
        # Enter key - insert newline
        tracker.insert_typed("\n", cursor_pos)
        state["cursor_pos"] = cursor_pos + 1
        print(f"  Enter at pos {cursor_pos}, new cursor: {state['cursor_pos']}")
        
    elif event.t == "backspace":
        # Delete one character before cursor
        if cursor_pos > 0:
            # Get what we're deleting
            deleted_char = tracker.current_text[cursor_pos-1:cursor_pos] if cursor_pos <= len(tracker.current_text) else ''
            tracker.delete_range(cursor_pos - 1, cursor_pos)
            state["cursor_pos"] = cursor_pos - 1
            print(f"  ⌫ Backspace at pos {cursor_pos}")
            print(f"    Deleted: '{deleted_char}'")
            print(f"    Remaining text length: {len(tracker.current_text)}")
            print(f"    Remaining segments: {len(tracker.segments)}")
            
    elif event.t == "delete":
        # Delete one character after cursor
        if cursor_pos < len(tracker.current_text):
            deleted_char = tracker.current_text[cursor_pos:cursor_pos+1]
            tracker.delete_range(cursor_pos, cursor_pos + 1)
            print(f"  ⌦ Delete at pos {cursor_pos}")
            print(f"    Deleted: '{deleted_char}'")
            print(f"    Remaining text length: {len(tracker.current_text)}")
            print(f"    Remaining segments: {len(tracker.segments)}")
        
    elif event.t == "paste":
        # Handle paste event
        text = event.snippet or (" " * (event.len or 0))
        
        # Check if it's internal (from recent copy)
        last_copy = state.get("last_copy")
        is_internal = False
        
        if last_copy and (event.ts - last_copy["timestamp"] < 30):  # Within 30 seconds
            # Check if paste text matches copied text (or starts with it)
            if text.strip() and last_copy["text"].strip():
                if text.strip() == last_copy["text"].strip():
                    is_internal = True
        
        paste_type = "internal" if is_internal else "external"
        tracker.insert_paste(text, cursor_pos, paste_type)
        state["cursor_pos"] = cursor_pos + len(text)
        print(f"  Paste ({paste_type}) {len(text)} chars at pos {cursor_pos}")
        
    elif event.t == "copy":
        # Track what was copied - use snippet if provided
        text = event.snippet or ""
        if not text and event.from_pos is not None and event.to_pos is not None:
            # Try to extract from current text if no snippet
            try:
                text = tracker.current_text[event.from_pos:event.to_pos]
            except:
                text = ""
        
        if text:
            state["last_copy"] = {
                "text": text,
                "from_pos": event.from_pos,
                "to_pos": event.to_pos,
                "timestamp": event.ts
            }
            print(f"  Copy: saved '{text[:50]}...' ({len(text)} chars)")
            
    elif event.t == "cut":
        # Cut is copy + delete
        text = event.snippet or ""
        if not text and event.from_pos is not None and event.to_pos is not None:
            try:
                text = tracker.current_text[event.from_pos:event.to_pos]
            except:
                text = ""
        
        if text:
            state["last_copy"] = {
                "text": text,
                "from_pos": event.from_pos,
                "to_pos": event.to_pos,
                "timestamp": event.ts
            }
            print(f"  Cut: saved and deleting '{text[:50]}...' ({len(text)} chars)")
        
        # Delete the cut content
        if event.from_pos is not None and event.to_pos is not None:
            tracker.delete_range(event.from_pos, event.to_pos)
            state["cursor_pos"] = event.from_pos
            
    elif event.t == "sel":
        # Selection change - update cursor position
        if event.from_pos is not None:
            state["cursor_pos"] = event.from_pos
            print(f"  Selection changed to pos {event.from_pos}")
    
    # Log current state
    content_preview = tracker.current_text[:100] if len(tracker.current_text) <= 100 else tracker.current_text[:100] + "..."
    print(f"  Current text ({len(tracker.current_text)} chars): '{content_preview}'")


@router.get("/status")
async def get_status(
    session_id: str,
    doc_id: Optional[str] = None
) -> IntegrityResponse:
    """Get current integrity status for a session"""
    
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    state = active_sessions[session_id]
    tracker = state["tracker"]
    
    # Calculate current composition
    composition = tracker.get_composition()
    
    # Calculate scores
    scoring_engine = ScoringEngine(strict=state.get("strict_mode", False))
    scores = scoring_engine.calculate_scores(composition)
    
    # Get external spans and convert tuples to dicts
    ext_spans_tuples = tracker.get_external_spans()
    ext_spans = [{"start": start, "end": end} for start, end in ext_spans_tuples]
    
    # Generate flags
    flags = []
    if composition['external'] > 0.3:
        flags.append(f"High external content: {composition['external']*100:.1f}%")
    if composition['external'] > 0.5:
        flags.append("Majority of content is from external sources")
    if composition['typed'] < 0.2:
        flags.append(f"Low typed content: {composition['typed']*100:.1f}%")
    
    return IntegrityResponse(
        scores=scores,
        mix=composition,
        flags=flags,
        ext_spans=ext_spans
    )


@router.post("/export/check")
async def check_export(session_id: str, doc_id: str) -> dict:
    """Check if document can be exported based on integrity"""
    
    if session_id not in active_sessions:
        return {"can_export": True, "reason": "No session found"}
    
    state = active_sessions[session_id]
    tracker = state["tracker"]
    composition = tracker.get_composition()
    
    # In strict mode, require high typed content
    if state.get("strict_mode", False):
        if composition['typed'] < 0.7:
            return {
                "can_export": False,
                "reason": f"Insufficient typed content: {composition['typed']*100:.1f}% (minimum 70% required)"
            }
    
    # Always block if too much external content
    if composition['external'] > 0.5:
        return {
            "can_export": False,
            "reason": f"Too much external content: {composition['external']*100:.1f}% (maximum 50% allowed)"
        }
    
    return {
        "can_export": True,
        "reason": "Document meets integrity requirements"
    }
