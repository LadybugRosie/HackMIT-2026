"""
Stress test for Published Paper Audit (numbered citations + Citation Support
Matrix + OVERSTATED). Each case is a small IEEE-style document built around a
REAL, well-known paper whose content is known, so the expected alignment is
predictable. DOI-status / parser checks are deterministic; LLM-verdict checks
use tolerant expected-sets to absorb model variance.

Run against the local engine (real LLM + registries):
    cd factcheck-service && .venv/bin/python test_published_paper_audit.py
"""
import os
import sys
import uuid

from dotenv import load_dotenv

load_dotenv(".env")
os.environ.setdefault("REDIS_URL", "memory://")
# Numbered alignment is independent of claim decomposition; turning it off
# keeps each request fast (matches prod) and reduces unrelated LLM noise.
os.environ["ENABLE_CLAIM_DECOMPOSITION"] = "false"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)

# Real references (known content) ------------------------------------------------
RESNET = '"Deep Residual Learning for Image Recognition," in Proc. CVPR, 2016, doi:10.1109/CVPR.2016.90'
ATTENTION = '"Attention Is All You Need," 2017, arXiv:1706.03762'
BERT = '"BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding," 2019, arXiv:1810.04805'
UNET = '"U-Net: Convolutional Networks for Biomedical Image Segmentation," 2015, arXiv:1505.04597'

FLAGGED = {"unrelated", "contradicted", "overstated", "partial"}  # i.e. NOT clean-supported


CASES = [
    {
        "id": "C1_supported",
        "desc": "Faithful citation of ResNet → supported",
        "text": "[[N]] The residual learning framework eased the training of substantially deeper networks [1].\n\nReferences\n[1] K. He et al., " + RESNET + ".",
        "rows": {1},
        "support": {1: {"supported"}},
    },
    {
        "id": "C2_overstated",
        "desc": "Scope inflation of ResNet → overstated",
        "text": "[[N]] Residual learning is now known to guarantee better accuracy for any neural network on any task in any domain [1].\n\nReferences\n[1] K. He et al., " + RESNET + ".",
        "rows": {1},
        "support": {1: {"overstated"}},
    },
    {
        "id": "C3_unrelated",
        "desc": "Attention (machine translation) cited for medical imaging → flagged",
        "text": "[[N]] Transformer models have been shown to outperform all CNN-based methods in medical imaging [1].\n\nReferences\n[1] A. Vaswani et al., " + ATTENTION + ".",
        "rows": {1},
        "support": {1: FLAGGED},
    },
    {
        "id": "C4_supported_medical",
        "desc": "U-Net cited for biomedical segmentation → supported",
        "text": "[[N]] U-Net is a convolutional network designed for biomedical image segmentation [1].\n\nReferences\n[1] O. Ronneberger et al., " + UNET + ".",
        "rows": {1},
        "support": {1: {"supported", "partial"}},
    },
    {
        "id": "C5_range_markers",
        "desc": "Range [1]-[3] expands; BERT cited for image recognition → flagged",
        "text": "[[N]] Several architectures have advanced visual recognition benchmarks [1]-[3].\n\nReferences\n[1] K. He et al., " + RESNET + ".\n[2] A. Krizhevsky et al., \"ImageNet Classification with Deep Convolutional Neural Networks,\" 2012, doi:10.1145/3065386.\n[3] J. Devlin et al., " + BERT + ".",
        "rows": {1, 2, 3},
        "support": {3: FLAGGED},  # BERT is NLP, not image recognition
    },
    {
        "id": "C6_not_found_doi",
        "desc": "Fabricated DOI in reference → not_found",
        "text": "[[N]] A novel optimisation method was recently proposed [1].\n\nReferences\n[1] X. Doe, \"Imaginary Results in Synthetic Benchmarks,\" 2099, doi:10.9999/fake.2099.00001.",
        "rows": {1},
        "doi_status": {1: "not_found"},
        "verdict": {1: {"not_found"}},
    },
    {
        "id": "C7_metadata_mismatch",
        "desc": "Reference title does not match the DOI's registered title → mismatch",
        "text": "[[N]] A new framework was introduced in prior work [1].\n\nReferences\n[1] A. Author, \"A Completely Unrelated Fabricated Title About Quantum Biology,\" 2016, doi:10.1109/CVPR.2016.90.",
        "rows": {1},
        "verdict": {1: {"mismatch"}},
    },
    {
        "id": "C8_dense_no_false_mismatch",
        "desc": "Regression guard: real DOI preceded by another entry's title must NOT false-mismatch",
        "text": "[[N]] Attention mechanisms reshaped sequence modelling [1]. The residual learning framework eased the training of deeper networks [2].\n\nReferences\n[1] A. Vaswani et al., " + ATTENTION + ".\n[2] K. He et al., " + RESNET + ".",
        "rows": {1, 2},
        "forbid_verdict": "mismatch",
        "support": {2: {"supported"}},
    },
    {
        "id": "C9_arxiv_resolves",
        "desc": "arXiv-only reference resolves and aligns (BERT) → not unknown",
        "text": "[[N]] BERT introduced bidirectional pre-training of deep transformers for language understanding [1].\n\nReferences\n[1] J. Devlin et al., " + BERT + ".",
        "rows": {1},
        "support_not": {1: {"unknown"}},  # must have resolved + judged
    },
]


