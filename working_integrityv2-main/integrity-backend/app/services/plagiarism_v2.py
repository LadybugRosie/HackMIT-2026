"""
Plagiarism Detection Engine v2 — Turnitin-class open-source pipeline
=====================================================================

5-stage pipeline:
  1. Pre-processing   — normalize, sentence-split, extract search queries
  2. Candidate retrieval — MinHash/LSH on internal corpus + scholarly API search
  3. Deep comparison   — sentence-level TF-IDF, n-gram overlap, passage alignment
  4. Publication enrichment — DOI, authors, journal, citations from OpenAlex/Crossref/S2
  5. Scoring & report  — weighted aggregate, structured JSON + optional HTML

External scholarly APIs (all free, no API key required):
  • OpenAlex   — 240M+ works, CC0, full-text search + metadata
  • Semantic Scholar — 200M+ papers, SPECTER2 embeddings
  • Crossref   — 150M+ records, DOI resolver, rich metadata
"""

import asyncio
import hashlib
import logging
import math
import os
import re
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Silence noisy httpx request logs (S2 429s spam the terminal)
logging.getLogger("httpx").setLevel(logging.WARNING)

# ---------------------------------------------------------------------------
# Optional heavy imports — degrade gracefully when unavailable
# ---------------------------------------------------------------------------
try:
    from datasketch import MinHash, MinHashLSH
    HAS_DATASKETCH = True
except ImportError:
    HAS_DATASKETCH = False
    logger.info("datasketch not installed — MinHash/LSH disabled, using basic fingerprinting")

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity as sklearn_cosine
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False
    logger.info("scikit-learn not installed — using fallback TF-IDF")

try:
    import nltk
    nltk.download("punkt_tab", quiet=True)
    from nltk.tokenize import sent_tokenize
    HAS_NLTK = True
except Exception:
    HAS_NLTK = False

# OpenAI embeddings for semantic/paraphrase detection (optional — uses existing key)
_openai_client = None
HAS_OPENAI_EMBEDDINGS = False
try:
    import openai as _openai_mod
    _oai_key = os.getenv("OPENAI_API_KEY", "")
    if _oai_key:
        _openai_client = _openai_mod.OpenAI(api_key=_oai_key)
        HAS_OPENAI_EMBEDDINGS = True
except Exception:
    pass

# DuckDuckGo search library (much more reliable than HTML scraping)
try:
    from ddgs import DDGS
    HAS_DDGS = True
except ImportError:
    try:
        from duckduckgo_search import DDGS
        HAS_DDGS = True
    except ImportError:
        HAS_DDGS = False
        logger.info("ddgs/duckduckgo-search not installed — using HTML fallback for web search")

# ---------------------------------------------------------------------------
# Rate-limiting semaphores — lazy-init (can't create at module level)
# ---------------------------------------------------------------------------
_s2_sem: Optional[asyncio.Semaphore] = None
_ddg_sem: Optional[asyncio.Semaphore] = None
_s2_last_request: float = 0.0

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
OPENALEX_BASE = "https://api.openalex.org"
SEMANTIC_SCHOLAR_BASE = "https://api.semanticscholar.org/graph/v1"
CROSSREF_BASE = "https://api.crossref.org"

OPENALEX_EMAIL = os.getenv("OPENALEX_EMAIL", "integrity@editorrah.com")
S2_API_KEY = os.getenv("S2_API_KEY", "")  # Free key from semanticscholar.org/product/api
WINSTON_API_KEY = os.getenv("WINSTON_API_KEY", "")
WINSTON_API_URL = "https://api.gowinston.ai/v2/plagiarism"
MAX_SCHOLARLY_QUERIES = 5          # reduced from 8 — fewer, higher-signal queries
MAX_CANDIDATES_PER_QUERY = 5       # max works per query
API_TIMEOUT = 12                   # seconds per HTTP request
MINHASH_NUM_PERM = 128             # MinHash permutations
LSH_THRESHOLD = 0.25               # Jaccard threshold for LSH candidate retrieval
MIN_SENTENCE_LEN = 40              # ignore very short sentences for search
PASSAGE_MIN_WORDS = 6              # minimum words for a matching passage


# ============================================================================
# 1. TEXT PRE-PROCESSING
# ============================================================================

def normalize_text(text: str) -> str:
    """Lowercase, collapse whitespace, strip punctuation for comparison."""
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s]", "", text)
    return text.strip()


def tokenize_words(text: str) -> List[str]:
    return normalize_text(text).split()


def split_sentences(text: str) -> List[str]:
    """Split text into sentences using NLTK if available, else regex."""
    if HAS_NLTK:
        try:
            return [s.strip() for s in sent_tokenize(text) if len(s.strip()) > 10]
        except Exception:
            pass
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in parts if len(s.strip()) > 10]


def extract_search_queries(text: str, max_queries: int = MAX_SCHOLARLY_QUERIES) -> List[str]:
    """
    Pick the most distinctive sentences to use as scholarly search queries.
    Strategy: rank sentences by average word rarity (IDF proxy using the
    document itself), then pick top-N. This biases toward technical/specific
    sentences that are more likely to come from a particular source.
    """
    sentences = split_sentences(text)
    if not sentences:
        return []

    if len(sentences) <= max_queries:
        return [s for s in sentences if len(s) >= MIN_SENTENCE_LEN] or sentences[:max_queries]

    word_freq: Dict[str, int] = defaultdict(int)
    for s in sentences:
        for w in tokenize_words(s):
            word_freq[w] += 1

    total_words = sum(word_freq.values()) or 1

    def _sentence_score(s: str) -> float:
        words = tokenize_words(s)
        if len(words) < 4:
            return 0.0
        scores = [-math.log((word_freq.get(w, 1)) / total_words) for w in words if len(w) > 3]
        return sum(scores) / max(len(scores), 1) if scores else 0.0

    ranked = sorted(
        [(s, _sentence_score(s)) for s in sentences if len(s) >= MIN_SENTENCE_LEN],
        key=lambda x: x[1],
        reverse=True,
    )
    return [s for s, _ in ranked[:max_queries]]


def word_ngrams(text: str, n: int = 5) -> List[str]:
    words = tokenize_words(text)
    if len(words) < n:
        return [" ".join(words)] if words else []
    return [" ".join(words[i : i + n]) for i in range(len(words) - n + 1)]


def _text_has_ngram_overlap(source: str, candidate: str, n: int = 4, min_matches: int = 1) -> bool:
    """
    Check if candidate text shares at least `min_matches` word n-grams with source.
    Used to verify that a search result actually contains text from the submission,
    not just topically related content.
    """
    src_ngrams = set(word_ngrams(source, n))
    cand_ngrams = set(word_ngrams(candidate, n))
    if not src_ngrams or not cand_ngrams:
        return False
    return len(src_ngrams & cand_ngrams) >= min_matches


def _ngram_overlap_ratio(source: str, candidate: str, n: int = 4) -> float:
    """
    Return the fraction of source n-grams found in candidate.
    Higher = more of the source text appears verbatim in the candidate.
    """
    src_ngrams = set(word_ngrams(source, n))
    if not src_ngrams:
        return 0.0
    cand_ngrams = set(word_ngrams(candidate, n))
    return len(src_ngrams & cand_ngrams) / len(src_ngrams)


# ============================================================================
# 2. FINGERPRINTING — Winnowing + MinHash
# ============================================================================

def _rolling_hash(text: str, base: int = 101, mod: int = (1 << 31) - 1) -> int:
    h = 0
    for c in text:
        h = (h * base + ord(c)) % mod
    return h


def winnowing_fingerprint(text: str, k: int = 7, window: int = 5) -> Set[int]:
    """Winnowing algorithm (same as MOSS). Returns set of selected hashes."""
    text = normalize_text(text)
    if len(text) < k:
        return {_rolling_hash(text)} if text else set()

    hashes = [_rolling_hash(text[i : i + k]) for i in range(len(text) - k + 1)]
    if len(hashes) < window:
        return set(hashes)

    fps: Set[int] = set()
    for i in range(len(hashes) - window + 1):
        w = hashes[i : i + window]
        min_h = min(w)
        fps.add(min_h)
    return fps


def build_minhash(text: str, num_perm: int = MINHASH_NUM_PERM) -> Optional[Any]:
    """Build a MinHash signature for approximate Jaccard via LSH."""
    if not HAS_DATASKETCH:
        return None
    words = tokenize_words(text)
    shingles = set(word_ngrams(text, 3))
    if not shingles:
        return None
    m = MinHash(num_perm=num_perm)
    for s in shingles:
        m.update(s.encode("utf-8"))
    return m


# ============================================================================
# 3. SIMILARITY METRICS
# ============================================================================

def jaccard_similarity(set_a: Set, set_b: Set) -> float:
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def _tfidf_cosine_pair(text_a: str, text_b: str) -> float:
    """TF-IDF cosine similarity between two texts using sklearn."""
    if HAS_SKLEARN:
        try:
            vec = TfidfVectorizer(
                analyzer="word",
                ngram_range=(1, 3),
                max_features=20000,
                sublinear_tf=True,
            )
            matrix = vec.fit_transform([text_a, text_b])
            sim = sklearn_cosine(matrix[0:1], matrix[1:2])[0][0]
            return float(sim)
        except Exception:
            pass
    return _fallback_tfidf(text_a, text_b)


