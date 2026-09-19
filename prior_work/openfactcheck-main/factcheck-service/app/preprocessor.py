"""
Text preprocessor for claim extraction.
University-grade filtering: removes meta-text, headers, fragments, and noise.
"""
import re
from typing import List, Set


# Section header keywords
_SECTION_HEADERS = (
    'introduction', 'abstract', 'conclusion', 'methods', 'method',
    'results', 'result', 'discussion', 'references', 'bibliography',
    'acknowledgments', 'acknowledgements', 'appendix', 'appendices',
    'facts', 'background', 'overview', 'summary', 'related work',
    'future work', 'limitations', 'ethics', 'data availability',
    'title', 'keywords', 'funding', 'conflicts of interest',
)

# Meta-statement keywords for filtering non-factual claims
_META_KEYWORDS = {
    'this document', 'this section', 'this paper', 'this article',
    'stress-test', 'stress test', 'pipeline', 'checker', 'verifier',
    'intentionally', 'the goal is', 'section is written', 'written to',
    'should be', 'could be', 'might be', 'will be', 'expected to be',
    'for testing', 'test case', 'example claim', 'to test', 'to demonstrate',
    'evaluate robustness', 'robustness evaluation', 'designed to',
}

# Strong meta indicators (single match = filter, EVEN with a DOI/number present)
_STRONG_META_INDICATORS = [
    'this document', 'this section', 'this paper', 'this article',
    'stress-test', 'stress test', 'section is written', 'written to test',
    'written to demonstrate', 'intentionally incorrect', 'intentionally false',
    'intentional error', 'intentional mistake', 'intentionally wrong',
    'for testing purposes', 'evaluate robustness', 'robustness test',
    'designed to be incorrect', 'should be flagged', 'should be contradicted',
    'fact-checker', 'factchecker', 'fact checker',
    # Commentary about the CHECKING/EXTRACTION process or a reference's
    # registry status — not factual assertions to verify.
    'weak extractor', 'accidentally capture', 'mark the reference as missing',
    'trustworthy registry', 'registry hit', 'registry failure',
    'registry absence', 'syntax validity', 'distinguish between syntax',
    'good stress test', 'stress test for', 'a robust system should',
    'should require extraordinary', 'a good checker should', 'plausible prefix',
    'prefix format', 'doi-like string', 'should not resolve',
]

# Patterns to remove entirely (line-level)
_REMOVE_LINE_PATTERNS = [
    # Section numbers alone: "1.", "1.1", "1.1.2.", "10."
    r'^[\s]*\d+(?:\.\d+)*\.?\s*$',
    # Title/abstract markers (standalone)
    r'^(?:' + '|'.join(_SECTION_HEADERS) + r')\s*:?\s*$',
    # Numbered section headers: "1. Introduction", "2. Methods", "2. Facts"
    r'^\s*\d+(?:\.\d+)*\.?\s+(?:' + '|'.join(_SECTION_HEADERS) + r')\s*$',
    # End markers
    r'^(?:end of document|end of paper|the end)\.?\s*$',
    # Bibliography entries: [1], [2], [10], etc.
    r'^\s*\[\d+\]',
    # Lines starting with DOI only
    r'^(?:doi\s*:|https?://(?:dx\.)?doi\.org/)\S+\s*$',
    # Lines that are ONLY a DOI
    r'^10\.\d{4,}/\S+\s*$',
    # Meta sentences about the document itself
    r'(?:this (?:should be|might be|is expected to be|will be) (?:contradicted|supported|flagged|verified))',
    r'(?:a (?:checker|verifier|system|model) (?:might|should|will|could) (?:label|flag|mark|identify))',
    r'(?:for testing purposes?|test case|example claim)',
    # Page numbers
    r'^(?:page\s+)?\d+\s*(?:of\s+\d+)?\s*$',
    # Figure/table captions markers
    r'^(?:figure|fig\.|table|tab\.)\s*\d+',
    # Empty or whitespace-only
    r'^\s*$',
    # Single word lines that are likely headers (capitalized)
    r'^[A-Z][a-z]+\s*$',
    # Section markers like "Title:" "Abstract:" at start of line
    r'^(?:title|abstract|introduction|conclusion|methods|results|discussion|facts)\s*:\s*',
]

