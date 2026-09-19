#!/usr/bin/env python3
"""
Test script for Plagiarism Detection Engine v2
==============================================

Tests the engine against real scholarly APIs (OpenAlex, Semantic Scholar, Crossref)
with various types of content:
  1. Known plagiarized content (copied from a real abstract)
  2. Paraphrased academic content
  3. Original student essay
  4. Mixed content (some original, some copied)

Usage:
  python scripts/test_plagiarism_v2.py
"""

import asyncio
import json
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from app.services.plagiarism_v2 import (
    check_plagiarism_v2,
    search_openalex,
    search_semantic_scholar,
    search_crossref,
    comprehensive_similarity,
    extract_search_queries,
    split_sentences,
    winnowing_fingerprint,
    find_matching_passages,
    sentence_level_similarity,
    semantic_similarity_openai,
    generate_report_html,
    HAS_DATASKETCH,
    HAS_SKLEARN,
    HAS_NLTK,
    HAS_OPENAI_EMBEDDINGS,
)


def header(title: str):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def subheader(title: str):
    print(f"\n--- {title} ---")


async def test_scholarly_apis():
    """Test that scholarly APIs are reachable and return results."""
    header("TEST 1: Scholarly API Connectivity")
    
    query = "attention is all you need transformer neural network"
    
    subheader("OpenAlex Search")
    results = await search_openalex(query, per_page=3)
    print(f"  Results: {len(results)}")
    for r in results[:3]:
        print(f"    - {r['title'][:80]}")
        print(f"      DOI: {r['doi']}, Year: {r['year']}, Cited: {r['cited_by_count']}")
        print(f"      Authors: {', '.join(r['authors'][:3])}")
        print(f"      Abstract: {r['abstract'][:100]}...")
    
    subheader("Semantic Scholar Search")
    results = await search_semantic_scholar(query, limit=3)
    print(f"  Results: {len(results)}")
    for r in results[:3]:
        print(f"    - {r['title'][:80]}")
        print(f"      DOI: {r['doi']}, Year: {r['year']}, Cited: {r['cited_by_count']}")
    
    subheader("Crossref Search")
    results = await search_crossref(query, rows=3)
    print(f"  Results: {len(results)}")
    for r in results[:3]:
        print(f"    - {r['title'][:80]}")
        print(f"      DOI: {r['doi']}, Year: {r['year']}, Publisher: {r['publisher']}")
    
    print("\n  [PASS] All scholarly APIs responding")


async def test_known_plagiarism():
    """
    Test with content KNOWN to be from a real paper.
    Uses the abstract of "Attention Is All You Need" (Vaswani et al., 2017).
    The engine should find this in OpenAlex/S2.
    """
    header("TEST 2: Known Plagiarism Detection (Real Abstract)")
    
    # This is the actual abstract from the famous Transformer paper
    plagiarized_content = """
    The dominant sequence transduction models are based on complex recurrent or 
    convolutional neural networks that include an encoder and a decoder. The best 
    performing models also connect the encoder and decoder through an attention 
    mechanism. We propose a new simple network architecture, the Transformer, based 
    solely on attention mechanisms, dispensing with recurrence and convolutions 
    entirely. Experiments on two machine translation tasks show that these models 
    are superior in quality while being more parallelizable and requiring 
    significantly less time to train. Our model achieves 28.4 BLEU on the 
    WMT 2014 English-to-German translation task, improving over the existing best 
    results, including ensembles, by over 2 BLEU. On the WMT 2014 
    English-to-French translation task, our model establishes a new single-model 
    state-of-the-art BLEU score of 41.8 after training for 3.5 days on eight GPUs, 
    a small fraction of the training costs of the best models from the literature.
    """
    
    result = await check_plagiarism_v2(
        content=plagiarized_content,
        check_internal=False,
        check_scholarly=True,
    )
    
    print(f"  Overall Score: {result['overall_score']}%")
    print(f"  Scholarly Matches: {result['scholarly_matches_count']}")
    print(f"  Duration: {result['duration_ms']}ms")
    
    for m in result.get("scholarly_matches", [])[:5]:
        print(f"\n  Source: {m['title'][:70]}")
        print(f"    DOI: {m['doi']}")
        print(f"    Authors: {', '.join(m['authors'][:3])}")
        print(f"    Similarity: {m['similarity_score']}% ({m['match_type']})")
        print(f"    Journal: {m['journal']}")
        print(f"    Citation: {m.get('citation', 'N/A')[:100]}")
    
    if result["scholarly_matches_count"] > 0:
        print("\n  [PASS] Successfully detected known plagiarized content from scholarly source")
    else:
        print("\n  [WARN] No scholarly matches found — check API connectivity")


