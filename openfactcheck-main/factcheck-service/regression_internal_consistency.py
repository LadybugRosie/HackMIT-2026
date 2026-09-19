"""
No-regression proof for the additive internal-consistency pass.

A) DETERMINISTIC isolation: run the CoVe paper through /verify with the flag OFF
   then ON, with the LLM disabled so the claim pipeline is fully deterministic.
   Any difference between the two claim arrays is therefore attributable ONLY to
   the flag. Assert: identical claims (count, text, verdict, zone, citation_mapped).
B) LIVE profile: one real-LLM CoVe run (flag ON) — report the author-claim count
   (the user's "~145 author-claims" benchmark) + the internal_consistency field.
C) Behavior: tiny same-quantity mismatch must be caught; legit different-method
   numbers must NOT be flagged (no false positive).

Run: cd factcheck-service && .venv/bin/python regression_internal_consistency.py
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


def _claim_key(c):
    return (c.claim, c.verdict, c.zone, c.citation_mapped)


async def run(text, mode, flag):
    settings.ENABLE_INTERNAL_CONSISTENCY = flag
    req = FactcheckRequest(text=text, mode=mode, include_evidence=False,
                           include_reference_report=False)
    return await api.verify(req, _rate_key="test")


async def main():
    fails = []

    # ---- A) deterministic isolation (LLM disabled) -------------------------
    print("A) DETERMINISTIC isolation — CoVe, LLM disabled, flag OFF vs ON")
    orig_client = llm_verifier._get_client
    llm_verifier._get_client = lambda: None      # kill every LLM call → deterministic
    try:
        off = await run(COVE, "published_paper", False)
        on = await run(COVE, "published_paper", True)
    finally:
        llm_verifier._get_client = orig_client

    off_keys = [_claim_key(c) for c in off.claims]
    on_keys = [_claim_key(c) for c in on.claims]
    print(f"   claims OFF = {len(off_keys)} | ON = {len(on_keys)}")
    same = off_keys == on_keys
    print(f"   claim arrays identical (count/text/verdict/zone/mapped): {same}")
    if not same:
        fails.append("claims changed between flag OFF and ON")
        added = set(on_keys) - set(off_keys)
        removed = set(off_keys) - set(on_keys)
        for k in list(added)[:5]:
            print(f"     + {k}")
        for k in list(removed)[:5]:
            print(f"     - {k}")
    n_author_off = sum(1 for c in off.claims if c.verdict == "author_claim")
    n_author_on = sum(1 for c in on.claims if c.verdict == "author_claim")
    print(f"   author_claim count OFF={n_author_off} ON={n_author_on} "
          f"(stable: {n_author_off == n_author_on})")
    print(f"   OFF internal_consistency present: {off.internal_consistency is not None} "
          f"| ON status: {on.internal_consistency.status if on.internal_consistency else None}")
    if off.internal_consistency is not None:
        fails.append("flag OFF still emitted internal_consistency")

    # ---- C) behavior on tiny synthetics (real LLM) -------------------------
    print("\nC) behavior — real LLM")
    mismatch_doc = (
        "Abstract. Our method SelfRAG achieves 98.7% accuracy on the TruthfulQA "
        "benchmark, a new state of the art. "
        "We describe the architecture and training procedure in detail. "
        "Table 2 reports the final results: SelfRAG reaches 94.2% accuracy on "
        "TruthfulQA, outperforming all baselines."
    )
    legit_doc = (
        "We compare three systems on the same SQuAD test set. "
        "Method A attains 88.0% F1 on SQuAD. "
        "Method B attains 91.5% F1 on SQuAD. "
        "Our proposed Method C attains 94.3% F1 on SQuAD."
    )
    mm = await run(mismatch_doc, "published_paper", True)
    ic = mm.internal_consistency
    caught = bool(ic and ic.status == "internal_mismatch" and ic.findings)
    print(f"   same-quantity mismatch (98.7 vs 94.2, same method/dataset): "
          f"status={ic.status if ic else None}, findings={len(ic.findings) if ic else 0} "
          f"-> caught: {caught}")
    if caught:
        f0 = ic.findings[0]
        print(f"     -> {f0.metric}: {f0.value_a} vs {f0.value_b} — {f0.note}")
    if not caught:
        fails.append("did NOT catch the genuine same-quantity mismatch")

    lg = await run(legit_doc, "published_paper", True)
    icl = lg.internal_consistency
    no_fp = bool(icl and not icl.findings)
    print(f"   legit different-method numbers (A/B/C on SQuAD): "
          f"status={icl.status if icl else None}, findings={len(icl.findings) if icl else 0} "
          f"-> no false positive: {no_fp}")
    if not no_fp:
        fails.append("FALSE POSITIVE on legitimately different methods")

    # ---- B) live CoVe profile (real LLM, flag ON) --------------------------
    print("\nB) LIVE profile — CoVe, real LLM, flag ON")
    live = await run(COVE, "published_paper", True)
    from collections import Counter
    dist = Counter(c.verdict for c in live.claims)
    n_author = dist.get("author_claim", 0)
    print(f"   total claims={len(live.claims)} | author_claim={n_author} | "
          f"verdict dist={dict(dist)}")
    print(f"   references_parsed={live.references_parsed} | "
          f"citation_matrix rows={len(live.citation_matrix)}")
    licl = live.internal_consistency
    print(f"   internal_consistency: status={licl.status if licl else None}, "
          f"checked={licl.checked if licl else 0}, "
          f"findings={len(licl.findings) if licl else 0}")
    if licl and licl.findings:
        for f in licl.findings[:5]:
            print(f"     - {f.metric}: {f.value_a} vs {f.value_b} — {f.note}")

    print("\n" + ("FAILURES: " + "; ".join(fails) if fails else "ALL PROOFS PASS"))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    asyncio.run(main())
