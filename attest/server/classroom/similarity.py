"""In-class similarity with winnowing fingerprints (Schleimer, Wilkerson & Aiken 2003).

K-token grams are hashed with crc32 (deterministic across processes — Python's hash() is
salted), and one hash per window of W is kept (rightmost minimum), which guarantees that
any run of at least K+W-1 shared tokens produces at least one shared fingerprint. Grams
that also appear in the assignment instructions are excluded so quoting the prompt is not
"similarity". Scores are only ever shown with the matched passages, so teachers judge.
"""
from __future__ import annotations

import json
import re
import time
import zlib
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from .db import Db

TOKEN_RE = re.compile(r"[^\W_]+(?:['’][^\W_]+)?")  # Unicode letters/digits; apostrophe contractions stay one token
MAX_MATCHES = 5
MAX_SEGMENTS = 10


@dataclass
class Fingerprint:
    tokens: List[str]
    spans: List[Tuple[int, int]]          # code-point offsets into the original text
    prints: List[Tuple[int, int]]         # (hash, gram start token index)

    @property
    def hashes(self) -> Set[int]:
        return {h for h, _ in self.prints}


def tokenize(text: str) -> Tuple[List[str], List[Tuple[int, int]]]:
    tokens, spans = [], []
    for m in TOKEN_RE.finditer(text):  # match on the original so offsets stay exact (no casefold length changes)
        tokens.append(m.group(0).lower())
        spans.append((m.start(), m.end()))
    return tokens, spans


def gram_hashes(tokens: List[str], k: int) -> List[int]:
    return [zlib.crc32(" ".join(tokens[i:i + k]).encode("utf-8")) & 0xFFFFFFFF for i in range(len(tokens) - k + 1)]


def winnow(hashes: List[int], w: int) -> List[Tuple[int, int]]:
    if not hashes:
        return []
    if len(hashes) <= w:
        best = max(range(len(hashes)), key=lambda i: (-hashes[i], i))  # rightmost minimum
        return [(hashes[best], best)]
    out: List[Tuple[int, int]] = []
    last: Optional[Tuple[int, int]] = None
    for start in range(len(hashes) - w + 1):
        window = range(start, start + w)
        best = max(window, key=lambda i: (-hashes[i], i))
        pick = (hashes[best], best)
        if pick != last:
            out.append(pick)
            last = pick
    return out


def all_gram_hashes(text: str, k: int) -> Set[int]:
    """Every k-gram of `text` (not winnowed). Used to exclude prompt text: winnowing selects
    different grams depending on context, so excluding only the prompt's own fingerprints leaks."""
    return set(gram_hashes(tokenize(text)[0], k))


def fingerprint(text: str, k: int = 5, w: int = 4, exclude: Optional[Set[int]] = None) -> Fingerprint:
    tokens, spans = tokenize(text)
    prints = winnow(gram_hashes(tokens, k), w)
    if exclude:
        prints = [(h, p) for h, p in prints if h not in exclude]
    return Fingerprint(tokens, spans, prints)


def _segments(a: Fingerprint, b: Fingerprint, shared: Set[int], k: int, a_text: str) -> List[Dict[str, Any]]:
    a_hash_at = {p: h for h, p in a.prints if h in shared}
    b_by_hash: Dict[int, List[int]] = {}
    for h, p in b.prints:
        if h in shared:
            b_by_hash.setdefault(h, []).append(p)
    runs: List[List[int]] = []  # [first gram pos, last gram pos]
    for p in sorted(a_hash_at):
        if runs and p - runs[-1][1] <= k:
            runs[-1][1] = p
        else:
            runs.append([p, p])
    out = []
    for first, last in runs:
        end_tok = min(last + k, len(a.tokens))
        hs = [a_hash_at[p] for p in range(first, last + 1) if p in a_hash_at]
        b_pos = [q for h in hs for q in b_by_hash.get(h, [])]
        b_first, b_end = min(b_pos), min(max(b_pos) + k, len(b.tokens))
        a_start, a_end = a.spans[first][0], a.spans[end_tok - 1][1]
        out.append({"a_start": a_start, "a_end": a_end, "b_start": b.spans[b_first][0], "b_end": b.spans[b_end - 1][1],
                    "text": a_text[a_start:a_end], "grams": len(hs)})
    out.sort(key=lambda s: -(s["a_end"] - s["a_start"]))
    return out[:MAX_SEGMENTS]


