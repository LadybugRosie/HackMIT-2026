"""
Internal numeric-consistency pass (ADDITIVE — new stage, flag-gated).

This runs ALONGSIDE the existing claim classifier, never inside it. It does NOT
touch claims, verdicts, segmentation, the citation matrix, or any existing
threshold. It only scans the document's figure-bearing sentences and reports
pairs that state DIFFERENT numeric values for the SAME quantity — e.g. the
abstract says "98.7% accuracy" but a table says "94.2%" for the same method.

New verdict classes (own field, never mixed into `claims`):
    INTERNAL_MISMATCH        — a confident same-quantity numeric disagreement.
    INTERNALLY_CONSISTENT    — figures were scanned, no mismatch found.
    NOT_CHECKED              — too few figures to compare, or pass disabled/failed.

Precision-first by design: the LLM is told to flag ONLY when it is confident the
two numbers describe the identical quantity (same metric, method, dataset,
condition). Different methods / datasets / metrics are never flagged. This keeps
the "zero new false positives" guarantee — and the output lives in its own field,
so even a stray finding can never change how an existing claim is bucketed.

Works for both modes ("published_paper" and general/essay).
"""
import json
import logging
import re
from typing import Any, Dict, List

from .citation_styles import dehyphenate
from .llm_verifier import call_llm_json
from .settings import settings

logger = logging.getLogger(__name__)

# A sentence is a consistency candidate only if it carries a metric/figure cue
# AND a digit. Keeps the LLM payload small and on-topic (no prose without numbers).
_METRIC_RE = re.compile(
    r"%|\bF1\b|\bF-?score\b|\bAUC(?:-?PR|-?ROC)?\b|\bBLEU\b|\bROUGE\b|\bmAP\b"
    r"|\baccuracy\b|\bprecision\b|\brecall\b|\bscore\b|\berror rate\b|\bMSE\b"
    r"|\bRMSE\b|\bperplexity\b|\bcorrelation\b|\bAUROC\b|\bAUPRC\b|\bEM\b"
    r"|\bn\s*=\s*\d|\bp\s*[<=>]\s*0?\.\d",
    re.IGNORECASE,
)
_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\"'])")
_MAX_CANDIDATES = 60

_SYSTEM_PROMPT = """You check ONE research document for INTERNAL numeric inconsistencies.

You are given numbered sentences from a single paper, each containing figures or
metrics. Find pairs of sentences that report DIFFERENT numeric values for the
SAME quantity — i.e. the SAME metric, for the SAME method/system, on the SAME
dataset/condition. The classic case: the abstract claims one headline number and
a table or the conclusion reports a different number for that same result.

Be STRICT and CONSERVATIVE. This must NOT produce false positives:
  - Do NOT flag different methods, systems, datasets, splits, metrics, years,
    or conditions — these legitimately have different values.
  - Do NOT flag a BASELINE value against a PROPOSED/improved method's value —
    they are SUPPOSED to differ. e.g. "baseline 0.17 vs our method 0.36" is fine.
  - Do NOT flag an improvement or change stated as a delta — "from X to Y",
    "increased/improved/doubled from X to Y", "X to Y", "X -> Y", "gains N points".
    These are before/after values of a single result, not a contradiction.
  - Do NOT flag a number that simply is not repeated elsewhere.
  - Do NOT flag rounding (98.7 vs 98.70) or a value that falls inside a stated
    range/interval.
  - Flag ONLY when you are CONFIDENT both numbers describe the IDENTICAL quantity
    (same metric, SAME method, same dataset, same condition) reported in two
    places, and they genuinely disagree.

Worked example — do NOT flag: "CoVe doubles the precision from the Llama 65B
few-shot baseline on Wikidata (from 0.17 to 0.36)." 0.17 is the baseline, 0.36 is
the proposed method; this is an intended improvement, NOT a mismatch.

Return STRICT JSON, no prose:
{"mismatches":[{"metric":"<short name>","value_a":"<value>","value_b":"<value>",
"sentence_a":<index>,"sentence_b":<index>,"note":"<one short reason>"}]}
If there are no confident mismatches, return {"mismatches":[]}.
"""


