# Factcheck Service

Academic-integrity verification API targeted at **AI hallucinations researchers actually face**:
fabricated citations, real-DOI-with-wrong-claim, fabricated stats, ghost authors, fabricated venues,
snowball cascades, source amnesia (Athaluri et al. 2023, Ji et al. 2023, Zhang et al. 2023, Berberette et al. 2024).

## What it does (beyond DOI format checks)

| Check | Mechanism | Sources |
|---|---|---|
| DOI format + resolution | `https://doi.org/...` HEAD + registry lookup | Crossref, DataCite |
| **Citation-content alignment** *(new)* | strict-RAG gpt-4o asks "does the abstract actually support the claim?" | OpenAlex, Unpaywall, Crossref, DataCite, Semantic Scholar |
| **Retraction detection** *(new)* | Crossref `update-to` + OpenAlex `is_retracted` | Crossref, OpenAlex |
| **Fabricated venue** *(new)* | name not in OpenAlex `/sources` (fuzzy candidate offered) | OpenAlex |
| **Fabricated institution** *(new)* | name not in ROR | ROR |
| **Ghost author** *(new)* | `Smith et al.` whose surname is missing from the cited DOI's / arXiv id's / resolved title's author list | Crossref + S2 + arXiv |
| **Citation without identifier** *(new)* | author-year / quoted-title cites resolved by title across OpenAlex, Crossref, S2 and arXiv → registry evidence, wrong-venue contradiction, unresolvable-title flag | OpenAlex, Crossref, S2, arXiv |
| **Fabricated grant** *(new)* | NSF award / NIH project numbers that the agencies' public APIs do not know | NSF Award API, NIH RePORTER |
| **Numeric hallucination guard** *(new)* | precise stats / p-values / n=… / impact factors with no DOI/URL anchor → unsupported | regex |
| **Snowball / cascade** *(new)* | entity-mention graph annotates downstream claims with their root hallucination | internal |
| **Bibliography ↔ in-text** *(new)* | orphan in-text citations & uncited bibliography entries | internal |
| **Taxonomy** *(new)* | Ji et al. intrinsic/extrinsic × Zhang et al. input/context/reality | internal |
| **Domain severity** *(new)* | medical/legal contradictions → `critical`; creative → `low` | internal |
| **Calibrated confidence** *(new)* | signal-vector model; surfaces `failure_mode = no_evidence_found / conflicting_evidence / partial_support` | internal |

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/healthz` | GET | Health check |
| `/v1/verify` | POST | Verify references and claims |

## Evidence Modes

| Mode | Description | Cost | Recommended For |
|------|-------------|------|-----------------|
| `REGISTRY_ONLY` | DOI/URL verification via Crossref/DataCite + knowledge base | **Free** | Universities (default) |
| `OFFLINE_ONLY` | Knowledge base only, no external calls | Free | Air-gapped environments |
| `HYBRID` | Registry + optional web retrieval for unresolved claims | Varies | Research institutions |

**REGISTRY_ONLY is the recommended default for universities.** It provides:
- DOI validation via Crossref and DataCite (free APIs)
- URL accessibility checks
- Factual claim verification against curated knowledge base
- No OpenAI/LLM costs

## Quick Start

```bash
# With Docker
docker compose up --build

# Without Docker (requires Redis or use memory fallback)
REDIS_URL=memory:// EVIDENCE_MODE=REGISTRY_ONLY uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Docs UI available at `http://localhost:8080/docs` (disable with `ENABLE_DOCS=false`).

## Usage

```bash
# Verify mixed claims with real and fake DOIs
curl -s http://localhost:8080/v1/verify \
  -H 'Content-Type: application/json' \
  -d '{
    "text": "The Transformer architecture was introduced in Attention Is All You Need (DOI: 10.48550/arXiv.1706.03762). Marie Curie won the Nobel Prize in Chemistry in 1911. A fake study claims 35% improvement (DOI: 10.9999/fake.2021.12345).",
    "include_evidence": true,
    "include_reference_report": true
  }'
```

## What It Validates

### Reference Integrity
- **DOI Resolution**: Checks if DOI resolves via doi.org
- **Registry Verification**: Validates against Crossref (papers) and DataCite (datasets, arXiv)
- **Metadata Extraction**: Title, authors, year, venue
- **URL Accessibility**: HEAD/GET checks with timeout handling
- **Fake DOI Detection**: Flags invalid prefixes (10.9999, 10.0000)

### Factual Claims
- **Known Facts**: Verified against curated knowledge base with real sources
- **Nobel Prizes**: Accurate dates and categories
- **Common Myths**: Flags misconceptions (Great Wall from Moon, 10% brain usage)
- **Scientific Facts**: Speed of light, boiling points, etc.

## Response Format

```json
{
  "summary": {
    "supported": 2,
    "unsupported": 1,
    "contradicted": 0,
    "unknown": 0
  },
  "claims": [
    {
      "claim": "Marie Curie won the Nobel Prize in Chemistry in 1911.",
      "verdict": "supported",
      "evidence": [
        {
          "source": "Nobel Prize Official",
          "snippet": "Marie Curie was awarded the Nobel Prize in Chemistry in 1911...",
          "url": "https://www.nobelprize.org/prizes/chemistry/1911/marie-curie/facts/"
        }
      ]
    }
  ],
  "reference_report": {
    "dois": [
      {
        "doi": "10.48550/arXiv.1706.03762",
        "status": "valid",
        "registrar": "datacite",
        "resolved_url": "https://arxiv.org/abs/1706.03762",
        "metadata": {
          "title": "Attention Is All You Need",
          "authors": ["Ashish Vaswani", "..."],
          "year": 2017
        }
      },
      {
        "doi": "10.9999/fake.2021.12345",
        "status": "not_found",
        "note": "DOI not found in doi.org, Crossref, or DataCite"
      }
    ],
    "summary": {
      "total_dois": 2,
      "valid_dois": 1,
      "invalid_dois": 1
    }
  },
  "warnings": ["Invalid DOI format: 10.9999/fake.2021.12345"]
}
```

