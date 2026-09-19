"""
LLM-powered claim verification using OpenAI.
Supports both Chat Completions API (gpt-4o, gpt-4.1) and
Responses API (gpt-5.4+).
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional

from .settings import settings

logger = logging.getLogger(__name__)

_client = None
_use_responses_api = False


def _is_responses_api_model(model: str) -> bool:
    """Check if the model uses the new Responses API (gpt-5.x+)."""
    model_lower = model.lower().strip()
    # gpt-5.x models use Responses API
    if re.match(r'^gpt-5', model_lower):
        return True
    # o-series reasoning models also use Responses API
    if re.match(r'^o[1-9]', model_lower):
        return True
    return False


def _get_client():
    """Lazy-initialize OpenAI client."""
    global _client, _use_responses_api
    if _client is None:
        try:
            from openai import AsyncOpenAI
            _client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            _use_responses_api = _is_responses_api_model(settings.LLM_MODEL)
            if _use_responses_api:
                logger.info(f"Using Responses API for model {settings.LLM_MODEL}")
            else:
                logger.info(f"Using Chat Completions API for model {settings.LLM_MODEL}")
        except ImportError:
            logger.warning("openai package not installed; LLM verification disabled")
            return None
        except Exception as e:
            logger.warning(f"Failed to init OpenAI client: {e}")
            return None
    return _client


async def _call_responses_api(client, system_prompt: str, user_prompt: str) -> Optional[str]:
    """Call the OpenAI Responses API (gpt-5.x+)."""
    combined_input = f"{system_prompt}\n\n---\n\n{user_prompt}"
    try:
        response = await client.responses.create(
            model=settings.LLM_MODEL,
            input=combined_input,
        )
        return response.output_text
    except AttributeError:
        # If responses API not available in this SDK version, fall back
        logger.warning("Responses API not available in SDK; falling back to Chat Completions")
        return await _call_chat_completions_api(client, system_prompt, user_prompt)


async def _call_chat_completions_api(client, system_prompt: str, user_prompt: str) -> Optional[str]:
    """Call the OpenAI Chat Completions API (gpt-4o, gpt-4.1, etc.)."""
    response = await client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,   # deterministic: citation verdicts must be reproducible
        seed=7,
        max_tokens=500,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content


async def _call_llm(system_prompt: str, user_prompt: str) -> Optional[str]:
    """Call the appropriate OpenAI API based on model."""
    client = _get_client()
    if not client:
        return None

    if _use_responses_api:
        return await _call_responses_api(client, system_prompt, user_prompt)
    else:
        return await _call_chat_completions_api(client, system_prompt, user_prompt)


async def call_llm_json(system_prompt: str, user_prompt: str, max_tokens: int = 6000) -> Optional[str]:
    """Like _call_llm but for LARGE structured JSON output (e.g. parsing a whole
    reference list). The default _call_llm caps output at 500 tokens, which
    truncates anything bigger than a few items."""
    client = _get_client()
    if not client:
        return None
    try:
        if _use_responses_api:
            resp = await client.responses.create(
                model=settings.LLM_MODEL,
                input=f"{system_prompt}\n\n---\n\n{user_prompt}",
                max_output_tokens=max_tokens,
            )
            return resp.output_text
        resp = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        return resp.choices[0].message.content
    except Exception as e:  # noqa: BLE001
        logger.warning(f"call_llm_json failed: {e}")
        return None


def _parse_json_response(content: str) -> Optional[dict]:
    """Extract JSON from LLM response, handling markdown code blocks."""
    if not content:
        return None
    content = content.strip()
    # Strip markdown code fences if present
    if content.startswith("```"):
        content = re.sub(r'^```(?:json)?\s*', '', content)
        content = re.sub(r'\s*```$', '', content)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # Try to find JSON object in the response
        match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        logger.warning("LLM returned unparseable response")
        return None


async def verify_claim_with_llm(
    claim: str,
    evidence_context: Optional[str] = None,
    scholarly_evidence: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Use LLM to verify a claim against provided evidence.

    Returns dict with:
        verdict: supported | contradicted | unsupported | unknown
        confidence: 0-100
        reasoning: explanation string
        evidence_used: list of evidence snippets that informed the verdict
    """
    if not settings.ENABLE_LLM_VERIFICATION:
        return None

    # Build evidence section
    evidence_text = ""
    if scholarly_evidence:
        evidence_text += "\n\n## Scholarly Evidence:\n"
        for i, ev in enumerate(scholarly_evidence, 1):
            evidence_text += f"\n[{i}] Source: {ev.get('source', 'Unknown')}\n"
            evidence_text += f"    Snippet: {ev.get('snippet', 'No snippet')}\n"
            if ev.get('url'):
                evidence_text += f"    URL: {ev['url']}\n"

    if evidence_context:
        evidence_text += f"\n\n## Additional Context:\n{evidence_context[:2000]}\n"

    system_prompt = """You are a strict, source-grounded academic fact-checker.

You will receive a CLAIM and (optionally) EVIDENCE retrieved from external
registries — Crossref, DataCite, OpenAlex, Unpaywall, Semantic Scholar,
Wikidata, Wikipedia. You must evaluate the claim USING ONLY this retrieved
evidence. Do not draw on facts that are not in the evidence below.

STEP 1 — decide which case you are in:

CASE A: evidence WAS retrieved and bears on the claim. Judge strictly
from that evidence:

  - "supported"     : evidence directly entails the claim's specifics.
  - "contradicted"  : the retrieved evidence — or basic scientific consensus
                      stated or reflected in that evidence — directly
                      conflicts with the claim (wrong year, wrong
                      attribution, opposite finding, retracted source,
                      physically or factually impossible assertion). If the
                      claim and the evidence cannot both be true, the
                      verdict MUST be "contradicted" — never "unsupported"
                      and never "unknown".
  - "unsupported"   : evidence addresses the topic without confirming or
                      conflicting with the specific assertion. Precise
                      numerics with no anchor MUST be at most "unsupported".

  COMPOUND CLAIMS — decompose first: if the claim bundles several atomic facts
  (e.g. "X won the 1921 Nobel in Physics FOR general relativity" = [won the 1921
  Physics prize] + [the reason was general relativity]), judge EACH part:
    • "supported" ONLY if the evidence supports EVERY part.
    • if the evidence CONTRADICTS any one part (e.g. the prize was for the
      photoelectric effect, not general relativity) → "contradicted".
    • if the evidence is SILENT on a checkable part → at most "unsupported".
  A confirmed sub-fact (the prize/year) does NOT make the whole claim supported
  when another part (the reason) is wrong or unverified.

CASE B: evidence is EMPTY or unrelated to the claim. Then decide by the
NATURE of the claim itself:

  - The claim INVERTS or conflicts with widely-documented, textbook,
    non-controversial knowledge (basic physics, geography, famous history;
    e.g. "the Berlin Wall fell in 1991", "X travels faster than light",
    "Marie Curie never won a Nobel", an obviously impossible population
    or date) → verdict MUST be "contradicted", confidence ≤ 70, and the
    reasoning must state the established fact it conflicts with.
    Do NOT use "unsupported" or "unknown" for these.
  - The claim STATES widely-documented, textbook, non-controversial
    knowledge correctly → "supported", confidence ≤ 70, reasoning notes
    it is common established knowledge.
  - The claim makes ANY specific factual assertion (a study, statistic,
    organization, person, date, percentage, finding) that you cannot
    anchor to a source (e.g. "a 2023 study found 73.4%...", "the WHO
    reported that...") → "unsupported". NEVER "supported" on parametric
    memory for these, and NEVER "unknown" — a concrete assertion with no
    evidence is by definition unsupported.
  - "unknown" is reserved for text that is NOT a checkable factual
    assertion at all (opinion, instruction, fragment). If the claim
    asserts something factual, you must pick one of the other three.

The textbook-knowledge branches apply ONLY to widely-documented,
non-controversial facts — not to specialist claims, recent results, or
anything where genuine domain disagreement is plausible.

GUARDS AGAINST FALSE CONTRADICTIONS (apply before choosing "contradicted"):
  - "contradicted" requires the evidence (or established fact) to DIRECTLY
    PROVE THE OPPOSITE of the claim. If you are merely unsure, or the
    evidence is only loosely related, the answer is "unsupported", NOT
    "contradicted".
  - Do NOT contradict a claim just because the cited work was later
    criticized, corrected, partially retracted, controversial, or debated.
    A paper having known flaws (e.g. Reinhart & Rogoff "Growth in a Time of
    Debt") does NOT make a claim about WHERE/WHEN it was published false. A
    correct attribution (right authors, title, journal, DOI) is "supported"
    even if the paper's conclusions were challenged.
  - A statement about a REFERENCE'S STATUS rather than a fact about the world
    — e.g. "the DOI is not a trustworthy registry hit", "this should be
    treated as a registry failure", "the complete DOI is not found" — is NOT
    a factual claim to contradict. Return "unknown" for such reference-status
    commentary; the DOI/URL checker handles registry validity separately.
  - Do NOT contradict on MINOR BIBLIOGRAPHIC VARIATION. A venue, title, author,
    or year that is a near-match, abbreviation, sub-series, journal-vs-issue,
    or partial form of the evidence is "supported", not "contradicted". For
    example "American Economic Review Papers and Proceedings" vs the evidence's
    "American Economic Review" is the SAME venue (Papers & Proceedings is an
    issue of that journal) → "supported". Contradiction requires a SUBSTANTIVE
    factual conflict (wrong paper, wrong finding, wrong decade), not a
    formatting or granularity difference.

Researcher-grade hallucination patterns to actively look for:
  - Fabricated DOIs / arXiv IDs / journals / institutions / ORCIDs
  - Real DOI but the abstract doesn't say what's claimed (the dominant
    research case — see Athaluri et al. 2023)
  - Fabricated precise statistics ("73.4%", "n=12,500", "p<0.001") with no
    resolvable source
  - Ghost authors: "Smith et al." citing a paper that Smith didn't write
  - Snowball: a plausible-sounding cascade where every step depends on a
    previous wrong fact
  - Source amnesia: claims with no anchor to any source

Respond ONLY with valid JSON:
{
    "verdict": "supported|contradicted|unsupported|unknown",
    "confidence": 0-100,
    "reasoning": "Brief explanation grounded in the evidence above.",
    "evidence_used": ["Short quote 1", "Short quote 2"]
}"""

    user_prompt = f"""Evaluate this claim against the provided evidence:

## Claim:
{claim}
{evidence_text}

Respond with JSON only."""

    try:
        content = await _call_llm(system_prompt, user_prompt)
        result = _parse_json_response(content)
        if not result:
            return None

        # Validate verdict
        verdict = result.get("verdict", "unknown").lower()
        if verdict not in {"supported", "contradicted", "unsupported", "unknown"}:
            verdict = "unknown"

        # Validate confidence
        confidence = result.get("confidence", 50)
        if not isinstance(confidence, (int, float)):
            confidence = 50
        confidence = max(0, min(100, int(confidence)))

        return {
            "verdict": verdict,
            "confidence": confidence,
            "reasoning": result.get("reasoning", ""),
            "evidence_used": result.get("evidence_used", []),
        }

    except Exception as e:
        logger.warning(f"LLM verification failed: {e}")
        return None


