"""
Draft Evolution Forensics — Process topology analysis for academic integrity.

Computes 9 forensic signals across 3 tiers:
  Tier 1 (Process): 6 signals from current submission snapshots
  Tier 2 (Baseline): 2 signals comparing against prior submissions
  Tier 3 (Linguistic): 1 signal analyzing error patterns vs student baseline

Each signal returns a verdict ("genuine", "review", "suspicious", "insufficient_data")
and a plain-English label for non-technical teachers.
"""

import re
import math
import logging
from collections import Counter
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants — tuned to NEVER punish innocents, only flag with high confidence
# ---------------------------------------------------------------------------
MIN_SNAPSHOTS_FULL = 10        # Minimum for full Tier 1 analysis
SAMPLE_STEP_EDIT_DEPTH = 5     # Diff every Nth snapshot for large sessions
SAMPLE_STEP_STRUCTURE = 50     # Sample every Nth for structure evolution
WPM_SPIKE_THRESHOLD = 120      # Words/min — 80 is normal for fast typists; 120+ is paste-speed
THINKING_PAUSE_LO = 3.0        # Seconds
THINKING_PAUSE_HI = 8.0

# Tier 1 minimum sample sizes (prevent noise on small data)
MIN_EDITS_DIRECTION = 20       # Minimum edit transitions for edit direction verdict
MIN_EDITS_DEPTH = 15           # Minimum classified edits for edit depth verdict
MIN_PAUSES_FOR_VERDICT = 30    # Minimum pause transitions for thinking pause verdict

# Tier 2 thresholds
RHYTHM_GENUINE = 0.70
RHYTHM_SUSPICIOUS = 0.30       # Lowered from 0.40 — device/context changes cause drift
RHYTHM_MIN_PRIOR = 3           # Need 3+ prior submissions for suspicious verdict
VOCAB_NOVEL_GENUINE = 0.08     # <8% novel words (raised from 5% — new topics have new vocab)
VOCAB_NOVEL_SUSPICIOUS = 0.25  # >25% novel words (raised from 15% — generous for new topics)
VOCAB_RICHNESS_STD_DEVS = 2.5  # Flag if richness jumps >2.5 std devs
VOCAB_MIN_PRIOR = 3            # Need 3+ prior submissions for suspicious verdict

# Tier 3 thresholds
ERROR_CLEAN_THRESHOLD = 0.10   # <10% of baseline = suspiciously clean (lowered from 25%)
ERROR_DIFFERENT_THRESHOLD = 3.0 # >300% = different writer (raised from 200%)
ERROR_MIN_BASELINE_RATE = 2.0  # Baseline must have ≥2 errors/500 words to flag "clean"
ERROR_MIN_PRIOR = 3            # Need 3+ prior submissions for suspicious verdict

# Forensics cache version — increment when algorithm changes to invalidate stale caches
FORENSICS_VERSION = 2


# ═══════════════════════════════════════════════════════════════════════════
# TIER 1: PROCESS SIGNALS (snapshot-only)
# ═══════════════════════════════════════════════════════════════════════════

def _signal_effort_ratio(snapshots: list[dict]) -> dict:
    """Signal 1: Writing Effort Ratio — keystrokes vs final document length."""
    last = snapshots[-1]
    keystrokes = last.get("typedCount", 0)
    doc_length = len(last.get("plaintext", ""))
    if doc_length == 0:
        return {"ratio": 0, "keystrokes": keystrokes, "doc_length": 0,
                "verdict": "insufficient_data", "label": "No document content"}

    ratio = round(keystrokes / doc_length, 2)
    if ratio > 2.0:
        verdict, label = "genuine", f"High writing effort — {ratio}x revision ratio"
    elif ratio >= 0.5:
        verdict, label = "review", f"Moderate effort — {ratio}x ratio"
    else:
        verdict, label = "suspicious", f"Low effort — {ratio}x ratio (may indicate pasted content or voice dictation)"
    return {"ratio": ratio, "keystrokes": keystrokes, "doc_length": doc_length,
            "verdict": verdict, "label": label}


def _signal_content_arrival(snapshots: list[dict]) -> dict:
    """Signal 2: Content Arrival Timeline — words per minute over session."""
    if len(snapshots) < 2:
        return {"timeline": [], "spikes": 0, "verdict": "insufficient_data",
                "label": "Not enough data"}

    t0 = snapshots[0].get("timestamp", 0)
    t_end = snapshots[-1].get("timestamp", 0)
    duration_ms = t_end - t0
    if duration_ms <= 0:
        return {"timeline": [], "spikes": 0, "verdict": "insufficient_data",
                "label": "Session too short"}

    # Divide into 1-minute windows
    window_ms = 60_000
    timeline = []
    spikes = 0
    si = 0  # snapshot index
    window_idx = 0

    t = t0
    while t < t_end:
        window_end = t + window_ms
        # Find wordCount at start and end of window
        wc_start = 0
        wc_end = 0
        # Track paste count delta to cross-reference
        pc_start = 0
        pc_end = 0
        for i in range(si, len(snapshots)):
            ts = snapshots[i].get("timestamp", 0)
            if ts <= t:
                wc_start = snapshots[i].get("wordCount", 0)
                pc_start = snapshots[i].get("pasteCount", 0)
                si = i
            if ts <= window_end:
                wc_end = snapshots[i].get("wordCount", 0)
                pc_end = snapshots[i].get("pasteCount", 0)
            else:
                break

        wpm = max(0, wc_end - wc_start)
        paste_in_window = pc_end > pc_start
        # Skip first window (draft restore on mount can create false spike)
        # Only flag as spike if paste event also occurred in this window
        is_spike = (wpm > WPM_SPIKE_THRESHOLD and window_idx > 0 and paste_in_window)
        if is_spike:
            spikes += 1
        timeline.append({"t": round(t - t0), "wpm": wpm, "spike": is_spike})
        t = window_end
        window_idx += 1

    if spikes == 0:
        verdict, label = "genuine", "Steady writing pace, no abnormal bursts"
    elif spikes <= 2:
        verdict, label = "review", f"{spikes} high-speed burst(s) with paste events detected"
    else:
        verdict, label = "suspicious", f"{spikes} paste-speed bursts above {WPM_SPIKE_THRESHOLD} WPM"
    return {"timeline": timeline, "spikes": spikes, "verdict": verdict, "label": label}


