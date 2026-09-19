"""
Test that confidence scores are preserved through the full API pipeline.
Specifically tests that _add_doi_evidence and _run_contradiction_pass
don't drop confidence fields when creating new ClaimResult objects.
"""
import asyncio
import sys
import os

# Add parent to path so we can import app
sys.path.insert(0, os.path.dirname(__file__))

from app.schemas import ClaimResult, ConfidenceScore, ConfidenceBreakdown, EvidenceItem
from app.api import _add_doi_evidence, _run_contradiction_pass
from app.ref_integrity import ReferenceReport


def make_claim_with_confidence(claim_text: str, verdict: str = "supported") -> ClaimResult:
    """Create a ClaimResult with a non-null confidence score."""
    return ClaimResult(
        claim=claim_text,
        verdict=verdict,
        confidence=ConfidenceScore(
            score=72,
            breakdown=ConfidenceBreakdown(
                source_quality=80,
                evidence_strength=65,
                source_agreement=70,
            ),
            grade="B",
            explanation="Test confidence",
        ),
        reasoning="Test reasoning",
        evidence=[EvidenceItem(source="Test", snippet="Test snippet", url=None)],
    )


def test_add_doi_evidence_preserves_confidence():
    """_add_doi_evidence must not drop confidence/reasoning."""
    claims = [
        make_claim_with_confidence("The Earth orbits the Sun."),
        make_claim_with_confidence("Water boils at 100°C.", verdict="unknown"),
    ]
    # Empty reference report (no DOIs/URLs)
    report = ReferenceReport(dois=[], urls=[])

    enhanced = _add_doi_evidence(claims, report)

    for i, claim in enumerate(enhanced):
        assert claim.confidence is not None, (
            f"Claim {i} ({claim.claim!r}) lost its confidence after _add_doi_evidence"
        )
        assert claim.confidence.score == 72, (
            f"Claim {i} confidence score changed: {claim.confidence.score}"
        )
        assert claim.reasoning == "Test reasoning", (
            f"Claim {i} lost reasoning after _add_doi_evidence"
        )

    print("PASS: _add_doi_evidence preserves confidence and reasoning")


def test_run_contradiction_pass_preserves_confidence():
    """_run_contradiction_pass must not drop confidence for non-contradicted claims."""
    claims = [
        make_claim_with_confidence("Paris is the capital of France."),
        make_claim_with_confidence("Berlin is the capital of Germany."),
    ]

    result = _run_contradiction_pass(claims)

    for i, claim in enumerate(result):
        assert claim.confidence is not None, (
            f"Claim {i} ({claim.claim!r}) lost its confidence after _run_contradiction_pass"
        )
        assert claim.confidence.score == 72
        assert claim.reasoning == "Test reasoning"

    print("PASS: _run_contradiction_pass preserves confidence and reasoning")


def test_contradiction_detection_preserves_confidence():
    """When claims ARE contradicted, confidence should still be preserved."""
    claims = [
        make_claim_with_confidence("Mars has two moons.", verdict="unknown"),
        make_claim_with_confidence("Mars has five moons.", verdict="unknown"),
    ]

    result = _run_contradiction_pass(claims)

    contradicted = [c for c in result if c.verdict == "contradicted"]
    assert len(contradicted) == 2, f"Expected 2 contradicted claims, got {len(contradicted)}"

    for claim in contradicted:
        assert claim.confidence is not None, (
            f"Contradicted claim ({claim.claim!r}) lost confidence"
        )
        assert claim.confidence.score == 72

    print("PASS: contradicted claims preserve confidence")


def test_full_pipeline_confidence():
    """Integration test: run the full verify endpoint and check confidence."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    response = client.post("/v1/verify", json={
        "text": "The Earth orbits the Sun.",
        "include_evidence": True,
    })

    assert response.status_code == 200, f"Got {response.status_code}: {response.text}"
    data = response.json()

    for i, claim in enumerate(data["claims"]):
        assert claim["confidence"] is not None, (
            f"Claim {i} ({claim['claim']!r}) has null confidence in API response!\n"
            f"Full claim: {claim}"
        )
        assert claim["confidence"]["score"] > 0 or claim["confidence"]["grade"], (
            f"Claim {i} has empty confidence: {claim['confidence']}"
        )

    print(f"PASS: All {len(data['claims'])} claims have non-null confidence in API response")
    for claim in data["claims"]:
        c = claim["confidence"]
        print(f"  [{c['grade']}] score={c['score']} - {claim['claim'][:60]}")


if __name__ == "__main__":
    test_add_doi_evidence_preserves_confidence()
    test_run_contradiction_pass_preserves_confidence()
    test_contradiction_detection_preserves_confidence()
    print()
    test_full_pipeline_confidence()
    print("\nAll tests passed!")