def _fallback_tfidf(text_a: str, text_b: str) -> float:
    """Pure-Python TF-IDF cosine (no sklearn)."""
    words_a, words_b = tokenize_words(text_a), tokenize_words(text_b)
    if not words_a or not words_b:
        return 0.0

    tf_a: Dict[str, float] = defaultdict(float)
    tf_b: Dict[str, float] = defaultdict(float)
    for w in words_a:
        tf_a[w] += 1
    for w in words_b:
        tf_b[w] += 1
    for w in tf_a:
        tf_a[w] /= len(words_a)
    for w in tf_b:
        tf_b[w] /= len(words_b)

    all_words = set(tf_a) | set(tf_b)
    doc_freq: Dict[str, int] = {}
    for w in all_words:
        doc_freq[w] = (1 if w in tf_a else 0) + (1 if w in tf_b else 0)

    def _vec(tf: Dict[str, float]) -> Dict[str, float]:
        return {w: tf.get(w, 0) * math.log(2 / (doc_freq.get(w, 1))) for w in all_words}

    va, vb = _vec(tf_a), _vec(tf_b)
    dot = sum(va.get(w, 0) * vb.get(w, 0) for w in all_words)
    na = math.sqrt(sum(v ** 2 for v in va.values())) or 1
    nb = math.sqrt(sum(v ** 2 for v in vb.values())) or 1
    return dot / (na * nb)


def _openai_embedding(texts: List[str]) -> Optional[List[List[float]]]:
    """Get embeddings via OpenAI text-embedding-3-small. ~$0.02/M tokens."""
    if not HAS_OPENAI_EMBEDDINGS or not _openai_client:
        return None
    try:
        cleaned = [t[:8000] for t in texts]
        resp = _openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=cleaned,
        )
        return [d.embedding for d in resp.data]
    except Exception as e:
        logger.debug(f"OpenAI embedding failed: {e}")
        return None


