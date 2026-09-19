"""
CLEAN INTEGRITY TRACKING
================================
1. Store everything in 3 databases:
   - typed_db: All typed characters
   - external_paste_db: All external pastes
   - internal_paste_db: All internal pastes (copy within doc)
   
2. When analyzing: Compare current editor text with these databases
3. Calculate trust based on what matches
"""

from fastapi import APIRouter
from typing import Dict, List
import uuid
import time

from ..models import SessionStartRequest, IngestRequest, IntegrityResponse, IntegrityScores, ContentMix, ExternalSpan

router = APIRouter(prefix="/api/integrity", tags=["integrity"])

# Session storage
sessions: Dict[str, dict] = {}


@router.post("/session/start")
async def start_session(request: SessionStartRequest) -> dict:
    """Start new tracking session"""
    session_id = str(uuid.uuid4())
    
    sessions[session_id] = {
        "typed_db": [],          # Store all typed text
        "external_paste_db": [], # Store all external pastes
        "internal_paste_db": [], # Store all internal pastes
        "copy_buffer": None,     # Last copied text
        "created_at": time.time()
    }
    
    print(f"\n{'='*70}")
    print(f"✅ NEW SESSION CREATED: {session_id[:8]}...")
    print(f"   Databases initialized:")
    print(f"   - typed_db: empty")
    print(f"   - external_paste_db: empty")
    print(f"   - internal_paste_db: empty")
    print(f"{'='*70}\n")
    
    return {
        "session_id": session_id,
        "doc_id": request.doc_id or f"doc-{int(time.time())}"
    }


