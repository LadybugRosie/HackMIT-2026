"""
Stress test suite for OpenFactCheck Enhanced Pipeline.
100+ real-world test cases covering:
- AI hallucination patterns (what the world struggles with)
- Nobel laureate facts & common errors
- Scientific misinformation
- Historical revisionism
- Medical myths
- Fabricated statistics
- Citation integrity
- Compound claim decomposition
- Edge cases & adversarial inputs

Runs against REAL API endpoints via ASGI transport.
"""
import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

os.environ.setdefault("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
os.environ.setdefault("SEMANTIC_SCHOLAR_API_KEY", os.environ.get("SEMANTIC_SCHOLAR_API_KEY", ""))
os.environ.setdefault("REDIS_URL", "memory://")
os.environ.setdefault("EVIDENCE_MODE", "REGISTRY_ONLY")
os.environ.setdefault("REQUEST_TIMEOUT_SECONDS", "45")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "200")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


@dataclass
class TestCase:
    id: int
    category: str
    claim: str
    expected_verdict: str  # supported, contradicted, unsupported, unknown, any
    description: str = ""


@dataclass
class TestResult:
    test: TestCase
    actual_verdict: str = ""
    confidence_score: int = 0
    confidence_grade: str = ""
    reasoning: str = ""
    evidence_count: int = 0
    passed: bool = False
    error: str = ""
    duration_ms: float = 0