## Verdicts

| Verdict | Meaning |
|---------|---------|
| `supported` | Claim verified against trusted source |
| `contradicted` | Claim conflicts with established facts |
| `unsupported` | Reference invalid (fake DOI, broken URL) |
| `unknown` | No evidence found; requires manual verification |

**Note**: `unknown` ≠ false. It means "not enough evidence to verify."

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `EVIDENCE_MODE` | `REGISTRY_ONLY` | Verification mode |
| `DOI_TIMEOUT_SECONDS` | `3` | Timeout for DOI resolution |
| `URL_TIMEOUT_SECONDS` | `3` | Timeout for URL checks |
| `SOURCE_FETCH_TIMEOUT_SECONDS` | `8` | Timeout for metadata/abstract lookups (Crossref, OpenAlex, S2, arXiv, ROR, Wikipedia) |
| `SEMANTIC_SCHOLAR_API_KEY` | `` | Free key from semanticscholar.org — without it S2 shares a global rate limit and title lookups are often 429'd |
| `MAX_REFERENCES_TO_CHECK` | `300` | Max DOIs to validate per request |
| `MAX_URLS_TO_CHECK` | `200` | Max URLs to validate per request |
| `CACHE_TTL_SECONDS` | `604800` | Cache TTL (7 days) |
| `ENABLE_DOCS` | `true` | Enable Swagger UI |
| `ENABLE_OPENAI_WEBSEARCH` | `false` | Cost control: disabled by default |
| `ENABLE_CITATION_ALIGNMENT` | `true` | Per-DOI strict-RAG check |
| `MAX_ALIGNMENT_DOIS` | `25` | Cap on per-request alignment calls |
| `ENABLE_FABRICATION_DETECTORS` | `true` | Numeric / venue / institution / ghost-author checks |
| `ENABLE_BIBLIOGRAPHY_REPORT` | `true` | Bibliography ↔ in-text consistency |
| `ALIGNMENT_BACKEND` | `openai` | `openai` (gpt-4o), `minicheck` (SOTA Bespoke-MiniCheck-7B), `hhem` (Vectara HHEM-2.1-Open), or `ensemble` (MiniCheck + HHEM) |
| `LOCAL_MODEL_CACHE_DIR` | `./ckpts` | Where local HF weights get cached |

### Alignment backends — accuracy vs cost

| Backend | Accuracy | Size | License | Needs |
|---|---|---|---|---|
| `openai` (default) | GPT-4 strict-RAG | API call | proprietary | `OPENAI_API_KEY` |
| `hhem` | ≈ GPT-4 (74.3% RAGTruth) | ~600 MB | Apache-2.0 | `pip install -r requirements-local.txt` |
| `minicheck` | **SOTA on LLM-AggreFact, beats GPT-4** | ~14 GB | CC-BY-NC-4.0 | `requirements-local.txt` + GPU recommended |
| `ensemble` | lowest FPR — averages MiniCheck + HHEM | ~14.6 GB | CC-BY-NC-4.0 | both above |

To use the highest-accuracy backend:

```bash
pip install -r requirements-local.txt
ALIGNMENT_BACKEND=minicheck uvicorn app.main:app --port 8080
# First request downloads the Bespoke-MiniCheck-7B weights (~14 GB).
```

## Backend Integration

```python
import httpx

async def verify_student_paper(text: str, doc_id: str):
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "http://factcheck-service:8080/v1/verify",
            json={
                "text": text,
                "doc_id": doc_id,
                "include_evidence": True,
                "include_reference_report": True,
            },
            headers={"X-API-Key": "your-key"},
            timeout=30.0,
        )
        result = resp.json()
        
        # Check for invalid references
        if result.get("reference_report"):
            invalid = result["reference_report"]["summary"]["invalid_dois"]
            if invalid > 0:
                print(f"Warning: {invalid} invalid DOI(s) detected")
        
        return result
```

## Tests

### Test 1: Valid arXiv DOI (DataCite)
```bash
curl -s http://localhost:8080/v1/verify \
  -H 'Content-Type: application/json' \
  -d '{"text": "Attention Is All You Need (DOI: 10.48550/arXiv.1706.03762)"}' \
  | jq '.reference_report.dois[0].status'
# Expected: "valid"
```

### Test 2: Fake DOI
```bash
curl -s http://localhost:8080/v1/verify \
  -H 'Content-Type: application/json' \
  -d '{"text": "Fake study (DOI: 10.9999/fake.2021.12345)"}' \
  | jq '.reference_report.dois[0].status'
# Expected: "not_found"
#   "invalid"   = string is not DOI syntax at all
#   "not_found" = well-formed but unknown to doi.org / Crossref / DataCite
# Both count toward reference_report.summary.invalid_dois.
```

### Test 3: Marie Curie Fact Check
```bash
curl -s http://localhost:8080/v1/verify \
  -H 'Content-Type: application/json' \
  -d '{"text": "Marie Curie won the Nobel Prize in Chemistry in 1911."}' \
  | jq '.claims[0].verdict'
# Expected: "supported"
```

## Scaling

- Run N replicas behind load balancer
- Shared Redis for cache + rate limits
- DOI/URL results cached for 7 days (configurable)
- No external API costs in REGISTRY_ONLY mode
