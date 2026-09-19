"""
Integration test for the enhanced OpenFactCheck pipeline.
Tests: Semantic Scholar, LLM verification, confidence scoring, claim decomposition.
"""
import asyncio
import json
import os
import sys

# Set API keys from environment (or inline for testing)
os.environ.setdefault("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
os.environ.setdefault("SEMANTIC_SCHOLAR_API_KEY", os.environ.get("SEMANTIC_SCHOLAR_API_KEY", ""))
os.environ.setdefault("REDIS_URL", "memory://")
os.environ.setdefault("EVIDENCE_MODE", "REGISTRY_ONLY")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


async def test_semantic_scholar():
    """Test Semantic Scholar search."""
    print("\n" + "=" * 60)
    print("TEST 1: Semantic Scholar API")
    print("=" * 60)

    from app.semantic_scholar import search_papers, get_evidence_for_claim

    # Search for a well-known paper
    papers = await search_papers("Attention Is All You Need transformer", limit=3)
    print(f"\nSearch 'Attention Is All You Need': found {len(papers)} papers")
    for p in papers[:2]:
        print(f"  - {p.get('title', 'N/A')} ({p.get('year', '?')})")
        print(f"    Citations: {p.get('citationCount', 0)}")

    # Get evidence for a claim
    evidence = await get_evidence_for_claim("CRISPR gene editing was developed for use in human cells")
    print(f"\nEvidence for CRISPR claim: {len(evidence)} items")
    for ev in evidence[:2]:
        print(f"  - {ev['source']}")
        print(f"    {ev['snippet'][:120]}...")

    return len(papers) > 0


async def test_llm_verification():
    """Test LLM-powered claim verification."""
    print("\n" + "=" * 60)
    print("TEST 2: LLM Claim Verification")
    print("=" * 60)

    from app.llm_verifier import verify_claim_with_llm

    # Test with evidence
    result = await verify_claim_with_llm(
        claim="The Transformer architecture was introduced in 2017.",
        scholarly_evidence=[{
            "source": "Semantic Scholar",
            "snippet": "Attention Is All You Need, published in 2017, introduced the Transformer architecture.",
            "url": "https://arxiv.org/abs/1706.03762",
        }],
    )

    if result:
        print(f"\nClaim: 'Transformer architecture was introduced in 2017'")
        print(f"  Verdict: {result['verdict']}")
        print(f"  Confidence: {result['confidence']}")
        print(f"  Reasoning: {result['reasoning']}")
        return True
    else:
        print("\nLLM verification returned None (check API key)")
        return False


async def test_claim_decomposition():
    """Test compound claim decomposition."""
    print("\n" + "=" * 60)
    print("TEST 3: Claim Decomposition")
    print("=" * 60)

    from app.llm_verifier import decompose_claim

    compound = "Marie Curie, who was born in Warsaw in 1867, won the Nobel Prize in Physics in 1903 and the Nobel Prize in Chemistry in 1911."
    sub_claims = await decompose_claim(compound)

    print(f"\nOriginal: {compound}")
    print(f"Decomposed into {len(sub_claims)} sub-claims:")
    for i, sc in enumerate(sub_claims, 1):
        print(f"  {i}. {sc}")

    return len(sub_claims) > 1


async def test_confidence_scoring():
    """Test confidence scoring engine."""
    print("\n" + "=" * 60)
    print("TEST 4: Confidence Scoring")
    print("=" * 60)

    from app.confidence import compute_confidence

    # High confidence: KB match + DOI
    score1 = compute_confidence(
        verdict="supported",
        evidence=[
            {"source": "NASA", "snippet": "Mars has two moons", "url": "https://nasa.gov"},
            {"source": "Wikipedia", "snippet": "Phobos and Deimos", "url": "https://en.wikipedia.org"},
        ],
        knowledge_base_match=True,
        doi_verified=True,
    )
    print(f"\nHigh-confidence case (KB + DOI + NASA):")
    print(f"  Score: {score1['score']}/100 (Grade: {score1['grade']})")
    print(f"  Breakdown: {score1['breakdown']}")
    print(f"  Explanation: {score1['explanation']}")

    # Low confidence: unknown verdict
    score2 = compute_confidence(
        verdict="unknown",
        evidence=[],
        knowledge_base_match=False,
    )
    print(f"\nLow-confidence case (unknown, no evidence):")
    print(f"  Score: {score2['score']}/100 (Grade: {score2['grade']})")

    # Medium confidence: LLM only
    score3 = compute_confidence(
        verdict="supported",
        evidence=[{"source": "Semantic Scholar (Smith et al., 2020)", "snippet": "The study confirmed...", "url": None}],
        llm_result={"verdict": "supported", "confidence": 80},
    )
    print(f"\nMedium-confidence case (LLM + S2):")
    print(f"  Score: {score3['score']}/100 (Grade: {score3['grade']})")

    return score1["score"] > score2["score"]


async def test_full_pipeline():
    """Test the full enhanced verification pipeline via API."""
    print("\n" + "=" * 60)
    print("TEST 5: Full Enhanced Pipeline (API endpoint)")
    print("=" * 60)

    from httpx import AsyncClient, ASGITransport
    from app.main import app

    test_text = """
    The Berlin Wall fell in 1989, marking the end of the Cold War division of Germany.
    Marie Curie won the Nobel Prize in Physics in 1903.
    Mars has two natural satellites called Phobos and Deimos.
    The Transformer architecture, introduced in the paper "Attention Is All You Need", revolutionized natural language processing in 2017.
    A randomized controlled trial with 500 participants showed that the drug reduced mortality by 45.3% (p < 0.001).
    """

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/v1/verify",
            json={
                "text": test_text,
                "include_evidence": True,
                "include_reference_report": False,
            },
            timeout=60.0,
        )

    print(f"\nStatus: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        summary = data["summary"]
        print(f"\nSummary: supported={summary['supported']}, contradicted={summary['contradicted']}, "
              f"unsupported={summary['unsupported']}, unknown={summary['unknown']}")

        print(f"\nClaims ({len(data['claims'])}):")
        for c in data["claims"]:
            conf = c.get("confidence")
            conf_str = f" [{conf['score']}/100 {conf['grade']}]" if conf else ""
            print(f"\n  [{c['verdict'].upper()}]{conf_str} {c['claim'][:80]}")
            if c.get("reasoning"):
                print(f"    Reasoning: {c['reasoning'][:100]}")
            for ev in c.get("evidence", [])[:2]:
                print(f"    Evidence: [{ev['source']}] {ev['snippet'][:80]}")

        if data.get("warnings"):
            print(f"\nWarnings: {data['warnings']}")

        return True
    else:
        print(f"Error: {resp.text}")
        return False


async def main():
    print("=" * 60)
    print("OpenFactCheck Enhanced Pipeline - Integration Tests")
    print("=" * 60)

    results = {}

    # Test 1: Semantic Scholar
    try:
        results["Semantic Scholar"] = await test_semantic_scholar()
    except Exception as e:
        print(f"\nSemantic Scholar test failed: {e}")
        results["Semantic Scholar"] = False

    # Test 2: LLM Verification
    try:
        results["LLM Verification"] = await test_llm_verification()
    except Exception as e:
        print(f"\nLLM Verification test failed: {e}")
        results["LLM Verification"] = False

    # Test 3: Claim Decomposition
    try:
        results["Claim Decomposition"] = await test_claim_decomposition()
    except Exception as e:
        print(f"\nClaim Decomposition test failed: {e}")
        results["Claim Decomposition"] = False

    # Test 4: Confidence Scoring
    try:
        results["Confidence Scoring"] = await test_confidence_scoring()
    except Exception as e:
        print(f"\nConfidence Scoring test failed: {e}")
        results["Confidence Scoring"] = False

    # Test 5: Full Pipeline
    try:
        results["Full Pipeline"] = await test_full_pipeline()
    except Exception as e:
        print(f"\nFull Pipeline test failed: {e}")
        import traceback
        traceback.print_exc()
        results["Full Pipeline"] = False

    # Summary
    print("\n" + "=" * 60)
    print("TEST RESULTS SUMMARY")
    print("=" * 60)
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {status}: {name}")

    total = len(results)
    passed = sum(1 for v in results.values() if v)
    print(f"\n  {passed}/{total} tests passed")


if __name__ == "__main__":
    asyncio.run(main())