def compare(a: Fingerprint, b: Fingerprint, k: int, a_text: str) -> Optional[Dict[str, Any]]:
    shared = a.hashes & b.hashes
    if not shared or not a.hashes:
        return None
    return {"score": round(100 * len(shared) / len(a.hashes)), "shared_grams": len(shared),
            "segments": _segments(a, b, shared, k, a_text)}


def index_submission(db: Db, assignment_id: str, submission_id: str, fp: Fingerprint) -> None:
    with db.tx() as conn:
        conn.execute("DELETE FROM fingerprints WHERE submission_id = ?", (submission_id,))
        conn.executemany("INSERT OR IGNORE INTO fingerprints (assignment_id, submission_id, hash, pos) VALUES (?,?,?,?)",
                         [(assignment_id, submission_id, h, p) for h, p in fp.prints])


def _candidates(db: Db, assignment_id: str, submission_id: str, hashes: Iterable[int]) -> List[str]:
    hs = list(hashes)
    found: Set[str] = set()
    for i in range(0, len(hs), 500):
        chunk = hs[i:i + 500]
        rows = db.all(f"SELECT DISTINCT submission_id FROM fingerprints WHERE assignment_id = ? AND submission_id != ? "
                      f"AND hash IN ({','.join('?' * len(chunk))})", [assignment_id, submission_id, *chunk])
        found.update(r["submission_id"] for r in rows)
    return sorted(found)


def run_similarity(db: Db, submission_id: str, k: int = 5, w: int = 4) -> Dict[str, Any]:
    row = db.one("SELECT s.submission_id, s.assignment_id, s.content, a.instructions FROM submissions s "
                 "JOIN assignments a ON a.assignment_id = s.assignment_id WHERE s.submission_id = ?", (submission_id,))
    if row is None:
        raise KeyError(submission_id)
    exclude = all_gram_hashes(row["instructions"], k) if row["instructions"] else set()
    fp = fingerprint(row["content"], k, w, exclude)
    index_submission(db, row["assignment_id"], submission_id, fp)

    matches: List[Dict[str, Any]] = []
    mirror: List[Tuple[str, Dict[str, Any]]] = []
    ids = _candidates(db, row["assignment_id"], submission_id, fp.hashes) if fp.prints else []
    others = db.all(f"SELECT s.submission_id, s.content, s.similarity_json, s.similarity_status, u.name AS student_name "
                    f"FROM submissions s JOIN users u ON u.user_id = s.student_id "
                    f"WHERE s.status != 'draft' AND s.submission_id IN ({','.join('?' * len(ids))})", ids) if ids else []
    me = db.one("SELECT u.name FROM submissions s JOIN users u ON u.user_id = s.student_id WHERE s.submission_id = ?", (submission_id,))
    for o in others:
        fb = fingerprint(o["content"], k, w, exclude)
        m = compare(fp, fb, k, row["content"])
        if not m:
            continue
        matches.append({"submission_id": o["submission_id"], "student_name": o["student_name"], **m})
        reverse = compare(fb, fp, k, o["content"])
        if reverse:
            mirror.append((o["submission_id"], {"submission_id": submission_id, "student_name": me["name"] if me else "", **reverse}))
    matches.sort(key=lambda m: -m["score"])
    matches = matches[:MAX_MATCHES]
    result = {"computed_ms": int(time.time() * 1000), "max_score": max((m["score"] for m in matches), default=0),
              "matches": matches, "compared": len(others), "params": {"k": k, "w": w, "prompt_grams_excluded": len(exclude)}}

    # Keep the other side symmetric so the teacher's table shows the overlap on both rows.
    for other_id, entry in mirror:
        o = next(x for x in others if x["submission_id"] == other_id)
        current = json.loads(o["similarity_json"]) if o["similarity_json"] else {"computed_ms": result["computed_ms"], "matches": [], "compared": 0}
        current["matches"] = [x for x in current.get("matches", []) if x["submission_id"] != submission_id] + [entry]
        current["matches"].sort(key=lambda x: -x["score"])
        current["matches"] = current["matches"][:MAX_MATCHES]
        current["max_score"] = max(x["score"] for x in current["matches"])
        status = "done" if o["similarity_status"] != "pending" else "pending"
        db.exec("UPDATE submissions SET similarity_json = ?, similarity_status = ? WHERE submission_id = ?",
                (json.dumps(current), status, other_id))
    return result
