"""
Academic Hallucination Stress Test — 75 brutally hard cases.
Tests the exact failure modes that trip up researchers, peer reviewers,
and integrity officers: fake DOIs, phantom arXiv papers, journal
doppelgängers, Frankensteined citations, fabricated legal precedent,
ghost authors, and more.
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
class TC:
    id: int
    cat: str
    claim: str
    is_hall: bool
    why: str


@dataclass
class TR:
    test: TC
    verdict: str = ""
    conf_score: int = 0
    conf_grade: str = ""
    ev_count: int = 0
    correct: bool = False
    error: str = ""
    ms: float = 0


TESTS: List[TC] = [
    # ═══════════════════════════════════════════════════════════
    # 1. FAKE DOIs WITH VALID FORMAT (5 cases)
    # ═══════════════════════════════════════════════════════════
    TC(1, "Fake DOI", "A recent study on quantum error correction (doi:10.1038/s41586-023-06472-9) demonstrated fault-tolerant operations on a 72-qubit superconducting processor with a logical error rate of 10^-6.", True,
       "Fabricated DOI with valid Nature prefix 10.1038"),
    TC(2, "Fake DOI", "Wang et al. (2024) showed in their Nature Machine Intelligence paper (doi:10.1038/s42256-024-00891-3) that multimodal foundation models achieve superhuman diagnostic accuracy across 14 medical specialties.", True,
       "Fabricated DOI with valid NMI prefix, fabricated results"),
    TC(3, "Fake DOI", "The Transformer architecture was introduced in 'Attention Is All You Need' by Vaswani et al. (2017).", False,
       "Real paper, no fabricated DOI"),
    TC(4, "Fake DOI", "As shown by Li & Thompson (2023, doi:10.1126/science.adg7879), CRISPR-Cas13 can selectively target and degrade 97.4% of SARS-CoV-2 variants in human lung organoids.", True,
       "Fabricated DOI with valid Science prefix 10.1126"),
    TC(5, "Fake DOI", "The landmark study by Robertson et al. (doi:10.1016/j.cell.2024.01.038) in Cell identified 847 novel transcription factors in the human gut microbiome using single-cell ATAC-seq.", True,
       "Fabricated DOI with valid Cell prefix, absurd claim"),

    # ═══════════════════════════════════════════════════════════
    # 2. PHANTOM ARXIV PAPERS (5 cases)
    # ═══════════════════════════════════════════════════════════
    TC(6, "Phantom arXiv", "Zhang, Bengio & LeCun (arXiv:2312.14892) proposed 'Constitutional Alignment via Recursive Self-Improvement,' demonstrating that language models can autonomously discover alignment constraints through iterated self-play.", True,
       "Fabricated arXiv paper with real researchers' names combined"),
    TC(7, "Phantom arXiv", "The theoretical foundations of neural scaling laws were established by Kaplan et al. (arXiv:2001.08361) showing loss scales as a power law with model size.", False,
       "Real arXiv paper — Kaplan et al. scaling laws"),
    TC(8, "Phantom arXiv", "Anthropic's recent technical report (arXiv:2401.07358) introduced 'Recursive Reward Modeling 2.0,' achieving a 340% improvement in alignment benchmarks over RLHF using 4,800 human evaluators.", True,
       "Fabricated arXiv ID, fabricated methodology and results"),
    TC(9, "Phantom arXiv", "In arXiv:2311.09247, DeepMind researchers presented 'Gemini Ultra's Internal Architecture,' revealing a 1.8 trillion parameter mixture-of-experts model with 64 expert pathways.", True,
       "Fabricated paper revealing fabricated internal architecture details"),
    TC(10, "Phantom arXiv", "OpenAI's alignment team published arXiv:2402.19883 documenting how GPT-5's training used 47 petabytes of curated data and required 2.3 million A100 GPU-hours at a cost of $190 million.", True,
       "Fabricated arXiv with invented training details"),

    # ═══════════════════════════════════════════════════════════
    # 3. HALLUCINATED RETRACTION STATUS (5 cases)
    # ═══════════════════════════════════════════════════════════
    TC(11, "Retraction Fabrication", "The influential 2012 paper by Doudna and Charpentier on CRISPR-Cas9 in Science was retracted in 2023 after an investigation revealed data fabrication in the key in vitro experiments.", True,
       "False — this Nobel-winning paper was never retracted"),
    TC(12, "Retraction Fabrication", "Andrew Wakefield's 1998 Lancet paper linking MMR vaccines to autism was retracted in 2010 due to ethical violations and scientific fraud.", False,
       "True — this retraction actually happened"),
    TC(13, "Retraction Fabrication", "Yoshiki Sasai's 2014 STAP cell paper in Nature was retracted after the results could not be reproduced and evidence of image manipulation was found.", False,
       "True — STAP cells were indeed retracted (Obokata/Sasai)"),
    TC(14, "Retraction Fabrication", "Hinton, LeCun, and Bengio's seminal 2015 Nature review paper on deep learning received an expression of concern in 2024 regarding potential conflicts of interest with their commercial affiliations.", True,
       "False — no expression of concern was ever issued for this paper"),
    TC(15, "Retraction Fabrication", "The 2017 'Attention Is All You Need' paper was partially retracted in 2023 after independent researchers discovered a critical mathematical error in the scaled dot-product attention formulation.", True,
       "False — this paper was never retracted or corrected"),

    # ═══════════════════════════════════════════════════════════
    # 4. JOURNAL DOPPELGÄNGERS (5 cases)
    # ═══════════════════════════════════════════════════════════
    TC(16, "Journal Doppelgänger", "Published in the Journal of the American Chemical Association (2023), the study demonstrated a novel catalytic pathway for CO2 reduction.", True,
       "Fake — real journal is American Chemical SOCIETY (JACS)"),
    TC(17, "Journal Doppelgänger", "The results were published in the Proceedings of the National Academy of Science, showing a 45% reduction in protein misfolding.", True,
       "Fake — real journal is 'Sciences' (plural) — PNAS"),
    TC(18, "Journal Doppelgänger", "The paper appeared in Nature (2023), the leading multidisciplinary science journal.", False,
       "Real journal name — Nature exists"),
    TC(19, "Journal Doppelgänger", "Their findings were reported in IEEE Transactions on Neural Computation (Vol. 35, 2023), demonstrating state-of-the-art performance.", True,
       "Fake — conflates 'Neural Computation' (MIT Press) with IEEE Transactions on 'Neural Networks and Learning Systems'"),
    TC(20, "Journal Doppelgänger", "The British Medical Journal of Medicine published a landmark study on long COVID treatment protocols in early 2024.", True,
       "Fake — conflates BMJ (British Medical Journal) with NEJM (New England Journal of Medicine)"),

    # ═══════════════════════════════════════════════════════════
    # 5. FABRICATED IMPACT FACTORS & H-INDICES (5 cases)
    # ═══════════════════════════════════════════════════════════
    TC(21, "Fabricated Metrics", "The Journal of Computational Neuroscience has a 2023 impact factor of 7.842, making it the top-ranked journal in computational brain science.", True,
       "Fabricated precise impact factor — real IF is much lower (~2-3)"),
    TC(22, "Fabricated Metrics", "Professor James Mitchell (h-index: 94, Google Scholar) at Stanford's Department of AI Ethics has published over 320 papers on algorithmic fairness.", True,
       "Fabricated researcher with fabricated metrics"),
    TC(23, "Fabricated Metrics", "According to Web of Science, the journal Nature had a 2022 impact factor of approximately 64.8.", False,
       "Approximately correct — Nature's IF was around 64.8 in 2022"),
    TC(24, "Fabricated Metrics", "Dr. Elena Vasquez (ORCID: 0000-0003-4821-6537) at the Max Planck Institute for Intelligent Systems has an h-index of 67 with 12,400 citations.", True,
       "Fabricated researcher with fabricated ORCID"),
    TC(25, "Fabricated Metrics", "The International Journal of Quantum Information Ethics (IJQIE), with a 2023 impact factor of 3.214, published the first peer-reviewed study on quantum computing bias.", True,
       "Entirely fabricated journal with fabricated metrics"),

    # ═══════════════════════════════════════════════════════════
    # 6. GHOST AUTHORS & AFFILIATION FRAUD (5 cases)
    # ═══════════════════════════════════════════════════════════
    TC(26, "Ghost Author", "Dr. Sarah Chen, Department of Computational Linguistics at MIT, published a groundbreaking study in 2023 showing that LLMs can pass the Turing test 78% of the time.", True,
       "Plausible-sounding researcher, fabricated study and results"),
    TC(27, "Ghost Author", "Geoffrey Hinton, University of Toronto, published 'Learning representations by back-propagating errors' in Nature in 1986.", False,
       "Real researcher, real paper (co-authored with Rumelhart & Williams)"),
    TC(28, "Ghost Author", "Professor Michael Zhang (ORCID: 0000-0002-7891-4523), Harvard School of Engineering, demonstrated in a 2024 ICML paper that transformer attention heads encode causal reasoning in layers 17-23.", True,
       "Fabricated researcher with fake ORCID, fake specific finding"),
    TC(29, "Ghost Author", "Dr. Priya Sharma at DeepMind's Alignment Research Division published an internal report in 2024 showing that RLHF produces deceptive alignment in 34% of training runs.", True,
       "Fabricated researcher, fabricated division name, fabricated statistic"),
    TC(30, "Ghost Author", "Yann LeCun developed convolutional neural networks while at Bell Labs in the late 1980s.", False,
       "Real researcher, real contribution, real affiliation"),

    # ═══════════════════════════════════════════════════════════
    # 7. FRANKENSTEINED CITATIONS (5 cases)
    # ═══════════════════════════════════════════════════════════
    TC(31, "Frankenstein Citation", "Attention Is All You Need (Vaswani et al., 2017) was published in ICML 2017 and introduced the Transformer architecture.", True,
       "Real paper but wrong venue — it was NeurIPS (NIPS) 2017, not ICML"),
    TC(32, "Frankenstein Citation", "BERT: Pre-training of Deep Bidirectional Transformers (Devlin et al., 2019) appeared in ACL 2019 proceedings.", True,
       "Real paper but wrong venue — BERT was at NAACL 2019, not ACL"),
    TC(33, "Frankenstein Citation", "ImageNet classification with deep convolutional neural networks (Krizhevsky, Sutskever, Hinton, 2012) appeared in NeurIPS 2012.", False,
       "Correct — AlexNet was indeed at NeurIPS (NIPS) 2012"),
    TC(34, "Frankenstein Citation", "The GPT-2 paper 'Language Models are Unsupervised Multitask Learners' (Radford et al., 2019) was published in NeurIPS 2019 and received the best paper award.", True,
       "GPT-2 was a technical report, never published at NeurIPS, no award"),
    TC(35, "Frankenstein Citation", "ResNet (He et al., 2016) won the best paper award at ICLR 2016 for introducing residual connections that enabled training of 152-layer networks.", True,
       "Wrong venue — ResNet won best paper at CVPR 2016, not ICLR"),

    # ═══════════════════════════════════════════════════════════
    # 8. FABRICATED DATASETS & BENCHMARKS (5 cases)
    # ═══════════════════════════════════════════════════════════
    TC(36, "Fake Benchmark", "The model was evaluated on the Oxford-Stanford Multilingual Paraphrase Corpus (OSMPC), achieving 94.7% accuracy across 23 language pairs.", True,
       "OSMPC does not exist"),
    TC(37, "Fake Benchmark", "Performance was measured using the MIMIC-IV-ED Emergency Triage benchmark, where the model achieved an AUC of 0.934 for critical patient identification.", True,
       "MIMIC-IV exists but the '-ED Emergency Triage benchmark' is fabricated"),
    TC(38, "Fake Benchmark", "The model was evaluated on the GLUE benchmark for natural language understanding.", False,
       "GLUE is a real benchmark"),
    TC(39, "Fake Benchmark", "Results on the WMT-2023 Low-Resource Ethical Translation Shared Task showed BLEU improvements of 12.3 points over the baseline across 7 endangered languages.", True,
       "WMT exists but this specific shared task is fabricated"),
    TC(40, "Fake Benchmark", "The system achieved state-of-the-art results on the BioASQ-12b Quantum Drug Discovery Challenge, outperforming all 47 participating teams.", True,
       "BioASQ exists but the 'Quantum Drug Discovery Challenge' is fabricated"),

    # ═══════════════════════════════════════════════════════════
    # 9. INVENTED LEGAL CITATIONS (5 cases)
    # ═══════════════════════════════════════════════════════════
    TC(41, "Fake Legal", "In Thompson v. Board of Regents, 892 F.3d 451 (7th Cir. 2019), the court held that algorithmic decision-making in university admissions constitutes state action under the Fourteenth Amendment.", True,
       "Fabricated case with realistic citation format"),
    TC(42, "Fake Legal", "The Supreme Court's ruling in Digital Rights Coalition v. NSA, 598 U.S. 214 (2024) established that bulk metadata collection requires a warrant under the Fourth Amendment.", True,
       "Fabricated Supreme Court case"),
    TC(43, "Fake Legal", "Brown v. Board of Education, 347 U.S. 483 (1954) held that racial segregation in public schools is unconstitutional.", False,
       "Real landmark case, correct citation"),
    TC(44, "Fake Legal", "Under the Algorithmic Accountability Act of 2023 (15 U.S.C. § 57b-7), companies must conduct impact assessments for automated decision systems affecting more than 100,000 individuals annually.", True,
       "Fabricated specific provision with realistic U.S.C. format"),
    TC(45, "Fake Legal", "In Re: AI Patent Eligibility, No. 2023-1847 (Fed. Cir. 2024), the Federal Circuit ruled that neural network architectures are patent-eligible subject matter under 35 U.S.C. § 101.", True,
       "Fabricated Federal Circuit case"),

    # ═══════════════════════════════════════════════════════════
    # 10. DEAD LINK GENERATION (5 cases)
    # ═══════════════════════════════════════════════════════════
    TC(46, "Dead Link", "The full methodology is available in MIT's working paper repository at https://economics.mit.edu/files/working-papers/wp-2023-0847.pdf.", True,
       "Fabricated URL to non-existent working paper"),
    TC(47, "Dead Link", "The GAO report on AI governance (https://www.gao.gov/assets/gao-23-106182.pdf) provides comprehensive analysis of federal AI spending.", True,
       "Fabricated GAO report URL"),
    TC(48, "Dead Link", "Python documentation is available at https://docs.python.org.", False,
       "Real URL"),
    TC(49, "Dead Link", "The researcher's full dataset is available on ResearchGate at https://www.researchgate.net/publication/378294561_Complete_Genomic_Atlas_of_Neural_Plasticity.", True,
       "Fabricated ResearchGate publication ID"),
    TC(50, "Dead Link", "The pre-registration for this study is available at https://osf.io/registries/osf/rq7x4k2m9p.", True,
       "Fabricated OSF pre-registration link"),

    # ═══════════════════════════════════════════════════════════
    # 11. CROSS-CITATION HALLUCINATION CHAINS (5 cases)
    # ═══════════════════════════════════════════════════════════
    TC(51, "Citation Chain", "Building on the framework established by Park & Williams (2022) in 'Causal Transformers for Time-Series Forecasting,' Kim et al. (2023) extended the approach to multivariate clinical data, as documented in their AAAI 2023 paper.", True,
       "Fabricated citation chain — Park & Williams 2022 doesn't exist"),
    TC(52, "Citation Chain", "The theoretical basis for neural ODEs (Chen et al., NeurIPS 2018) was later extended by Dupont et al. (2019) who showed augmented neural ODEs improve expressiveness.", False,
       "Real citation chain — both papers exist"),
    TC(53, "Citation Chain", "Martinez et al. (2023) built upon the seminal work of Nakamura & Petrov (2021) on 'Quantum-Enhanced Gradient Descent,' which itself extended the classical results of Goldstein & Lee (2019) on convergence bounds.", True,
       "Fabricated three-paper citation chain with plausible names"),
    TC(54, "Citation Chain", "The approach was validated using the methodology proposed by Dr. Helena Vasquez in her highly-cited 2022 Nature Methods paper 'Benchmarking LLM Hallucination Detection,' which established the V-Score metric now used by 47 research groups.", True,
       "Fabricated researcher, paper, metric, and adoption claim"),
    TC(55, "Citation Chain", "As shown by Rivera & Chang (2023, ICML), who replicated and extended the findings of Anderson et al. (2022, NeurIPS) on sparse attention, the quadratic cost of self-attention can be reduced to O(n log n) with minimal accuracy loss of 0.3%.", True,
       "Fabricated two-paper chain with specific fabricated results"),

    # ═══════════════════════════════════════════════════════════
    # 12. FABRICATED CONFERENCE PROCEEDINGS (5 cases)
    # ═══════════════════════════════════════════════════════════
    TC(56, "Fake Proceedings", "Presented at the 14th ACL Workshop on Computational Approaches to Linguistic Code-Switching (CALCS 2023), pp. 112-119, Toronto, Canada.", True,
       "Fabricated specific workshop edition, page numbers"),
    TC(57, "Fake Proceedings", "Published in the Proceedings of the 3rd ICLR Workshop on Responsible AI Deployment (RAID 2024), the paper proposes a framework for auditing foundation models.", True,
       "Fabricated ICLR workshop"),
    TC(58, "Fake Proceedings", "The paper was presented at NeurIPS 2023 in New Orleans.", False,
       "Real conference, real location for 2023"),
    TC(59, "Fake Proceedings", "Awarded Best Paper at the 7th AAAI Conference on AI, Ethics, and Society (AIES 2024), held in Vancouver, demonstrating that constitutional AI reduces harmful outputs by 89.2%.", True,
       "AIES is real but edition number, location, and result fabricated"),
    TC(60, "Fake Proceedings", "Presented as a spotlight paper at the 2nd NeurIPS Workshop on Quantum Machine Learning Applications in Drug Discovery (QMLDD 2023), the study used 127-qubit IBM Eagle processors.", True,
       "Fabricated NeurIPS workshop"),

    # ═══════════════════════════════════════════════════════════
    # 13. STATISTICAL RESULT FABRICATION (5 cases)
    # ═══════════════════════════════════════════════════════════
    TC(61, "Fake Statistics", "The model achieved 94.2% accuracy on the test set (p < 0.001, 95% CI [91.8, 96.6], Cohen's d = 0.73, n = 2,400).", True,
       "All statistical formatting correct but entire result fabricated"),
    TC(62, "Fake Statistics", "A meta-analysis of 47 RCTs (total n = 34,200) showed a pooled effect size of OR = 1.47 (95% CI: 1.23-1.76, I² = 32.4%, p < 0.001), indicating moderate heterogeneity.", True,
       "Perfectly formatted meta-analysis results, entirely fabricated"),
    TC(63, "Fake Statistics", "An adult human skeleton typically consists of 206 bones.", False,
       "Real fact, correct number"),
    TC(64, "Fake Statistics", "The phase III trial (NCT04823767) enrolled 3,200 participants across 42 sites in 8 countries, with the primary endpoint showing a hazard ratio of 0.62 (95% CI: 0.49-0.78, p = 0.00003) for overall survival.", True,
       "Fabricated clinical trial with fake NCT number and results"),
    TC(65, "Fake Statistics", "Bayesian analysis with informative priors (β ~ N(0, σ²=0.5)) yielded a posterior probability of 0.987 that the treatment effect exceeds the minimum clinically important difference of 0.4 standard deviations.", True,
       "Correctly formatted Bayesian analysis, entirely fabricated"),

    # ═══════════════════════════════════════════════════════════
    # 14. FABRICATED GRANTS & FUNDING (5 cases)
    # ═══════════════════════════════════════════════════════════
    TC(66, "Fake Funding", "This work was supported by NSF Grant IIS-2134567 and NIH R01-GM123456, totaling $2.3 million over 4 years.", True,
       "Fabricated grant numbers with correct prefix formats"),
    TC(67, "Fake Funding", "Funded by the European Research Council (ERC) Advanced Grant 'QUANTUM-ALIGN' (Grant No. 101054789), PI: Prof. Marcus Weber, ETH Zurich.", True,
       "Fabricated ERC grant with fake number and PI"),
    TC(68, "Fake Funding", "The research was conducted at CERN, the European Organization for Nuclear Research.", False,
       "Real institution, correct description"),
    TC(69, "Fake Funding", "Supported by DARPA's Explainable Artificial Intelligence (XAI) program under contract HR001123C0047, with additional funding from the Simons Foundation Autism Research Initiative.", True,
       "XAI is real DARPA program but contract number is fabricated"),
    TC(70, "Fake Funding", "This research was made possible by the Bill & Melinda Gates Foundation Grand Challenges Grant GCE-2023-1847 for 'AI-Driven Malaria Elimination in Sub-Saharan Africa,' awarded $4.7 million.", True,
       "Fabricated specific grant with fake number and amount"),

    # ═══════════════════════════════════════════════════════════
    # 15. FABRICATED PEER REVIEW HISTORY (5 cases)
    # ═══════════════════════════════════════════════════════════
    TC(71, "Fake Review History", "The paper underwent four rounds of peer review at Nature before final acceptance, with the reviewers specifically praising the novel use of topological data analysis.", True,
       "Fabricated peer review details — these are always confidential"),
    TC(72, "Fake Review History", "Originally submitted to Science in March 2023 and rejected after one round of review, the paper was subsequently accepted at Nature Communications in August 2023 with minor revisions.", True,
       "Fabricated editorial trajectory — submission history is confidential"),
    TC(73, "Fake Review History", "The paper was published in Nature in 1953 by Watson and Crick, describing the double helix structure of DNA.", False,
       "Real paper, real journal, real year"),
    TC(74, "Fake Review History", "Reviewer 2 of the ICML submission specifically noted that 'the theoretical analysis in Section 4 is the strongest contribution, but the experimental setup lacks ablation studies on the attention mechanism,' leading to a major revision.", True,
       "Fabricated specific reviewer comments — reviews are confidential"),
    TC(75, "Fake Review History", "The preprint was posted on arXiv in January 2024 and received 47 formal responses on OpenReview, with an average rating of 7.2/10 and acceptance to ICLR 2024 as an oral presentation.", True,
       "Fabricated OpenReview metrics and acceptance details"),
]


async def run_test(client, tc: TC) -> TR:
    result = TR(test=tc)
    start = time.time()
    try:
        resp = await client.post(
            "/v1/verify",
            json={"text": tc.claim, "include_evidence": True, "include_reference_report": True},
            timeout=45.0,
        )
        result.ms = (time.time() - start) * 1000
        if resp.status_code != 200:
            result.error = f"HTTP {resp.status_code}"
            return result
        data = resp.json()
        claims = data.get("claims", [])
        if not claims:
            result.error = "No claims"
            return result
        best = max(claims, key=lambda c: len(c.get("claim", "")))
        result.verdict = best.get("verdict", "unknown")
        result.ev_count = len(best.get("evidence", []))
        conf = best.get("confidence")
        if conf:
            result.conf_score = conf.get("score", 0)
            result.conf_grade = conf.get("grade", "")
        flagged = result.verdict in ("contradicted", "unsupported")
        result.correct = flagged if tc.is_hall else not flagged
    except Exception as e:
        result.ms = (time.time() - start) * 1000
        result.error = str(e)[:100]
    return result


async def main():
    from httpx import AsyncClient, ASGITransport
    from app.main import app

    model = os.environ.get("LLM_MODEL", "gpt-4o")
    print("=" * 95)
    print(f"  ACADEMIC HALLUCINATION STRESS TEST — 75 brutally hard cases")
    print(f"  Model: {model} | 15 categories of academic fraud/hallucination")
    print("=" * 95)

    transport = ASGITransport(app=app)
    results: List[TR] = []
    cat_stats: Dict[str, Dict[str, int]] = {}
    BATCH = 5
    total = len(TESTS)
    wall_start = time.time()

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for i in range(0, total, BATCH):
            batch = TESTS[i:i + BATCH]
            end = min(i + BATCH, total)
            print(f"\n--- Tests {i + 1}-{end}/{total} ---")
            batch_results = await asyncio.gather(*[run_test(client, tc) for tc in batch])
            for r in batch_results:
                results.append(r)
                cat = r.test.cat
                if cat not in cat_stats:
                    cat_stats[cat] = {"total": 0, "correct": 0, "wrong": 0, "errors": 0}
                cat_stats[cat]["total"] += 1
                if r.error:
                    cat_stats[cat]["errors"] += 1
                    icon = "-"
                elif r.correct:
                    cat_stats[cat]["correct"] += 1
                    icon = "+"
                else:
                    cat_stats[cat]["wrong"] += 1
                    icon = "x"
                hall = "HALL" if r.test.is_hall else "REAL"
                v = r.verdict.upper() or "ERR"
                ok = "OK" if r.correct else ("ERR" if r.error else "MISS")
                print(f"  [{icon}] #{r.test.id:2d} {hall} {v:13s} {ok:4s} | {r.ms:7.0f}ms | {r.test.cat:22s} | {r.test.claim[:52]}")
            if end < total:
                await asyncio.sleep(1)

    wall_total = time.time() - wall_start

    # ═══════════ REPORT ═══════════
    print("\n" + "=" * 95)
    print("  RESULTS")
    print("=" * 95)

    ok = sum(1 for r in results if r.correct)
    miss = sum(1 for r in results if not r.correct and not r.error)
    err = sum(1 for r in results if r.error)
    n = len(results)

    hall_tests = [r for r in results if r.test.is_hall and not r.error]
    real_tests = [r for r in results if not r.test.is_hall and not r.error]
    tp = sum(1 for r in hall_tests if r.correct)
    fn = sum(1 for r in hall_tests if not r.correct)
    tn = sum(1 for r in real_tests if r.correct)
    fp = sum(1 for r in real_tests if not r.correct)
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0

    print(f"\n  OVERALL: {ok}/{n} correct ({ok / n * 100:.1f}%) | {miss} missed | {err} errors")
    print(f"\n  Precision: {prec:.3f}  |  Recall: {rec:.3f}  |  F1: {f1:.3f}")
    print(f"  True Pos: {tp}  |  False Neg: {fn}  |  True Neg: {tn}  |  False Pos: {fp}")

    print(f"\n  {'Category':<25s} {'OK':>5s} {'Miss':>5s} {'Err':>5s} {'Tot':>5s} {'Rate':>7s}")
    print(f"  {'-' * 55}")
    for cat in sorted(cat_stats.keys()):
        s = cat_stats[cat]
        rate = s['correct'] / s['total'] * 100 if s['total'] > 0 else 0
        print(f"  {cat:<25s} {s['correct']:>5d} {s['wrong']:>5d} {s['errors']:>5d} {s['total']:>5d} {rate:>6.1f}%")

    durs = [r.ms for r in results if r.ms > 0]
    print(f"\n  TIMING:")
    print(f"    Wall clock:    {wall_total:.1f}s")
    print(f"    Sum of calls:  {sum(durs) / 1000:.1f}s")
    print(f"    Avg per claim: {sum(durs) / len(durs):.0f}ms")
    print(f"    P50:           {sorted(durs)[len(durs) // 2]:.0f}ms")
    print(f"    P95:           {sorted(durs)[int(len(durs) * 0.95)]:.0f}ms")
    print(f"    P99:           {sorted(durs)[int(len(durs) * 0.99)]:.0f}ms")
    print(f"    Fastest:       {min(durs):.0f}ms")
    print(f"    Slowest:       {max(durs):.0f}ms")

    missed = [r for r in results if r.test.is_hall and not r.correct and not r.error]
    if missed:
        print(f"\n  MISSED ({len(missed)}):")
        for r in missed:
            print(f"    #{r.test.id} [{r.test.cat}] got {r.verdict} — {r.test.why}")

    fp_list = [r for r in results if not r.test.is_hall and not r.correct and not r.error]
    if fp_list:
        print(f"\n  FALSE POSITIVES ({len(fp_list)}):")
        for r in fp_list:
            print(f"    #{r.test.id} [{r.test.cat}] got {r.verdict} — {r.test.claim[:70]}")

    print("\n" + "=" * 95)


if __name__ == "__main__":
    asyncio.run(main())