# Compiled patterns
_REMOVE_COMPILED = [re.compile(p, re.IGNORECASE) for p in _REMOVE_LINE_PATTERNS]

# Bibliography block detection
_BIB_START_PATTERN = re.compile(r'^(?:references|bibliography|works cited)\s*:?\s*$', re.IGNORECASE)
_BIB_ENTRY_PATTERN = re.compile(r'^\s*\[\d+\]|\^\d+\.|^\d+\.\s+[A-Z]')

# Common verbs for sentence validation (simple heuristic)
_COMMON_VERBS = {
    'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'has', 'have', 'had', 'having',
    'do', 'does', 'did', 'done',
    'will', 'would', 'shall', 'should', 'may', 'might', 'can', 'could', 'must',
    'shows', 'showed', 'shown', 'show',
    'found', 'finds', 'find',
    'demonstrates', 'demonstrated', 'demonstrate',
    'indicates', 'indicated', 'indicate',
    'suggests', 'suggested', 'suggest',
    'reports', 'reported', 'report',
    'states', 'stated', 'state',
    'claims', 'claimed', 'claim',
    'argues', 'argued', 'argue',
    'proves', 'proved', 'proven', 'prove',
    'discovered', 'discovers', 'discover',
    'observed', 'observes', 'observe',
    'concluded', 'concludes', 'conclude',
    'established', 'establishes', 'establish',
    'confirmed', 'confirms', 'confirm',
    'revealed', 'reveals', 'reveal',
    'contains', 'contained', 'contain',
    'includes', 'included', 'include',
    'provides', 'provided', 'provide',
    'describes', 'described', 'describe',
    'explains', 'explained', 'explain',
    'occurs', 'occurred', 'occur',
    'exists', 'existed', 'exist',
    'remains', 'remained', 'remain',
    'becomes', 'became', 'become',
    'appears', 'appeared', 'appear',
    'seems', 'seemed', 'seem',
    'won', 'wins', 'win',
    'received', 'receives', 'receive',
    'awarded', 'awards', 'award',
    'completed', 'completes', 'complete',
    'built', 'builds', 'build',
    'created', 'creates', 'create',
    'developed', 'develops', 'develop',
    'introduced', 'introduces', 'introduce',
    'published', 'publishes', 'publish',
    'wrote', 'writes', 'write',
    'said', 'says', 'say',
    'made', 'makes', 'make',
    'took', 'takes', 'take',
    'gave', 'gives', 'give',
    'came', 'comes', 'come',
    'went', 'goes', 'go',
    'known', 'knows', 'know',
    'thought', 'thinks', 'think',
    'believed', 'believes', 'believe',
    'considered', 'considers', 'consider',
    'used', 'uses', 'use',
    'called', 'calls', 'call',
    'named', 'names', 'name',
    'located', 'locates', 'locate',
    'measured', 'measures', 'measure',
    'calculated', 'calculates', 'calculate',
    'estimated', 'estimates', 'estimate',
    'tested', 'tests', 'test',
    'analyzed', 'analyzes', 'analyze',
    'studied', 'studies', 'study',
    'examined', 'examines', 'examine',
    'investigated', 'investigates', 'investigate',
    'explored', 'explores', 'explore',
    'proposed', 'proposes', 'propose',
    'hypothesized', 'hypothesizes', 'hypothesize',
    'predicted', 'predicts', 'predict',
    'expected', 'expects', 'expect',
    'assumed', 'assumes', 'assume',
    'required', 'requires', 'require',
    'needed', 'needs', 'need',
    'wanted', 'wants', 'want',
    'allowed', 'allows', 'allow',
    'enabled', 'enables', 'enable',
    'caused', 'causes', 'cause',
    'led', 'leads', 'lead',
    'resulted', 'results', 'result',
    'affected', 'affects', 'affect',
    'influenced', 'influences', 'influence',
    'changed', 'changes', 'change',
    'improved', 'improves', 'improve',
    'increased', 'increases', 'increase',
    'decreased', 'decreases', 'decrease',
    'reduced', 'reduces', 'reduce',
    'achieved', 'achieves', 'achieve',
    'reached', 'reaches', 'reach',
    'obtained', 'obtains', 'obtain',
    'produced', 'produces', 'produce',
    'generated', 'generates', 'generate',
    'formed', 'forms', 'form',
    'consisted', 'consists', 'consist',
    'comprised', 'comprises', 'comprise',
    'represented', 'represents', 'represent',
    'meant', 'means', 'mean',
    'defined', 'defines', 'define',
    'identified', 'identifies', 'identify',
    'recognized', 'recognizes', 'recognize',
    'determined', 'determines', 'determine',
    'decided', 'decides', 'decide',
    'selected', 'selects', 'select',
    'chosen', 'chooses', 'choose',
    'preferred', 'prefers', 'prefer',
    'recommended', 'recommends', 'recommend',
    'supported', 'supports', 'support',
    'helped', 'helps', 'help',
    'served', 'serves', 'serve',
    'worked', 'works', 'work',
    'performed', 'performs', 'perform',
    'operated', 'operates', 'operate',
    'functioned', 'functions', 'function',
    'ran', 'runs', 'run',
    'moved', 'moves', 'move',
    'turned', 'turns', 'turn',
    'returned', 'returns', 'return',
    'passed', 'passes', 'pass',
    'failed', 'fails', 'fail',
    'succeeded', 'succeeds', 'succeed',
    'stopped', 'stops', 'stop',
    'started', 'starts', 'start',
    'began', 'begins', 'begin',
    'ended', 'ends', 'end',
    'continued', 'continues', 'continue',
    'remained', 'remains', 'remain',
    'stayed', 'stays', 'stay',
    'left', 'leaves', 'leave',
    'arrived', 'arrives', 'arrive',
    'entered', 'enters', 'enter',
    'joined', 'joins', 'join',
    'met', 'meets', 'meet',
    'seen', 'sees', 'see',
    'heard', 'hears', 'hear',
    'felt', 'feels', 'feel',
    'lived', 'lives', 'live',
    'died', 'dies', 'die',
    'born',
    'fell', 'falls', 'fall', 'fallen',
    'boils', 'boil', 'boiled', 'boiling',
    'treat', 'treats', 'treated', 'treating',
    'cure', 'cures', 'cured', 'curing',
    'stands', 'stood', 'stand', 'standing',
    'orbits', 'orbited', 'orbit', 'orbiting',
    'revolves', 'revolved', 'revolve', 'revolving',
    'sank', 'sinks', 'sink', 'sunk',
    'strikes', 'struck', 'strike', 'striking',
    'invented', 'invents', 'invent', 'inventing',
    'walked', 'walks', 'walk', 'walking',
    'landed', 'lands', 'land', 'landing',
    'declared', 'declares', 'declare',
    'achieved', 'achieves', 'achieve',
    'solved', 'solves', 'solve',
    'demonstrated', 'demonstrates', 'demonstrate',
}


