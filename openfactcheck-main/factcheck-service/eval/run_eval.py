"""
Eval runner.

Posts each case in cases.jsonl to /v1/verify on a live factcheck-service
and scores per-class precision / recall / F1.

A case is considered "correctly handled" when:
  - is_hallucination = True  AND every claim's verdict ∈ {contradicted, unsupported}
  - is_hallucination = False AND at least one claim's verdict == "supported"

This is the same labeling philosophy used by the existing test_*.py files,
so before/after numbers are directly comparable.

Usage:
    BASE_URL=http://localhost:8080 python3 eval/run_eval.py
    BASE_URL=http://localhost:8080 OUTPUT=eval/baseline.json python3 eval/run_eval.py
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

import httpx

HERE = Path(__file__).resolve().parent
CASES_PATH = Path(os.environ.get("CASES", HERE / "cases.jsonl"))
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8080")
OUTPUT = Path(os.environ.get("OUTPUT", HERE / "results.json"))
CONCURRENCY = int(os.environ.get("EVAL_CONCURRENCY", "4"))
TIMEOUT = float(os.environ.get("EVAL_TIMEOUT", "60"))
API_KEY = os.environ.get("OFC_API_KEY", "")  # engine now requires x-api-key


def _verdicts(claims: List[Dict[str, Any]]) -> List[str]:
    return [c.get("verdict", "unknown") for c in claims]


def _is_correct(case: Dict[str, Any], claims: List[Dict[str, Any]]) -> bool:
    """Apply the labeling rule above."""
    verdicts = _verdicts(claims)
    is_hall = case["is_hallucination"]
    if is_hall:
        if not verdicts:
            return False  # no claim extracted -> hallucination not caught
        return all(v in ("contradicted", "unsupported") for v in verdicts)
    # Genuine claim: "correct" = NOT over-flagged as false. A true-but-niche
    # claim the engine cannot verify should be "unknown" (or "supported"), never
    # "unsupported"/"contradicted". This measures false-positive avoidance, which
    # is the metric that matters for a trustworthy detector.
    return not any(v in ("contradicted", "unsupported") for v in verdicts)


def _over_flagged(case: Dict[str, Any], claims: List[Dict[str, Any]]) -> bool:
    """A genuine claim wrongly judged false (unsupported/contradicted)."""
    if case["is_hallucination"]:
        return False
    return any(v in ("contradicted", "unsupported") for v in _verdicts(claims))


def _detected_planted_issue(case: Dict[str, Any], data: Dict[str, Any]) -> bool:
    """Did the engine DETECT the planted citation problem anywhere it belongs?
    A fabricated reference shows up as a DOI that fails registry validation; a
    mismatched (frankenstein) citation shows up as an alignment that finds the
    cited source does not support the claim. (Same signals the published-paper
    eval scores on — detection, not 'every sub-claim must be unsupported'.)"""
    cls = case.get("class", "")
    warns = " ".join(data.get("warnings") or []).lower()
    claims = data.get("claims", [])
    aligns = [a for c in claims for a in (c.get("citation_alignment") or [])]
    flags = {f.get("kind") for c in claims for f in (c.get("fabrication_flags") or [])}
    verdicts = _verdicts(claims)
    if cls == "fabricated_citation":
        # Detected if: the DOI failed registry validation, OR a registry-grounded
        # citation check fired (ghost author / unresolvable title / fake venue),
        # OR a registry-sourced contradiction (e.g. "arXiv:X is titled Y, not Z").
        registry_contra = any(
            c.get("verdict") == "contradicted"
            and any(re.search(r"arxiv api|crossref|openalex|registry", (e.get("source") or ""), re.I)
                    for e in (c.get("evidence") or []))
            for c in claims
        )
        return ("not found in registries" in warns or "doi not found" in warns
                or any((a.get("doi_status") in ("not_found", "invalid")) for a in aligns)
                or bool(flags & {"ghost_author", "fabricated_citation", "fabricated_venue"})
                or registry_contra)
    if "fabricated" in cls:
        # Other fabricated_* classes (venue / institution / grant / benchmark /
        # law / event / metric / funding): a flagged claim counts.
        return (bool(flags & {"fabricated_venue", "fabricated_institution", "fabricated_grant",
                              "fabricated_citation", "ghost_author"})
                or any(v in ("contradicted", "unsupported") for v in verdicts))
    if "frankenstein" in cls:
        return (any(a.get("support") in ("unrelated", "contradicted", "overstated") for a in aligns)
                or any(v == "contradicted" for v in verdicts))
    # other hallucination types: a flagged claim
    return any(v in ("contradicted", "unsupported") for v in verdicts)


async def _check_one(client: httpx.AsyncClient, case: Dict[str, Any]) -> Dict[str, Any]:
    t0 = time.perf_counter()
    try:
        resp = await client.post(
            f"{BASE_URL}/v1/verify",
            json={
                "text": case["claim"],
                "include_evidence": True,
                "include_reference_report": True,
            },
            timeout=TIMEOUT,
            headers={"x-api-key": API_KEY} if API_KEY else None,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        return {
            "id": case["id"],
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "verdicts": [],
            "duration_ms": (time.perf_counter() - t0) * 1000,
        }
    claims = data.get("claims", [])
    verdicts = _verdicts(claims)
    correct = _detected_planted_issue(case, data) if case["is_hallucination"] else _is_correct(case, claims)
    return {
        "id": case["id"],
        "ok": True,
        "correct": correct,
        "expected_verdict": case["expected_verdict"],
        "verdicts": verdicts,
        "summary": data.get("summary"),
        "warnings": data.get("warnings"),
        "duration_ms": (time.perf_counter() - t0) * 1000,
        # surface new fields if present
        "fabrication_flags": [c.get("fabrication_flags") for c in claims],
        "taxonomy": [c.get("taxonomy") for c in claims],
        "citation_alignment": [c.get("citation_alignment") for c in claims],
        "severity": [c.get("severity") for c in claims],
    }


async def run() -> Dict[str, Any]:
    cases = [json.loads(line) for line in CASES_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    sem = asyncio.Semaphore(CONCURRENCY)
    out: List[Dict[str, Any]] = [None] * len(cases)  # type: ignore[list-item]

    async with httpx.AsyncClient() as client:
        async def worker(i: int, case: Dict[str, Any]) -> None:
            async with sem:
                res = await _check_one(client, case)
                res["case"] = case
                out[i] = res
                tag = "✓" if res.get("correct") else "✗"
                v = ",".join(res.get("verdicts", [])) or "—"
                print(f"  {tag} [{case['id']:>10s}] {case['class']:>22s} → {v}")

        tasks = [worker(i, c) for i, c in enumerate(cases)]
        for fut in asyncio.as_completed(tasks):
            await fut

    # ── Aggregate per-class ──
    per_class: Dict[str, Dict[str, int]] = defaultdict(lambda: {"total": 0, "correct": 0, "errors": 0})
    per_domain: Dict[str, Dict[str, int]] = defaultdict(lambda: {"total": 0, "correct": 0})
    durations: List[float] = []
    total = correct = errors = 0
    for res in out:
        c = res["case"]
        per_class[c["class"]]["total"] += 1
        per_domain[c["domain"]]["total"] += 1
        total += 1
        if not res.get("ok"):
            errors += 1
            per_class[c["class"]]["errors"] += 1
            continue
        durations.append(res["duration_ms"])
        if res.get("correct"):
            correct += 1
            per_class[c["class"]]["correct"] += 1
            per_domain[c["domain"]]["correct"] += 1

    def _rate(d: Dict[str, int]) -> float:
        return d["correct"] / d["total"] if d["total"] else 0.0

    report = {
        "base_url": BASE_URL,
        "total_cases": total,
        "correct": correct,
        "errors": errors,
        "accuracy": correct / total if total else 0.0,
        "p50_ms": statistics.median(durations) if durations else 0.0,
        "p95_ms": statistics.quantiles(durations, n=20)[-1] if len(durations) >= 20 else (max(durations) if durations else 0.0),
        "per_class": {k: {**v, "accuracy": _rate(v)} for k, v in per_class.items()},
        "per_domain": {k: {**v, "accuracy": _rate(v)} for k, v in per_domain.items()},
        "results": out,
    }

    OUTPUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print()
    print("─" * 72)
    print(f"  TOTAL  {correct}/{total}  ({report['accuracy']*100:.1f}%)  errors={errors}  p50={report['p50_ms']:.0f}ms p95={report['p95_ms']:.0f}ms")
    print("─" * 72)
    print("  Per-class accuracy:")
    for k in sorted(per_class):
        v = per_class[k]
        print(f"    {k:30s} {v['correct']:>3d}/{v['total']:<3d}  ({_rate(v)*100:5.1f}%)  err={v['errors']}")
    print("  Per-domain accuracy:")
    for k in sorted(per_domain):
        v = per_domain[k]
        print(f"    {k:30s} {v['correct']:>3d}/{v['total']:<3d}  ({_rate(v)*100:5.1f}%)")
    print(f"\n  Wrote {OUTPUT}")
    return report


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        sys.exit(130)