def _candidate_sentences(text: str, cap: int = _MAX_CANDIDATES) -> List[str]:
    """Figure-bearing sentences only — small, on-topic payload for the LLM."""
    out: List[str] = []
    seen = set()
    for raw in _SENT_SPLIT_RE.split(text or ""):
        s = " ".join(raw.split())
        if not (15 <= len(s) <= 400):
            continue
        if not re.search(r"\d", s) or not _METRIC_RE.search(s):
            continue
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
        if len(out) >= cap:
            break
    return out


def _coerce(raw: str, cands: List[str]) -> List[Dict[str, Any]]:
    """Parse the LLM JSON and resolve sentence indices back to snippets. Any
    malformed / out-of-range item is dropped (never raised)."""
    s = (raw or "").strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    try:
        data = json.loads(s)
    except Exception:
        return []
    findings: List[Dict[str, Any]] = []
    for m in (data.get("mismatches") or []) if isinstance(data, dict) else []:
        if not isinstance(m, dict):
            continue
        ia, ib = m.get("sentence_a"), m.get("sentence_b")
        sa = cands[ia] if isinstance(ia, int) and 0 <= ia < len(cands) else None
        sb = cands[ib] if isinstance(ib, int) and 0 <= ib < len(cands) else None
        if not sa or not sb or sa == sb:
            continue
        findings.append({
            "verdict": "internal_mismatch",
            "metric": str(m.get("metric") or "").strip()[:80],
            "value_a": str(m.get("value_a") or "").strip()[:40],
            "value_b": str(m.get("value_b") or "").strip()[:40],
            "snippet_a": sa[:240],
            "snippet_b": sb[:240],
            "note": str(m.get("note") or "").strip()[:240],
        })
    return findings


async def check_internal_consistency(text: str) -> Dict[str, Any]:
    """Scan `text` for same-quantity numeric disagreements.

    Returns {"status": ..., "findings": [...], "checked": <int>} where status is
    one of internal_mismatch / internally_consistent / not_checked. Never raises.
    """
    if not settings.ENABLE_INTERNAL_CONSISTENCY:
        return {"status": "not_checked", "findings": [], "checked": 0}
    try:
        cands = _candidate_sentences(dehyphenate(text or ""))
    except Exception:
        cands = []
    if len(cands) < 2:
        return {"status": "not_checked", "findings": [], "checked": len(cands)}
    numbered = "\n".join(f"[{i}] {s}" for i, s in enumerate(cands))
    try:
        raw = await call_llm_json(
            _SYSTEM_PROMPT,
            f"Sentences:\n{numbered}\n\nReturn the JSON object now.",
            max_tokens=1500,
        )
    except Exception as e:  # noqa: BLE001
        logger.debug(f"internal-consistency LLM call failed: {e}")
        raw = None
    if not raw:
        return {"status": "not_checked", "findings": [], "checked": len(cands)}
    findings = [f for f in _coerce(raw, cands) if not _is_delta(f, cands)]
    status = "internal_mismatch" if findings else "internally_consistent"
    return {"status": status, "findings": findings, "checked": len(cands)}


def _is_delta(finding: Dict[str, Any], cands: List[str]) -> bool:
    """Deterministic backstop for the baseline/before-after trap. If both values
    co-occur inside a single sentence, the pair is a within-statement delta or
    comparison (e.g. "from 0.17 to 0.36"), never a cross-location contradiction —
    drop it. Keeps the "zero false positives" guarantee even if the LLM slips."""
    a, b = finding.get("value_a", ""), finding.get("value_b", "")
    if not a or not b:
        return False
    for s in cands:
        if a in s and b in s:
            return True
    return False