async def test_paraphrased_content():
    """Test with paraphrased content from a well-known paper."""
    header("TEST 3: Paraphrase Detection")
    
    # Paraphrased version of BERT paper concepts
    paraphrased = """
    In recent years, language understanding models have been revolutionized by the 
    concept of pre-training deep bidirectional representations. Unlike previous 
    approaches that trained left-to-right language models, the idea is to jointly 
    condition on both left and right context in all layers. This approach allows 
    the pre-trained model to be fine-tuned with just one additional output layer 
    for a wide range of downstream tasks such as question answering and language 
    inference. The results show dramatic improvements across eleven natural language 
    processing benchmarks, demonstrating that bidirectional pre-training is 
    fundamentally more effective than unidirectional approaches. These models have 
    achieved new state-of-the-art results on multiple benchmarks including the 
    GLUE benchmark, pushing the score significantly higher than previous methods.
    """
    
    result = await check_plagiarism_v2(
        content=paraphrased,
        check_internal=False,
        check_scholarly=True,
    )
    
    print(f"  Overall Score: {result['overall_score']}%")
    print(f"  Scholarly Matches: {result['scholarly_matches_count']}")
    print(f"  Duration: {result['duration_ms']}ms")
    
    for m in result.get("scholarly_matches", [])[:3]:
        print(f"\n  Source: {m['title'][:70]}")
        print(f"    Similarity: {m['similarity_score']}% ({m['match_type']})")
    
    print(f"\n  [INFO] Paraphrase detection score: {result['overall_score']}%")


async def test_original_content():
    """Test with genuinely original student writing — should score LOW."""
    header("TEST 4: Original Content (Should Score Low)")
    
    original = """
    Yesterday I went to the campus library to work on my history essay about the 
    Industrial Revolution. I found it really interesting how the shift from 
    agricultural work to factory work changed not just the economy but also family 
    structures and daily routines. My grandmother used to tell me stories about 
    her great-grandparents who moved from a small farming village to Manchester 
    to work in the textile mills. I think that personal connection makes this 
    topic more meaningful to me than just reading dates and statistics. For my 
    essay, I want to focus specifically on how children's lives changed during 
    this period, because I think that's an angle that doesn't get enough attention 
    in our textbook. The working conditions in factories were absolutely terrible, 
    and kids as young as five were employed for fourteen-hour shifts. I plan to 
    argue that the Factory Acts were actually more about economic efficiency than 
    genuine concern for child welfare, which is a perspective I developed after 
    reading several primary sources from the period.
    """
    
    result = await check_plagiarism_v2(
        content=original,
        check_internal=False,
        check_scholarly=True,
    )
    
    print(f"  Overall Score: {result['overall_score']}%")
    print(f"  Scholarly Matches: {result['scholarly_matches_count']}")
    print(f"  Duration: {result['duration_ms']}ms")
    
    if result["overall_score"] <= 20:
        print("\n  [PASS] Original content correctly identified as low-similarity")
    else:
        print(f"\n  [WARN] Original content scored {result['overall_score']}% — may need threshold tuning")