def _signal_pause_patterns(snapshots: list[dict]) -> dict:
    """Signal 3: Thinking Pauses — distribution of inter-edit pauses."""
    buckets = {"under_1s": 0, "1_3s": 0, "3_8s": 0, "8_30s": 0, "over_30s": 0}
    prev_ts = None
    prev_text = None
    total = 0

    for snap in snapshots:
        text = snap.get("plaintext", "")
        ts = snap.get("timestamp", 0)
        if prev_ts is not None and text != prev_text:
            gap = (ts - prev_ts) / 1000.0  # seconds
            if gap < 1:
                buckets["under_1s"] += 1
            elif gap < 3:
                buckets["1_3s"] += 1
            elif gap < 8:
                buckets["3_8s"] += 1
            elif gap < 30:
                buckets["8_30s"] += 1
            else:
                buckets["over_30s"] += 1
            total += 1
        prev_ts = ts
        prev_text = text

    if total < MIN_PAUSES_FOR_VERDICT:
        return {"buckets": buckets, "thinking_ratio": 0,
                "verdict": "insufficient_data",
                "label": f"Only {total} edit transitions — need {MIN_PAUSES_FOR_VERDICT}+ for analysis"}

    thinking_ratio = round(buckets["3_8s"] / total, 2)
    if thinking_ratio > 0.15:
        verdict = "genuine"
        label = f"{int(thinking_ratio * 100)}% thinking pauses — consistent with real-time composition"
    elif thinking_ratio >= 0.02:
        verdict = "review"
        label = f"{int(thinking_ratio * 100)}% thinking pauses — may indicate prepared/outlined writing or fast composition"
    else:
        verdict = "suspicious"
        label = f"Only {int(thinking_ratio * 100)}% thinking pauses — very few cognitive breaks detected"
    return {"buckets": buckets, "thinking_ratio": thinking_ratio,
            "verdict": verdict, "label": label}


def _signal_edit_direction(snapshots: list[dict]) -> dict:
    """Signal 4: Edit Direction — forward vs backward edits (retroactive coherence)."""
    forward = 0
    backward = 0
    frontier = 0  # highest written position
    prev_text = ""
    prev_cursor_valid = False

    for snap in snapshots:
        text = snap.get("plaintext", "")
        cursor = snap.get("cursorPos", 0)
        if text != prev_text and prev_cursor_valid:
            if cursor < frontier and frontier > 0:
                backward += 1
            else:
                forward += 1
        # Update frontier
        if len(text) > frontier:
            frontier = len(text)
        prev_text = text
        prev_cursor_valid = cursor > 0

    total = forward + backward
    if total < MIN_EDITS_DIRECTION:
        return {"forward": forward, "backward": backward, "backward_ratio": 0,
                "verdict": "insufficient_data",
                "label": f"Only {total} edits — need {MIN_EDITS_DIRECTION}+ for direction analysis"}

    ratio = round(backward / total, 2)
    if ratio > 0.25:
        verdict = "genuine"
        label = f"{int(ratio * 100)}% backward edits — revisited earlier sections"
    elif ratio >= 0.05:
        verdict = "review"
        label = f"{int(ratio * 100)}% backward edits — may indicate outlined or sequential writing style"
    else:
        verdict = "suspicious"
        label = f"Only {int(ratio * 100)}% backward edits — almost entirely linear writing"
    return {"forward": forward, "backward": backward, "backward_ratio": ratio,
            "verdict": verdict, "label": label}


def _signal_edit_depth(snapshots: list[dict]) -> dict:
    """Signal 5: Edit Depth — surface vs structural vs semantic edits."""
    surface = 0
    structural = 0
    semantic = 0

    step = SAMPLE_STEP_EDIT_DEPTH if len(snapshots) > 1000 else 1
    prev_text = snapshots[0].get("plaintext", "")

    for i in range(step, len(snapshots), step):
        curr_text = snapshots[i].get("plaintext", "")
        if curr_text == prev_text:
            prev_text = curr_text
            continue

        # Quick diff: compare character-level change size
        len_diff = abs(len(curr_text) - len(prev_text))

        # Check if change crosses paragraph boundary
        prev_paras = prev_text.split("\n")
        curr_paras = curr_text.split("\n")
        para_count_changed = len(prev_paras) != len(curr_paras)

        # New paragraph or large insertion in new location = semantic
        if para_count_changed and len_diff > 100:
            semantic += 1
        # Crosses sentence boundary or moderate change = structural
        elif len_diff >= 15 or para_count_changed:
            structural += 1
        # Small change within same structure = surface
        else:
            surface += 1

        prev_text = curr_text

    total = surface + structural + semantic
    if total < MIN_EDITS_DEPTH:
        return {"surface": surface, "structural": structural, "semantic": semantic,
                "verdict": "insufficient_data",
                "label": f"Only {total} edits classified — need {MIN_EDITS_DEPTH}+ for depth analysis"}

    surface_pct = round(surface / total, 2)
    semantic_pct = round(semantic / total, 2)

    # Time-weighted analysis: check if surface edits cluster in the final 30% of session
    # (proofreading pass) vs being distributed throughout (humanizer pattern)
    late_surface = 0
    late_total = 0
    cutoff_idx = int(len(snapshots) * 0.7)
    prev_text_tw = snapshots[max(0, cutoff_idx - step)].get("plaintext", "") if cutoff_idx > 0 else ""
    for i in range(cutoff_idx, len(snapshots), step):
        curr_text_tw = snapshots[i].get("plaintext", "")
        if curr_text_tw != prev_text_tw:
            ld = abs(len(curr_text_tw) - len(prev_text_tw))
            late_total += 1
            if ld < 15 and len(curr_text_tw.split("\n")) == len(prev_text_tw.split("\n")):
                late_surface += 1
        prev_text_tw = curr_text_tw

    # If most surface edits are in the final 30%, it's a proofreading pass — not suspicious
    is_proofreading_pass = (late_total > 0 and late_surface / max(1, late_total) > 0.7
                            and surface > 0 and late_surface / surface > 0.5)

    if semantic_pct >= 0.15 and surface_pct < 0.80:
        verdict = "genuine"
        label = "Mixed edit types including new ideas"
    elif surface_pct >= 0.90 and not is_proofreading_pass:
        verdict = "suspicious"
        label = f"{int(surface_pct * 100)}% surface-level edits throughout — almost no structural or semantic changes"
    elif surface_pct >= 0.90 and is_proofreading_pass:
        verdict = "review"
        label = f"{int(surface_pct * 100)}% surface edits — but concentrated in final proofreading phase"
    else:
        verdict = "review"
        label = f"Mostly surface edits ({int(surface_pct * 100)}%) — may reflect a proofreading pass"
    return {"surface": surface, "structural": structural, "semantic": semantic,
            "verdict": verdict, "label": label}


