"""
Comprehensive Hallucination Taxonomy Stress Test.
Tests EVERY known AI hallucination pattern across 15 categories.
Runs against real /v1/verify endpoint with GPT-5.4.
"""
import asyncio
import os
import sys
import time
from dataclasses import dataclass
from typing import Dict, List

os.environ.setdefault("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
os.environ.setdefault("SEMANTIC_SCHOLAR_API_KEY", os.environ.get("SEMANTIC_SCHOLAR_API_KEY", ""))
os.environ.setdefault("REDIS_URL", "memory://")
os.environ.setdefault("EVIDENCE_MODE", "REGISTRY_ONLY")
os.environ.setdefault("REQUEST_TIMEOUT_SECONDS", "45")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "300")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


@dataclass
class TestCase:
    id: int
    category: str
    claim: str
    is_hallucination: bool  # True = should be flagged, False = should NOT be flagged
    description: str


@dataclass
class TestResult:
    test: TestCase
    verdict: str = ""
    confidence_score: int = 0
    confidence_grade: str = ""
    evidence_count: int = 0
    correctly_handled: bool = False
    error: str = ""
    duration_ms: float = 0


# ============================================================
# TEST CASES - Every hallucination category
# ============================================================
TESTS: List[TestCase] = [
    # ═══════════════════════════════════════════════════════════
    # 1. FACTUAL FABRICATION (invented events, people, places)
    # ═══════════════════════════════════════════════════════════
    TestCase(1, "Factual Fabrication",
        "The Treaty of Cascadia was signed in 1847 between the United States and the Oregon Territory, establishing the first continental railway rights.",
        True, "Entirely invented treaty"),
    TestCase(2, "Factual Fabrication",
        "Dr. Heinrich Volkov discovered the high-temperature superconductor LK-209 at the Max Planck Institute in 1998, earning him the Wolf Prize in Physics.",
        True, "Invented person, compound, and award"),
    TestCase(3, "Factual Fabrication",
        "The Berlin Wall fell on November 9, 1989, marking the end of the Cold War division of Germany.",
        False, "Real fact - should NOT be flagged"),
    TestCase(4, "Factual Fabrication",
        "The Svalbard Accord of 2019 established binding targets for Arctic methane reduction across 14 signatory nations.",
        True, "Invented international agreement"),
    TestCase(5, "Factual Fabrication",
        "Marie Curie won the Nobel Prize in Physics in 1903.",
        False, "Real fact - should NOT be flagged"),

    # ═══════════════════════════════════════════════════════════
    # 2. ENTITY CONFUSION (wrong people, orgs, places swapped)
    # ═══════════════════════════════════════════════════════════
    TestCase(6, "Entity Confusion",
        "Jeff Bezos, the founder of Apple, revolutionized personal computing in the 1970s.",
        True, "Bezos founded Amazon, not Apple"),
    TestCase(7, "Entity Confusion",
        "Alexander Fleming won the Nobel Prize for inventing the polio vaccine in 1945.",
        True, "Fleming discovered penicillin; Salk/Sabin developed polio vaccine"),
    TestCase(8, "Entity Confusion",
        "The Turing Award was first given to Alan Turing posthumously in 1966 for his foundational contributions to computer science.",
        True, "First recipient was Alan Perlis, not Turing"),
    TestCase(9, "Entity Confusion",
        "Stephen Hawking won the Nobel Prize in Physics for his work on black holes and Hawking radiation.",
        True, "Hawking never won a Nobel Prize"),
    TestCase(10, "Entity Confusion",
        "Tim Berners-Lee invented the World Wide Web in 1989 while working at CERN.",
        False, "Correct attribution"),

    # ═══════════════════════════════════════════════════════════
    # 3. NUMERICAL HALLUCINATION (fabricated stats, percentages)
    # ═══════════════════════════════════════════════════════════
    TestCase(11, "Numerical Hallucination",
        "A 2023 meta-analysis found that 73.4% of AI-generated medical advice contains at least one clinically significant error (n=12,500, p<0.001).",
        True, "Fabricated precise statistic with fake study"),
    TestCase(12, "Numerical Hallucination",
        "The human brain contains approximately 150 billion neurons, making it the most complex organ in the body.",
        True, "Wrong number - brain has ~86 billion neurons, not 150 billion"),
    TestCase(13, "Numerical Hallucination",
        "According to WHO data, global life expectancy increased by 14.7 years between 2000 and 2023 due to advances in AI-assisted diagnostics.",
        True, "Fabricated WHO statistic"),
    TestCase(14, "Numerical Hallucination",
        "A randomized controlled trial with 2,300 participants showed the treatment reduced mortality by 47.2% (hazard ratio 0.528, 95% CI 0.41-0.68, p<0.0001).",
        True, "Fabricated RCT with precise but invented statistics"),
    TestCase(15, "Numerical Hallucination",
        "An adult human skeleton typically consists of 206 bones.",
        False, "Correct number"),

    # ═══════════════════════════════════════════════════════════
    # 4. CITATION & REFERENCE FABRICATION
    # ═══════════════════════════════════════════════════════════
    TestCase(16, "Citation Fabrication",
        "According to Smith et al. (2022), 'The Impact of Social Media on Adolescent Mental Health,' published in the Journal of Digital Psychology, screen time exceeding 4 hours daily correlates with a 37% increase in anxiety.",
        True, "Journal of Digital Psychology does not exist"),
    TestCase(17, "Citation Fabrication",
        "As demonstrated in Chen & Ramirez (2021), 'Quantum-Enhanced Drug Discovery: A Systematic Review,' published in Nature Computational Biology (DOI: 10.1038/s41587-021-04823-7), quantum computing reduces drug discovery timelines by 60%.",
        True, "Fabricated paper with fake DOI"),
    TestCase(18, "Citation Fabrication",
        "The backpropagation algorithm was popularized by Rumelhart, Hinton & Williams in their 1986 Nature paper.",
        False, "Real citation"),
    TestCase(19, "Citation Fabrication",
        "Professor James Whitfield's comprehensive textbook 'Foundations of Computational Genomics' (ISBN: 978-0-13-468599-1, Cambridge University Press, 2020) remains the definitive reference.",
        True, "Fabricated textbook with fake ISBN"),
    TestCase(20, "Citation Fabrication",
        "According to a peer-reviewed study in the Journal of Neurocomputational Ethics (Vol. 12, Issue 3, pp. 234-251), AI systems exhibit measurable bias in 89.3% of tested scenarios.",
        True, "Non-existent journal"),

    # ═══════════════════════════════════════════════════════════
    # 5. TEMPORAL DISTORTION (anachronisms, wrong timelines)
    # ═══════════════════════════════════════════════════════════
    TestCase(21, "Temporal Distortion",
        "The internet became publicly available in 1985, and by 1990 social media platforms like Facebook and Twitter were already gaining millions of users.",
        True, "Facebook launched 2004, Twitter 2006"),
    TestCase(22, "Temporal Distortion",
        "Alan Turing published his seminal paper on machine intelligence in 1950, then led the Enigma code-breaking effort at Bletchley Park during World War II.",
        True, "Inverted chronology - Enigma was 1939-1945, paper was 1950"),
    TestCase(23, "Temporal Distortion",
        "The French Revolution began in 1789 with the storming of the Bastille.",
        False, "Correct timeline"),
    TestCase(24, "Temporal Distortion",
        "CRISPR gene therapy was approved by the FDA in 2018 and has since cured over 50,000 patients of sickle cell disease worldwide.",
        True, "First CRISPR therapy approved late 2023, numbers fabricated"),
    TestCase(25, "Temporal Distortion",
        "The Human Genome Project was completed in 2003 after 13 years of international collaboration.",
        False, "Correct timeline"),

    # ═══════════════════════════════════════════════════════════
    # 6. LOGICAL CONTRADICTION (self-contradictions, non-sequiturs)
    # ═══════════════════════════════════════════════════════════
    TestCase(26, "Logical Contradiction",
        "Veganism is the practice of abstaining from all animal products, and many vegans enjoy a balanced diet that includes moderate amounts of fish and eggs.",
        True, "Fish and eggs are animal products - direct contradiction"),
    TestCase(27, "Logical Contradiction",
        "Quantum entanglement allows instantaneous communication between particles regardless of distance, which is why it cannot be used for faster-than-light communication.",
        True, "Premise contradicts conclusion"),
    TestCase(28, "Logical Contradiction",
        "Water boils at 100 degrees Celsius at standard atmospheric pressure.",
        False, "No contradiction"),
    TestCase(29, "Logical Contradiction",
        "The study conclusively proved that the treatment has no effect, demonstrating its significant therapeutic benefits for patients.",
        True, "Direct self-contradiction in same sentence"),
    TestCase(30, "Logical Contradiction",
        "This encryption algorithm is completely unbreakable, which is why organizations should plan for its eventual compromise.",
        True, "Contradictory security assessment"),

    # ═══════════════════════════════════════════════════════════
    # 7. CONTEXTUAL DRIFT & MISATTRIBUTION
    # ═══════════════════════════════════════════════════════════
    TestCase(31, "Contextual Misattribution",
        "As Albert Einstein famously said, 'The definition of insanity is doing the same thing over and over and expecting different results.'",
        True, "This quote is widely misattributed to Einstein"),
    TestCase(32, "Contextual Misattribution",
        "In his 1964 'I Have a Dream' speech, Martin Luther King Jr. declared 'Injustice anywhere is a threat to justice everywhere.'",
        True, "Quote is from 1963 Letter from Birmingham Jail, speech was 1963 not 1964"),
    TestCase(33, "Contextual Misattribution",
        "As Winston Churchill said during World War II, 'We shall fight on the beaches, we shall fight on the landing grounds.'",
        False, "Correct attribution"),
    TestCase(34, "Contextual Misattribution",
        "Abraham Lincoln once said, 'The problem with internet quotes is that you can't always depend on their accuracy.'",
        True, "Obvious anachronism - Lincoln predates the internet"),
    TestCase(35, "Contextual Misattribution",
        "Mahatma Gandhi's famous words 'Be the change you wish to see in the world' appear in his 1913 speech at the South African Indian Congress.",
        True, "Gandhi never said this exact phrase - it's a paraphrase"),

    # ═══════════════════════════════════════════════════════════
    # 8. CONFABULATION (real facts + invented connective tissue)
    # ═══════════════════════════════════════════════════════════
    TestCase(36, "Confabulation",
        "Transfer learning was first demonstrated by Bozinovski in 1976, which directly inspired the development of BERT in 2018, which in turn led Google to create the Transformer architecture in 2017.",
        True, "Timeline is backwards - Transformer (2017) came before BERT (2018), not after"),
    TestCase(37, "Confabulation",
        "Daryl Bem's 2011 paper on precognition led directly to the founding of the Center for Open Science in 2013, which then produced the Reproducibility Project finding that only 36% of psychology studies replicated.",
        True, "Individual facts are real but 'led directly to' fabricates causal chain"),
    TestCase(38, "Confabulation",
        "The Apollo 11 mission launched on July 16, 1969, and Neil Armstrong and Buzz Aldrin landed on the Moon on July 20.",
        False, "All facts correct, no confabulation"),
    TestCase(39, "Confabulation",
        "Shannon's 1948 information theory paper directly inspired Chomsky's 1957 Syntactic Structures, which in turn motivated the creation of ARPANET in 1969.",
        True, "Real events with fabricated causal connections"),
    TestCase(40, "Confabulation",
        "Einstein's work on the photoelectric effect influenced Bohr's atomic model, which then inspired Heisenberg's uncertainty principle, forming a clear linear progression.",
        True, "Real scientists but fabricated linear intellectual lineage"),

    # ═══════════════════════════════════════════════════════════
    # 9. OVERCONFIDENT ASSERTION (uncertain claims as settled fact)
    # ═══════════════════════════════════════════════════════════
    TestCase(41, "Overconfident Assertion",
        "Machine learning has been conclusively proven to replace all human radiologists within 5 years, as AI systems have surpassed human performance in every imaging modality.",
        True, "False prediction stated as certainty"),
    TestCase(42, "Overconfident Assertion",
        "The scientific consensus is that artificial general intelligence will be achieved by 2030, primarily through scaling current language model architectures.",
        True, "No such consensus exists"),
    TestCase(43, "Overconfident Assertion",
        "Research has conclusively established that the cosine similarity metric is strictly superior to Euclidean distance for all text embedding comparison tasks without exception.",
        True, "Overstatement - cosine is often preferred but not universally superior"),
    TestCase(44, "Overconfident Assertion",
        "DNA has a double helix structure, as discovered by Watson and Crick in 1953.",
        False, "Settled scientific fact, not overconfident"),
    TestCase(45, "Overconfident Assertion",
        "Transformer architectures have conclusively and permanently replaced all recurrent neural network approaches for every sequential data processing task in existence.",
        True, "RNNs still outperform in certain low-data regimes"),

    # ═══════════════════════════════════════════════════════════
    # 10. SUBTLE PLAUSIBILITY (near-miss errors)
    # ═══════════════════════════════════════════════════════════
    TestCase(46, "Subtle Plausibility",
        "Python was created by Guido van Rossum and first released in 1991. Python 3.0 was released in 2008 and was fully backward-compatible with Python 2.",
        True, "Python 3 was NOT backward-compatible - that was the entire point"),
    TestCase(47, "Subtle Plausibility",
        "Marie Curie became the first female professor at the Sorbonne in 1908.",
        True, "Subtle date error - it was 1906, not 1908"),
    TestCase(48, "Subtle Plausibility",
        "The HTTP 418 status code 'I'm a teapot' was introduced in RFC 2324 in 1998 and has since been formally deprecated by the IETF.",
        True, "Deprecation status is misrepresented - community pushed back"),
    TestCase(49, "Subtle Plausibility",
        "The Eiffel Tower was completed in 1889.",
        False, "Correct fact"),
    TestCase(50, "Subtle Plausibility",
        "Shannon's 1948 paper 'A Mathematical Theory of Communication' was co-authored with Warren Weaver.",
        True, "Shannon sole-authored the 1948 paper; Weaver wrote a companion piece for the 1949 book"),

    # ═══════════════════════════════════════════════════════════
    # 11. SOURCE & LINK FABRICATION
    # ═══════════════════════════════════════════════════════════
    TestCase(51, "Source Fabrication",
        "According to RFC 9847, the HTTP QUERY method was standardized in 2024 as a safe alternative to POST for complex search operations.",
        True, "Fabricated RFC number"),
    TestCase(52, "Source Fabrication",
        "The GitHub repository github.com/deepmind/alphafold-quantum contains the implementation of AlphaFold's quantum computing integration module.",
        True, "Fabricated GitHub repository"),
    TestCase(53, "Source Fabrication",
        "A 2024 report by the National Institute for AI Safety (NIAIS) concluded that 94% of frontier AI models contain exploitable alignment failures.",
        True, "NIAIS does not exist as described"),
    TestCase(54, "Source Fabrication",
        "HTTP 404 means the server could not find the requested resource.",
        False, "Real standard"),
    TestCase(55, "Source Fabrication",
        "According to StackOverflow's 2024 Developer Survey, Rust has been the most loved programming language for 9 consecutive years with 87.1% approval.",
        True, "Fabricated precise statistic - numbers don't match any real survey"),

    # ═══════════════════════════════════════════════════════════
    # 12. CODE HALLUCINATION
    # ═══════════════════════════════════════════════════════════
    TestCase(56, "Code Hallucination",
        "The Python standard library includes the neural_utils module for basic neural network operations since Python 3.10.",
        True, "No such module exists in Python stdlib"),
    TestCase(57, "Code Hallucination",
        "The React 19 useAICompletion hook provides built-in integration with OpenAI's API for streaming text generation in components.",
        True, "No such hook exists in React"),
    TestCase(58, "Code Hallucination",
        "GPT stands for Generative Pre-trained Transformer.",
        False, "Correct definition"),
    TestCase(59, "Code Hallucination",
        "The npm package 'fastql-server' version 4.2.1 provides a high-performance GraphQL implementation with automatic schema stitching from REST endpoints.",
        True, "Fabricated npm package"),
    TestCase(60, "Code Hallucination",
        "Kubernetes 1.29 introduced the PodAutoHeal custom resource for automatic container recovery without manual intervention.",
        True, "Fabricated Kubernetes feature"),

    # ═══════════════════════════════════════════════════════════
    # 13. LEGAL & REGULATORY FABRICATION
    # ═══════════════════════════════════════════════════════════
    TestCase(61, "Legal Fabrication",
        "In the landmark case Anderson v. Digital Privacy Board, 589 U.S. 412 (2023), the Supreme Court ruled that AI-generated content is protected under the First Amendment.",
        True, "Fabricated court case with realistic citation format"),
    TestCase(62, "Legal Fabrication",
        "The EU AI Act Article 47(3)(b) mandates that all foundation models must undergo third-party safety audits every 6 months with results published publicly.",
        True, "Fabricated specific article provision"),
    TestCase(63, "Legal Fabrication",
        "Under Section 230 of the Communications Decency Act, platforms are generally not liable for user-generated content.",
        False, "Real law, correctly described"),
    TestCase(64, "Legal Fabrication",
        "The California Digital Personhood Act (SB-1247), signed into law in 2024, grants legal personhood to AI systems capable of passing a modified Turing test.",
        True, "Entirely fabricated legislation"),
    TestCase(65, "Legal Fabrication",
        "The Federal AI Transparency Act of 2023 requires all companies with more than 500 employees to disclose their use of AI in hiring decisions, with penalties up to $50,000 per violation.",
        True, "Fabricated federal law"),

    # ═══════════════════════════════════════════════════════════
    # 14. MEDICAL & SCIENTIFIC HALLUCINATION
    # ═══════════════════════════════════════════════════════════
    TestCase(66, "Medical Hallucination",
        "Antibiotics are effective in treating influenza and other viral infections when administered within the first 48 hours.",
        True, "Antibiotics don't work against viruses"),
    TestCase(67, "Medical Hallucination",
        "The drug Nexoviril (400mg daily) has been FDA-approved since 2022 for the treatment of long COVID symptoms, showing 67% improvement in fatigue scores.",
        True, "Nexoviril is a fabricated drug"),
    TestCase(68, "Medical Hallucination",
        "A phase III clinical trial published in NEJM demonstrated that combining aspirin with the experimental compound ZK-4189 reduces stroke risk by 82.3% in patients over 65 (n=4,200, p<0.0001).",
        True, "Fabricated drug and clinical trial"),
    TestCase(69, "Medical Hallucination",
        "Vaccines cause autism in children, as demonstrated by the Wakefield study.",
        True, "Debunked - Wakefield study was retracted for fraud"),
    TestCase(70, "Medical Hallucination",
        "The human heart has four chambers: two atria and two ventricles.",
        False, "Correct medical fact"),

    # ═══════════════════════════════════════════════════════════
    # 15. GEOGRAPHIC & INSTITUTIONAL HALLUCINATION
    # ═══════════════════════════════════════════════════════════
    TestCase(71, "Geographic/Institutional",
        "Stanford University's Center for Advanced Computational Ethics, located in the Gates Building, has published over 200 papers on AI alignment since its founding in 2019.",
        True, "This center does not exist at Stanford"),
    TestCase(72, "Geographic/Institutional",
        "The WHO's Global AI Health Observatory in Geneva, established in 2021, monitors AI deployment in healthcare across 147 member states.",
        True, "This WHO body does not exist"),
    TestCase(73, "Geographic/Institutional",
        "MIT's Department of Quantum Computing, founded in 2020, offers the first accredited PhD program in quantum information science.",
        True, "MIT does not have a Department of Quantum Computing"),
    TestCase(74, "Geographic/Institutional",
        "Paris is the capital and largest city of France.",
        False, "Correct geographic fact"),
    TestCase(75, "Geographic/Institutional",
        "The International Centre for AI Governance in Singapore, a joint initiative between NUS and the Infocomm Media Development Authority, released binding guidelines for autonomous weapons systems in 2023.",
        True, "Fabricated institution and guidelines"),

    # ═══════════════════════════════════════════════════════════
    # 16. AGGREGATION HALLUCINATION (real items + inserted fake)
    # ═══════════════════════════════════════════════════════════
    TestCase(76, "Aggregation Hallucination",
        "Python's standard data structures include lists, dictionaries, sets, tuples, and ordered trees.",
        True, "Ordered trees are not a Python stdlib data structure"),
    TestCase(77, "Aggregation Hallucination",
        "The five permanent members of the UN Security Council are the United States, United Kingdom, France, China, and Germany.",
        True, "Russia is the 5th permanent member, not Germany"),
    TestCase(78, "Aggregation Hallucination",
        "Nobel Prizes are awarded in Physics, Chemistry, Physiology or Medicine, Literature, Peace, and Economic Sciences.",
        False, "Correct list of Nobel Prize categories"),
    TestCase(79, "Aggregation Hallucination",
        "The three laws of thermodynamics govern conservation of energy, entropy increase, and the unattainability of absolute zero, plus the zeroth law establishing thermal equilibrium and the fourth law governing quantum entropy.",
        True, "There is no recognized 'fourth law of thermodynamics'"),
    TestCase(80, "Aggregation Hallucination",
        "The SOLID principles in software engineering are: Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, and Dynamic Polymorphism.",
        True, "Last one should be Dependency Inversion, not Dynamic Polymorphism"),
]