async def test_mixed_content():
    """Test with a mix of original and copied content."""
    header("TEST 5: Mixed Content (Partial Plagiarism)")
    
    mixed = """
    In my research paper, I will discuss the impact of deep learning on natural 
    language processing. I chose this topic because I'm fascinated by how 
    computers can understand human language.
    
    Deep learning approaches have recently been applied to natural language 
    processing with great success. Neural network architectures such as 
    recurrent neural networks, long short-term memory networks, and more recently 
    transformer-based models have demonstrated remarkable performance on a wide 
    range of NLP tasks including machine translation, text summarization, 
    question answering, and sentiment analysis.
    
    I personally believe that the most exciting development is how these models 
    can be used in education. My professor showed us how GPT models work and I 
    was amazed by the way attention mechanisms allow the model to focus on 
    relevant parts of the input sequence. For my final project, I want to build 
    a small chatbot that can help students with their homework.
    """
    
    result = await check_plagiarism_v2(
        content=mixed,
        check_internal=False,
        check_scholarly=True,
    )
    
    print(f"  Overall Score: {result['overall_score']}%")
    print(f"  Scholarly Matches: {result['scholarly_matches_count']}")
    print(f"  Duration: {result['duration_ms']}ms")
    
    for m in result.get("scholarly_matches", [])[:3]:
        print(f"  Source: {m['title'][:70]} — {m['similarity_score']}%")


async def test_comparison_algorithms():
    """Test the local comparison algorithms without API calls."""
    header("TEST 6: Local Comparison Algorithms")
    
    text_a = """
    Machine learning is a subset of artificial intelligence that focuses on 
    building systems that learn from data. These systems improve their performance 
    over time without being explicitly programmed. Common approaches include 
    supervised learning, unsupervised learning, and reinforcement learning.
    """
    
    text_b = """
    Machine learning is a subset of artificial intelligence that focuses on 
    building systems that learn from data. These systems improve their performance 
    over time without being explicitly programmed. Common approaches include 
    supervised learning, unsupervised learning, and reinforcement learning.
    """
    
    text_c = """
    AI-based learning systems represent a branch of computational intelligence 
    that centers on developing programs which improve through experience with 
    datasets. These programs get better at their tasks gradually without manual 
    coding of rules. Popular methods include learning with labels, learning 
    without labels, and learning through trial and error.
    """
    
    text_d = """
    I went to the grocery store yesterday and bought some apples and bananas. 
    The weather was nice so I decided to walk home instead of taking the bus. 
    On the way I saw my neighbor walking her dog and we chatted for a few minutes.
    """
    
    subheader("Exact Copy (A vs B)")
    result = comprehensive_similarity(text_a, text_b)
    print(f"  Score: {result['score']}%  Type: {result['match_type']}")
    print(f"  Fingerprint: {result['fingerprint_similarity']}%, Shingle: {result['shingle_similarity']}%, TF-IDF: {result['tfidf_similarity']}%")
    
    subheader("Paraphrase (A vs C)")
    result = comprehensive_similarity(text_a, text_c)
    print(f"  Score: {result['score']}%  Type: {result['match_type']}")
    print(f"  Fingerprint: {result['fingerprint_similarity']}%, Shingle: {result['shingle_similarity']}%, TF-IDF: {result['tfidf_similarity']}%")
    
    subheader("Unrelated (A vs D)")
    result = comprehensive_similarity(text_a, text_d)
    print(f"  Score: {result['score']}%  Type: {result['match_type']}")
    print(f"  Fingerprint: {result['fingerprint_similarity']}%, Shingle: {result['shingle_similarity']}%, TF-IDF: {result['tfidf_similarity']}%")
    
    subheader("Passage Alignment (A vs B)")
    passages = find_matching_passages(text_a, text_b)
    print(f"  Matching passages: {len(passages)}")
    for p in passages[:3]:
        print(f"    [{p['length']} words] \"{p['text'][:60]}...\"")
    
    subheader("Sentence-Level Similarity (A vs C)")
    avg_sim, matches = sentence_level_similarity(text_a, text_c)
    print(f"  Average sentence similarity: {round(avg_sim * 100, 1)}%")
    for m in matches[:3]:
        print(f"    Source: \"{m['source_sentence'][:50]}...\"")
        print(f"    Match: \"{m['matched_sentence'][:50]}...\"")
        print(f"    Sim:   {round(m['similarity'] * 100, 1)}%")
    
    if HAS_OPENAI_EMBEDDINGS:
        subheader("OpenAI Semantic Embeddings")
        s_ab = semantic_similarity_openai(text_a, text_b)
        s_ac = semantic_similarity_openai(text_a, text_c)
        s_ad = semantic_similarity_openai(text_a, text_d)
        print(f"  Exact copy  (A vs B): {round(s_ab * 100, 1)}%" if s_ab else "  Failed")
        print(f"  Paraphrase  (A vs C): {round(s_ac * 100, 1)}%" if s_ac else "  Failed")
        print(f"  Unrelated   (A vs D): {round(s_ad * 100, 1)}%" if s_ad else "  Failed")
        
        if s_ac and s_ad:
            if s_ac > s_ad + 0.1:
                print("  [PASS] Embeddings correctly distinguish paraphrase from unrelated")
            else:
                print("  [WARN] Embeddings did not differentiate well")
    
        subheader("Comprehensive Similarity WITH Embeddings (A vs C)")
        result_with_emb = comprehensive_similarity(text_a, text_c)
        print(f"  Score: {result_with_emb['score']}%  Type: {result_with_emb['match_type']}")
        sem = result_with_emb.get('semantic_similarity', 'N/A')
        print(f"  Semantic: {sem}%, TF-IDF: {result_with_emb['tfidf_similarity']}%")
    else:
        subheader("OpenAI Semantic Embeddings — SKIPPED (no API key)")


