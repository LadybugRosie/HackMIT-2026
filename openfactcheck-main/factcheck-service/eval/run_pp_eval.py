"""
Runner for the published-paper citation-integrity eval (eval/pp_cases.jsonl).

Posts each mini-paper to /v1/verify with mode="published_paper" and scores off
the Citation Support Matrix + reference report + coverage verdict:

  - pp_genuine      correct  : NOT flagged (no mismatch, no fabrication) -> false-positive control
  - pp_fabricated   correct  : DOI flagged not_found / invalid (fabricated reference)
  - pp_frankenstein correct  : cited source does not support the claim
                               (support in unrelated / contradicted / overstated)

Usage:
    BASE_URL=http://localhost:8090 OFC_API_KEY=... OUTPUT=eval/pp_results.json \
        .venv/bin/python eval/run_pp_eval.py
"""
from __future__ import annotations
import asyncio
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

import httpx

HERE = Path(__file__).resolve().parent
CASES = Path(os.environ.get("CASES", HERE / "pp_cases.jsonl"))
BASE = os.environ.get("BASE_URL", "http://localhost:8090")
KEY = os.environ.get("OFC_API_KEY", "")
OUT = Path(os.environ.get("OUTPUT", HERE / "pp_results.json"))
CONC = int(os.environ.get("PP_CONCURRENCY", "4"))
TIMEOUT = float(os.environ.get("PP_TIMEOUT", "200"))

_MISMATCH = {"unrelated", "contradicted", "overstated"}


def _flags_mismatch(matrix: List[Dict[str, Any]]) -> bool:
    return any(
        (r.get("supports_claim") in _MISMATCH) or (r.get("verdict") in _MISMATCH)
        for r in matrix
    )


def _flags_fabrication(matrix: List[Dict[str, Any]], refrep: Dict[str, Any] | None) -> bool:
    # A fabricated reference cannot be found anywhere: the DOI fails registry
    # validation AND the source does not resolve. A "not_found" DOI that still
    # resolved to a real abstract is a registrar-coverage miss, not fabrication.
    return any(
        r.get("doi_status") in ("not_found", "invalid")
        and r.get("evidence_scope") in (None, "not_retrieved")
        for r in matrix
    )


def _correct(case: Dict[str, Any], d: Dict[str, Any]) -> bool:
    matrix = d.get("citation_matrix") or []
    refrep = d.get("reference_report")
    cls = case["class"]
    if cls == "pp_genuine":
        return not _flags_mismatch(matrix) and not _flags_fabrication(matrix, refrep)
    if cls == "pp_fabricated":
        return _flags_fabrication(matrix, refrep)
    if cls == "pp_frankenstein":
        return _flags_mismatch(matrix)
    return False


async def _one(client: httpx.AsyncClient, case: Dict[str, Any]) -> Dict[str, Any]:
    try:
        r = await client.post(
            f"{BASE}/v1/verify",
            json={"text": case["text"], "mode": "published_paper",
                  "include_evidence": True, "include_reference_report": True},
            headers={"x-api-key": KEY} if KEY else None,
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        d = r.json()
    except Exception as e:
        return {"id": case["id"], "class": case["class"], "ok": False, "error": f"{type(e).__name__}: {e}", "correct": False}
    matrix = d.get("citation_matrix") or []
    return {
        "id": case["id"], "class": case["class"], "ok": True,
        "correct": _correct(case, d),
        "matrix": [{"citation": m.get("citation"), "doi": m.get("doi"),
                    "doi_status": m.get("doi_status"), "supports_claim": m.get("supports_claim"),
                    "verdict": m.get("verdict"), "evidence_scope": m.get("evidence_scope")} for m in matrix],
        "coverage": d.get("citation_coverage"),
        "audit_verdict": d.get("verdict"),
    }


async def run() -> None:
    cases = [json.loads(l) for l in CASES.read_text().splitlines() if l.strip()]
    sem = asyncio.Semaphore(CONC)
    out: List[Dict[str, Any]] = [None] * len(cases)

    async with httpx.AsyncClient() as client:
        async def worker(i, c):
            async with sem:
                out[i] = await _one(client, c)
                r = out[i]
                print(f"  {'✓' if r['correct'] else '✗'} [{c['id']:>14s}] {c['class']:>16s}"
                      f" -> {'ERR ' + r.get('error','') if not r['ok'] else (r['matrix'][0] if r['matrix'] else 'no-matrix')}")
        await asyncio.gather(*(worker(i, c) for i, c in enumerate(cases)))

    pc = defaultdict(lambda: {"total": 0, "correct": 0, "err": 0})
    for r in out:
        pc[r["class"]]["total"] += 1
        if not r["ok"]:
            pc[r["class"]]["err"] += 1
        if r["correct"]:
            pc[r["class"]]["correct"] += 1
    report = {"base_url": BASE, "per_class": {k: dict(v) for k, v in pc.items()}, "results": out}
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\n" + "─" * 60)
    tot = sum(v["total"] for v in pc.values()); cor = sum(v["correct"] for v in pc.values())
    print(f"  PP TOTAL  {cor}/{tot} ({cor/tot*100:.0f}%)")
    for k in sorted(pc):
        v = pc[k]; print(f"    {k:18s} {v['correct']}/{v['total']} ({v['correct']/v['total']*100:.0f}%)  err={v['err']}")
    print(f"  wrote {OUT}")


if __name__ == "__main__":
    asyncio.run(run())