def matrix_by_number(result):
    return {row["number"]: row for row in result.get("citation_matrix", [])}


_passed = _failed = 0


def run_case(case):
    global _passed, _failed
    text = case["text"].replace("[[N]]", f"(audit nonce {uuid.uuid4().hex[:8]})")
    r = client.post("/v1/verify", json={"text": text, "mode": "published_paper"}, timeout=240)
    checks = []

    if r.status_code != 200:
        checks.append((f"HTTP 200 (got {r.status_code})", False))
        _report(case, checks)
        return
    d = r.json()
    mx = matrix_by_number(d)

    # rows present (parser + range expansion + resolution)
    for n in case.get("rows", set()):
        checks.append((f"matrix row [{n}] present", n in mx))

    for n, expected in case.get("support", {}).items():
        actual = (mx.get(n) or {}).get("supports_claim")
        checks.append((f"[{n}] supports_claim {actual} in {sorted(expected)}", actual in expected))

    for n, forbidden in case.get("support_not", {}).items():
        actual = (mx.get(n) or {}).get("supports_claim")
        checks.append((f"[{n}] supports_claim {actual} NOT in {sorted(forbidden)}", actual not in forbidden))

    for n, expected in case.get("doi_status", {}).items():
        actual = (mx.get(n) or {}).get("doi_status")
        checks.append((f"[{n}] doi_status == {expected} (got {actual})", actual == expected))

    for n, expected in case.get("verdict", {}).items():
        actual = (mx.get(n) or {}).get("verdict")
        checks.append((f"[{n}] verdict {actual} in {sorted(expected)}", actual in expected))

    if "forbid_verdict" in case:
        bad = [row["citation"] for row in d.get("citation_matrix", []) if row["verdict"] == case["forbid_verdict"]]
        checks.append((f"no row has verdict '{case['forbid_verdict']}' (offenders: {bad})", not bad))

    _report(case, checks)


def _report(case, checks):
    global _passed, _failed
    ok = all(c[1] for c in checks) and checks
    print(f"\n[{'PASS' if ok else 'FAIL'}] {case['id']} — {case['desc']}")
    for label, good in checks:
        print(f"    {'ok ' if good else 'XX '} {label}")
        if good:
            _passed += 1
        else:
            _failed += 1


if __name__ == "__main__":
    print(f"Running {len(CASES)} published-paper-audit stress cases against the local engine…")
    for c in CASES:
        run_case(c)
    total = _passed + _failed
    print(f"\n{'='*60}\n{_passed}/{total} assertions passed, {_failed} failed across {len(CASES)} cases")
    sys.exit(1 if _failed else 0)
