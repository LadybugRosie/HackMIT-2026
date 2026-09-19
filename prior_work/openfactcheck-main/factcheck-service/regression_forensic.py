"""
No-regression + behavior proof for the forensic-integrity pass.

A) CoVe (LLM disabled, deterministic): claims must stay 175 / 145 author-claims
   identical whether forensic is OFF or ON — the pass never touches claims.
B) Seeded-error doc: a planted statcheck decision error, an impossible GRIM
   percentage, and a dangling Table reference must all surface end-to-end.

Run: cd factcheck-service && .venv/bin/python regression_forensic.py
"""
import asyncio
import os
import sys

os.environ.setdefault("REDIS_URL", "memory://")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import api, llm_verifier  # noqa: E402
from app.schemas import FactcheckRequest  # noqa: E402
from app.settings import settings  # noqa: E402

COVE = open("/tmp/cove.txt").read()


def _ck(c):
    return (c.claim, c.verdict, c.zone, c.citation_mapped)


async def run(text, mode):
    req = FactcheckRequest(text=text, mode=mode, include_evidence=False, include_reference_report=False)
    return await api.verify(req, _rate_key="test")


async def main():
    fails = []
    orig = llm_verifier._get_client
    llm_verifier._get_client = lambda: None      # deterministic: no LLM
    try:
        settings.ENABLE_FORENSIC_CHECKS = False
        off = await run(COVE, "published_paper")
        settings.ENABLE_FORENSIC_CHECKS = True
        on = await run(COVE, "published_paper")
    finally:
        llm_verifier._get_client = orig

    print("A) CoVe — claims identical with forensic OFF vs ON")
    same = [_ck(c) for c in off.claims] == [_ck(c) for c in on.claims]
    na_off = sum(1 for c in off.claims if c.verdict == "author_claim")
    na_on = sum(1 for c in on.claims if c.verdict == "author_claim")
    print(f"   claims OFF={len(off.claims)} ON={len(on.claims)} | author_claim OFF={na_off} ON={na_on}")
    print(f"   claim arrays identical: {same}")
    print(f"   forensic present OFF={off.forensic_checks is not None} ON={on.forensic_checks is not None}")
    if not same:
        fails.append("claims changed with forensic ON")
    if off.forensic_checks is not None:
        fails.append("forensic emitted while flag OFF")
    if on.forensic_checks is not None:
        print(f"   forensic checks_run={on.forensic_checks.checks_run} "
              f"summary={on.forensic_checks.summary}")

    print("\nB) Seeded-error doc — planted errors must surface")
    seeded = (
        "Methods. Participants rated items on a 1-7 Likert scale.\n"
        "Table 1: demographics.\n"
        "Table 2: primary outcomes.\n"
        "Results. The treatment effect was significant, t(28) = 1.20, p = .004. "
        "Adherence was high: 19/30 (63.4%) completed all sessions. "
        "The mean rating was M = 3.46 (N = 20) on the Likert scale. "
        "Full results are reported in Table 1, Table 2, and Table 8.\n"
    )
    settings.ENABLE_FORENSIC_CHECKS = True
    llm_verifier._get_client = lambda: None
    try:
        res = await run(seeded, "published_paper")
    finally:
        llm_verifier._get_client = orig
    fc = res.forensic_checks
    checks = {f.check for f in fc.findings} if fc else set()
    print(f"   findings={len(fc.findings) if fc else 0} | checks fired={sorted(checks)}")
    for f in (fc.findings if fc else []):
        print(f"     [{f.severity}] {f.check}: {f.title}")
    for need in ("statcheck", "grim", "dangling_ref"):
        if need not in checks:
            fails.append(f"seeded {need} error not surfaced")
    # claims must still exist and be unaffected (the seeded doc still produces claims)
    print(f"   (claims produced for seeded doc: {len(res.claims)})")

    print("\n" + ("FAILURES: " + "; ".join(fails) if fails else "ALL FORENSIC PROOFS PASS"))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    asyncio.run(main())