@router.post("/ingest")
async def ingest_events(request: IngestRequest) -> IntegrityResponse:
    """
    1. Store events in appropriate databases
    2. Analyze current text against databases
    3. Return trust score
    """
    
    # Get or create session
    if request.session_id not in sessions:
        sessions[request.session_id] = {
            "typed_db": [],
            "external_paste_db": [],
            "internal_paste_db": [],
            "copy_buffer": None,
            "created_at": time.time()
        }
    
    session = sessions[request.session_id]
    
    print(f"\n{'='*70}")
    print(f"📥 INGEST REQUEST")
    print(f"   Session: {request.session_id[:8]}...")
    print(f"   Events: {len(request.events)}")
    print(f"   Current text length: {len(request.current_text or '')}")
    print(f"{'='*70}\n")
    
    # STEP 1: STORE EVENTS IN DATABASES
    for event in request.events:
        
        if event.t == "key" and event.k:
            # Store typed character
            session["typed_db"].append(event.k)
            print(f"  ✏️  TYPED: '{event.k}' → typed_db (total: {len(session['typed_db'])} chars)")
            
        elif event.t == "enter":
            # Store newline as typed
            session["typed_db"].append("\n")
            print(f"  ✏️  TYPED: newline → typed_db")
            
        elif event.t == "copy" and event.snippet:
            # Store in copy buffer for internal paste detection
            session["copy_buffer"] = {
                "text": event.snippet,
                "timestamp": event.ts
            }
            print(f"  📄 COPY: {len(event.snippet)} chars → copy_buffer")
            
        elif event.t == "paste" and event.snippet:
            # Determine if internal or external
            is_internal = False
            
            if session["copy_buffer"]:
                time_diff = abs(event.ts - session["copy_buffer"]["timestamp"])
                if time_diff < 30:  # Within 30 seconds
                    # Check if paste matches copied text
                    if event.snippet.strip() in session["copy_buffer"]["text"]:
                        is_internal = True
            
            if is_internal:
                session["internal_paste_db"].append(event.snippet)
                print(f"  📋 PASTE (INTERNAL): {len(event.snippet)} chars → internal_paste_db")
                print(f"     Total internal pastes: {len(session['internal_paste_db'])}")
            else:
                session["external_paste_db"].append(event.snippet)
                print(f"  📋 PASTE (EXTERNAL): {len(event.snippet)} chars → external_paste_db")
                print(f"     Total external pastes: {len(session['external_paste_db'])}")
    
    # STEP 2: ANALYZE CURRENT TEXT AGAINST DATABASES
    current_text = request.current_text or ""
    
    print(f"\n{'🔍'*35}")
    print(f"ANALYZING CURRENT EDITOR CONTENT")
    print(f"{'🔍'*35}")
    print(f"Current text length: {len(current_text)} chars")
    print(f"Current text preview: {current_text[:100]}...")
    print()
    
    print(f"DATABASE CONTENTS:")
    print(f"  Typed DB: {len(session['typed_db'])} characters")
    print(f"  Internal Paste DB: {len(session['internal_paste_db'])} pastes")
    print(f"  External Paste DB: {len(session['external_paste_db'])} pastes")
    print()
    
    # Count how much of current text matches each database
    typed_chars_in_current = 0
    internal_chars_in_current = 0
    external_chars_in_current = 0
    
    # Check EXTERNAL pastes
    for paste_text in session["external_paste_db"]:
        if paste_text in current_text:
            external_chars_in_current += len(paste_text)
            print(f"  ✅ External paste FOUND in current text: {len(paste_text)} chars")
            print(f"     Preview: '{paste_text[:50]}...'")
        else:
            print(f"  ❌ External paste NOT in current (was deleted): {len(paste_text)} chars")
    
    # Check INTERNAL pastes
    for paste_text in session["internal_paste_db"]:
        if paste_text in current_text:
            internal_chars_in_current += len(paste_text)
            print(f"  ✅ Internal paste FOUND in current text: {len(paste_text)} chars")
        else:
            print(f"  ❌ Internal paste NOT in current (was deleted): {len(paste_text)} chars")
    
    # Remaining characters are considered TYPED
    total_chars = len(current_text)
    typed_chars_in_current = max(0, total_chars - external_chars_in_current - internal_chars_in_current)
    
    print(f"\n{'📊'*35}")
    print(f"ANALYSIS RESULTS")
    print(f"{'📊'*35}")
    print(f"Total current text: {total_chars} chars")
    print(f"  - Typed: {typed_chars_in_current} chars")
    print(f"  - Internal paste: {internal_chars_in_current} chars")
    print(f"  - External paste: {external_chars_in_current} chars")
    
    # STEP 3: CALCULATE COMPOSITION AND TRUST SCORE
    if total_chars > 0:
        typed_ratio = typed_chars_in_current / total_chars
        internal_ratio = internal_chars_in_current / total_chars
        external_ratio = external_chars_in_current / total_chars
    else:
        # Empty document = 100% typed (no suspicious content)
        typed_ratio = 1.0
        internal_ratio = 0.0
        external_ratio = 0.0
    
    # Calculate trust score
    # Typed = 100%, Internal = 90%, External = 50%
    trust_score = int(
        typed_ratio * 100 +
        internal_ratio * 90 +
        external_ratio * 50
    )
    
    composition_score = trust_score
    
    print(f"\n{'💯'*35}")
    print(f"FINAL SCORES")
    print(f"{'💯'*35}")
    print(f"Composition:")
    print(f"  - Typed: {typed_ratio*100:.1f}%")
    print(f"  - Internal: {internal_ratio*100:.1f}%")
    print(f"  - External: {external_ratio*100:.1f}%")
    print(f"\nTrust Score: {trust_score}/100")
    print(f"Composition Score: {composition_score}/100")
    print(f"{'='*70}\n")
    
    # Generate flags
    flags = []
    if external_ratio > 0.3:
        flags.append(f"High external content: {external_ratio*100:.1f}%")
    if external_ratio > 0.5:
        flags.append("Majority of content is from external sources")
    if typed_ratio < 0.2 and total_chars > 0:
        flags.append(f"Low typed content: {typed_ratio*100:.1f}%")
    
    return IntegrityResponse(
        scores=IntegrityScores(trust=trust_score, composition=composition_score),
        mix=ContentMix(typed=typed_ratio, internal=internal_ratio, external=external_ratio),
        flags=flags,
        ext_spans=[]
    )