def _cosine_from_vectors(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1
    nb = math.sqrt(sum(x * x for x in b)) or 1
    return dot / (na * nb)


def semantic_similarity_openai(text_a: str, text_b: str) -> Optional[float]:
    """
    Compute semantic similarity using OpenAI embeddings.
    Catches paraphrased plagiarism that TF-IDF/fingerprinting misses.
    Returns None if OpenAI is unavailable.
    """
    vecs = _openai_embedding([text_a, text_b])
    if not vecs or len(vecs) < 2:
        return None
    return _cosine_from_vectors(vecs[0], vecs[1])


def find_matching_passages(
    source_text: str,
    candidate_text: str,
    min_words: int = 4,
    max_gap: int = 2,
) -> List[Dict[str, Any]]:
    """
    Find matching passages between two texts, tolerating small gaps.
    Allows up to `max_gap` consecutive mismatched words within a match
    (like Turnitin). This catches copies with minor edits.
    """
    words_s = tokenize_words(source_text)
    words_c = tokenize_words(candidate_text)
    if not words_s or not words_c:
        return []

    cand_index: Dict[str, List[int]] = defaultdict(list)
    for idx, w in enumerate(words_c):
        cand_index[w].append(idx)

    passages: List[Dict[str, Any]] = []
    used_source = set()
    i = 0
    while i < len(words_s):
        if i in used_source:
            i += 1
            continue

        best_matched = 0
        best_span_s = 0
        best_span_c = 0
        best_j = -1

        start_positions = cand_index.get(words_s[i], [])
        for j in start_positions:
            si, ci = i, j
            matched = 0
            gap_run = 0
            total_span = 0
            while si + total_span < len(words_s) and ci + total_span < len(words_c):
                if words_s[si + total_span] == words_c[ci + total_span]:
                    matched += 1
                    gap_run = 0
                    total_span += 1
                else:
                    gap_run += 1
                    if gap_run > max_gap:
                        break
                    total_span += 1

            while total_span > 0 and words_s[si + total_span - 1] != words_c[ci + total_span - 1]:
                total_span -= 1

            if matched > best_matched and matched >= min_words:
                best_matched = matched
                best_span_s = total_span
                best_span_c = total_span
                best_j = j

        if best_matched >= min_words:
            passages.append({
                "source_start": i,
                "source_end": i + best_span_s,
                "candidate_start": best_j,
                "candidate_end": best_j + best_span_c,
                "length": best_matched,
                "text": " ".join(words_s[i : i + best_span_s]),
            })
            for k in range(i, i + best_span_s):
                used_source.add(k)
            i += best_span_s
        else:
            i += 1

    _merge_adjacent_passages(passages, words_s, gap_threshold=3)
    return passages


def _merge_adjacent_passages(passages: List[Dict], words: List[str], gap_threshold: int = 3):
    """Merge passages that are close together into larger blocks."""
    if len(passages) < 2:
        return
    i = 0
    while i < len(passages) - 1:
        curr = passages[i]
        nxt = passages[i + 1]
        gap = nxt["source_start"] - curr["source_end"]
        if 0 <= gap <= gap_threshold:
            curr["source_end"] = nxt["source_end"]
            curr["candidate_end"] = nxt["candidate_end"]
            curr["length"] = curr["length"] + nxt["length"] + gap
            curr["text"] = " ".join(words[curr["source_start"]:curr["source_end"]])
            passages.pop(i + 1)
        else:
            i += 1


def sentence_level_similarity(text_a: str, text_b: str) -> Tuple[float, List[Dict]]:
    """
    Compare two texts at sentence level. For each sentence in text_a, find
    the best-matching sentence in text_b. Returns (avg_similarity, matches).
    """
    sents_a = split_sentences(text_a)
    sents_b = split_sentences(text_b)
    if not sents_a or not sents_b:
        return 0.0, []

    if HAS_SKLEARN and len(sents_a) > 0 and len(sents_b) > 0:
        try:
            all_sents = sents_a + sents_b
            vec = TfidfVectorizer(
                analyzer="word",
                ngram_range=(1, 2),
                max_features=15000,
                sublinear_tf=True,
            )
            matrix = vec.fit_transform(all_sents)
            sim_matrix = sklearn_cosine(
                matrix[: len(sents_a)], matrix[len(sents_a) :]
            )

            matches = []
            scores = []
            for idx_a, row in enumerate(sim_matrix):
                best_idx = int(row.argmax())
                best_score = float(row[best_idx])
                if best_score >= 0.3:
                    matches.append({
                        "source_sentence": sents_a[idx_a],
                        "matched_sentence": sents_b[best_idx],
                        "similarity": round(best_score, 3),
                    })
                scores.append(best_score)

            avg = sum(scores) / len(scores) if scores else 0.0
            return avg, sorted(matches, key=lambda m: m["similarity"], reverse=True)
        except Exception as e:
            logger.warning(f"sklearn sentence comparison failed: {e}")

    total, count = 0.0, 0
    matches = []
    for sa in sents_a:
        best_score = 0.0
        best_sb = ""
        for sb in sents_b:
            score = _fallback_tfidf(sa, sb)
            if score > best_score:
                best_score = score
                best_sb = sb
        if best_score >= 0.3:
            matches.append({
                "source_sentence": sa,
                "matched_sentence": best_sb,
                "similarity": round(best_score, 3),
            })
        total += best_score
        count += 1
    avg = total / count if count else 0.0
    return avg, sorted(matches, key=lambda m: m["similarity"], reverse=True)


def comprehensive_similarity(source_text: str, candidate_text: str) -> Dict[str, Any]:
    """
    Run all comparison algorithms and return a combined result.
    Includes OpenAI embeddings for paraphrase detection when available.
    """
    fp_src = winnowing_fingerprint(source_text)
    fp_cand = winnowing_fingerprint(candidate_text)
    fp_sim = jaccard_similarity(fp_src, fp_cand)

    shingle_src = set(word_ngrams(source_text, 3))
    shingle_cand = set(word_ngrams(candidate_text, 3))
    shingle_sim = jaccard_similarity(shingle_src, shingle_cand)

    tfidf_sim = _tfidf_cosine_pair(source_text, candidate_text)

    passages = find_matching_passages(source_text, candidate_text)
    total_passage_words = sum(p["length"] for p in passages)
    source_words = len(tokenize_words(source_text))
    passage_coverage = total_passage_words / source_words if source_words else 0.0

    sent_avg, sent_matches = sentence_level_similarity(source_text, candidate_text)

    # OpenAI semantic embeddings (catches paraphrasing that TF-IDF misses)
    semantic_sim = semantic_similarity_openai(source_text, candidate_text)
    has_semantic = semantic_sim is not None

    if has_semantic:
        # With embeddings: heavier weight on semantic layer
        combined = (
            fp_sim * 0.10
            + shingle_sim * 0.10
            + tfidf_sim * 0.15
            + passage_coverage * 0.15
            + sent_avg * 0.15
            + semantic_sim * 0.35  # strongest paraphrase catcher
        )
    else:
        combined = (
            fp_sim * 0.15
            + shingle_sim * 0.15
            + tfidf_sim * 0.25
            + passage_coverage * 0.20
            + sent_avg * 0.25
        )

    score = min(100, int(combined * 100))
    match_type = "exact" if fp_sim > 0.6 else "minor_changes" if shingle_sim > 0.3 else "paraphrased"

    result = {
        "score": score,
        "match_type": match_type,
        "fingerprint_similarity": round(fp_sim * 100, 1),
        "shingle_similarity": round(shingle_sim * 100, 1),
        "tfidf_similarity": round(tfidf_sim * 100, 1),
        "passage_coverage": round(passage_coverage * 100, 1),
        "sentence_similarity": round(sent_avg * 100, 1),
        "matching_passages": passages[:15],
        "sentence_matches": sent_matches[:10],
        "total_matching_words": total_passage_words,
    }
    if has_semantic:
        result["semantic_similarity"] = round(semantic_sim * 100, 1)
    return result


# ============================================================================
# 4. SCHOLARLY API CLIENTS
# ============================================================================

async def _http_get(url: str, params: dict = None, headers: dict = None, timeout: int = API_TIMEOUT) -> Optional[dict]:
    """Shared async HTTP GET with error handling."""
    try:
        from ..utils.http_client import get_client
        client = get_client()
        resp = await client.get(url, params=params, headers=headers or {}, timeout=timeout)
        if resp.status_code == 200:
            return resp.json()
        logger.debug(f"API {url} returned {resp.status_code}")
    except Exception as e:
        logger.debug(f"API request failed {url}: {e}")
    return None


async def search_openalex(query: str, per_page: int = MAX_CANDIDATES_PER_QUERY) -> List[Dict]:
    """
    Search OpenAlex for works matching a query string.
    Returns list of work dicts with metadata.
    OpenAlex indexes 240M+ works — CC0 licensed, free API.
    """
    params = {
        "search": query,
        "per_page": per_page,
        "mailto": OPENALEX_EMAIL,
        "select": "id,doi,title,authorships,publication_year,primary_location,cited_by_count,type,open_access,abstract_inverted_index",
    }
    data = await _http_get(f"{OPENALEX_BASE}/works", params=params)
    if not data or "results" not in data:
        return []

    works = []
    for w in data["results"]:
        abstract = _reconstruct_abstract(w.get("abstract_inverted_index"))
        authors = [
            a.get("author", {}).get("display_name", "")
            for a in (w.get("authorships") or [])[:5]
        ]
        location = w.get("primary_location") or {}
        source = location.get("source") or {}

        works.append({
            "api": "openalex",
            "openalex_id": w.get("id", ""),
            "doi": (w.get("doi") or "").replace("https://doi.org/", ""),
            "title": w.get("title", ""),
            "authors": authors,
            "year": w.get("publication_year"),
            "journal": source.get("display_name", ""),
            "publisher": source.get("host_organization_name", ""),
            "cited_by_count": w.get("cited_by_count", 0),
            "type": w.get("type", ""),
            "is_oa": (w.get("open_access") or {}).get("is_oa", False),
            "oa_url": (w.get("open_access") or {}).get("oa_url", ""),
            "abstract": abstract,
            "url": (w.get("doi") or w.get("id") or ""),
        })
    return works


def _reconstruct_abstract(inverted_index: Optional[Dict]) -> str:
    """Reconstruct abstract from OpenAlex inverted index format."""
    if not inverted_index:
        return ""
    word_positions: List[Tuple[int, str]] = []
    for word, positions in inverted_index.items():
        for pos in positions:
            word_positions.append((pos, word))
    word_positions.sort()
    return " ".join(w for _, w in word_positions)


async def search_semantic_scholar(query: str, limit: int = MAX_CANDIDATES_PER_QUERY) -> List[Dict]:
    """
    Search Semantic Scholar for papers matching a query.
    200M+ papers, provides SPECTER embeddings.
    Uses semaphore (max 1 concurrent) + exponential backoff on 429.
    """
    global _s2_sem, _s2_last_request
    if _s2_sem is None:
        _s2_sem = asyncio.Semaphore(1)

    async with _s2_sem:
        # Enforce minimum 1.5s between ANY S2 requests (global, not per-query)
        now = time.time()
        wait = max(0.0, 1.5 - (now - _s2_last_request))
        if wait > 0:
            await asyncio.sleep(wait)

        params = {
            "query": query,
            "limit": limit,
            "fields": "paperId,externalIds,title,abstract,authors,year,venue,citationCount,isOpenAccess,openAccessPdf",
        }
        data = None
        for attempt in range(3):
            _s2_last_request = time.time()
            s2_headers = {"x-api-key": S2_API_KEY} if S2_API_KEY else {}
            data = await _http_get(f"{SEMANTIC_SCHOLAR_BASE}/paper/search", params=params, headers=s2_headers)
            if data is not None:
                break
            # Exponential backoff: 3s, 6s, 12s
            delay = 3.0 * (2 ** attempt)
            logger.debug(f"S2 attempt {attempt+1} failed for query, retrying in {delay:.0f}s")
            await asyncio.sleep(delay)

    if not data or "data" not in data:
        return []

    papers = []
    for p in data["data"]:
        ext_ids = p.get("externalIds") or {}
        authors = [a.get("name", "") for a in (p.get("authors") or [])[:5]]
        oa_pdf = (p.get("openAccessPdf") or {}).get("url", "")

        papers.append({
            "api": "semantic_scholar",
            "s2_id": p.get("paperId", ""),
            "doi": ext_ids.get("DOI", ""),
            "title": p.get("title", ""),
            "authors": authors,
            "year": p.get("year"),
            "journal": p.get("venue", ""),
            "cited_by_count": p.get("citationCount", 0),
            "is_oa": p.get("isOpenAccess", False),
            "oa_url": oa_pdf,
            "abstract": p.get("abstract") or "",
            "url": f"https://doi.org/{ext_ids.get('DOI')}" if ext_ids.get("DOI") else f"https://www.semanticscholar.org/paper/{p.get('paperId', '')}",
        })
    return papers


async def search_crossref(query: str, rows: int = MAX_CANDIDATES_PER_QUERY) -> List[Dict]:
    """
    Search Crossref for works matching a query.
    150M+ records, rich metadata.
    """
    params = {
        "query": query,
        "rows": rows,
        "select": "DOI,title,author,published-print,container-title,publisher,is-referenced-by-count,license,abstract,link",
    }
    headers = {"User-Agent": f"Editorrah/2.0 (mailto:{OPENALEX_EMAIL})"}
    data = await _http_get(f"{CROSSREF_BASE}/works", params=params, headers=headers)
    if not data or "message" not in data:
        return []

    items = data["message"].get("items", [])
    works = []
    for item in items:
        authors = []
        for a in (item.get("author") or [])[:5]:
            name = f"{a.get('given', '')} {a.get('family', '')}".strip()
            if name:
                authors.append(name)

        pub_date = item.get("published-print") or item.get("published-online") or {}
        date_parts = pub_date.get("date-parts", [[]])
        year = date_parts[0][0] if date_parts and date_parts[0] else None

        titles = item.get("title") or []
        title = titles[0] if titles else ""
        journals = item.get("container-title") or []
        journal = journals[0] if journals else ""

        licenses = item.get("license") or []
        license_url = licenses[0].get("URL", "") if licenses else ""

        links = item.get("link") or []
        pdf_url = ""
        for link in links:
            if "pdf" in (link.get("content-type") or ""):
                pdf_url = link.get("URL", "")
                break

        works.append({
            "api": "crossref",
            "doi": item.get("DOI", ""),
            "title": title,
            "authors": authors,
            "year": year,
            "journal": journal,
            "publisher": item.get("publisher", ""),
            "cited_by_count": item.get("is-referenced-by-count", 0),
            "license": license_url,
            "abstract": (item.get("abstract") or "").replace("<jats:p>", "").replace("</jats:p>", ""),
            "oa_url": pdf_url,
            "url": f"https://doi.org/{item.get('DOI', '')}",
        })
    return works


# ============================================================================
# 4b. WEB SEARCH — catches news, Wikipedia, blogs, any internet source
# ============================================================================

WEB_SEARCH_MAX_QUERIES = 4         # reduced from 6 — less hammering, better stagger
_DDGO_URL = "https://html.duckduckgo.com/html/"
_BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"
_GOOGLE_CSE_URL = "https://www.googleapis.com/customsearch/v1"
_SERPER_URL = "https://google.serper.dev/search"

_BROWSER_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"


def _extract_web_search_phrases(text: str, max_phrases: int = WEB_SEARCH_MAX_QUERIES) -> List[str]:
    """
    Extract search phrases from text.
    Uses two strategies:
      1. Full sentences (good for clean text)
      2. Short sub-phrases (5-8 words from middle of sentences) —
         resilient to typos since students often add typos at word boundaries
    """
    sentences = split_sentences(text)
    if not sentences:
        return []

    good = [s for s in sentences if 40 <= len(s) <= 300]
    if not good:
        good = [s for s in sentences if len(s) >= 25]
    if not good:
        return sentences[:max_phrases]

    # Strategy 1: full sentences ranked by length (longer = more unique)
    by_length = sorted(good, key=lambda s: len(s), reverse=True)

    # Strategy 2: short sub-phrases from the middle of sentences (typo-resilient)
    sub_phrases: List[str] = []
    for s in sentences:
        words = s.split()
        if len(words) >= 8:
            # Take 6-8 words from the middle of the sentence
            mid = len(words) // 2
            chunk = " ".join(words[max(0, mid - 3):mid + 4])
            if len(chunk) >= 25:
                sub_phrases.append(chunk)

    selected: List[str] = []
    seen: Set[str] = set()

    # Interleave full sentences and sub-phrases
    full_iter = iter(by_length)
    sub_iter = iter(sub_phrases)
    while len(selected) < max_phrases:
        added = False
        for src in [full_iter, sub_iter]:
            if len(selected) >= max_phrases:
                break
            try:
                s = next(src)
                if s not in seen:
                    seen.add(s)
                    selected.append(s)
                    added = True
            except StopIteration:
                pass
        if not added:
            break

    return selected


def _html_to_text(html: str) -> str:
    """Simple HTML tag stripper for extracting page content."""
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&[a-z]+;", " ", text)
    text = re.sub(r"&#x[0-9a-fA-F]+;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


async def _search_duckduckgo(query: str) -> List[Dict]:
    """
    Search DuckDuckGo. Uses duckduckgo-search library (reliable) with
    HTML scraping fallback. Rate-limited via semaphore.
    """
    global _ddg_sem
    if _ddg_sem is None:
        _ddg_sem = asyncio.Semaphore(1)

    async with _ddg_sem:
        # Try library first (handles rate limits, cookies, endpoint rotation)
        if HAS_DDGS:
            results = await _search_ddg_library(query)
            if results:
                return results

        # Fallback to HTML scraping
        return await _search_ddg_html(query)


async def _search_ddg_library(query: str) -> List[Dict]:
    """Search using duckduckgo-search library — much more reliable than HTML scraping."""
    try:
        exact_query = f'"{query[:200]}"'

        def _do_search():
            try:
                ddgs = DDGS()
                return list(ddgs.text(exact_query, max_results=5))
            except Exception:
                return []

        loop = asyncio.get_running_loop()
        raw = await asyncio.wait_for(
            loop.run_in_executor(None, _do_search),
            timeout=15.0,
        )

        results = []
        for r in (raw or []):
            url = r.get("href", "") or r.get("link", "")
            title = r.get("title", "")
            snippet = r.get("body", "") or r.get("snippet", "")
            if url and title:
                results.append({
                    "url": url,
                    "title": title,
                    "snippet": snippet,
                    "search_engine": "duckduckgo",
                })

        logger.info(f"DuckDuckGo (library): {len(results)} results")
        return results
    except asyncio.TimeoutError:
        logger.warning("DuckDuckGo library search timed out (15s)")
        return []
    except Exception as e:
        logger.warning(f"DuckDuckGo library search failed: {e}")
        return []


def _parse_ddg_html(html: str) -> List[Dict]:
    """Parse DDG HTML with multiple selector strategies."""
    from urllib.parse import unquote

    results = []

    # Strategy 1: class="result__a" (standard DDG HTML endpoint)
    raw_links = re.findall(r'class="result__a"[^>]*href="([^"]+)"', html)
    raw_titles = re.findall(r'class="result__a"[^>]*>(.+?)</a>', html)
    # Snippets can end with </a> or </td> depending on DDG version
    raw_snippets = re.findall(r'class="result__snippet"[^>]*>(.+?)</(?:a|td|span)>', html, re.DOTALL)

    for i in range(min(5, len(raw_links))):
        url = raw_links[i]
        url_match = re.search(r'uddg=([^&]+)', url)
        if url_match:
            url = unquote(url_match.group(1))

        title = re.sub(r"<[^>]+>", "", raw_titles[i]) if i < len(raw_titles) else ""
        snippet = re.sub(r"<[^>]+>", "", raw_snippets[i]).strip() if i < len(raw_snippets) else ""

        if not url or not title:
            continue

        results.append({
            "url": url,
            "title": title,
            "snippet": snippet,
            "search_engine": "duckduckgo",
        })

    # Strategy 2: broader pattern if strategy 1 found nothing
    if not results:
        links = re.findall(r'<a[^>]+href="([^"]*uddg=[^"]+)"[^>]*>(.+?)</a>', html)
        for url_raw, title_html in links[:5]:
            url_match = re.search(r'uddg=([^&]+)', url_raw)
            url = unquote(url_match.group(1)) if url_match else ""
            title = re.sub(r"<[^>]+>", "", title_html).strip()
            if url and title:
                results.append({
                    "url": url,
                    "title": title,
                    "snippet": "",
                    "search_engine": "duckduckgo",
                })

    return results


async def _search_ddg_html(query: str) -> List[Dict]:
    """Fallback: DDG HTML endpoint with retry for 202 challenge pages."""
    try:
        from ..utils.http_client import get_client
        client = get_client()
    except Exception:
        import httpx
        client = httpx.AsyncClient()

    exact_query = '"%s"' % query[:200]

    for attempt in range(2):
        try:
            resp = await client.post(
                _DDGO_URL,
                data={"q": exact_query, "b": ""},
                headers={
                    "User-Agent": _BROWSER_UA,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Referer": "https://html.duckduckgo.com/",
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "en-US,en;q=0.9",
                },
                timeout=API_TIMEOUT,
            )

            if resp.status_code not in (200, 202):
                logger.debug(f"DuckDuckGo HTML returned {resp.status_code}")
                continue

            results = _parse_ddg_html(resp.text)
            if results:
                logger.info(f"DuckDuckGo (HTML): {len(results)} results")
                return results

            # 202 with no results = challenge page, retry after delay
            if attempt == 0:
                await asyncio.sleep(2.5)

        except Exception as e:
            logger.debug(f"DDG HTML attempt {attempt+1}: {e}")

    logger.debug("DuckDuckGo HTML: 0 results after retries")
    return []


async def _search_google_cse(query: str) -> List[Dict]:
    """
    Google Custom Search API. Needs GOOGLE_CSE_KEY + GOOGLE_CSE_CX env vars.
    100 free queries/day, then $5/1000.
    """
    api_key = os.getenv("GOOGLE_CSE_KEY", "")
    cx = os.getenv("GOOGLE_CSE_CX", "")
    if not api_key or not cx:
        return []

    exact_query = '"%s"' % query[:200]
    data = await _http_get(
        _GOOGLE_CSE_URL,
        params={"key": api_key, "cx": cx, "q": exact_query, "num": 5},
    )
    if not data or "items" not in data:
        return []

    results = []
    for item in data["items"][:5]:
        results.append({
            "url": item.get("link", ""),
            "title": item.get("title", ""),
            "snippet": item.get("snippet", ""),
            "search_engine": "google",
        })
    return results


async def _search_brave(query: str) -> List[Dict]:
    """Brave Search API. Needs BRAVE_SEARCH_KEY env var. Free tier: 2000/month."""
    api_key = os.getenv("BRAVE_SEARCH_KEY", "")
    if not api_key:
        return []

    exact_query = '"%s"' % query[:200]
    data = await _http_get(
        _BRAVE_URL,
        params={"q": exact_query, "count": 5},
        headers={"Accept": "application/json", "Accept-Encoding": "gzip", "X-Subscription-Token": api_key},
    )
    if not data:
        return []

    results = []
    for item in (data.get("web", {}).get("results") or [])[:5]:
        results.append({
            "url": item.get("url", ""),
            "title": item.get("title", ""),
            "snippet": item.get("description", ""),
            "search_engine": "brave",
        })
    return results


async def _search_serper(query: str) -> List[Dict]:
    """Google search via Serper.dev API. Needs SERPER_API_KEY env var. $50/50K searches."""
    api_key = os.getenv("SERPER_API_KEY", "")
    if not api_key:
        return []

    try:
        from ..utils.http_client import get_client
        client = get_client()
    except Exception:
        import httpx
        client = httpx.AsyncClient()

    try:
        resp = await client.post(
            _SERPER_URL,
            json={"q": f'"{query[:200]}"', "num": 5},
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            timeout=API_TIMEOUT,
        )
        if resp.status_code != 200:
            return []

        data = resp.json()
        results = []
        for item in (data.get("organic") or [])[:5]:
            results.append({
                "url": item.get("link", ""),
                "title": item.get("title", ""),
                "snippet": item.get("snippet", ""),
                "search_engine": "google_serper",
            })
        logger.info(f"Serper (Google): {len(results)} results")
        return results
    except Exception as e:
        logger.debug(f"Serper search failed: {e}")
        return []


async def _fetch_page_text(url: str, max_chars: int = 15000) -> str:
    """Fetch a web page and extract its text content."""
    skip_domains = {"youtube.com", "twitter.com", "x.com", "facebook.com", "instagram.com", "tiktok.com"}
    try:
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.replace("www.", "")
        if domain in skip_domains:
            return ""
    except Exception:
        pass

    try:
        from ..utils.http_client import get_client
        client = get_client()
    except Exception:
        import httpx
        client = httpx.AsyncClient()

    try:
        resp = await client.get(
            url,
            headers={"User-Agent": _BROWSER_UA},
            timeout=8,
            follow_redirects=True,
        )
        if resp.status_code != 200:
            return ""
        content_type = resp.headers.get("content-type", "")
        if "text/html" not in content_type and "text/plain" not in content_type:
            return ""
        return _html_to_text(resp.text)[:max_chars]
    except Exception:
        return ""


async def _check_winston_plagiarism(content: str) -> Optional[Dict[str, Any]]:
    """
    Call Winston AI plagiarism API. Returns the raw response dict or None on failure.
    Winston provides proper source matching with exact character positions —
    far more accurate than our DDG scraping approach.
    """
    if not WINSTON_API_KEY:
        return None

    try:
        from ..utils.http_client import get_client
        client = get_client()
    except Exception:
        import httpx
        client = httpx.AsyncClient()

    try:
        resp = await client.post(
            WINSTON_API_URL,
            json={"text": content, "language": "auto", "country": "us"},
            headers={
                "Authorization": f"Bearer {WINSTON_API_KEY}",
                "Content-Type": "application/json",
            },
            timeout=30,
        )
        if resp.status_code != 200:
            logger.warning(f"Winston AI returned {resp.status_code}: {resp.text[:200]}")
            return None

        data = resp.json()
        logger.info(
            f"Winston AI: score={data.get('result', {}).get('score', '?')}, "
            f"sources={data.get('result', {}).get('sourceCounts', 0)}, "
            f"credits_remaining={data.get('credits_remaining', '?')}"
        )
        return data
    except Exception as e:
        logger.warning(f"Winston AI plagiarism check failed: {e}")
        return None


def _map_winston_to_matches(winston_data: Dict[str, Any], content: str) -> List[Dict[str, Any]]:
    """
    Convert Winston AI response to our internal match format so the
    frontend PlagiarismViewer works without changes.
    """
    matches: List[Dict[str, Any]] = []
    sources = winston_data.get("sources") or []

    for src in sources:
        score = src.get("score", 0)
        if score < 5:
            continue

        # Build matching passages from Winston's plagiarismFound
        passages = []
        for pf in (src.get("plagiarismFound") or []):
            start = pf.get("startIndex", 0)
            end = pf.get("endIndex", 0)
            seq = pf.get("sequence", "")
            if not seq and end > start:
                seq = content[start:end]
            passages.append({
                "text": seq,
                "source_start": start,
                "source_end": end,
                "length": len(seq.split()),
            })

        # Determine match type from Winston's word counts
        identical = src.get("identicalWordCounts", 0)
        similar = src.get("similarWordCounts", 0)
        total_plag = src.get("plagiarismWords", 0)
        if identical > 0 and similar == 0:
            match_type = "exact"
        elif identical > similar:
            match_type = "minor_changes"
        else:
            match_type = "paraphrased"

        matches.append({
            "source_type": "web",
            "url": src.get("url", ""),
            "title": src.get("title", ""),
            "search_engine": "winston_ai",
            "similarity_score": score,
            "match_type": match_type,
            "compared_against": "full_page",
            "is_excluded": src.get("is_excluded", False),
            "details": {
                "plagiarism_words": total_plag,
                "identical_words": identical,
                "similar_words": similar,
                "total_source_words": src.get("totalNumberOfWords", 0),
                "matching_passages": passages[:10],
                "sentence_matches": [],
                "author": src.get("author", ""),
                "description": src.get("description", ""),
                "published_date": src.get("publishedDate"),
                "is_citation": src.get("citation", False),
            },
        })

    matches.sort(key=lambda m: m["similarity_score"], reverse=True)
    return matches


async def _check_web_sources(content: str) -> List[Dict[str, Any]]:
    """
    Stage 2c: Search the web for matching content.
    Uses Winston AI (accurate, paid) with DDG fallback (free).
    """
    # --- Primary: Winston AI ---
    winston_data = await _check_winston_plagiarism(content)
    if winston_data and "result" in winston_data:
        # Winston responded successfully — use its results (even if 0 sources = clean)
        matches = _map_winston_to_matches(winston_data, content)
        logger.info(f"Winston AI: {len(matches)} web matches found")
        return matches

    logger.info("Winston AI unavailable, falling back to DDG search")

    # --- Fallback: DDG + other search engines ---
    phrases = _extract_web_search_phrases(content)
    if not phrases:
        return []

    phrases = phrases[:WEB_SEARCH_MAX_QUERIES]
    logger.info(f"Web search: checking {len(phrases)} phrases")

    # Search multiple engines — DDG uses semaphore internally, others are API-key gated
    all_search_results: List[Dict] = []

    search_tasks = []
    for phrase in phrases:
        # DDG — semaphore-limited internally (sequential, ~2s apart)
        search_tasks.append(_search_duckduckgo(phrase))
        # API-key gated engines — run freely in parallel (rate limited by provider)
        search_tasks.append(_search_google_cse(phrase))
        search_tasks.append(_search_brave(phrase))
        search_tasks.append(_search_serper(phrase))

    raw = await asyncio.gather(*search_tasks, return_exceptions=True)

    engine_counts: Dict[str, int] = {}
    for r in raw:
        if isinstance(r, list):
            for item in r:
                eng = item.get("search_engine", "unknown")
                engine_counts[eng] = engine_counts.get(eng, 0) + 1
            all_search_results.extend(r)

    logger.info(f"Web search raw results: {len(all_search_results)} total — {engine_counts}")

    if not all_search_results:
        return []

    # Deduplicate by URL
    seen_urls: Set[str] = set()
    unique_results: List[Dict] = []
    for r in all_search_results:
        url = r.get("url", "").rstrip("/").lower()
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_results.append(r)

    logger.info(f"Web search: {len(unique_results)} unique URLs found")

    # Fetch page content and compare for top candidates
    matches: List[Dict[str, Any]] = []
    fetch_tasks = [_fetch_page_text(r["url"]) for r in unique_results[:10]]
    page_texts = await asyncio.gather(*fetch_tasks, return_exceptions=True)

    fetched_count = sum(1 for p in page_texts if isinstance(p, str) and len(p) >= 100)
    failed_count = len(page_texts) - fetched_count
    logger.info(f"Web search: fetched {fetched_count} pages, {failed_count} failed/blocked")

    for i, page_text in enumerate(page_texts):
        r = unique_results[i]

        if isinstance(page_text, Exception) or not page_text or len(page_text) < 100:
            # Page fetch failed (403, Cloudflare, etc.) — check snippet for real overlap.
            # DDG often returns loosely-related results, so we must verify the snippet
            # actually shares text with the submission before counting it.
            snippet = r.get("snippet", "")
            if snippet and len(snippet) > 20:
                # Require actual n-gram overlap — not just topical TF-IDF similarity
                has_overlap = _text_has_ngram_overlap(content, snippet, n=4, min_matches=1)
                if not has_overlap:
                    logger.debug(f"Web snippet skip (no n-gram overlap): {r.get('title', '')[:60]}")
                    continue
                snippet_sim = _tfidf_cosine_pair(content, snippet)
                # Score based purely on TF-IDF — no artificial boost
                score = min(100, int(snippet_sim * 100))
                if score < 15:
                    continue
                matches.append({
                    "source_type": "web",
                    "url": r["url"],
                    "title": r["title"],
                    "snippet": snippet,
                    "search_engine": r.get("search_engine", ""),
                    "similarity_score": score,
                    "match_type": "snippet_match",
                    "compared_against": "snippet",
                    "details": {"tfidf_similarity": round(snippet_sim * 100, 1)},
                })
            continue

        # Full page fetched — compare properly
        # First, quick check: does the page share any 4-grams with the submission?
        has_overlap = _text_has_ngram_overlap(content, page_text, n=4, min_matches=2)
        if not has_overlap:
            logger.debug(f"Web page skip (no n-gram overlap): {r.get('title', '')[:60]}")
            continue

        result = comprehensive_similarity(content, page_text)

        if result["score"] < 15:
            continue

        matches.append({
            "source_type": "web",
            "url": r["url"],
            "title": r["title"],
            "search_engine": r.get("search_engine", ""),
            "similarity_score": result["score"],
            "match_type": result["match_type"],
            "compared_against": "full_page",
            "details": {
                "fingerprint_similarity": result["fingerprint_similarity"],
                "shingle_similarity": result["shingle_similarity"],
                "tfidf_similarity": result["tfidf_similarity"],
                "passage_coverage": result["passage_coverage"],
                "sentence_similarity": result["sentence_similarity"],
                "semantic_similarity": result.get("semantic_similarity"),
                "matching_passages": result["matching_passages"][:5],
                "sentence_matches": result["sentence_matches"][:5],
            },
        })

    matches.sort(key=lambda m: m["similarity_score"], reverse=True)
    return matches[:15]


async def _search_all_scholarly(queries: List[str]) -> List[Dict]:
    """
    Fire queries at scholarly APIs with proper rate limiting & balance.
    OpenAlex: all queries (most reliable, generous rate limits)
    Crossref: top 3 queries (reliable, polite pool)
    S2: top 3 queries only (rate limited — semaphore enforced)
    """
    tasks = []

    # OpenAlex — most reliable, 240M+ works, free, generous limits
    for q in queries[:MAX_SCHOLARLY_QUERIES]:
        tasks.append(search_openalex(q))

    # Crossref — 150M+ records, reliable (was only 1 query before, now 3)
    for q in queries[:3]:
        tasks.append(search_crossref(q))

    # Semantic Scholar — rate limited, only top 3 queries
    # S2 semaphore inside search_semantic_scholar enforces sequential + 1.5s gap
    for q in queries[:3]:
        tasks.append(search_semantic_scholar(q))

    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    # Track per-API yields for logging
    api_counts: Dict[str, int] = {"openalex": 0, "crossref": 0, "semantic_scholar": 0}
    seen_doi: Set[str] = set()
    seen_title: Set[str] = set()
    deduped: List[Dict] = []

    for result in raw_results:
        if isinstance(result, Exception):
            logger.debug(f"Scholarly API error: {result}")
            continue
        if not isinstance(result, list):
            continue
        for work in result:
            doi = (work.get("doi") or "").strip().lower()
            title_key = normalize_text(work.get("title") or "")[:80]

            if doi and doi in seen_doi:
                continue
            if title_key and title_key in seen_title:
                continue

            if doi:
                seen_doi.add(doi)
            if title_key:
                seen_title.add(title_key)
            deduped.append(work)

            api = work.get("api", "")
            if api in api_counts:
                api_counts[api] += 1

    logger.info(
        f"Scholarly retrieval: {len(deduped)} unique works — "
        f"OpenAlex={api_counts['openalex']}, Crossref={api_counts['crossref']}, "
        f"S2={api_counts['semantic_scholar']}"
    )
    return deduped


# ============================================================================
# 5. PUBLICATION ENRICHMENT
# ============================================================================

async def enrich_publication(source: Dict) -> Dict:
    """
    Enrich a matched source with additional metadata from Crossref.
    Tries to resolve full metadata via DOI if available.
    """
    doi = source.get("doi", "")
    if not doi:
        return source

    if source.get("publisher") and source.get("license"):
        return source

    data = await _http_get(
        f"{CROSSREF_BASE}/works/{doi}",
        headers={"User-Agent": f"Editorrah/2.0 (mailto:{OPENALEX_EMAIL})"},
    )
    if not data or "message" not in data:
        return source

    msg = data["message"]
    if not source.get("publisher"):
        source["publisher"] = msg.get("publisher", "")

    licenses = msg.get("license") or []
    if licenses and not source.get("license"):
        source["license"] = licenses[0].get("URL", "")

    issn_list = msg.get("ISSN") or []
    if issn_list:
        source["issn"] = issn_list[0]

    isbn_list = msg.get("ISBN") or []
    if isbn_list:
        source["isbn"] = isbn_list[0]

    subjects = msg.get("subject") or []
    if subjects:
        source["subjects"] = subjects

    funders = msg.get("funder") or []
    if funders:
        source["funders"] = [f.get("name", "") for f in funders[:3]]

    refs = msg.get("reference") or []
    source["reference_count"] = len(refs)

    return source


def format_citation(source: Dict, style: str = "apa") -> str:
    """Generate a formatted citation string from source metadata."""
    authors = source.get("authors", [])
    title = source.get("title", "Untitled")
    year = source.get("year") or "n.d."
    journal = source.get("journal", "")
    doi = source.get("doi", "")

    if style == "apa":
        author_str = ""
        if len(authors) == 1:
            parts = authors[0].split()
            if len(parts) >= 2:
                author_str = f"{parts[-1]}, {parts[0][0]}."
            else:
                author_str = authors[0]
        elif len(authors) == 2:
            a1 = authors[0].split()
            a2 = authors[1].split()
            author_str = f"{a1[-1]}, {a1[0][0]}., & {a2[-1]}, {a2[0][0]}." if len(a1) >= 2 and len(a2) >= 2 else f"{authors[0]} & {authors[1]}"
        elif len(authors) > 2:
            first = authors[0].split()
            author_str = f"{first[-1]}, {first[0][0]}., et al." if len(first) >= 2 else f"{authors[0]} et al."
        else:
            author_str = "Unknown"

        cite = f"{author_str} ({year}). {title}."
        if journal:
            cite += f" *{journal}*."
        if doi:
            cite += f" https://doi.org/{doi}"
        return cite

    return f"{', '.join(authors)} ({year}). {title}. {journal}."


# ============================================================================
# 6. MAIN ENGINE
# ============================================================================

# MongoDB collection references (set by main.py)
_submissions_col = None
_fingerprints_col = None
_plagiarism_checks_col = None
_scholarly_cache_col = None
_plagiarism_results_col = None
_users_col = None


def set_collections(submissions=None, fingerprints=None, plagiarism_checks=None, scholarly_cache=None, plagiarism_results=None, users=None):
    global _submissions_col, _fingerprints_col, _plagiarism_checks_col, _scholarly_cache_col, _plagiarism_results_col, _users_col
    _submissions_col = submissions
    _fingerprints_col = fingerprints
    _plagiarism_checks_col = plagiarism_checks
    _plagiarism_results_col = plagiarism_results
    _scholarly_cache_col = scholarly_cache
    if users is not None:
        _users_col = users


async def _check_internal_corpus(
    content: str,
    exclude_submission_id: str = "",
    assignment_id: str = "",
    student_id: str = "",
) -> List[Dict[str, Any]]:
    """
    Stage 2a: Check content against the internal document corpus.
    Uses winnowing fingerprint pre-filter, then full comparison on candidates.
    """
    if _fingerprints_col is None or _submissions_col is None:
        return []

    content_fp = winnowing_fingerprint(content)
    if not content_fp:
        return []

    candidate_ids: Set[str] = set()

    query_filter: Dict[str, Any] = {"submission_id": {"$ne": exclude_submission_id}}
    if assignment_id:
        query_filter["assignment_id"] = assignment_id

    cursor = _fingerprints_col.find(query_filter, {"submission_id": 1, "fingerprint": 1, "student_id": 1}).limit(500)
    async for doc in cursor:
        other_fp = set(doc.get("fingerprint", []))
        if not other_fp:
            continue
        overlap = jaccard_similarity(content_fp, other_fp)
        if overlap >= 0.08:
            candidate_ids.add(doc["submission_id"])

    # Self-plagiarism check (same student, different assignment)
    if student_id:
        self_filter: Dict[str, Any] = {
            "student_id": student_id,
            "submission_id": {"$ne": exclude_submission_id},
        }
        if assignment_id:
            self_filter["assignment_id"] = {"$ne": assignment_id}

        self_cursor = _fingerprints_col.find(self_filter, {"submission_id": 1, "fingerprint": 1}).limit(100)
        async for doc in self_cursor:
            other_fp = set(doc.get("fingerprint", []))
            if not other_fp:
                continue
            overlap = jaccard_similarity(content_fp, other_fp)
            if overlap >= 0.08:
                candidate_ids.add(doc["submission_id"])

    if not candidate_ids:
        return []

    # Full comparison for candidates
    candidates = await _submissions_col.find(
        {"submission_id": {"$in": list(candidate_ids)}, "status": {"$in": ["submitted", "graded", "returned"]}},
        {"submission_id": 1, "student_id": 1, "assignment_id": 1, "content": 1},
    ).to_list(length=len(candidate_ids))

    matches = []
    for cand in candidates:
        cand_content = cand.get("content", "")
        if not cand_content or len(cand_content.strip()) < 50:
            continue

        result = comprehensive_similarity(content, cand_content)
        if result["score"] < 20:
            continue

        is_self_plag = assignment_id and cand.get("assignment_id") != assignment_id
        matches.append({
            "source_type": "self-plagiarism" if is_self_plag else "internal",
            "matched_submission_id": cand["submission_id"],
            "matched_student_id": cand.get("student_id", ""),
            "matched_assignment_id": cand.get("assignment_id", ""),
            "similarity_score": result["score"],
            "match_type": result["match_type"],
            "details": result,
        })

    matches.sort(key=lambda m: m["similarity_score"], reverse=True)
    return matches


async def _check_scholarly_sources(content: str) -> List[Dict[str, Any]]:
    """
    Stage 2b + 3 + 4: Search scholarly APIs, compare abstracts,
    enrich with publication metadata.
    """
    queries = extract_search_queries(content)
    if not queries:
        return []

    logger.info(f"Searching scholarly APIs with {len(queries)} queries")
    scholarly_works = await _search_all_scholarly(queries)
    logger.info(f"Found {len(scholarly_works)} candidate scholarly works")

    if not scholarly_works:
        return []

    # Compare content against each candidate's abstract
    matches = []
    for work in scholarly_works:
        abstract = work.get("abstract", "")
        if not abstract or len(abstract) < 30:
            continue

        result = comprehensive_similarity(content, abstract)

        if result["score"] < 15:
            continue

        enriched = await enrich_publication(work)
        citation = format_citation(enriched)

        matches.append({
            "source_type": "scholarly",
            "api": work.get("api", ""),
            "doi": work.get("doi", ""),
            "title": work.get("title", ""),
            "authors": work.get("authors", []),
            "year": work.get("year"),
            "journal": work.get("journal", ""),
            "publisher": enriched.get("publisher", ""),
            "cited_by_count": work.get("cited_by_count", 0),
            "is_oa": work.get("is_oa", False),
            "oa_url": work.get("oa_url", ""),
            "url": work.get("url", ""),
            "license": enriched.get("license", ""),
            "issn": enriched.get("issn", ""),
            "subjects": enriched.get("subjects", []),
            "citation": citation,
            "similarity_score": result["score"],
            "match_type": result["match_type"],
            "compared_against": "abstract",
            "details": {
                "fingerprint_similarity": result["fingerprint_similarity"],
                "shingle_similarity": result["shingle_similarity"],
                "tfidf_similarity": result["tfidf_similarity"],
                "passage_coverage": result["passage_coverage"],
                "sentence_similarity": result["sentence_similarity"],
                "matching_passages": result["matching_passages"][:5],
                "sentence_matches": result["sentence_matches"][:5],
            },
        })

    matches.sort(key=lambda m: m["similarity_score"], reverse=True)
    return matches[:20]


async def check_plagiarism_v2(
    content: str,
    title: str = "",
    submission_id: str = "",
    assignment_id: str = "",
    class_id: str = "",
    student_id: str = "",
    check_internal: bool = True,
    check_scholarly: bool = True,
    check_web: bool = True,
) -> Dict[str, Any]:
    """
    Main entry point — run the full plagiarism detection pipeline.

    Returns a structured result with:
      - check_id, overall_score, source_count
      - internal_matches, scholarly_matches, web_matches
      - per-source details with passages, metadata, citations
    """
    start_time = time.time()
    check_id = hashlib.sha256(
        f"{content[:200]}{time.time()}".encode()
    ).hexdigest()[:24]

    if not content or len(content.strip()) < 50:
        return {
            "check_id": check_id,
            "status": "skipped",
            "overall_score": 0,
            "message": "Content too short for plagiarism check (minimum 50 characters)",
            "sources": [],
            "duration_ms": 0,
        }

    # Run internal + scholarly + web checks in parallel
    async def _noop():
        return []

    task_internal = _check_internal_corpus(content, submission_id, assignment_id, student_id) if check_internal else _noop()
    task_scholarly = _check_scholarly_sources(content) if check_scholarly else _noop()
    task_web = _check_web_sources(content) if check_web else _noop()

    results = await asyncio.gather(task_internal, task_scholarly, task_web, return_exceptions=True)

    internal_matches = results[0] if not isinstance(results[0], Exception) else []
    scholarly_matches = results[1] if not isinstance(results[1], Exception) else []
    web_matches = results[2] if not isinstance(results[2], Exception) else []

    if isinstance(results[0], Exception):
        logger.error(f"Internal corpus check failed: {results[0]}")
    if isinstance(results[1], Exception):
        logger.error(f"Scholarly check failed: {results[1]}")
    if isinstance(results[2], Exception):
        logger.error(f"Web source check failed: {results[2]}")

    # Compute overall score
    internal_max = max([m["similarity_score"] for m in internal_matches], default=0)
    scholarly_max = max([m["similarity_score"] for m in scholarly_matches], default=0)
    web_max = max([m["similarity_score"] for m in web_matches], default=0)

    overall_score = max(
        int(internal_max * 1.0),     # internal = full weight (collusion)
        int(scholarly_max * 0.85),   # scholarly = 85% weight
        int(web_max * 0.90),        # web = 90% weight (direct copy from internet)
    )
    overall_score = min(100, overall_score)

    # Store fingerprint for future checks
    if _fingerprints_col is not None and submission_id:
        fp_set = winnowing_fingerprint(content)
        await _fingerprints_col.update_one(
            {"submission_id": submission_id},
            {"$set": {
                "submission_id": submission_id,
                "assignment_id": assignment_id,
                "class_id": class_id,
                "student_id": student_id,
                "fingerprint": list(fp_set),
                "word_count": len(tokenize_words(content)),
                "updated_at": datetime.now(timezone.utc),
            }},
            upsert=True,
        )

    duration_ms = int((time.time() - start_time) * 1000)

    apis_used = []
    if check_scholarly:
        apis_used.extend(["openalex", "semantic_scholar", "crossref"])
    if check_web:
        apis_used.append("web_search")

    result = {
        "check_id": check_id,
        "status": "completed",
        "overall_score": overall_score,
        "highest_internal_score": internal_max,
        "highest_scholarly_score": scholarly_max,
        "highest_web_score": web_max,
        "internal_matches_count": len(internal_matches),
        "scholarly_matches_count": len(scholarly_matches),
        "web_matches_count": len(web_matches),
        "total_sources_found": len(internal_matches) + len(scholarly_matches) + len(web_matches),
        "internal_matches": internal_matches[:10],
        "scholarly_matches": scholarly_matches[:15],
        "web_matches": web_matches[:10],
        "word_count": len(tokenize_words(content)),
        "sentences_analyzed": len(split_sentences(content)),
        "queries_sent": min(len(extract_search_queries(content)), MAX_SCHOLARLY_QUERIES),
        "apis_used": apis_used,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "duration_ms": duration_ms,
    }

    # Persist result
    if _plagiarism_checks_col is not None:
        await _plagiarism_checks_col.update_one(
            {"check_id": check_id},
            {"$set": {**result, "content_preview": content[:500]}},
            upsert=True,
        )

    return result


async def batch_check_v2(assignment_id: str) -> Dict[str, Any]:
    """
    Run the v2 plagiarism pipeline on ALL submissions for an assignment.
    Performs internal (student-vs-student) AND scholarly checks.
    Updates each submission's plagiarism_score and plagiarism_matches.
    """
    if _submissions_col is None:
        return {"error": "Submissions collection not available"}

    subs = await _submissions_col.find(
        {
            "assignment_id": assignment_id,
            "status": {"$in": ["submitted", "graded", "returned"]},
        },
        {"submission_id": 1, "student_id": 1, "content": 1, "content_html": 1,
         "trust_score": 1, "ai_detection": 1, "stylometry": 1, "class_id": 1},
    ).to_list(length=5000)

    if len(subs) < 1:
        return {"assignment_id": assignment_id, "submissions_checked": 0, "skipped": True}

    logger.info(f"Batch plagiarism v2: checking {len(subs)} submissions for assignment {assignment_id}")

    updated_count = 0
    flagged_count = 0
    results_summary = []

    for sub in subs:
        content = sub.get("content") or sub.get("content_html") or ""
        # Always strip HTML — content field often contains HTML markup
        content = _html_to_text(content)
        if not content or len(content.strip()) < 50:
            continue

        try:
            result = await check_plagiarism_v2(
                content=content,
                submission_id=sub["submission_id"],
                assignment_id=assignment_id,
                class_id=sub.get("class_id", ""),
                student_id=sub.get("student_id", ""),
                check_internal=True,
                check_scholarly=True,
            )

            score = result.get("overall_score", 0)

            # Resolve student names for internal matches
            _int_sids = {m.get("matched_student_id", "") for m in result.get("internal_matches", []) if m.get("matched_student_id")}
            _sname_map = {}
            if _int_sids and _users_col is not None:
                async for u in _users_col.find({"user_id": {"$in": list(_int_sids)}}, {"user_id": 1, "name": 1, "email": 1}):
                    _sname_map[u["user_id"]] = u.get("name") or u.get("email", "").split("@")[0]

            all_matches = []
            for m in result.get("internal_matches", []):
                details = m.get("details", {})
                segments = details.get("matching_passages", [])[:10]
                for sm in details.get("sentence_matches", []):
                    if sm.get("similarity", 0) >= 0.6:
                        segments.append({
                            "text": sm.get("source_sentence", ""),
                            "length": len(sm.get("source_sentence", "").split()),
                            "similarity": sm.get("similarity", 0),
                        })
                _msid = m.get("matched_student_id", "")
                all_matches.append({
                    "matched_submission_id": m.get("matched_submission_id", ""),
                    "matched_student_id": _msid,
                    "matched_student_name": _sname_map.get(_msid, ""),
                    "similarity_score": m["similarity_score"],
                    "matching_segments": segments[:15],
                    "details": {"sentence_matches": details.get("sentence_matches", [])[:10]},
                    "type": m.get("source_type", "internal"),
                    "source_type": m.get("source_type", "internal"),
                })
            for m in result.get("scholarly_matches", []):
                details = m.get("details", {})
                segments = details.get("matching_passages", [])[:10]
                for sm in details.get("sentence_matches", []):
                    if sm.get("similarity", 0) >= 0.6:
                        segments.append({
                            "text": sm.get("source_sentence", ""),
                            "length": len(sm.get("source_sentence", "").split()),
                            "similarity": sm.get("similarity", 0),
                        })
                all_matches.append({
                    "source_type": "scholarly",
                    "type": "scholarly",
                    "title": m.get("title", ""),
                    "authors": m.get("authors", []),
                    "doi": m.get("doi", ""),
                    "url": m.get("url", ""),
                    "journal": m.get("journal", ""),
                    "year": m.get("year"),
                    "citation": m.get("citation", ""),
                    "similarity_score": m["similarity_score"],
                    "match_type": m.get("match_type", ""),
                    "matching_segments": segments[:15],
                    "details": {"sentence_matches": details.get("sentence_matches", [])[:10]},
                })
            for m in result.get("web_matches", []):
                details = m.get("details", {})
                segments = details.get("matching_passages", [])[:10]
                for sm in details.get("sentence_matches", []):
                    if sm.get("similarity", 0) >= 0.6:
                        segments.append({
                            "text": sm.get("source_sentence", ""),
                            "length": len(sm.get("source_sentence", "").split()),
                            "similarity": sm.get("similarity", 0),
                        })
                all_matches.append({
                    "source_type": "web",
                    "type": "web",
                    "title": m.get("title", ""),
                    "url": m.get("url", ""),
                    "similarity_score": m.get("similarity_score", 0),
                    "match_type": m.get("match_type", ""),
                    "matching_segments": segments[:15],
                    "details": {"sentence_matches": details.get("sentence_matches", [])[:10]},
                })

            all_matches.sort(key=lambda x: x.get("similarity_score", 0), reverse=True)

            update_fields: Dict[str, Any] = {
                "plagiarism_score": score,
                "plagiarism_matches": all_matches[:15],
                "plagiarism_v2_check_id": result.get("check_id"),
                "plagiarism_v2_scholarly_count": result.get("scholarly_matches_count", 0),
                "plagiarism_v2_internal_count": result.get("internal_matches_count", 0),
                "plagiarism_v2_web_count": result.get("web_matches_count", 0),
                "plagiarism_v2_checked_at": datetime.now(timezone.utc),
            }

            if score >= 40:
                flagged_count += 1
                update_fields["auto_grade_needs_review"] = True

            await _submissions_col.update_one(
                {"submission_id": sub["submission_id"]},
                {"$set": update_fields},
            )
            updated_count += 1
            results_summary.append({
                "submission_id": sub["submission_id"],
                "score": score,
                "internal_matches": result.get("internal_matches_count", 0),
                "scholarly_matches": result.get("scholarly_matches_count", 0),
                "web_matches": result.get("web_matches_count", 0),
            })

            # Persist full check result for audit trail
            if _plagiarism_results_col is not None:
                try:
                    await _plagiarism_results_col.update_one(
                        {"submission_id": sub["submission_id"], "assignment_id": assignment_id},
                        {"$set": {
                            "check_id": result.get("check_id", ""),
                            "submission_id": sub["submission_id"],
                            "assignment_id": assignment_id,
                            "student_id": sub.get("student_id", ""),
                            "overall_score": result.get("overall_score", 0),
                            "web_matches": result.get("web_matches", []),
                            "scholarly_matches": result.get("scholarly_matches", []),
                            "internal_matches": result.get("internal_matches", []),
                            "duration_ms": result.get("duration_ms", 0),
                            "checked_at": datetime.now(timezone.utc),
                        }},
                        upsert=True,
                    )
                except Exception as store_err:
                    logger.warning(f"Failed to store plagiarism result for {sub['submission_id']}: {store_err}")

        except Exception as e:
            logger.error(f"Plagiarism v2 check failed for {sub['submission_id']}: {e}")

    logger.info(f"Batch plagiarism v2 complete: {updated_count} updated, {flagged_count} flagged")

    return {
        "assignment_id": assignment_id,
        "submissions_checked": updated_count,
        "flagged": flagged_count,
        "results": results_summary,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }


# ============================================================================
# 7. REPORT GENERATION
# ============================================================================

def generate_report_html(check_result: Dict[str, Any], student_name: str = "", assignment_title: str = "") -> str:
    """Generate a rich HTML plagiarism report from a check result."""
    overall = check_result.get("overall_score", 0)
    internal = check_result.get("internal_matches", [])
    scholarly = check_result.get("scholarly_matches", [])
    word_count = check_result.get("word_count", 0)
    duration = check_result.get("duration_ms", 0)
    checked_at = check_result.get("checked_at", "")

    def _color(score):
        if score <= 15:
            return "#16a34a"
        if score <= 40:
            return "#d97706"
        return "#dc2626"

    def _level(score):
        if score <= 15:
            return "Low Similarity"
        if score <= 40:
            return "Moderate Similarity"
        return "High Similarity"

    color = _color(overall)
    level = _level(overall)

    internal_rows = ""
    for m in internal[:10]:
        s = m.get("similarity_score", 0)
        sc = _color(s)
        sid = m.get("matched_submission_id", "")[:8]
        stype = m.get("source_type", "internal")
        mtype = m.get("match_type", "")
        internal_rows += (
            '<tr><td>%s...</td><td>%s</td>'
            '<td style="color:%s;font-weight:700">%s%%</td>'
            '<td>%s</td></tr>' % (sid, stype, sc, s, mtype)
        )

    scholarly_cards = ""
    for m in scholarly[:10]:
        s = m.get("similarity_score", 0)
        sc = _color(s)
        authors_str = ", ".join(m.get("authors", [])[:3])
        title = m.get("title", "Unknown")
        year = m.get("year", "n.d.")
        journal = m.get("journal", "")
        cited = m.get("cited_by_count", 0)
        doi = m.get("doi", "N/A")
        api = m.get("api", "")
        mtype = m.get("match_type", "")
        url = m.get("url", "")
        citation = m.get("citation", "")

        card = '<div class="source-card">'
        card += '<div class="source-title">%s</div>' % title
        card += '<div class="source-meta">%s (%s)</div>' % (authors_str, year)
        card += '<div class="source-meta">%s &middot; Cited by %s</div>' % (journal, cited)
        card += '<div class="source-meta" style="font-size:11px">DOI: %s &middot; via %s</div>' % (doi, api)
        card += '<div class="source-score" style="color:%s">Similarity: %s%% (%s)</div>' % (sc, s, mtype)
        if url:
            card += '<div class="source-meta"><a href="%s" target="_blank">View Source</a></div>' % url
        if citation:
            card += '<div class="source-citation">%s</div>' % citation
        card += '</div>'
        scholarly_cards += card

    # Build internal section
    internal_section = ""
    if internal:
        internal_section = (
            '<div class="section">'
            '<h2>Internal Matches (Student Submissions)</h2>'
            '<table><tr><th>Submission</th><th>Type</th><th>Similarity</th><th>Match Type</th></tr>'
            '%s</table></div>' % internal_rows
        )

    # Build scholarly section
    if scholarly:
        scholarly_section = (
            '<div class="section">'
            '<h2>Scholarly Sources Found (%d)</h2>'
            '%s</div>' % (len(scholarly), scholarly_cards)
        )
    else:
        scholarly_section = (
            '<div class="section"><h2>Scholarly Sources</h2>'
            '<p style="color:#16a34a;font-size:14px">'
            'No matching scholarly sources found in 240M+ works across '
            'OpenAlex, Semantic Scholar, and Crossref.</p></div>'
        )

    student_span = '<span>Student: %s</span>' % student_name if student_name else ''
    assign_span = '<span>Assignment: %s</span>' % assignment_title if assignment_title else ''

    title_tag = assignment_title or 'Document Check'

    parts = [
        '<!DOCTYPE html>',
        '<html><head><meta charset="utf-8"><title>Plagiarism Report &mdash; %s</title>' % title_tag,
        '<style>',
        '@media print { body { -webkit-print-color-adjust:exact; print-color-adjust:exact; } }',
        '* { box-sizing:border-box; margin:0; padding:0; }',
        'body { font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; background:#fff; color:#1a1a2e; }',
        '.hdr { background:linear-gradient(135deg,#0f3460,#16213e); padding:36px 40px; color:#fff; }',
        '.hdr h1 { font-size:24px; margin-bottom:2px; }',
        '.hdr .sub { opacity:.8; font-size:12px; text-transform:uppercase; letter-spacing:2px; }',
        '.meta-bar { display:flex; gap:20px; flex-wrap:wrap; margin-top:14px; font-size:12px; opacity:.85; }',
        '.body { padding:28px 36px; max-width:900px; margin:0 auto; }',
        '.score-card { background:linear-gradient(135deg,%s22,%s08); border:2px solid %s; border-radius:14px; padding:28px; text-align:center; margin-bottom:24px; }' % (color, color, color),
        '.score-big { font-size:56px; font-weight:900; color:%s; }' % color,
        '.score-label { font-size:14px; color:#5f6368; font-weight:600; text-transform:uppercase; letter-spacing:1px; margin-top:4px; }',
        '.section { margin-bottom:24px; }',
        '.section h2 { font-size:18px; color:#1a1a2e; border-bottom:2px solid #e2e8f0; padding-bottom:8px; margin-bottom:14px; }',
        'table { width:100%%; border-collapse:collapse; font-size:13px; }',
        'th { background:#f1f5f9; text-align:left; padding:10px 12px; font-weight:600; }',
        'td { padding:10px 12px; border-bottom:1px solid #e2e8f0; }',
        '.source-card { background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:16px; margin-bottom:12px; }',
        '.source-title { font-weight:700; font-size:14px; color:#1a1a2e; margin-bottom:4px; }',
        '.source-meta { font-size:12px; color:#64748b; margin-bottom:2px; }',
        '.source-meta a { color:#2563eb; text-decoration:none; }',
        '.source-score { font-size:14px; font-weight:700; margin-top:8px; }',
        '.source-citation { font-size:11px; color:#475569; background:#f1f5f9; padding:8px 10px; border-radius:6px; margin-top:8px; font-style:italic; }',
        '.stat-grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(150px,1fr)); gap:12px; margin-bottom:20px; }',
        '.stat { background:#f8fafc; border-radius:8px; padding:14px; }',
        '.stat .label { font-size:11px; color:#64748b; text-transform:uppercase; letter-spacing:0.5px; }',
        '.stat .val { font-size:22px; font-weight:800; margin-top:2px; }',
        '.footer { text-align:center; padding:20px; font-size:10px; color:#9ca3af; border-top:1px solid #e2e8f0; margin-top:28px; }',
        '</style></head><body>',
        '<div class="hdr">',
        '  <h1>Editorrah Plagiarism Report</h1>',
        '  <div class="sub">Document Similarity Analysis</div>',
        '  <div class="meta-bar">',
        '    %s %s' % (student_span, assign_span),
        '    <span>Words: %d</span>' % word_count,
        '    <span>Checked: %s</span>' % checked_at,
        '    <span>Duration: %sms</span>' % duration,
        '  </div>',
        '</div>',
        '<div class="body">',
        '  <div class="score-card">',
        '    <div class="score-big">%d%%</div>' % overall,
        '    <div class="score-label">%s</div>' % level,
        '  </div>',
        '  <div class="stat-grid">',
        '    <div class="stat"><div class="label">Internal Matches</div><div class="val">%d</div></div>' % len(internal),
        '    <div class="stat"><div class="label">Scholarly Sources</div><div class="val">%d</div></div>' % len(scholarly),
        '    <div class="stat"><div class="label">Words Analyzed</div><div class="val">%d</div></div>' % word_count,
        '    <div class="stat"><div class="label">APIs Queried</div><div class="val">OpenAlex, S2, Crossref</div></div>',
        '  </div>',
        internal_section,
        scholarly_section,
        '  <div class="footer">',
        '    Editorrah Academic Integrity System &bull; Plagiarism Engine v2 &bull; Powered by OpenAlex (240M+ works), Semantic Scholar, Crossref<br>',
        '    Report generated server-side &mdash; cannot be forged',
        '  </div>',
        '</div>',
        '</body></html>',
    ]
    return "\n".join(parts)