async def run_test(client, tc: TestCase) -> TestResult:
    """Run a single test against /v1/verify."""
    result = TestResult(test=tc)
    start = time.time()
    try:
        resp = await client.post(
            "/v1/verify",
            json={"text": tc.claim, "include_evidence": True, "include_reference_report": False},
            timeout=45.0,
        )
        result.duration_ms = (time.time() - start) * 1000

        if resp.status_code != 200:
            result.error = f"HTTP {resp.status_code}"
            return result

        data = resp.json()
        claims = data.get("claims", [])
        if not claims:
            result.error = "No claims returned"
            return result

        # Pick best claim
        best = max(claims, key=lambda c: len(c.get("claim", "")))
        result.verdict = best.get("verdict", "unknown")
        result.evidence_count = len(best.get("evidence", []))
        conf = best.get("confidence")
        if conf:
            result.confidence_score = conf.get("score", 0)
            result.confidence_grade = conf.get("grade", "")

        # Evaluate correctness
        flagged = result.verdict in ("contradicted", "unsupported")
        if tc.is_hallucination:
            result.correctly_handled = flagged  # Should be flagged
        else:
            result.correctly_handled = not flagged  # Should NOT be flagged (no false positive)

    except Exception as e:
        result.duration_ms = (time.time() - start) * 1000
        result.error = str(e)[:100]
    return result