def _signal_structure_evolution(snapshots: list[dict]) -> dict:
    """Signal 6: Structure Evolution — how paragraph organization changes over time."""
    step = SAMPLE_STEP_STRUCTURE if len(snapshots) > 500 else max(1, len(snapshots) // 20)
    if step < 1:
        step = 1

    timeline = []
    for i in range(0, len(snapshots), step):
        text = snapshots[i].get("plaintext", "")
        ts = snapshots[i].get("timestamp", 0)
        # Split into paragraphs (double newline or single newline with content)
        paras = [p.strip() for p in re.split(r'\n\s*\n|\n', text) if p.strip()]
        para_count = max(1, len(paras))
        lengths = [len(p) for p in paras] if paras else [0]
        mean_len = sum(lengths) / len(lengths)
        std_dev = math.sqrt(sum((l - mean_len) ** 2 for l in lengths) / len(lengths)) if len(lengths) > 1 else 0
        timeline.append({
            "t": round(ts - snapshots[0].get("timestamp", 0)),
            "paras": para_count,
            "std": round(std_dev, 1)
        })

    if len(timeline) < 3:
        return {"timeline": timeline, "trend": "unknown",
                "verdict": "insufficient_data", "label": "Not enough data for structure analysis"}

    # Determine trend: is std_dev converging (decreasing) or flat?
    early_std = sum(t["std"] for t in timeline[:len(timeline)//3]) / max(1, len(timeline)//3)
    late_std = sum(t["std"] for t in timeline[-len(timeline)//3:]) / max(1, len(timeline)//3)
    first_paras = timeline[0]["paras"]
    last_paras = timeline[-1]["paras"]

    if early_std > late_std * 1.3 or last_paras > first_paras * 1.5:
        trend = "converging"
        verdict = "genuine"
        label = "Document structure evolved during writing"
    elif early_std < 3 and late_std < 3 and first_paras > 3:
        # Stricter: std < 3 (not 5), and > 3 paras (not 2)
        # Flat structure CAN be legitimate (outlined writing) — only flag as review, not suspicious
        trend = "flat"
        verdict = "review"
        label = "Document structure was stable from the start — may indicate pre-planned outline"
    else:
        trend = "moderate"
        verdict = "genuine"
        label = "Normal structural progression during writing"
    return {"timeline": timeline, "trend": trend, "verdict": verdict, "label": label}


# ═══════════════════════════════════════════════════════════════════════════
# TIER 2: BASELINE SIGNALS (cross-submission comparison)
# ═══════════════════════════════════════════════════════════════════════════

def _compute_rhythm_fingerprint(snapshots: list[dict]) -> Optional[dict]:
    """Compute a typing rhythm fingerprint from a snapshot array."""
    if len(snapshots) < 5:
        return None

    pauses = []
    wpms = []
    burst_lengths = []
    current_burst = 0
    prev_ts = None
    prev_text = None

    for snap in snapshots:
        text = snap.get("plaintext", "")
        ts = snap.get("timestamp", 0)
        wc = snap.get("wordCount", 0)

        if prev_ts is not None and text != prev_text:
            gap = (ts - prev_ts) / 1000.0
            pauses.append(gap)
            if gap > THINKING_PAUSE_LO:
                if current_burst > 0:
                    burst_lengths.append(current_burst)
                current_burst = 0
            else:
                current_burst += 1

        prev_ts = ts
        prev_text = text

    if current_burst > 0:
        burst_lengths.append(current_burst)

    # Compute WPM from word count changes over time windows
    if len(snapshots) >= 2:
        duration_min = (snapshots[-1].get("timestamp", 0) - snapshots[0].get("timestamp", 0)) / 60000
        if duration_min > 0:
            total_words = snapshots[-1].get("wordCount", 0)
            wpms.append(total_words / duration_min)

    if not pauses:
        return None

    # Pause bucket distribution (normalized)
    total_pauses = len(pauses)
    bucket_dist = [0.0] * 5
    for p in pauses:
        if p < 1:
            bucket_dist[0] += 1
        elif p < 3:
            bucket_dist[1] += 1
        elif p < 8:
            bucket_dist[2] += 1
        elif p < 30:
            bucket_dist[3] += 1
        else:
            bucket_dist[4] += 1
    bucket_dist = [b / total_pauses for b in bucket_dist]

    median_pause = sorted(pauses)[len(pauses) // 2]
    mean_burst = sum(burst_lengths) / len(burst_lengths) if burst_lengths else 0
    mean_wpm = wpms[0] if wpms else 0

    return {
        "median_pause": round(median_pause, 3),
        "mean_burst": round(mean_burst, 2),
        "mean_wpm": round(mean_wpm, 2),
        "bucket_dist": [round(b, 3) for b in bucket_dist],
    }


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def _fingerprint_to_vector(fp: dict) -> list[float]:
    """Flatten a rhythm fingerprint into a comparable vector."""
    return [
        fp["median_pause"],
        fp["mean_burst"],
        fp["mean_wpm"] / 50.0,  # normalize WPM
    ] + fp["bucket_dist"]


async def _signal_cognitive_rhythm(
    current_snapshots: list[dict],
    student_id: str,
    current_submission_id: str,
    snapshots_collection,
) -> dict:
    """Signal 7: Cognitive Rhythm Match — compare typing rhythm to prior sessions."""
    current_fp = _compute_rhythm_fingerprint(current_snapshots)
    if not current_fp:
        return {"similarity": 0, "prior_count": 0,
                "verdict": "insufficient_data",
                "label": "Not enough data to compute rhythm"}

    # Fetch prior snapshot docs for this student
    prior_docs = await snapshots_collection.find(
        {"student_id": student_id, "submission_id": {"$ne": current_submission_id, "$exists": True}},
        {"snapshots": 1}
    ).to_list(length=20)

    prior_fps = []
    for doc in prior_docs:
        snaps = doc.get("snapshots", [])
        # Reconstruct plaintext fill-forward
        _reconstruct_plaintext(snaps)
        fp = _compute_rhythm_fingerprint(snaps)
        if fp:
            prior_fps.append(fp)

    if not prior_fps:
        return {"similarity": 0, "prior_count": 0,
                "verdict": "no_baseline",
                "label": "No baseline available yet — this is the student's first analyzed submission"}

    # Average similarity against all prior fingerprints
    current_vec = _fingerprint_to_vector(current_fp)
    similarities = [_cosine_similarity(current_vec, _fingerprint_to_vector(fp)) for fp in prior_fps]
    avg_sim = round(sum(similarities) / len(similarities), 2)

    prior_count = len(prior_fps)
    confidence_note = " (low confidence — limited baseline data)" if prior_count < RHYTHM_MIN_PRIOR else ""

    if avg_sim >= RHYTHM_GENUINE:
        verdict = "genuine"
        label = f"Typing rhythm matches prior {prior_count} assignment(s) ({int(avg_sim * 100)}%){confidence_note}"
    elif avg_sim >= RHYTHM_SUSPICIOUS:
        verdict = "review"
        label = f"Typing rhythm partially matches baseline ({int(avg_sim * 100)}%) — may reflect device change, fatigue, or different context{confidence_note}"
    elif prior_count >= RHYTHM_MIN_PRIOR:
        verdict = "suspicious"
        label = f"Typing rhythm differs from prior {prior_count} assignments ({int(avg_sim * 100)}%){confidence_note}"
    else:
        # Not enough baseline data — cap at review, never suspicious
        verdict = "review"
        label = f"Typing rhythm differs ({int(avg_sim * 100)}%) but baseline is limited ({prior_count} prior submission(s))"
    return {"similarity": avg_sim, "prior_count": prior_count,
            "verdict": verdict, "label": label}


def _extract_words(text: str) -> list[str]:
    """Extract lowercase words from text, stripping punctuation."""
    return re.findall(r"[a-z']+", text.lower())


def _extract_sentences(text: str) -> list[str]:
    """Split text into sentences."""
    return [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]


async def _signal_vocabulary_drift(
    current_text: str,
    student_id: str,
    current_submission_id: str,
    submissions_collection,
) -> dict:
    """Signal 8: Vocabulary Drift — detect sudden vocabulary changes."""
    current_words = _extract_words(current_text)
    if not current_words:
        return {"novel_words": 0, "novel_pct": 0, "richness": 0, "baseline_richness": 0,
                "avg_sentence_len": 0, "baseline_avg_sentence_len": 0,
                "verdict": "insufficient_data", "label": "No text to analyze"}

    current_word_set = set(current_words)
    current_richness = round(len(current_word_set) / len(current_words), 3) if current_words else 0
    current_sentences = _extract_sentences(current_text)
    current_avg_sent = round(sum(len(s.split()) for s in current_sentences) / max(1, len(current_sentences)), 1)

    # Fetch prior submissions
    prior_subs = await submissions_collection.find(
        {"student_id": student_id, "submission_id": {"$ne": current_submission_id},
         "status": {"$in": ["submitted", "graded", "returned"]}},
        {"content": 1, "content_html": 1}
    ).to_list(length=20)

    if not prior_subs:
        return {"novel_words": 0, "novel_pct": 0, "richness": current_richness,
                "baseline_richness": 0, "avg_sentence_len": current_avg_sent,
                "baseline_avg_sentence_len": 0,
                "verdict": "no_baseline",
                "label": "No baseline available yet — need prior submissions"}

    # Build historical vocabulary
    all_prior_words = set()
    richness_values = []
    sent_lens = []
    for sub in prior_subs:
        text = sub.get("content", "") or ""
        # Strip HTML tags if content_html was used
        text = re.sub(r'<[^>]+>', ' ', text)
        words = _extract_words(text)
        if not words:
            continue
        all_prior_words.update(words)
        richness_values.append(len(set(words)) / len(words))
        sentences = _extract_sentences(text)
        if sentences:
            sent_lens.append(sum(len(s.split()) for s in sentences) / len(sentences))

    if not all_prior_words:
        return {"novel_words": 0, "novel_pct": 0, "richness": current_richness,
                "baseline_richness": 0, "avg_sentence_len": current_avg_sent,
                "baseline_avg_sentence_len": 0,
                "verdict": "no_baseline", "label": "Prior submissions had no analyzable text"}

    # Novel words: in current but NOT in any prior submission
    novel = current_word_set - all_prior_words
    # Filter out very short/common words
    novel = {w for w in novel if len(w) > 3}
    novel_pct = round(len(novel) / len(current_word_set), 3) if current_word_set else 0

    baseline_richness = round(sum(richness_values) / len(richness_values), 3) if richness_values else 0
    baseline_sent_len = round(sum(sent_lens) / len(sent_lens), 1) if sent_lens else 0

    # Check richness deviation
    richness_std = 0
    if len(richness_values) > 1:
        mean_r = sum(richness_values) / len(richness_values)
        richness_std = math.sqrt(sum((r - mean_r) ** 2 for r in richness_values) / len(richness_values))

    richness_deviation = abs(current_richness - baseline_richness) / max(richness_std, 0.01)

    prior_sub_count = len(prior_subs)

    if novel_pct < VOCAB_NOVEL_GENUINE and richness_deviation < VOCAB_RICHNESS_STD_DEVS:
        verdict = "genuine"
        label = f"{len(novel)} new words ({int(novel_pct * 100)}%) — within normal range"
    elif (novel_pct > VOCAB_NOVEL_SUSPICIOUS or richness_deviation > VOCAB_RICHNESS_STD_DEVS) and prior_sub_count >= VOCAB_MIN_PRIOR:
        verdict = "suspicious"
        label = f"{len(novel)} new words ({int(novel_pct * 100)}%) — significant vocabulary shift (may reflect new topic or learning)"
    elif novel_pct > VOCAB_NOVEL_SUSPICIOUS and prior_sub_count < VOCAB_MIN_PRIOR:
        # Not enough baseline — cap at review
        verdict = "review"
        label = f"{len(novel)} new words ({int(novel_pct * 100)}%) — elevated, but only {prior_sub_count} prior submission(s) for comparison"
    else:
        verdict = "review"
        label = f"{len(novel)} new words ({int(novel_pct * 100)}%) — slightly elevated, may reflect new topic"

    return {
        "novel_words": len(novel), "novel_pct": novel_pct,
        "richness": current_richness, "baseline_richness": baseline_richness,
        "avg_sentence_len": current_avg_sent, "baseline_avg_sentence_len": baseline_sent_len,
        "verdict": verdict, "label": label,
    }


# ═══════════════════════════════════════════════════════════════════════════
# TIER 3: LINGUISTIC SIGNAL (error DNA)
# ═══════════════════════════════════════════════════════════════════════════

# Common misspelling patterns (regex-based)
_MISSPELLING_PATTERNS = [
    r'\bdefin[ai]tely\b',     # definitely
    r'\boccur[ae]nce\b',      # occurrence
    r'\bsep[ea]r[ea]te\b',    # separate
    r'\baccommod[ea]te\b',    # accommodate
    r'\bnecess[ae]ry\b',      # necessary
    r'\brecieve\b',           # receive
    r'\bwich\b',              # which
    r'\bteh\b',               # the
    r'\badn\b',               # and
    r'\bthier\b',             # their
    r'\byuo\b',               # you
    r'\bwoudl\b',             # would
    r'\bcoudl\b',             # could
    r'\bshoudl\b',            # should
]

_GRAMMAR_PATTERNS = [
    (r',\s*(?:and|but|or|so)\s+[a-z]', "comma_splice"),          # comma before conjunction (potential splice)
    (r'\b(a)\s+[aeiou]', "article_error"),                        # "a" before vowel sound
    (r'\b(\w+)\s+\1\b', "repeated_word"),                         # repeated words
    (r'[.!?]\s*[a-z]', "capitalization"),                         # lowercase after sentence end
    (r'\bi\b', "lowercase_i"),                                     # lowercase "i" (not "I")
    (r'(?<![.!?])\s*\n\s*[A-Z]', "fragment"),                    # potential sentence fragment
]


def _count_errors(text: str) -> dict:
    """Count error patterns in text. Returns error counts by type + total rate."""
    if not text or len(text) < 50:
        return {"total": 0, "rate_per_500": 0, "types": {}}

    # Strip HTML
    clean = re.sub(r'<[^>]+>', ' ', text)
    word_count = len(clean.split())
    if word_count < 10:
        return {"total": 0, "rate_per_500": 0, "types": {}}

    errors = {}
    total = 0

    # Misspellings
    misspelling_count = 0
    for pattern in _MISSPELLING_PATTERNS:
        matches = len(re.findall(pattern, clean, re.IGNORECASE))
        misspelling_count += matches
    if misspelling_count:
        errors["misspellings"] = misspelling_count
        total += misspelling_count

    # Grammar patterns
    for pattern, name in _GRAMMAR_PATTERNS:
        matches = len(re.findall(pattern, clean))
        if matches:
            errors[name] = matches
            total += matches

    rate = round(total / word_count * 500, 2) if word_count > 0 else 0
    return {"total": total, "rate_per_500": rate, "types": errors}


async def _signal_error_dna(
    current_text: str,
    student_id: str,
    current_submission_id: str,
    submissions_collection,
) -> dict:
    """Signal 9: Error DNA Match — compare error patterns to student baseline."""
    current_errors = _count_errors(current_text)
    if current_errors["total"] == 0 and len(current_text) < 200:
        return {"current_rate": 0, "baseline_rate": 0, "deviation": 0,
                "verdict": "insufficient_data", "label": "Not enough text to analyze errors"}

    # Fetch prior submissions
    prior_subs = await submissions_collection.find(
        {"student_id": student_id, "submission_id": {"$ne": current_submission_id},
         "status": {"$in": ["submitted", "graded", "returned"]}},
        {"content": 1, "content_html": 1}
    ).to_list(length=20)

    if not prior_subs:
        return {"current_rate": current_errors["rate_per_500"], "baseline_rate": 0, "deviation": 0,
                "current_types": current_errors["types"],
                "verdict": "no_baseline",
                "label": "No baseline available yet — need prior submissions"}

    # Build baseline error rate
    prior_rates = []
    for sub in prior_subs:
        text = sub.get("content", "") or ""
        text = re.sub(r'<[^>]+>', ' ', text)
        if len(text) < 100:
            continue
        errors = _count_errors(text)
        prior_rates.append(errors["rate_per_500"])

    if not prior_rates:
        return {"current_rate": current_errors["rate_per_500"], "baseline_rate": 0, "deviation": 0,
                "current_types": current_errors["types"],
                "verdict": "no_baseline", "label": "Prior submissions too short for error analysis"}

    baseline_rate = round(sum(prior_rates) / len(prior_rates), 2)
    current_rate = current_errors["rate_per_500"]

    if baseline_rate == 0:
        deviation = 0 if current_rate == 0 else 1.0
    else:
        deviation = round(abs(current_rate - baseline_rate) / baseline_rate, 2)

    prior_count = len(prior_rates)
    confidence_note = " (limited baseline)" if prior_count < ERROR_MIN_PRIOR else ""

    # Only flag "suspiciously clean" if baseline is meaningful AND we have enough data
    is_suspiciously_clean = (
        baseline_rate >= ERROR_MIN_BASELINE_RATE
        and current_rate < baseline_rate * ERROR_CLEAN_THRESHOLD
        and prior_count >= ERROR_MIN_PRIOR
    )
    is_different_writer = (
        baseline_rate > 0
        and current_rate > baseline_rate * ERROR_DIFFERENT_THRESHOLD
        and prior_count >= ERROR_MIN_PRIOR
    )

    if is_suspiciously_clean:
        verdict = "suspicious"
        label = f"Error rate {current_rate}/500 words (baseline: {baseline_rate}) — unusually clean, may indicate grammar tools or external authorship{confidence_note}"
    elif is_different_writer:
        verdict = "suspicious"
        label = f"Error rate {current_rate}/500 words (baseline: {baseline_rate}) — significantly different error pattern{confidence_note}"
    elif deviation < 0.50:
        verdict = "genuine"
        label = f"Error rate {current_rate}/500 words (baseline: {baseline_rate}) — consistent{confidence_note}"
    elif prior_count < ERROR_MIN_PRIOR:
        # Not enough data — never suspicious
        verdict = "review"
        label = f"Error rate {current_rate}/500 words (baseline: {baseline_rate}) — deviation noted but only {prior_count} prior submission(s){confidence_note}"
    else:
        verdict = "review"
        label = f"Error rate {current_rate}/500 words (baseline: {baseline_rate}) — some deviation, may reflect proofreading or grammar tools{confidence_note}"

    return {
        "current_rate": current_rate, "baseline_rate": baseline_rate,
        "deviation": deviation, "current_types": current_errors["types"],
        "verdict": verdict, "label": label,
    }


# ═══════════════════════════════════════════════════════════════════════════
# BONUS DETECTION SIGNALS (catch sophisticated cheating)
# ═══════════════════════════════════════════════════════════════════════════

def _signal_document_birth(snapshots: list[dict]) -> dict:
    """Detect instant bulk content appearance (paste or draft restore).
    If >200 words appear between two consecutive snapshots that are <5s apart,
    and pasteCount increased, this is a bulk insertion."""
    bulk_events = []
    for i in range(1, len(snapshots)):
        prev = snapshots[i - 1]
        curr = snapshots[i]
        ts_gap = (curr.get("timestamp", 0) - prev.get("timestamp", 0)) / 1000.0
        wc_delta = (curr.get("wordCount", 0) or 0) - (prev.get("wordCount", 0) or 0)
        pc_delta = (curr.get("pasteCount", 0) or 0) - (prev.get("pasteCount", 0) or 0)

        if wc_delta > 50 and ts_gap < 5.0 and pc_delta > 0:
            bulk_events.append({
                "words_added": wc_delta,
                "time_gap_s": round(ts_gap, 1),
                "at_pct": round(i / len(snapshots) * 100),
            })

    if not bulk_events:
        return {"events": [], "verdict": "genuine",
                "label": "No bulk content insertions detected"}

    total_bulk_words = sum(e["words_added"] for e in bulk_events)
    final_words = snapshots[-1].get("wordCount", 1) or 1
    bulk_pct = round(total_bulk_words / final_words * 100)

    if bulk_pct > 60:
        verdict = "suspicious"
        label = f"{len(bulk_events)} bulk insertion(s) — {bulk_pct}% of final document appeared via paste"
    elif bulk_pct > 30:
        verdict = "review"
        label = f"{len(bulk_events)} bulk insertion(s) — {bulk_pct}% of content appeared instantly"
    else:
        verdict = "review"
        label = f"Minor bulk insertion ({bulk_pct}% of content) — may be notes or draft restore"
    return {"events": bulk_events, "bulk_pct": bulk_pct,
            "verdict": verdict, "label": label}


def _signal_delete_then_paste(snapshots: list[dict]) -> dict:
    """Detect session manipulation: type garbage, delete all, paste real essay.
    Pattern: wordCount reaches peak, drops >50%, then recovers within a short window."""
    if len(snapshots) < 20:
        return {"detected": False, "verdict": "insufficient_data",
                "label": "Not enough data for pattern analysis"}

    peak_wc = 0
    peak_idx = 0
    drops = []

    for i, snap in enumerate(snapshots):
        wc = snap.get("wordCount", 0) or 0
        if wc > peak_wc:
            peak_wc = wc
            peak_idx = i
        elif peak_wc > 50 and wc < peak_wc * 0.5:
            # Major drop detected — check if content recovers
            for j in range(i, min(i + 50, len(snapshots))):
                recovery_wc = snapshots[j].get("wordCount", 0) or 0
                if recovery_wc > peak_wc * 0.8:
                    # Check if paste event occurred during recovery
                    pc_at_drop = snap.get("pasteCount", 0) or 0
                    pc_at_recovery = snapshots[j].get("pasteCount", 0) or 0
                    if pc_at_recovery > pc_at_drop:
                        drops.append({
                            "drop_at_pct": round(i / len(snapshots) * 100),
                            "peak_words": peak_wc,
                            "drop_to_words": wc,
                            "recovered_words": recovery_wc,
                        })
                    break
            # Reset peak tracking after drop
            peak_wc = wc
            peak_idx = i

    if not drops:
        return {"detected": False, "verdict": "genuine",
                "label": "No delete-then-paste patterns detected"}

    return {"detected": True, "drops": drops,
            "verdict": "suspicious",
            "label": f"Content was deleted and replaced via paste {len(drops)} time(s) — possible session manipulation"}


# ═══════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _reconstruct_plaintext(snapshots: list[dict]) -> None:
    """Fill forward plaintext for delta-compressed snapshots. Mutates in place."""
    prev = ""
    for snap in snapshots:
        if snap.get("plaintext") is not None:
            prev = snap["plaintext"]
        else:
            snap["plaintext"] = prev


def _detect_context_flags(snapshots: list[dict], final_text: str, session_duration_ms: float) -> dict:
    """
    Detect innocent context that explains multiple suspicious signals.
    Returns a dict of detected contexts with their affected signals.
    A single root cause should never trigger multiple independent flags.
    """
    contexts = {}
    word_count = len(final_text.split()) if final_text else 0

    # ── Short document gate ──
    if word_count < 500:
        contexts["short_document"] = {
            "detected": True,
            "label": f"Short document ({word_count} words) — some signals may not be reliable",
            "suppress_signals": ["edit_direction", "edit_depth", "structure_evolution", "error_dna"],
        }

    # ── Short session gate ──
    if session_duration_ms < 600_000:  # < 10 minutes
        contexts["short_session"] = {
            "detected": True,
            "label": f"Short session ({round(session_duration_ms / 60000)}m) — behavioral signals have limited data",
            "suppress_signals": ["pause_patterns", "edit_direction", "cognitive_rhythm"],
        }

    # ── Dictation detection ──
    # Signature: high word count, very low typedCount, very few paste events, uniform timing
    if snapshots:
        final = snapshots[-1]
        typed = final.get("typedCount", 0)
        pastes = final.get("pasteCount", 0)
        doc_len = len(final.get("plaintext", ""))
        if doc_len > 200 and typed < doc_len * 0.3 and pastes < 3:
            # Very little typing relative to content, but also very few pastes
            # This suggests dictation or programmatic input, not paste-from-AI
            contexts["possible_dictation"] = {
                "detected": True,
                "label": "Low keystroke count with few paste events — possible voice dictation or alternative input method",
                "suppress_signals": ["effort_ratio", "pause_patterns", "content_arrival", "cognitive_rhythm"],
            }

    # ── Grammar tool detection ──
    # Signature: many small surface edits in rapid succession (Grammarly accept-all pattern)
    if snapshots and len(snapshots) > 20:
        rapid_small_edits = 0
        for i in range(1, len(snapshots)):
            prev_t = snapshots[i - 1].get("plaintext", "")
            curr_t = snapshots[i].get("plaintext", "")
            ts_gap = (snapshots[i].get("timestamp", 0) - snapshots[i - 1].get("timestamp", 0)) / 1000.0
            if curr_t != prev_t and ts_gap < 2.0 and 0 < abs(len(curr_t) - len(prev_t)) < 20:
                rapid_small_edits += 1
        if rapid_small_edits > 10:
            contexts["possible_grammar_tool"] = {
                "detected": True,
                "label": f"Multiple rapid small corrections detected ({rapid_small_edits}) — may indicate grammar-checking tool",
                "suppress_signals": ["error_dna", "edit_depth"],
            }

    # ── Planned writing detection ──
    # Signature: flat structure + good effort ratio = outlined writing, not paste
    # (Checked during verdict computation by cross-referencing signals)

    return contexts


def _apply_context_suppression(signals: dict, contexts: dict) -> None:
    """
    Apply context-based signal suppression. For each detected context,
    downgrade affected suspicious signals to 'review' (never worse than review
    when an innocent explanation exists). Mutates signals dict in place.
    """
    suppressed_signals = set()
    for ctx_key, ctx in contexts.items():
        if ctx.get("detected"):
            for sig_key in ctx.get("suppress_signals", []):
                suppressed_signals.add(sig_key)

    if not suppressed_signals:
        return

    for tier_key in ("tier1_process", "tier2_baseline", "tier3_linguistic"):
        tier = signals.get(tier_key, {})
        for sig_key, signal in tier.items():
            if sig_key in suppressed_signals and signal.get("verdict") == "suspicious":
                signal["verdict"] = "review"
                signal["label"] = signal.get("label", "") + " [context: innocent explanation detected]"
                signal["suppressed_by_context"] = True


def _deduplicate_correlated_signals(signals: dict) -> None:
    """
    Prevent a single root cause from triggering multiple suspicious verdicts.

    Correlation groups (same root cause):
    - Paste group: effort_ratio, content_arrival, document_birth — all triggered by paste events
    - Rhythm group: pause_patterns, cognitive_rhythm — both affected by device/context changes
    - Style group: vocabulary_drift, error_dna — both affected by topic/tools

    Rule: Within each group, at most 1 signal can contribute as "suspicious" to the overall
    verdict. Others are downgraded to "review" to prevent double-counting.
    """
    CORRELATION_GROUPS = [
        # (group_name, signal_keys_in_order_of_priority)
        ("paste_evidence", ["document_birth", "effort_ratio", "content_arrival"]),
        ("behavioral_rhythm", ["pause_patterns", "cognitive_rhythm"]),
        ("linguistic_style", ["vocabulary_drift", "error_dna"]),
    ]

    for group_name, signal_keys in CORRELATION_GROUPS:
        suspicious_in_group = []
        for sig_key in signal_keys:
            for tier_key in ("tier1_process", "tier2_baseline", "tier3_linguistic"):
                tier = signals.get(tier_key, {})
                if sig_key in tier and tier[sig_key].get("verdict") == "suspicious":
                    suspicious_in_group.append((tier_key, sig_key))

        # Keep the first (highest-priority) suspicious signal, downgrade the rest
        if len(suspicious_in_group) > 1:
            for tier_key, sig_key in suspicious_in_group[1:]:
                signals[tier_key][sig_key]["verdict"] = "review"
                signals[tier_key][sig_key]["label"] += f" [correlated with {suspicious_in_group[0][1]}]"
                signals[tier_key][sig_key]["deduplicated"] = True


def _compute_overall_verdict(signals: dict) -> tuple[str, float]:
    """
    Compute overall verdict using WEIGHTED scoring with innocence protection.

    Design principles:
    1. NEVER punish innocents — require overwhelming evidence for "suspicious"
    2. Weight process signals (Tier 1) higher — they're harder to fake
    3. Discount context-dependent signals (Tier 2/3) — they have many innocent explanations
    4. If 5+ signals are genuine, cap at "review" regardless
    5. If 3+ signals lack data, cap at "review" regardless
    """
    # Signal weights — process signals (harder to fake) weigh more
    SIGNAL_WEIGHTS = {
        # Tier 1 process (high confidence)
        "effort_ratio": 1.5,
        "content_arrival": 1.5,
        "pause_patterns": 1.0,
        "edit_direction": 0.75,
        "edit_depth": 0.75,
        "structure_evolution": 0.5,  # easily explained by outlining
        # Bonus detection (high confidence when triggered)
        "document_birth": 2.0,      # hard evidence of bulk paste
        "delete_then_paste": 2.5,   # strong manipulation signal
        # Tier 2 baseline (context-dependent)
        "cognitive_rhythm": 0.5,     # device/context changes cause drift
        "vocabulary_drift": 0.5,     # topic changes cause drift
        # Tier 3 linguistic (context-dependent)
        "error_dna": 0.5,            # grammar tools and improvement
    }

    genuine_weighted = 0
    suspicious_weighted = 0
    genuine_count = 0
    suspicious_count = 0
    no_data_count = 0
    total_signals = 0

    for tier_key in ("tier1_process", "tier2_baseline", "tier3_linguistic"):
        tier = signals.get(tier_key, {})
        for signal_key, signal in tier.items():
            v = signal.get("verdict", "")
            w = SIGNAL_WEIGHTS.get(signal_key, 0.5)

            if v in ("insufficient_data", "no_baseline", "error"):
                no_data_count += 1
                continue

            total_signals += 1
            if v == "genuine":
                genuine_weighted += w
                genuine_count += 1
            elif v == "suspicious":
                suspicious_weighted += w
                suspicious_count += 1

    if total_signals == 0:
        return "insufficient_data", 0

    # Gate 1: If 3+ signals lack data, not enough evidence for any strong verdict
    if no_data_count >= 3:
        return "review", 0.3

    # Gate 2: Genuine bonus — if 5+ signals are genuine, student is protected
    if genuine_count >= 5:
        confidence = round(genuine_count / total_signals, 2)
        return "genuine", confidence

    # Gate 3: Require high weighted suspicious score for "suspicious" verdict
    # Need weighted score > 4.0 (roughly 4+ strong signals or many weak ones)
    if suspicious_weighted >= 4.0 and suspicious_count >= 4:
        return "suspicious", round(suspicious_weighted / (suspicious_weighted + genuine_weighted + 0.01), 2)

    # Gate 4: Moderate evidence
    if suspicious_count >= 2 or suspicious_weighted >= 2.0:
        return "review", 0.5

    # Default: genuine
    confidence = round(genuine_weighted / (suspicious_weighted + genuine_weighted + 0.01), 2)
    return "genuine", min(confidence, 0.95)


# ═══════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

async def compute_forensics(
    snapshots: list[dict],
    student_id: str,
    submission_id: str,
    snapshots_collection,
    submissions_collection,
) -> dict:
    """
    Compute all 9 forensic signals for a submission.

    Args:
        snapshots: Reconstructed snapshot array (plaintext filled forward)
        student_id: The student who wrote this submission
        submission_id: Current submission ID (excluded from baseline queries)
        snapshots_collection: MongoDB session_snapshots collection
        submissions_collection: MongoDB submissions collection

    Returns:
        Full forensic analysis dict with 3 tiers of signals.
    """
    if not snapshots:
        return {
            "session_duration_ms": 0, "snapshot_count": 0, "prior_submissions_count": 0,
            "overall_verdict": "insufficient_data", "overall_confidence": 0,
            "tier1_process": {}, "tier2_baseline": {}, "tier3_linguistic": {},
        }

    # Reconstruct plaintext for delta-compressed snapshots
    _reconstruct_plaintext(snapshots)

    session_duration = snapshots[-1].get("timestamp", 0) - snapshots[0].get("timestamp", 0)
    has_enough = len(snapshots) >= MIN_SNAPSHOTS_FULL
    final_text = snapshots[-1].get("plaintext", "")
    # Strip HTML if needed
    final_text_clean = re.sub(r'<[^>]+>', ' ', final_text)

    # ── Tier 1: Process signals ──
    tier1 = {
        "effort_ratio": _signal_effort_ratio(snapshots),
        "content_arrival": _signal_content_arrival(snapshots),
    }
    if has_enough:
        tier1["pause_patterns"] = _signal_pause_patterns(snapshots)
        tier1["edit_direction"] = _signal_edit_direction(snapshots)
        tier1["edit_depth"] = _signal_edit_depth(snapshots)
        tier1["structure_evolution"] = _signal_structure_evolution(snapshots)
    else:
        for key in ("pause_patterns", "edit_direction", "edit_depth", "structure_evolution"):
            tier1[key] = {"verdict": "insufficient_data",
                          "label": "Not enough session data for this analysis"}

    # ── Bonus: Cheating pattern detectors ──
    if has_enough:
        tier1["document_birth"] = _signal_document_birth(snapshots)
        tier1["delete_then_paste"] = _signal_delete_then_paste(snapshots)
    else:
        tier1["document_birth"] = {"verdict": "insufficient_data", "label": "Not enough data"}
        tier1["delete_then_paste"] = {"verdict": "insufficient_data", "label": "Not enough data"}

    # ── Tier 2: Baseline signals ──
    tier2 = {}
    try:
        tier2["cognitive_rhythm"] = await _signal_cognitive_rhythm(
            snapshots, student_id, submission_id, snapshots_collection)
    except Exception as e:
        logger.error(f"Cognitive rhythm signal failed: {e}")
        tier2["cognitive_rhythm"] = {"verdict": "error", "label": "Analysis failed"}

    try:
        tier2["vocabulary_drift"] = await _signal_vocabulary_drift(
            final_text_clean, student_id, submission_id, submissions_collection)
    except Exception as e:
        logger.error(f"Vocabulary drift signal failed: {e}")
        tier2["vocabulary_drift"] = {"verdict": "error", "label": "Analysis failed"}

    # ── Tier 3: Linguistic signal ──
    tier3 = {}
    try:
        tier3["error_dna"] = await _signal_error_dna(
            final_text_clean, student_id, submission_id, submissions_collection)
    except Exception as e:
        logger.error(f"Error DNA signal failed: {e}")
        tier3["error_dna"] = {"verdict": "error", "label": "Analysis failed"}

    # ── Count prior submissions used ──
    prior_count = max(
        tier2.get("cognitive_rhythm", {}).get("prior_count", 0),
        0,
    )

    result = {
        "forensics_version": FORENSICS_VERSION,
        "session_duration_ms": round(session_duration),
        "snapshot_count": len(snapshots),
        "prior_submissions_count": prior_count,
        "tier1_process": tier1,
        "tier2_baseline": tier2,
        "tier3_linguistic": tier3,
    }

    # ── INNOCENCE PROTECTION PIPELINE ──
    # Step 1: Detect context flags (short doc, dictation, grammar tools, etc.)
    contexts = _detect_context_flags(snapshots, final_text_clean, session_duration)
    result["context_flags"] = contexts

    # Step 2: Suppress signals that have innocent explanations from detected context
    _apply_context_suppression(result, contexts)

    # Step 3: Deduplicate correlated signals (single root cause → max 1 suspicious)
    _deduplicate_correlated_signals(result)

    # Step 4: Compute final verdict with all protections applied
    overall_verdict, overall_confidence = _compute_overall_verdict(result)
    result["overall_verdict"] = overall_verdict
    result["overall_confidence"] = overall_confidence

    return result