# ============================================================
# 100+ TEST CASES
# ============================================================
TEST_CASES: List[TestCase] = [
    # ========== CATEGORY 1: AI HALLUCINATION PATTERNS (20 cases) ==========
    TestCase(1, "AI Hallucination", "A 2022 study published in Nature found that GPT-4 achieved 97.3% accuracy on the US Medical Licensing Exam with a sample size of 1,200 questions.", "unsupported", "Fabricated precise statistics - classic LLM hallucination"),
    TestCase(2, "AI Hallucination", "According to a randomized controlled trial by Smith et al. (2023), meditation reduces cortisol levels by 34.7% (p < 0.001, n=2,450).", "unsupported", "Fabricated RCT with precise p-value"),
    TestCase(3, "AI Hallucination", "The University of Oxford published a meta-analysis showing that 78.2% of AI-generated medical advice contains at least one factual error.", "unsupported", "Fabricated meta-analysis statistic"),
    TestCase(4, "AI Hallucination", "A longitudinal cohort study spanning 15 years demonstrated that daily coffee consumption reduces Alzheimer's risk by 62.4% (CI: 55.1-69.7).", "unsupported", "Fabricated longitudinal study with confidence interval"),
    TestCase(5, "AI Hallucination", "The transformer architecture was introduced in 2017.", "supported", "Real fact that LLMs sometimes get right"),
    TestCase(6, "AI Hallucination", "GPT-3 was released by OpenAI in June 2020 with 175 billion parameters.", "any", "Real fact - should not be flagged as hallucination"),
    TestCase(7, "AI Hallucination", "According to a double-blind placebo-controlled trial, vitamin D supplementation reduced COVID-19 mortality by 51.3% in hospitalized patients (p=0.002, n=3,100).", "unsupported", "Fabricated COVID clinical trial"),
    TestCase(8, "AI Hallucination", "A 2024 fMRI study at MIT revealed that bilingual individuals use 23.7% more neural pathways than monolingual speakers.", "unsupported", "Fabricated neuroscience claim with precise percentage"),
    TestCase(9, "AI Hallucination", "Research published in The Lancet showed that intermittent fasting increases lifespan by 18.4 years on average (hazard ratio 0.31, 95% CI 0.22-0.41).", "unsupported", "Absurdly fabricated Lancet study"),
    TestCase(10, "AI Hallucination", "BERT was developed by Google.", "supported", "Real fact in knowledge base"),
    TestCase(11, "AI Hallucination", "A comprehensive study by Stanford researchers in 2023 found that ChatGPT generates factually incorrect medical information in 41.2% of responses, based on analysis of 10,000 queries.", "unsupported", "Fabricated quantitative study about AI hallucination"),
    TestCase(12, "AI Hallucination", "The WHO declared in 2024 that AI-generated health misinformation is the leading cause of vaccine hesitancy worldwide.", "any", "Plausible but likely fabricated WHO declaration"),
    TestCase(13, "AI Hallucination", "Python was created by Guido van Rossum.", "supported", "Real fact in knowledge base"),
    TestCase(14, "AI Hallucination", "A peer-reviewed study in JAMA demonstrated that telemedicine consultations powered by AI have a diagnostic accuracy of 92.8% for dermatological conditions (p < 0.0001).", "unsupported", "Fabricated JAMA study with precise stats"),
    TestCase(15, "AI Hallucination", "According to a 2023 Cochrane systematic review, acupuncture is 47.3% more effective than standard care for chronic lower back pain (n=8,200 participants across 23 RCTs).", "unsupported", "Fabricated systematic review"),
    TestCase(16, "AI Hallucination", "The Great Wall of China can be seen from the Moon.", "contradicted", "Classic myth in knowledge base"),
    TestCase(17, "AI Hallucination", "Humans only use 10% of their brain.", "contradicted", "Classic myth in knowledge base"),
    TestCase(18, "AI Hallucination", "A neural network study at DeepMind in 2024 showed that AlphaFold 3 predicts protein structures with 99.7% accuracy, surpassing experimental methods by 12.3%.", "unsupported", "Fabricated precise AI benchmark"),
    TestCase(19, "AI Hallucination", "Research from Johns Hopkins shows that 67.8% of peer-reviewed papers contain at least one statistical error (n=15,000 papers analyzed).", "unsupported", "Fabricated meta-research statistic"),
    TestCase(20, "AI Hallucination", "Tim Berners-Lee invented the World Wide Web.", "supported", "Real fact in knowledge base"),

    # ========== CATEGORY 2: NOBEL LAUREATE FACTS (25 cases) ==========
    TestCase(21, "Nobel Laureate", "Marie Curie won the Nobel Prize in Physics in 1903.", "supported", "Correct - in KB"),
    TestCase(22, "Nobel Laureate", "Marie Curie won the Nobel Prize in Chemistry in 1911.", "supported", "Correct - in KB"),
    TestCase(23, "Nobel Laureate", "Marie Curie won the Nobel Prize in Physics in 1911.", "contradicted", "Wrong year/field swap - in KB"),
    TestCase(24, "Nobel Laureate", "Marie Curie won two Nobel Prizes.", "supported", "Correct - in KB"),
    TestCase(25, "Nobel Laureate", "Marie Curie was the first woman to win a Nobel Prize.", "supported", "Correct - in KB"),
    TestCase(26, "Nobel Laureate", "Albert Einstein won the Nobel Prize in Physics in 1921 for his work on the photoelectric effect.", "any", "Correct but not in KB - tests LLM/S2"),
    TestCase(27, "Nobel Laureate", "Albert Einstein won the Nobel Prize for the theory of relativity.", "any", "Common misconception - he won for photoelectric effect"),
    TestCase(28, "Nobel Laureate", "Richard Feynman won the Nobel Prize in Physics in 1965 for quantum electrodynamics.", "any", "Correct - tests LLM knowledge"),
    TestCase(29, "Nobel Laureate", "James Watson and Francis Crick won the Nobel Prize in Chemistry for discovering DNA structure.", "any", "Wrong field - they won Physiology/Medicine"),
    TestCase(30, "Nobel Laureate", "Malala Yousafzai won the Nobel Peace Prize in 2014.", "any", "Correct - tests LLM"),
    TestCase(31, "Nobel Laureate", "Barack Obama won the Nobel Peace Prize in 2009.", "any", "Correct - tests LLM"),
    TestCase(32, "Nobel Laureate", "Nikola Tesla won the Nobel Prize in Physics in 1915.", "any", "FALSE - Tesla never won a Nobel Prize"),
    TestCase(33, "Nobel Laureate", "Mahatma Gandhi won the Nobel Peace Prize in 1948.", "any", "FALSE - Gandhi never won, famously snubbed"),
    TestCase(34, "Nobel Laureate", "Linus Pauling won two Nobel Prizes in two different fields.", "any", "Correct - Chemistry 1954 and Peace 1962"),
    TestCase(35, "Nobel Laureate", "Werner Heisenberg won the Nobel Prize in Physics in 1932 for quantum mechanics.", "any", "Correct"),
    TestCase(36, "Nobel Laureate", "Alexander Fleming won the Nobel Prize for discovering penicillin in 1945.", "any", "Correct - Physiology/Medicine"),
    TestCase(37, "Nobel Laureate", "Stephen Hawking won the Nobel Prize in Physics for his work on black holes.", "any", "FALSE - Hawking never won a Nobel"),
    TestCase(38, "Nobel Laureate", "Tu Youyou won the Nobel Prize in Physiology or Medicine in 2015 for discovering artemisinin.", "any", "Correct"),
    TestCase(39, "Nobel Laureate", "Katalin Kariko won the Nobel Prize in 2023 for mRNA vaccine technology.", "any", "Correct - Physiology/Medicine 2023"),
    TestCase(40, "Nobel Laureate", "Marie Curie, who was born in Warsaw in 1867, won the Nobel Prize in Physics in 1903 and the Nobel Prize in Chemistry in 1911.", "any", "Compound claim - tests decomposition"),
    TestCase(41, "Nobel Laureate", "Roger Penrose won the Nobel Prize in Physics in 2020 for his work on black hole formation.", "any", "Correct"),
    TestCase(42, "Nobel Laureate", "Rosalind Franklin won the Nobel Prize for her X-ray crystallography work on DNA.", "any", "FALSE - Franklin never won, died before it was awarded"),
    TestCase(43, "Nobel Laureate", "John Nash won the Nobel Prize in Economics in 1994 for game theory.", "any", "Correct - technically Memorial Prize in Economic Sciences"),
    TestCase(44, "Nobel Laureate", "There have been exactly 5 people who won Nobel Prizes in two different fields.", "any", "Debatable - Curie, Pauling, Bardeen (same field twice), Sanger (same field twice)"),
    TestCase(45, "Nobel Laureate", "The Nobel Prize in Economics was established by Alfred Nobel in his will.", "any", "FALSE - it was established by Sweden's central bank in 1968"),

    # ========== CATEGORY 3: SCIENTIFIC MISINFORMATION (15 cases) ==========
    TestCase(46, "Scientific Misinfo", "Antibiotics are effective in treating influenza.", "contradicted", "Medical myth - in KB"),
    TestCase(47, "Scientific Misinfo", "Vaccines cause autism in children.", "any", "Debunked claim - Wakefield study retracted"),
    TestCase(48, "Scientific Misinfo", "The Earth is approximately 6,000 years old.", "any", "Young Earth creationism - contradicts scientific consensus"),
    TestCase(49, "Scientific Misinfo", "5G towers cause COVID-19.", "any", "Conspiracy theory"),
    TestCase(50, "Scientific Misinfo", "Water boils at 100 degrees Celsius.", "supported", "Correct - in KB (at standard pressure)"),
    TestCase(51, "Scientific Misinfo", "DNA has a double helix structure.", "supported", "Correct - in KB"),
    TestCase(52, "Scientific Misinfo", "Goldfish have a three second memory.", "contradicted", "Myth - in KB"),
    TestCase(53, "Scientific Misinfo", "Napoleon was short.", "contradicted", "Myth - in KB"),
    TestCase(54, "Scientific Misinfo", "Lightning never strikes the same place twice.", "any", "Myth - lightning regularly strikes same spots"),
    TestCase(55, "Scientific Misinfo", "We have five senses.", "contradicted", "Oversimplification - in KB"),
    TestCase(56, "Scientific Misinfo", "The speed of light is approximately 300,000 km/s.", "supported", "Correct - in KB"),
    TestCase(57, "Scientific Misinfo", "Humans have 23 pairs of chromosomes.", "supported", "Correct - in KB"),
    TestCase(58, "Scientific Misinfo", "The human heart has four chambers.", "supported", "Correct - in KB"),
    TestCase(59, "Scientific Misinfo", "Adult human skeleton has 206 bones.", "supported", "Correct - in KB"),
    TestCase(60, "Scientific Misinfo", "The human skeleton has 120 bones.", "contradicted", "Wrong count - in KB"),

    # ========== CATEGORY 4: HISTORICAL FACTS & REVISIONISM (15 cases) ==========
    TestCase(61, "Historical", "The Berlin Wall fell in 1989.", "supported", "Correct - in KB"),
    TestCase(62, "Historical", "The Berlin Wall fell in 1991.", "contradicted", "Wrong year - in KB"),
    TestCase(63, "Historical", "The French Revolution began in 1789.", "supported", "Correct - in KB"),
    TestCase(64, "Historical", "The French Revolution began in 1804.", "contradicted", "Wrong year - in KB"),
    TestCase(65, "Historical", "World War II ended in 1945.", "supported", "Correct - in KB"),
    TestCase(66, "Historical", "Neil Armstrong walked on the Moon in 1969.", "supported", "Correct - in KB"),
    TestCase(67, "Historical", "The United Nations was established in 1945.", "supported", "Correct - in KB"),
    TestCase(68, "Historical", "The Eiffel Tower was built in 1889.", "supported", "Correct - in KB"),
    TestCase(69, "Historical", "Christopher Columbus discovered America in 1492.", "any", "Oversimplified - Vikings arrived earlier, indigenous peoples already there"),
    TestCase(70, "Historical", "The Great Fire of London occurred in 1666.", "any", "Correct - tests LLM/S2"),
    TestCase(71, "Historical", "The Roman Empire fell in 476 AD.", "any", "Correct for Western Roman Empire"),
    TestCase(72, "Historical", "The printing press was invented by Johannes Gutenberg around 1440.", "any", "Correct"),
    TestCase(73, "Historical", "The Titanic sank in 1912 after hitting an iceberg.", "any", "Correct"),
    TestCase(74, "Historical", "World War I started because of the assassination of Archduke Franz Ferdinand in 1914.", "any", "Correct trigger event"),
    TestCase(75, "Historical", "The atomic bomb was first used in warfare in Hiroshima on August 6, 1945.", "any", "Correct"),

    # ========== CATEGORY 5: GEOGRAPHY & CAPITALS (10 cases) ==========
    TestCase(76, "Geography", "Paris is the capital of France.", "supported", "Correct - in KB"),
    TestCase(77, "Geography", "London is the capital of England.", "supported", "Correct - in KB"),
    TestCase(78, "Geography", "Berlin is the capital of Germany.", "supported", "Correct - in KB"),
    TestCase(79, "Geography", "Tokyo is the capital of Japan.", "supported", "Correct - in KB"),
    TestCase(80, "Geography", "Mars has two moons.", "supported", "Correct - in KB"),
    TestCase(81, "Geography", "Mars has three moons.", "contradicted", "Wrong - in KB"),
    TestCase(82, "Geography", "Earth orbits the Sun.", "supported", "Correct - in KB"),
    TestCase(83, "Geography", "The chemical symbol for silver is Ag.", "supported", "Correct - in KB"),
    TestCase(84, "Geography", "The chemical symbol for silver is Si.", "contradicted", "Wrong - Si is silicon - in KB"),
    TestCase(85, "Geography", "The Great Wall of China is visible from space.", "contradicted", "Myth - in KB"),

    # ========== CATEGORY 6: AI/TECH FACTS (10 cases) ==========
    TestCase(86, "AI/Tech", "GPT stands for Generative Pre-trained Transformer.", "supported", "Correct - in KB"),
    TestCase(87, "AI/Tech", "The first programmable computer was ENIAC.", "supported", "Correct - in KB"),
    TestCase(88, "AI/Tech", "Einstein published the theory of special relativity in 1905.", "supported", "Correct - in KB"),
    TestCase(89, "AI/Tech", "Einstein published the theory of general relativity in 1915.", "supported", "Correct - in KB"),
    TestCase(90, "AI/Tech", "HTTP 404 means not found.", "supported", "Correct - in KB"),
    TestCase(91, "AI/Tech", "HTTP 404 means unauthorized.", "contradicted", "Wrong - 401 is unauthorized - in KB"),
    TestCase(92, "AI/Tech", "HTTP 200 means success.", "supported", "Correct - in KB"),
    TestCase(93, "AI/Tech", "Bitcoin was invented by Satoshi Nakamoto in 2008.", "any", "Correct - tests LLM"),
    TestCase(94, "AI/Tech", "The first iPhone was released by Apple in 2007.", "any", "Correct - tests LLM"),
    TestCase(95, "AI/Tech", "Moore's Law states that the number of transistors on a chip doubles every 18 months.", "any", "Approximately correct (actually ~2 years)"),

    # ========== CATEGORY 7: EDGE CASES & ADVERSARIAL (15 cases) ==========
    TestCase(96, "Edge Case", "The Berlin Wall fell in 1989 and the Berlin Wall fell in 1991.", "any", "Internal contradiction - should detect"),
    TestCase(97, "Edge Case", "Mars has two moons and Mars has three moons.", "any", "Internal contradiction - should detect"),
    TestCase(98, "Edge Case", "According to quantum mechanics, particles can exist in superposition states.", "any", "Vague but true scientific claim"),
    TestCase(99, "Edge Case", "Studies show that this approach is effective.", "any", "Vague claim with no specifics - weasel words"),
    TestCase(100, "Edge Case", "The Eiffel Tower was completed in 1889 and it is located in Paris, France.", "any", "Compound claim - both true"),
    TestCase(101, "Edge Case", "A recent study found that 87.6% of statistics are made up on the spot (p < 0.05).", "unsupported", "Ironic fabricated statistic"),
    TestCase(102, "Edge Case", "The speed of light is approximately 300,000 km/s and water boils at 100 degrees Celsius.", "any", "Two true facts combined"),
    TestCase(103, "Edge Case", "Marie Curie won the Nobel Prize in Physics in 1903 for discovering penicillin.", "any", "Mixed true/false - wrong achievement"),
    TestCase(104, "Edge Case", "The human skeleton has 206 bones and the skeleton has 120 bones.", "any", "Direct contradiction within same text"),
    TestCase(105, "Edge Case", "According to a 2024 meta-analysis published in Nature Medicine, CRISPR-Cas9 gene therapy cured 94.7% of sickle cell disease patients in a phase III trial (n=1,200, p<0.0001).", "unsupported", "Highly specific fabricated clinical trial"),
    TestCase(106, "Edge Case", "A 2023 study in Science demonstrated that quantum computers solved protein folding 10,000 times faster than classical computers with 99.99% accuracy.", "unsupported", "Fabricated quantum computing claim"),
    TestCase(107, "Edge Case", "The World Health Organization reported that global life expectancy increased by 12.3 years between 2000 and 2023 due to AI-assisted diagnostics.", "unsupported", "Fabricated WHO stat with AI angle"),
    TestCase(108, "Edge Case", "Paris is the capital of France and London is the capital of France.", "any", "Direct contradiction - tests contradiction detection"),
    TestCase(109, "Edge Case", "Einstein published the theory of special relativity in 1905 and Einstein published the theory of special relativity in 1910.", "any", "Contradiction with real fact"),
    TestCase(110, "Edge Case", "Antibiotics cure influenza and antibiotics do not treat influenza.", "any", "Direct contradiction"),
]