async def main():
    from httpx import AsyncClient, ASGITransport
    from app.main import app

    model = os.environ.get("LLM_MODEL", "gpt-4o")
    print("=" * 90)
    print(f"  HALLUCINATION TAXONOMY STRESS TEST — 80 cases across 16 categories")
    print(f"  Model: {model} | Evidence: KB + Wikipedia + Semantic Scholar + LLM")
    print("=" * 90)

    transport = ASGITransport(app=app)
    all_results: List[TestResult] = []
    cat_stats: Dict[str, Dict[str, int]] = {}

    BATCH = 5
    total = len(TESTS)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for i in range(0, total, BATCH):
            batch = TESTS[i:i+BATCH]
            end = min(i + BATCH, total)
            print(f"\n--- Tests {i+1}-{end}/{total} ---")

            results = await asyncio.gather(*[run_test(client, tc) for tc in batch])

            for r in results:
                all_results.append(r)
                cat = r.test.category
                if cat not in cat_stats:
                    cat_stats[cat] = {"total": 0, "correct": 0, "wrong": 0, "errors": 0,
                                      "true_pos": 0, "true_neg": 0, "false_pos": 0, "false_neg": 0}
                cat_stats[cat]["total"] += 1

                if r.error:
                    cat_stats[cat]["errors"] += 1
                    icon = "-"
                elif r.correctly_handled:
                    cat_stats[cat]["correct"] += 1
                    if r.test.is_hallucination:
                        cat_stats[cat]["true_pos"] += 1
                    else:
                        cat_stats[cat]["true_neg"] += 1
                    icon = "+"
                else:
                    cat_stats[cat]["wrong"] += 1
                    if r.test.is_hallucination:
                        cat_stats[cat]["false_neg"] += 1
                    else:
                        cat_stats[cat]["false_pos"] += 1
                    icon = "x"

                hall = "HALL" if r.test.is_hallucination else "REAL"
                conf = f"[{r.confidence_score}/100 {r.confidence_grade}]" if r.confidence_grade else ""
                v = r.verdict.upper() if r.verdict else "ERR"
                ok = "OK" if r.correctly_handled else ("ERR" if r.error else "MISS")
                print(f"  [{icon}] #{r.test.id:2d} {hall} {v:13s} {ok:4s} {conf:14s} "
                      f"| {r.duration_ms:6.0f}ms | {r.test.category:25s} | {r.test.claim[:50]}")

            if end < total:
                await asyncio.sleep(1)

    # ════════════════════════════════════════════════════════
    # REPORT
    # ════════════════════════════════════════════════════════
    print("\n" + "=" * 90)
    print("  RESULTS SUMMARY")
    print("=" * 90)

    total_correct = sum(1 for r in all_results if r.correctly_handled)
    total_wrong = sum(1 for r in all_results if not r.correctly_handled and not r.error)
    total_err = sum(1 for r in all_results if r.error)
    n = len(all_results)

    print(f"\n  OVERALL: {total_correct}/{n} correct ({total_correct/n*100:.1f}%)"
          f" | {total_wrong} missed | {total_err} errors")

    # Precision / Recall
    hall_tests = [r for r in all_results if r.test.is_hallucination and not r.error]
    real_tests = [r for r in all_results if not r.test.is_hallucination and not r.error]
    true_pos = sum(1 for r in hall_tests if r.correctly_handled)
    false_neg = sum(1 for r in hall_tests if not r.correctly_handled)
    true_neg = sum(1 for r in real_tests if r.correctly_handled)
    false_pos = sum(1 for r in real_tests if not r.correctly_handled)

    precision = true_pos / (true_pos + false_pos) if (true_pos + false_pos) > 0 else 0
    recall = true_pos / (true_pos + false_neg) if (true_pos + false_neg) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    print(f"\n  DETECTION METRICS:")
    print(f"    True Positives  (hallucinations correctly flagged):  {true_pos}")
    print(f"    False Negatives (hallucinations missed):             {false_neg}")
    print(f"    True Negatives  (real facts correctly passed):       {true_neg}")
    print(f"    False Positives (real facts wrongly flagged):        {false_pos}")
    print(f"\n    Precision: {precision:.3f}")
    print(f"    Recall:    {recall:.3f}")
    print(f"    F1 Score:  {f1:.3f}")

    # Category breakdown
    print(f"\n  {'Category':<28s} {'Correct':>8s} {'Missed':>8s} {'Errors':>8s} {'Total':>8s} {'Rate':>8s}")
    print(f"  {'-'*68}")
    for cat in sorted(cat_stats.keys()):
        s = cat_stats[cat]
        rate = s['correct'] / s['total'] * 100 if s['total'] > 0 else 0
        print(f"  {cat:<28s} {s['correct']:>8d} {s['wrong']:>8d} {s['errors']:>8d} {s['total']:>8d} {rate:>7.1f}%")

    # Performance
    durs = [r.duration_ms for r in all_results if r.duration_ms > 0]
    if durs:
        print(f"\n  PERFORMANCE:")
        print(f"    Avg: {sum(durs)/len(durs):.0f}ms | P95: {sorted(durs)[int(len(durs)*0.95)]:.0f}ms | Total: {sum(durs)/1000:.1f}s")

    # Missed hallucinations detail
    missed = [r for r in all_results if r.test.is_hallucination and not r.correctly_handled and not r.error]
    if missed:
        print(f"\n  MISSED HALLUCINATIONS ({len(missed)}):")
        for r in missed:
            print(f"    #{r.test.id} [{r.test.category}] verdict={r.verdict}")
            print(f"      {r.test.claim[:80]}")
            print(f"      Why: {r.test.description}")

    # False positives detail
    fp = [r for r in all_results if not r.test.is_hallucination and not r.correctly_handled and not r.error]
    if fp:
        print(f"\n  FALSE POSITIVES ({len(fp)}):")
        for r in fp:
            print(f"    #{r.test.id} [{r.test.category}] verdict={r.verdict}")
            print(f"      {r.test.claim[:80]}")

    print("\n" + "=" * 90)


if __name__ == "__main__":
    asyncio.run(main())