def _should_remove_line(line: str) -> bool:
    """Check if a line should be removed entirely."""
    line_stripped = line.strip()
    if not line_stripped:
        return True
    for pattern in _REMOVE_COMPILED:
        if pattern.search(line_stripped):
            return True
    return False


def _is_bibliography_section(lines: List[str], start_idx: int) -> bool:
    """Check if we're entering a bibliography section."""
    if start_idx >= len(lines):
        return False
    return bool(_BIB_START_PATTERN.match(lines[start_idx].strip()))


def _remove_bibliography(text: str) -> str:
    """Remove bibliography section from text."""
    lines = text.split('\n')
    result_lines = []
    in_bibliography = False
    
    for i, line in enumerate(lines):
        if _is_bibliography_section(lines, i):
            in_bibliography = True
            continue
        
        if in_bibliography:
            # Check if we've left the bibliography (new major section)
            if line.strip() and not _BIB_ENTRY_PATTERN.match(line.strip()):
                # Check if it looks like a new section header
                if re.match(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s*$', line.strip()):
                    in_bibliography = False
                    result_lines.append(line)
            continue
        
        result_lines.append(line)
    
    return '\n'.join(result_lines)


def _strip_section_artifacts(text: str) -> str:
    """Remove section numbers and headers from text."""
    # Remove section numbers (1-2 digits) at start of text
    text = re.sub(r'^(\d{1,2})\.\s+', '', text)
    # Remove section numbers after sentence endings
    text = re.sub(r'(\.\s+)(\d{1,2})\.\s+(?=[A-Z])', r'\1', text)
    # Remove section header words
    text = re.sub(r'\b(?:Introduction|Abstract|Conclusion|Methods|Results|Discussion|Facts|References|Background|Overview|Summary)\s+(?=[A-Z])', '', text)
    return text


def preprocess_text(text: str) -> str:
    """
    Clean academic text before claim extraction.
    Removes headings, bibliography, meta-text, etc.
    """
    # Remove bibliography section
    text = _remove_bibliography(text)
    
    # Process line by line
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        if not _should_remove_line(line):
            cleaned_lines.append(line)
    
    # Join lines with spaces (not newlines) to form continuous text
    text = ' '.join(cleaned_lines)
    
    # Normalize whitespace first
    text = re.sub(r'\s+', ' ', text)
    
    # Remove section number and header artifacts
    text = _strip_section_artifacts(text)
    
    # Normalize whitespace again
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()


def _tokenize_simple(text: str) -> List[str]:
    """Simple tokenization by whitespace and punctuation."""
    return re.findall(r'\b\w+\b', text.lower())


# Morphological fallback for verbs missing from the whitelist.
# The whitelist alone silently dropped factual claims like
# "Gravitational waves travel faster than light." (travel) and
# "Antarctica's population exceeded 50 million." (exceeded).
# Matches: -ed / -ing inflections, or a plural/3rd-person -s token
# followed by another word (e.g. "waves travel", "boils at").
_VERB_MORPH_RE = re.compile(r'\b\w{2,}(?:ed|ing)\b|\b\w{3,}s\b\s+\w')


def _contains_verb(tokens: List[str]) -> bool:
    """Check if tokens contain at least one verb (whitelist + morphology)."""
    if set(tokens) & _COMMON_VERBS:
        return True
    return bool(_VERB_MORPH_RE.search(' '.join(tokens)))


# ── Generic / process / advice sentence filtering ─────────────────────────
# These are not factual assertions to verify — they are commentary ABOUT
# checking, citations, or the writing process. Examples that must be dropped:
#   "A document may contain valid DOIs."
#   "A strong hallucination checker should parse references carefully."
#   "Some claims are well supported."
#   "The overall lesson is that reference integrity and claim integrity differ."
_PROCESS_PHRASES = (
    'reference integrity', 'claim integrity', 'overall lesson', 'the lesson is',
    'in university writing', 'this is a useful test', 'this is a test',
    'a good test', 'a strong hallucination checker', 'a robust system',
    'a robust checker', 'a good checker', 'a verifier should', 'a checker should',
    'a checker may', 'a writer may', 'a writer might', 'a writer can',
    'can look persuasive', 'need careful wording', 'needs careful wording',
    'need precision', 'are different tasks', 'is a different task',
    'well supported', 'partially supported', 'only partially supported',
    'some claims are', 'some statements are', 'this pattern is common',
    'this briefing', 'this paragraph', 'this is a stress', 'good stress test',
    'a good stress test', 'a useful test of whether', 'should be treated as',
    'should require extraordinary', 'should not be counted', 'should not call',
    'a bad summary might', 'a weak extractor',
    # NOTE: "a false paraphrase/extension/version says that ..." sentences are
    # intentionally NOT filtered — they embed a concrete FALSE claim that must
    # reach the verifier so it can be contradicted (e.g. "gravitational waves
    # travel faster than light").
    # Vague topic / transition sentences (no concrete assertion)
    'create their own', 'their own traps', 'also need', 'needs precision',
    'has the same problem', 'have the same problem', 'is another area',
    'is another example', 'are another example', 'create many opportunities',
    'relies on references', 'rely on references', 'on references that',
    'are especially vulnerable', 'are often especially', 'also need careful',
    'is still important', 'create their own traps', 'need their own',
    'is another clean example', 'provides another', 'have their own',
    'the same problem with', 'all rely on', 'often framed as',
)
_PROCESS_NOUNS = (
    'checker', 'verifier', 'document', 'citation', 'reference', 'references',
    'claim', 'claims', 'source', 'sources', 'sentence', 'statement', 'writer',
    'essay', 'paragraph', 'system', 'model', 'extractor', 'parser', 'briefing',
)
_PROCESS_GENERIC_RE = re.compile(
    r'^(?:a|an|some|many|most|the|this|these|those)\s+\w*\s*(?:' +
    '|'.join(_PROCESS_NOUNS) + r')\b',
    re.IGNORECASE,
)
_PROCESS_MODAL_RE = re.compile(r'\b(?:may|might|can|could|should|would|tends? to|is|are)\b', re.IGNORECASE)
# A "specific anchor" makes a sentence verifiable (and thus NOT generic):
# a DOI, URL, arXiv id, any digit, an ALL-CAPS acronym (NASA/ATLAS/FDA), a
# MID-SENTENCE proper noun, or a multi-word proper noun. A sentence-initial
# capitalized common word ("Vaccine", "Medical", "Climate") is NOT an anchor.
_ANCHOR_RE = re.compile(
    r'10\.\d{4,}/'                                       # DOI
    r'|https?://|arxiv'                                  # URL / arXiv
    r'|\d'                                               # any digit (year/number/%)
    r'|\b[A-Z]{2,}\b'                                    # acronym: NASA, ATLAS, FDA, DOI
    r'|(?<=[a-z,] )[A-Z][a-z]{2,}'                       # proper noun preceded by a lowercase word
    r'|[A-Z][a-z]+\s+(?:and\s+|of\s+|the\s+)?[A-Z][a-z]+'  # multi-word proper noun
)


def _is_generic_process_statement(claim: str) -> bool:
    """True if the sentence is generic/process commentary, not a checkable fact."""
    t = claim.lower()
    for p in _PROCESS_PHRASES:
        if p in t:
            # keep it only if it carries a concrete anchor (DOI/number/entity)
            if not _ANCHOR_RE.search(claim):
                return True
    # "A <process-noun> may/should/can ... " with no concrete anchor
    if _PROCESS_GENERIC_RE.match(t) and _PROCESS_MODAL_RE.search(t):
        if not _ANCHOR_RE.search(claim):
            return True
    return False


# Documents that DISCUSS misinformation wrap a false claim in attribution,
# e.g. "A false extension says that gravitational waves travel faster than
# light." Evaluating that literal sentence yields "supported" (it IS true that
# a false extension says that). Unwrap to the embedded claim so it gets
# verified — and contradicted — on its own merits.
_FALSE_FRAME_RE = re.compile(
    r'^(?:a|an|another|the|this|one)\s+'
    r'(?:false|misleading|incorrect|wrong|bad|suspicious|fabricated|fake|exaggerated)\s+'
    r'(?:\w+\s+){0,4}?'
    r'(?:paraphrase|version|variation|extension|claim|statement|reading|interpretation|summary|story|inference|citation|sentence)'
    r'[^.]*?\b(?:say|says|stated|states|claim|claims|assert|asserts|add|adds|suggest|suggests|report|reports|conclude|concludes)\s+that\s+(.+)$',
    re.IGNORECASE,
)


def _strip_false_attribution(claim: str) -> str:
    """Unwrap "a false X says that Y." → "Y." so the embedded claim is verified."""
    m = _FALSE_FRAME_RE.match(claim.strip())
    if m:
        inner = m.group(1).strip()
        if len(inner.split()) >= 4:
            return inner[0].upper() + inner[1:]
    return claim


def _is_meta_statement(claim: str) -> bool:
    """
    Check if a claim is a meta-statement about the document itself.
    Returns True if claim should be filtered out.
    """
    claim_lower = claim.lower()
    
    # Check strong indicators first (single match = filter)
    for indicator in _STRONG_META_INDICATORS:
        if indicator in claim_lower:
            return True
    
    # Count how many meta keywords appear
    keyword_count = sum(1 for keyword in _META_KEYWORDS if keyword in claim_lower)
    
    # If contains 2+ meta keywords, it's a meta-statement
    if keyword_count >= 2:
        return True
    
    return False


def _is_only_doi_or_url(claim: str) -> bool:
    """Check if claim is only a DOI or URL without proposition."""
    claim_stripped = claim.strip()
    
    # Pure DOI line
    if re.match(r'^(?:doi\s*:?\s*)?10\.\d{4,}/\S+\.?$', claim_stripped, re.IGNORECASE):
        return True
    
    # Pure URL line
    if re.match(r'^https?://\S+\.?$', claim_stripped, re.IGNORECASE):
        return True
    
    # DOI: prefix with just DOI
    if re.match(r'^DOI:\s*10\.\d{4,}/\S+\.?$', claim_stripped, re.IGNORECASE):
        return True
    
    return False


def _is_valid_claim(claim: str) -> bool:
    """
    Check if a claim is a valid, well-formed sentence.
    Returns True if claim should be kept.
    """
    claim = claim.strip()
    
    # Length check - minimum 15 chars (allow short factual claims)
    if len(claim) < 15:
        return False

    # Must end with sentence-ending punctuation — but tolerate a trailing inline
    # citation/DOI/URL ("... cases in 2020. (doi:10.x/y)", "... shown [12]") where
    # the citation displaces the terminal period. Otherwise a true claim with an
    # inline fabricated/real citation gets dropped entirely (so the citation is
    # never checked) — reference integrity must still be testable on the claim.
    # NB: DOIs legitimately contain parentheses (10.1016/S0140-6736(21)00516-X,
    # 10.1111/(ISSN)1468-2850), so match greedily to the FINAL closing bracket.
    _claim_core = re.sub(
        r'\s*[\(\[]\s*(?:doi:|https?://|arxiv:).*[\)\]]\s*$', '', claim, flags=re.IGNORECASE
    ).strip()
    # A sentence that ENDS in a quotation ("... said, 'X is Y.'") or a closing
    # bracket after the period is still a complete sentence — strip trailing
    # closing quotes/brackets before the terminal-punctuation check. Otherwise
    # every quoted/misattributed statement is silently dropped and never verified.
    _claim_core = _claim_core.rstrip('\'"\u2019\u201d)\]').rstrip()
    if not re.search(r'[.!?]$', _claim_core):
        return False

    # Token count check (minimum 3 tokens for short factual claims)
    tokens = _tokenize_simple(claim)
    if len(tokens) < 3:
        return False

    # Must contain a verb
    if not _contains_verb(tokens):
        return False
    
    # Reject meta-statements about the document
    if _is_meta_statement(claim):
        return False

    # Reject generic / process / advice commentary (not a checkable fact)
    if _is_generic_process_statement(claim):
        return False

    # Reject pure DOI/URL lines
    if _is_only_doi_or_url(claim):
        return False
    
    # Reject pure numbering/punctuation
    if re.match(r'^[\d\s.,;:\-–—]+$', claim):
        return False
    
    # Reject section headers that slipped through
    if re.match(r'^\d+(?:\.\d+)*\s+[A-Z]', claim) and len(tokens) < 8:
        return False
    
    # Reject reference-only lines
    if re.match(r'^\[?\d+\]?\s*[A-Z][a-z]+,?\s+[A-Z]', claim) and 'et al' in claim.lower():
        return False
    
    # Reject lines that are just author names
    if re.match(r'^[A-Z][a-z]+(?:\s+[A-Z]\.?)+(?:,\s+[A-Z][a-z]+(?:\s+[A-Z]\.?)+)*\s*$', claim):
        return False
    
    # Reject citation-style entries [1] Author, Title...
    if re.match(r'^\[\d+\]', claim):
        return False
    
    return True


def _normalize_claim(claim: str) -> str:
    """Normalize a claim for comparison/deduplication."""
    # Lowercase, remove extra whitespace, remove punctuation
    normalized = claim.lower().strip()
    normalized = re.sub(r'\s+', ' ', normalized)
    normalized = re.sub(r'[^\w\s]', '', normalized)
    return normalized


def _extract_numbers(text: str) -> Set[str]:
    """Extract all numbers from text for comparison."""
    return set(re.findall(r'\b\d+\b', text))


def filter_claims(claims: List[str]) -> List[str]:
    """
    Post-filter extracted claims.
    Removes invalid claims and deduplicates.
    """
    seen_normalized: Set[str] = set()
    filtered: List[str] = []
    
    for claim in claims:
        claim = claim.strip()

        # Unwrap "a false X says that Y" → "Y" so the embedded claim is verified
        claim = _strip_false_attribution(claim)

        # Validate claim
        if not _is_valid_claim(claim):
            continue
        
        # Deduplicate exact matches
        normalized = _normalize_claim(claim)
        if normalized in seen_normalized:
            continue
        
        # Check for near-duplicates (80% token overlap)
        # BUT don't deduplicate if numbers differ (important for contradiction detection)
        claim_tokens = set(_tokenize_simple(claim))
        claim_numbers = _extract_numbers(claim)
        is_near_duplicate = False
        
        for existing in filtered:
            existing_tokens = set(_tokenize_simple(existing))
            existing_numbers = _extract_numbers(existing)
            
            if claim_tokens and existing_tokens:
                overlap = len(claim_tokens & existing_tokens) / max(len(claim_tokens), len(existing_tokens))
                if overlap > 0.8:
                    # Don't deduplicate if numbers are different
                    # (could be conflicting claims like 1989 vs 1991)
                    if claim_numbers != existing_numbers:
                        continue  # Keep both, numbers differ
                    is_near_duplicate = True
                    break
        
        if is_near_duplicate:
            continue
        
        seen_normalized.add(normalized)
        filtered.append(claim)
    
    return filtered


def split_sentences(text: str) -> List[str]:
    """
    Split text into sentences with preprocessing.
    """
    # Preprocess
    text = preprocess_text(text)
    
    # Handle common abbreviations
    text = re.sub(r'(\b(?:Dr|Mr|Mrs|Ms|Prof|Sr|Jr|vs|etc|al|Fig|Tab|Eq|No|Vol|pp|ed|eds|trans|Rev|St|Mt|Inc|Ltd|Corp|Co))\.\s', r'\1<PERIOD> ', text)
    text = re.sub(r'(\b(?:i\.e|e\.g|cf|viz|et al))\.\s', r'\1<PERIOD> ', text, flags=re.IGNORECASE)
    
    # Split on sentence boundaries
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
    
    # Restore periods and clean up
    sentences = [s.replace('<PERIOD>', '.').strip() for s in sentences]
    
    # Filter
    sentences = filter_claims(sentences)
    
    return sentences
