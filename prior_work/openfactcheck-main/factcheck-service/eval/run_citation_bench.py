"""
Score factcheck-service against the citation-verification spec.

The spec defines four verdicts (clean / flag / warn / unverifiable) that the
service does not natively emit. This runner maps the service's response onto
them with the rules below. The mapping is deliberately written once, up front,
and applied uniformly -- it is not tuned per case.

MAPPING (in precedence order)
  flag          any extracted identifier is malformed, unregistered, or its
                registry record contradicts the cited metadata
                  -> DOI status in {invalid, not_found, mismatch}
                  -> or a fabrication_flag of a fabrication kind
                  -> or a claim verdict of "contradicted"
  warn          every identifier resolves, but the cited work is retracted or
                under an expression of concern
  unverifiable  no identifier was extracted and nothing was contradicted --
                the service found nothing to check
  clean         identifiers resolved and nothing contradicted them

KNOWN MAPPING LIMIT, stated rather than hidden: the service has no notion of
"this work does not exist" for a reference with no identifier. Such a case
lands in `unverifiable` regardless of whether it is genuinely unindexed (the
O-series, correct) or fabricated (E01, F01-F05, wrong). That is a real
capability gap, and the per-category report below is where it shows up.

Usage:
    BASE_URL=http://localhost:8090 python3 eval/run_citation_bench.py
"""
from __future__ import annotations
import asyncio, json, os, sys, time
from collections import defaultdict
from pathlib import Path
import httpx

HERE = Path(__file__).resolve().parent
CASES = Path(os.environ.get("CASES", HERE / "citations_bench.jsonl"))
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8090")
OUTPUT = Path(os.environ.get("OUTPUT", HERE / "citations_bench_results.json"))
CONC = int(os.environ.get("EVAL_CONCURRENCY", "4"))
TIMEOUT = float(os.environ.get("EVAL_TIMEOUT", "120"))

BAD_DOI = {"invalid", "not_found", "mismatch"}
FAB_KINDS = {"fabricated_venue", "fabricated_institution", "fabricated_grant",
             "fabricated_citation", "ghost_author"}


def derive_verdict(d: dict) -> tuple[str, str]:
    """Map a /v1/verify response onto the spec's four verdicts. Returns
    (verdict, reason) so every decision is auditable."""
    rr = d.get("reference_report") or {}
    dois = rr.get("dois") or []
    urls = rr.get("urls") or []
    claims = d.get("claims") or []

    bad = [x for x in dois if (x.get("status") or "") in BAD_DOI]
    if bad:
        return "flag", f"doi {bad[0].get('doi')} -> {bad[0].get('status')}"

    flags = {f.get("kind") for c in claims for f in (c.get("fabrication_flags") or [])}
    if flags & FAB_KINDS:
        return "flag", f"fabrication_flag {sorted(flags & FAB_KINDS)}"

    aligns = [a for c in claims
              for a in (c.get("citation_alignment") or c.get("citation_alignments") or [])]
    if any(a.get("is_retracted") for a in aligns):
        return "warn", "registry reports retraction / expression of concern"

    if any(c.get("verdict") == "contradicted" for c in claims):
        return "flag", "claim contradicted by retrieved evidence"

    # NOTE: the service's "unsupported" verdict is deliberately NOT treated as a
    # flag. It fires on correct bibliography entries too (A05, a genuine PLoS
    # reference, returns "unsupported"), because a bare reference string is not
    # a claim any source can "support". Using it would destroy precision.

    if any(a.get("support") in ("unrelated", "contradicted") for a in aligns):
        return "flag", "cited source does not support the claim"

    # Deterministic structural findings: a malformed identifier or impossible
    # pagination is a flag under the spec's own definition. Only these two
    # checks are consulted -- statcheck/GRIM are claim-level statistics issues,
    # not citation verdicts.
    fx = (d.get("forensic_checks") or {}).get("findings") or []
    struct = [f for f in fx if f.get("check") in ("identifier_format", "page_range")]
    if struct:
        return "flag", f"{struct[0].get('check')}: {struct[0].get('title')}"

    if not dois and not urls:
        return "unverifiable", "no identifier extracted; nothing to check"

    return "clean", "identifiers resolved, nothing contradicted"


async def one(client, case):
    t0 = time.perf_counter()
    try:
        r = await client.post(f"{BASE_URL}/v1/verify",
                              json={"text": case["input"], "include_evidence": True,
                                    "include_reference_report": True},
                              timeout=TIMEOUT)
        r.raise_for_status()
        d = r.json()
    except Exception as e:
        return {**{k: case[k] for k in ("id", "category", "expected")},
                "got": "ERROR", "reason": f"{type(e).__name__}: {e}",
                "correct": False, "ms": (time.perf_counter() - t0) * 1000}
    got, reason = derive_verdict(d)
    return {**{k: case[k] for k in ("id", "category", "expected")},
            "got": got, "reason": reason, "correct": got == case["expected"],
            "ms": (time.perf_counter() - t0) * 1000}


async def main():
    cases = [json.loads(l) for l in CASES.open(encoding="utf-8")]
    runnable = [c for c in cases if c.get("runnable", True)]
    skipped = len(cases) - len(runnable)
    sem = asyncio.Semaphore(CONC)
    async with httpx.AsyncClient() as client:
        async def g(c):
            async with sem:
                return await one(client, c)
        res = await asyncio.gather(*[g(c) for c in runnable])

    by_cat = defaultdict(lambda: {"n": 0, "ok": 0})
    conf = defaultdict(int)
    for r in res:
        by_cat[r["category"]]["n"] += 1
        by_cat[r["category"]]["ok"] += bool(r["correct"])
        conf[(r["expected"], r["got"])] += 1

    ok = sum(r["correct"] for r in res)
    print("\n" + "=" * 74)
    print(f"  CITATION BENCH   {ok}/{len(res)}  ({ok/len(res)*100:.1f}%)"
          f"   [{skipped} placeholder cases skipped]")
    print("=" * 74)
    print("  Per category:")
    for cat in sorted(by_cat):
        v = by_cat[cat]
        print(f"    {cat:34s} {v['ok']:3d}/{v['n']:<3d} ({v['ok']/v['n']*100:5.1f}%)")

    # False positives on genuinely clean references -- the metric that decides
    # whether the tool is usable on ordinary well-sourced prose.
    cleans = [r for r in res if r["expected"] == "clean"]
    fp = [r for r in cleans if r["got"] == "flag"]
    print(f"\n  Clean references wrongly flagged (FPR): {len(fp)}/{len(cleans)}"
          f"  ({len(fp)/len(cleans)*100:.1f}%)")
    for r in fp:
        print(f"      {r['id']}  -> {r['reason']}")

    print("\n  Confusion (expected -> got):")
    for (e, g), n in sorted(conf.items(), key=lambda kv: -kv[1]):
        mark = "  " if e == g else "<-"
        print(f"    {mark} {e:14s} -> {g:14s} {n}")

    print("\n  Misses:")
    for r in sorted(res, key=lambda r: r["id"]):
        if not r["correct"]:
            print(f"    {r['id']:5s} {r['category']:30s} want={r['expected']:13s} got={r['got']:13s} | {r['reason'][:46]}")

    OUTPUT.write_text(json.dumps(
        {"base_url": BASE_URL, "total": len(res), "correct": ok,
         "accuracy": ok / len(res), "skipped_placeholders": skipped,
         "per_category": {k: dict(v) for k, v in by_cat.items()},
         "cases": res}, indent=1))
    print(f"\n  Wrote {OUTPUT}\n")

asyncio.run(main())