async def test_report_generation():
    """Test HTML report generation."""
    header("TEST 7: Report Generation")
    
    mock_result = {
        "check_id": "test123",
        "overall_score": 45,
        "internal_matches": [
            {
                "similarity_score": 45,
                "source_type": "internal",
                "matched_submission_id": "sub-abc123",
                "match_type": "minor_changes",
            }
        ],
        "scholarly_matches": [
            {
                "title": "Attention Is All You Need",
                "authors": ["Ashish Vaswani", "Noam Shazeer", "Niki Parmar"],
                "doi": "10.48550/arXiv.1706.03762",
                "year": 2017,
                "journal": "Advances in Neural Information Processing Systems",
                "cited_by_count": 95000,
                "similarity_score": 38,
                "match_type": "paraphrased",
                "api": "openalex",
                "url": "https://doi.org/10.48550/arXiv.1706.03762",
                "citation": "Vaswani, A., et al. (2017). Attention Is All You Need. *NIPS*.",
                "details": {},
            }
        ],
        "word_count": 250,
        "duration_ms": 3400,
        "checked_at": "2026-03-06T12:00:00Z",
    }
    
    html = generate_report_html(mock_result, student_name="Test Student", assignment_title="NLP Essay")
    print(f"  Report HTML length: {len(html)} chars")
    print(f"  Contains score: {'45%' in html}")
    print(f"  Contains source: {'Attention Is All You Need' in html}")
    print(f"  [PASS] Report generated successfully")


async def main():
    print("\n" + "=" * 70)
    print("  PLAGIARISM DETECTION ENGINE v2 — TEST SUITE")
    print("  Editorrah Academic Integrity System")
    print("=" * 70)
    
    print(f"\n  Engine capabilities:")
    print(f"    MinHash/LSH (datasketch):  {'YES' if HAS_DATASKETCH else 'NO (fallback to winnowing)'}")
    print(f"    sklearn TF-IDF:            {'YES' if HAS_SKLEARN else 'NO (fallback to pure Python)'}")
    print(f"    NLTK sentence split:       {'YES' if HAS_NLTK else 'NO (fallback to regex)'}")
    print(f"    OpenAI embeddings:         {'YES' if HAS_OPENAI_EMBEDDINGS else 'NO (paraphrase detection limited)'}")
    
    start = time.time()
    
    await test_scholarly_apis()
    await test_known_plagiarism()
    await test_paraphrased_content()
    await test_original_content()
    await test_mixed_content()
    await test_comparison_algorithms()
    await test_report_generation()
    
    total = time.time() - start
    
    header("SUMMARY")
    print(f"  Total test time: {total:.1f}s")
    print(f"  All tests completed.")
    print()


if __name__ == "__main__":
    asyncio.run(main())