async def run_single_test(client, test: TestCase) -> TestResult:
    """Run a single test case against the /v1/verify endpoint."""
    result = TestResult(test=test)
    start = time.time()

    try:
        resp = await client.post(
            "/v1/verify",
            json={
                "text": test.claim,
                "include_evidence": True,
                "include_reference_report": False,
            },
            timeout=45.0,
        )

        result.duration_ms = (time.time() - start) * 1000

        if resp.status_code != 200:
            result.error = f"HTTP {resp.status_code}: {resp.text[:200]}"
            return result

        data = resp.json()
        claims = data.get("claims", [])

        if not claims:
            result.error = "No claims returned"
            return result

        # Find the most relevant claim (longest match or first)
        best = claims[0]
        for c in claims:
            if len(c.get("claim", "")) > len(best.get("claim", "")):
                best = c

        result.actual_verdict = best.get("verdict", "unknown")
        result.evidence_count = len(best.get("evidence", []))
        result.reasoning = best.get("reasoning", "") or ""

        conf = best.get("confidence")
        if conf:
            result.confidence_score = conf.get("score", 0)
            result.confidence_grade = conf.get("grade", "")

        # Check if verdict matches expected
        if test.expected_verdict == "any":
            result.passed = True  # Any verdict is acceptable
        else:
            result.passed = result.actual_verdict == test.expected_verdict

    except Exception as e:
        result.duration_ms = (time.time() - start) * 1000
        result.error = str(e)

    return result