async def decompose_claim(claim: str) -> List[str]:
    """
    Use LLM to decompose a compound claim into atomic sub-claims.
    E.g., "CRISPR, developed in 2012, has been used in 5000 trials"
    -> ["CRISPR was developed in 2012.", "CRISPR has been used in 5000 trials."]
    """
    if not settings.ENABLE_LLM_VERIFICATION:
        return [claim]

    if _get_client() is None:
        return [claim]

    # Quick heuristic: skip short/simple claims
    if len(claim.split()) < 12 or ',' not in claim:
        return [claim]

    try:
        system_prompt = (
            "You decompose compound sentences into atomic factual claims. "
            "Each sub-claim should be a complete, self-contained sentence. "
            "If the sentence contains only one claim, return it as-is. "
            "Respond with a JSON object: {\"claims\": [\"claim1\", \"claim2\"]}"
        )
        user_prompt = f"Decompose into atomic claims:\n\n\"{claim}\"\n\nRespond with JSON only."

        content = await _call_llm(system_prompt, user_prompt)
        result = _parse_json_response(content)
        if not result:
            return [claim]

        # Handle both {"claims": [...]} and direct [...]
        if isinstance(result, dict):
            sub_claims = result.get("claims") or result.get("sub_claims") or result.get("result") or [claim]
        elif isinstance(result, list):
            sub_claims = result
        else:
            return [claim]

        # Validate
        valid = [s.strip() for s in sub_claims if isinstance(s, str) and len(s.strip()) > 10]
        return valid if valid else [claim]

    except Exception as e:
        logger.debug(f"Claim decomposition failed: {e}")
        return [claim]