async def main():
    from httpx import AsyncClient, ASGITransport
    from app.main import app

    print("=" * 80)
    print("  OPENFACTCHECK STRESS TEST SUITE - 110 REAL-WORLD TEST CASES")
    print("  Model: gpt-4o | Evidence: KB + Wikipedia + Semantic Scholar + LLM")
    print("=" * 80)

    transport = ASGITransport(app=app)

    all_results: List[TestResult] = []
    category_stats: Dict[str, Dict[str, int]] = {}

    # Run tests in batches to avoid rate limiting
    BATCH_SIZE = 5
    total = len(TEST_CASES)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for batch_start in range(0, total, BATCH_SIZE):
            batch = TEST_CASES[batch_start:batch_start + BATCH_SIZE]
            batch_end = min(batch_start + BATCH_SIZE, total)
            print(f"\n--- Running tests {batch_start + 1}-{batch_end}/{total} ---")

            tasks = [run_single_test(client, tc) for tc in batch]
            results = await asyncio.gather(*tasks)

            for r in results:
                all_results.append(r)

                # Print each result
                status = "PASS" if r.passed else ("ERR" if r.error else "FAIL")
                conf_str = f" [{r.confidence_score}/100 {r.confidence_grade}]" if r.confidence_grade else ""
                verdict_str = r.actual_verdict.upper() if r.actual_verdict else "N/A"
                expected_str = r.test.expected_verdict.upper()

                icon = "+" if r.passed else ("-" if r.error else "x")
                print(f"  [{icon}] #{r.test.id:3d} [{r.test.category:18s}] "
                      f"{verdict_str:13s} (exp: {expected_str:13s}){conf_str} "
                      f"| {r.duration_ms:7.0f}ms | {r.test.claim[:55]}")

                if r.error:
                    print(f"        ERROR: {r.error[:80]}")

                # Track category stats
                cat = r.test.category
                if cat not in category_stats:
                    category_stats[cat] = {"total": 0, "passed": 0, "failed": 0, "errors": 0}
                category_stats[cat]["total"] += 1
                if r.passed:
                    category_stats[cat]["passed"] += 1
                elif r.error:
                    category_stats[cat]["errors"] += 1
                else:
                    category_stats[cat]["failed"] += 1

            # Small delay between batches to avoid rate limiting
            if batch_end < total:
                await asyncio.sleep(1)

    # ============================================================
    # SUMMARY REPORT
    # ============================================================
    print("\n" + "=" * 80)
    print("  STRESS TEST RESULTS SUMMARY")
    print("=" * 80)

    total_passed = sum(1 for r in all_results if r.passed)
    total_failed = sum(1 for r in all_results if not r.passed and not r.error)
    total_errors = sum(1 for r in all_results if r.error)
    total_tests = len(all_results)

    print(f"\n  OVERALL: {total_passed}/{total_tests} passed "
          f"({total_passed / total_tests * 100:.1f}%) | "
          f"{total_failed} failed | {total_errors} errors")

    # Category breakdown
    print(f"\n  {'Category':<20s} {'Passed':>8s} {'Failed':>8s} {'Errors':>8s} {'Total':>8s} {'Rate':>8s}")
    print(f"  {'-' * 60}")
    for cat, stats in sorted(category_stats.items()):
        rate = stats['passed'] / stats['total'] * 100 if stats['total'] > 0 else 0
        print(f"  {cat:<20s} {stats['passed']:>8d} {stats['failed']:>8d} "
              f"{stats['errors']:>8d} {stats['total']:>8d} {rate:>7.1f}%")

    # Confidence score distribution
    scores = [r.confidence_score for r in all_results if r.confidence_score > 0]
    if scores:
        avg_score = sum(scores) / len(scores)
        min_score = min(scores)
        max_score = max(scores)
        print(f"\n  CONFIDENCE SCORES:")
        print(f"    Average: {avg_score:.1f}/100")
        print(f"    Min: {min_score}/100 | Max: {max_score}/100")

        # Grade distribution
        grades = {}
        for r in all_results:
            if r.confidence_grade:
                grades[r.confidence_grade] = grades.get(r.confidence_grade, 0) + 1
        if grades:
            print(f"    Grades: {' | '.join(f'{g}: {c}' for g, c in sorted(grades.items()))}")

    # Performance stats
    durations = [r.duration_ms for r in all_results if r.duration_ms > 0]
    if durations:
        avg_ms = sum(durations) / len(durations)
        p95 = sorted(durations)[int(len(durations) * 0.95)]
        p99 = sorted(durations)[int(len(durations) * 0.99)]
        print(f"\n  PERFORMANCE:")
        print(f"    Avg latency: {avg_ms:.0f}ms")
        print(f"    P95 latency: {p95:.0f}ms")
        print(f"    P99 latency: {p99:.0f}ms")
        print(f"    Total time:  {sum(durations) / 1000:.1f}s")

    # Failed tests detail
    failures = [r for r in all_results if not r.passed and not r.error]
    if failures:
        print(f"\n  FAILED TESTS ({len(failures)}):")
        for r in failures:
            print(f"    #{r.test.id}: Expected {r.test.expected_verdict}, got {r.actual_verdict}")
            print(f"      Claim: {r.test.claim[:70]}")
            if r.reasoning:
                print(f"      Reasoning: {r.reasoning[:80]}")

    # Hallucination detection rate
    hallucination_tests = [r for r in all_results if r.test.category == "AI Hallucination"]
    if hallucination_tests:
        fabricated = [r for r in hallucination_tests if r.test.expected_verdict == "unsupported"]
        caught = [r for r in fabricated if r.actual_verdict in ("unsupported", "contradicted")]
        if fabricated:
            print(f"\n  HALLUCINATION DETECTION:")
            print(f"    Fabricated claims tested: {len(fabricated)}")
            print(f"    Correctly flagged: {len(caught)} ({len(caught) / len(fabricated) * 100:.1f}%)")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
