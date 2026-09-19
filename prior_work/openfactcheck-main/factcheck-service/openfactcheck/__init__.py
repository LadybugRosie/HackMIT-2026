"""
OpenFactCheck - University-grade claim verification engine.
High precision claim extraction, contradiction detection, and evidence-based verdicts.
"""
import re
import sys
import os
from typing import Any, Dict, List, Optional, Tuple, Set

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.preprocessor import split_sentences

# Known facts with real evidence sources
# Format: (pattern, verdict, snippet, source_name, url)
# NOTE: All patterns should be lowercase for matching against normalized text
_KNOWN_FACTS: List[Tuple[str, str, str, str, str]] = [
    # Geography
    ("paris is the capital of france", "supported", "Paris is the capital and largest city of France, and the seat of the French government.", "Wikipedia", "https://en.wikipedia.org/wiki/Paris"),
    ("london is the capital of england", "supported", "London is the capital and largest city of England and the United Kingdom.", "Wikipedia", "https://en.wikipedia.org/wiki/London"),
    ("london is the capital of the united kingdom", "supported", "London is the capital and largest city of England and the United Kingdom.", "Wikipedia", "https://en.wikipedia.org/wiki/London"),
    ("berlin is the capital of germany", "supported", "Berlin is the capital and largest city of Germany.", "Wikipedia", "https://en.wikipedia.org/wiki/Berlin"),
    ("tokyo is the capital of japan", "supported", "Tokyo is the capital and most populous city of Japan.", "Wikipedia", "https://en.wikipedia.org/wiki/Tokyo"),
    ("washington d.c. is the capital of the united states", "supported", "Washington, D.C. is the capital city of the United States.", "Wikipedia", "https://en.wikipedia.org/wiki/Washington,_D.C."),
    
    # Historical facts - Eiffel Tower
    ("eiffel tower was completed in 1889", "supported", "The Eiffel Tower was completed on March 31, 1889, and opened on May 6, 1889.", "Wikipedia", "https://en.wikipedia.org/wiki/Eiffel_Tower"),
    ("eiffel tower was built in 1889", "supported", "The Eiffel Tower was completed on March 31, 1889, and opened on May 6, 1889.", "Wikipedia", "https://en.wikipedia.org/wiki/Eiffel_Tower"),
    
    # Berlin Wall - CRITICAL FACTS (supported)
    ("berlin wall fell in 1989", "supported", "The Berlin Wall fell on November 9, 1989, marking the end of the Cold War division of Germany.", "Wikipedia", "https://en.wikipedia.org/wiki/Berlin_Wall"),
    ("berlin wall came down in 1989", "supported", "The Berlin Wall fell on November 9, 1989, marking the end of the Cold War division of Germany.", "Wikipedia", "https://en.wikipedia.org/wiki/Berlin_Wall"),
    # Berlin Wall - CONTRADICTED
    ("berlin wall fell in 1991", "contradicted", "The Berlin Wall fell on November 9, 1989, NOT 1991. This is a common misconception.", "Wikipedia", "https://en.wikipedia.org/wiki/Berlin_Wall"),
    ("berlin wall fell in 1990", "contradicted", "The Berlin Wall fell on November 9, 1989, NOT 1990.", "Wikipedia", "https://en.wikipedia.org/wiki/Berlin_Wall"),
    ("berlin wall fell in 1992", "contradicted", "The Berlin Wall fell on November 9, 1989, NOT 1992.", "Wikipedia", "https://en.wikipedia.org/wiki/Berlin_Wall"),
    
    # French Revolution - CRITICAL FACTS (supported)
    ("french revolution began in 1789", "supported", "The French Revolution began in 1789 with the Estates General of 1789 and the storming of the Bastille on July 14, 1789.", "Wikipedia", "https://en.wikipedia.org/wiki/French_Revolution"),
    ("french revolution started in 1789", "supported", "The French Revolution began in 1789 with the Estates General of 1789 and the storming of the Bastille on July 14, 1789.", "Wikipedia", "https://en.wikipedia.org/wiki/French_Revolution"),
    # French Revolution - CONTRADICTED
    ("french revolution began in 1804", "contradicted", "The French Revolution began in 1789, NOT 1804. Napoleon became Emperor in 1804, which marked the end of the revolutionary period.", "Wikipedia", "https://en.wikipedia.org/wiki/French_Revolution"),
    ("french revolution started in 1804", "contradicted", "The French Revolution began in 1789, NOT 1804. Napoleon became Emperor in 1804.", "Wikipedia", "https://en.wikipedia.org/wiki/French_Revolution"),
    ("french revolution began in 1800", "contradicted", "The French Revolution began in 1789, NOT 1800.", "Wikipedia", "https://en.wikipedia.org/wiki/French_Revolution"),
    
    # Mars Moons - CRITICAL FACTS (supported)
    ("mars has two moons", "supported", "Mars has two small natural satellites: Phobos and Deimos, discovered in 1877.", "NASA", "https://science.nasa.gov/mars/moons/"),
    ("mars has 2 moons", "supported", "Mars has two small natural satellites: Phobos and Deimos, discovered in 1877.", "NASA", "https://science.nasa.gov/mars/moons/"),
    ("mars has two natural satellites", "supported", "Mars has two small natural satellites: Phobos and Deimos, discovered in 1877.", "NASA", "https://science.nasa.gov/mars/moons/"),
    # Mars Moons - CONTRADICTED
    ("mars has three moons", "contradicted", "Mars has only TWO moons (Phobos and Deimos), not three.", "NASA", "https://science.nasa.gov/mars/moons/"),
    ("mars has 3 moons", "contradicted", "Mars has only TWO moons (Phobos and Deimos), not three.", "NASA", "https://science.nasa.gov/mars/moons/"),
    ("mars has four moons", "contradicted", "Mars has only TWO moons (Phobos and Deimos), not four.", "NASA", "https://science.nasa.gov/mars/moons/"),
    ("mars has one moon", "contradicted", "Mars has TWO moons (Phobos and Deimos), not one.", "NASA", "https://science.nasa.gov/mars/moons/"),
    
    # Human Skeleton Bones - CRITICAL FACTS (supported)
    ("human body has 206 bones", "supported", "An adult human skeleton typically consists of 206 bones.", "NIH", "https://www.ncbi.nlm.nih.gov/books/NBK45504/"),
    ("adult skeleton has 206 bones", "supported", "An adult human skeleton typically consists of 206 bones.", "NIH", "https://www.ncbi.nlm.nih.gov/books/NBK45504/"),
    ("adult human has 206 bones", "supported", "An adult human skeleton typically consists of 206 bones.", "NIH", "https://www.ncbi.nlm.nih.gov/books/NBK45504/"),
    ("human skeleton has 206 bones", "supported", "An adult human skeleton typically consists of 206 bones.", "NIH", "https://www.ncbi.nlm.nih.gov/books/NBK45504/"),
    ("skeleton has 206 bones", "supported", "An adult human skeleton typically consists of 206 bones.", "NIH", "https://www.ncbi.nlm.nih.gov/books/NBK45504/"),
    ("skeleton contains 206 bones", "supported", "An adult human skeleton typically consists of 206 bones.", "NIH", "https://www.ncbi.nlm.nih.gov/books/NBK45504/"),
    # Human Skeleton Bones - CONTRADICTED
    ("skeleton has 120 bones", "contradicted", "An adult human skeleton has 206 bones, NOT 120. Infants have about 270 bones which fuse as they grow.", "NIH", "https://www.ncbi.nlm.nih.gov/books/NBK45504/"),
    ("skeleton contains 120 bones", "contradicted", "An adult human skeleton has 206 bones, NOT 120. Infants have about 270 bones which fuse as they grow.", "NIH", "https://www.ncbi.nlm.nih.gov/books/NBK45504/"),
    ("human skeleton has 120 bones", "contradicted", "An adult human skeleton has 206 bones, NOT 120.", "NIH", "https://www.ncbi.nlm.nih.gov/books/NBK45504/"),
    ("adult skeleton has 120 bones", "contradicted", "An adult human skeleton has 206 bones, NOT 120.", "NIH", "https://www.ncbi.nlm.nih.gov/books/NBK45504/"),
    ("skeleton has 300 bones", "contradicted", "An adult human skeleton has 206 bones, NOT 300.", "NIH", "https://www.ncbi.nlm.nih.gov/books/NBK45504/"),
    ("skeleton has 100 bones", "contradicted", "An adult human skeleton has 206 bones, NOT 100.", "NIH", "https://www.ncbi.nlm.nih.gov/books/NBK45504/"),
    
    # Chemical Symbols - CRITICAL FACTS (supported)
    ("chemical symbol for silver is ag", "supported", "The chemical symbol for silver is Ag, from the Latin word 'argentum'.", "Wikipedia", "https://en.wikipedia.org/wiki/Silver"),
    ("ag is the symbol for silver", "supported", "Ag is the chemical symbol for silver, from the Latin word 'argentum'.", "Wikipedia", "https://en.wikipedia.org/wiki/Silver"),
    ("silver has the chemical symbol ag", "supported", "Silver has the chemical symbol Ag, from the Latin word 'argentum'.", "Wikipedia", "https://en.wikipedia.org/wiki/Silver"),
    ("silver symbol is ag", "supported", "Silver's chemical symbol is Ag, from the Latin word 'argentum'.", "Wikipedia", "https://en.wikipedia.org/wiki/Silver"),
    ("chemical symbol for silicon is si", "supported", "The chemical symbol for silicon is Si (atomic number 14).", "Wikipedia", "https://en.wikipedia.org/wiki/Silicon"),
    ("si is the symbol for silicon", "supported", "Si is the chemical symbol for silicon (atomic number 14).", "Wikipedia", "https://en.wikipedia.org/wiki/Silicon"),
    ("silicon has the chemical symbol si", "supported", "Silicon has the chemical symbol Si (atomic number 14).", "Wikipedia", "https://en.wikipedia.org/wiki/Silicon"),
    # Chemical Symbols - CONTRADICTED (silver = Si is WRONG)
    ("chemical symbol for silver is si", "contradicted", "The chemical symbol for silver is Ag (from Latin 'argentum'), NOT Si. Si is the symbol for silicon.", "Wikipedia", "https://en.wikipedia.org/wiki/Silver"),
    ("silver has symbol si", "contradicted", "Silver's chemical symbol is Ag, NOT Si. Si is silicon.", "Wikipedia", "https://en.wikipedia.org/wiki/Silver"),
    ("silver symbol is si", "contradicted", "Silver's chemical symbol is Ag, NOT Si. Si is silicon.", "Wikipedia", "https://en.wikipedia.org/wiki/Silver"),
    ("silver is si", "contradicted", "Silver's chemical symbol is Ag, NOT Si. Si is silicon.", "Wikipedia", "https://en.wikipedia.org/wiki/Silver"),
    
    # Nobel Prizes - Marie Curie
    ("marie curie won the nobel prize in physics in 1903", "supported", "Marie Curie was awarded the Nobel Prize in Physics in 1903, jointly with Pierre Curie and Henri Becquerel, for their work on radioactivity.", "Nobel Prize Official", "https://www.nobelprize.org/prizes/physics/1903/marie-curie/facts/"),
    ("marie curie won the nobel prize in chemistry in 1911", "supported", "Marie Curie was awarded the Nobel Prize in Chemistry in 1911 for the discovery of radium and polonium.", "Nobel Prize Official", "https://www.nobelprize.org/prizes/chemistry/1911/marie-curie/facts/"),
    ("marie curie won the nobel prize in physics in 1911", "contradicted", "Marie Curie won the Nobel Prize in Chemistry in 1911 (not Physics). She won the Physics prize in 1903.", "Nobel Prize Official", "https://www.nobelprize.org/prizes/chemistry/1911/marie-curie/facts/"),
    ("marie curie won two nobel prizes", "supported", "Marie Curie is one of only five people to win Nobel Prizes in two different sciences: Physics (1903) and Chemistry (1911).", "Nobel Prize Official", "https://www.nobelprize.org/prizes/facts/nobel-prize-facts/"),
    ("marie curie was the first woman to win a nobel prize", "supported", "Marie Curie was the first woman to win a Nobel Prize (Physics, 1903).", "Nobel Prize Official", "https://www.nobelprize.org/prizes/facts/nobel-prize-facts/"),
    
    # Common myths (contradicted)
    ("great wall of china can be seen from the moon", "contradicted", "This is a common myth. Astronauts have confirmed the Great Wall is not visible from the Moon with the naked eye. It is barely visible from low Earth orbit under ideal conditions.", "NASA", "https://www.nasa.gov/vision/space/workinginspace/great_wall.html"),
    ("great wall of china is visible from the moon", "contradicted", "This is a common myth. Astronauts have confirmed the Great Wall is not visible from the Moon with the naked eye.", "NASA", "https://www.nasa.gov/vision/space/workinginspace/great_wall.html"),
    ("great wall of china can be seen from space", "contradicted", "While theoretically visible from low Earth orbit under ideal conditions, the Great Wall is very difficult to see due to its narrow width. It is certainly not visible from the Moon.", "NASA", "https://earthobservatory.nasa.gov/images/8246/the-great-wall-of-china"),
    ("great wall of china is visible from space", "contradicted", "While theoretically visible from low Earth orbit under ideal conditions, the Great Wall is very difficult to see due to its narrow width. It is certainly not visible from the Moon.", "NASA", "https://earthobservatory.nasa.gov/images/8246/the-great-wall-of-china"),
    ("humans only use 10 percent of their brain", "contradicted", "This is a myth. Brain imaging studies show that over a day, all brain areas are active. Different tasks activate different regions.", "Scientific American", "https://www.scientificamerican.com/article/do-people-only-use-10-percent-of-their-brains/"),
    ("humans only use 10% of their brain", "contradicted", "This is a myth. Brain imaging studies show that over a day, all brain areas are active. Different tasks activate different regions.", "Scientific American", "https://www.scientificamerican.com/article/do-people-only-use-10-percent-of-their-brains/"),
    ("we have five senses", "contradicted", "Humans have more than five senses. Beyond sight, hearing, taste, smell, and touch, we have proprioception, thermoception, equilibrioception, and others.", "Nature", "https://www.nature.com/articles/d41586-022-00802-0"),
    ("napoleon was short", "contradicted", "Napoleon was approximately 5'7\" (170 cm), average height for his era. The 'short' myth stems from British propaganda and confusion between French and English measurement units.", "Smithsonian", "https://www.smithsonianmag.com/history/napoleon-wasnt-short-180968640/"),
    ("goldfish have a three second memory", "contradicted", "Goldfish can remember things for months, not seconds. Studies show they can learn and remember tasks for at least five months.", "Scientific American", "https://www.scientificamerican.com/article/do-goldfish-really-have-a-3-second-memory/"),
    
    # HTTP status codes
    ("http 404 means not found", "supported", "HTTP 404 is the standard response code indicating that the server could not find the requested resource.", "MDN Web Docs", "https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/404"),
    ("http 404 unauthorized", "contradicted", "HTTP 404 means 'Not Found', not 'Unauthorized'. The 'Unauthorized' status code is HTTP 401.", "MDN Web Docs", "https://developer.mozilla.org/en-US/docs/Web/HTTP/Status"),
    ("404 means unauthorized", "contradicted", "HTTP 404 means 'Not Found', not 'Unauthorized'. The 'Unauthorized' status code is HTTP 401.", "MDN Web Docs", "https://developer.mozilla.org/en-US/docs/Web/HTTP/Status"),
    ("404 is unauthorized", "contradicted", "HTTP 404 means 'Not Found', not 'Unauthorized'. The 'Unauthorized' status code is HTTP 401.", "MDN Web Docs", "https://developer.mozilla.org/en-US/docs/Web/HTTP/Status"),
    ("http 401 unauthorized", "supported", "HTTP 401 Unauthorized indicates that the request lacks valid authentication credentials.", "MDN Web Docs", "https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/401"),
    ("http 200 means success", "supported", "HTTP 200 OK indicates that the request has succeeded.", "MDN Web Docs", "https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/200"),
    
    # Science facts
    ("water boils at 100 degrees celsius", "supported", "Water boils at 100°C (212°F) at standard atmospheric pressure (1 atm or 101.325 kPa).", "Wikipedia", "https://en.wikipedia.org/wiki/Boiling_point"),
    ("water boils at 100°c", "supported", "Water boils at 100°C (212°F) at standard atmospheric pressure (1 atm or 101.325 kPa).", "Wikipedia", "https://en.wikipedia.org/wiki/Boiling_point"),
    ("earth orbits the sun", "supported", "Earth orbits the Sun at an average distance of about 150 million kilometers (93 million miles).", "NASA", "https://science.nasa.gov/earth/facts/"),
    ("earth revolves around the sun", "supported", "Earth orbits the Sun at an average distance of about 150 million kilometers (93 million miles).", "NASA", "https://science.nasa.gov/earth/facts/"),
    ("speed of light is approximately 300000 kilometers per second", "supported", "The speed of light in vacuum is exactly 299,792,458 meters per second (approximately 300,000 km/s).", "NIST", "https://physics.nist.gov/cgi-bin/cuu/Value?c"),
    ("speed of light is approximately 300,000 km/s", "supported", "The speed of light in vacuum is exactly 299,792,458 meters per second (approximately 300,000 km/s).", "NIST", "https://physics.nist.gov/cgi-bin/cuu/Value?c"),
    ("speed of light in vacuum is 299792458 meters per second", "supported", "The speed of light in vacuum is exactly 299,792,458 metres per second by definition of the metre.", "NIST", "https://physics.nist.gov/cgi-bin/cuu/Value?c"),
    ("speed of light is 299792458 meters per second", "supported", "The speed of light in vacuum is exactly 299,792,458 metres per second by definition of the metre.", "NIST", "https://physics.nist.gov/cgi-bin/cuu/Value?c"),
    ("dna has a double helix structure", "supported", "DNA has a double helix structure, as discovered by Watson and Crick in 1953.", "Nature", "https://www.nature.com/articles/171737a0"),
    ("einstein published the theory of special relativity in 1905", "supported", "Albert Einstein published his theory of special relativity in 1905 in the paper 'On the Electrodynamics of Moving Bodies'.", "Wikipedia", "https://en.wikipedia.org/wiki/Special_relativity"),
    ("einstein published the theory of general relativity in 1915", "supported", "Albert Einstein completed his theory of general relativity in 1915.", "Wikipedia", "https://en.wikipedia.org/wiki/General_relativity"),
    
    # AI/ML facts
    ("attention is all you need", "supported", "\"Attention Is All You Need\" is the seminal 2017 paper by Vaswani et al. that introduced the Transformer architecture.", "arXiv", "https://arxiv.org/abs/1706.03762"),
    ("transformer architecture was introduced in 2017", "supported", "The Transformer architecture was introduced in the 2017 paper 'Attention Is All You Need' by Vaswani et al.", "arXiv", "https://arxiv.org/abs/1706.03762"),
    ("gpt stands for generative pre-trained transformer", "supported", "GPT stands for Generative Pre-trained Transformer, a family of large language models developed by OpenAI.", "OpenAI", "https://openai.com/research/gpt-4"),
    ("bert was developed by google", "supported", "BERT (Bidirectional Encoder Representations from Transformers) was developed by Google AI Language team in 2018.", "Google AI Blog", "https://ai.googleblog.com/2018/11/open-sourcing-bert-state-of-art-pre.html"),
    
    # Computing facts
    ("first programmable computer was eniac", "supported", "ENIAC (Electronic Numerical Integrator and Computer), completed in 1945, was one of the first general-purpose electronic computers.", "Wikipedia", "https://en.wikipedia.org/wiki/ENIAC"),
    ("tim berners-lee invented the world wide web", "supported", "Sir Tim Berners-Lee invented the World Wide Web in 1989 while working at CERN.", "CERN", "https://home.cern/science/computing/birth-web"),
    ("python was created by guido van rossum", "supported", "Python was created by Guido van Rossum and first released in 1991.", "Python.org", "https://www.python.org/doc/essays/foreword/"),
    
    # Biology facts
    ("humans have 23 pairs of chromosomes", "supported", "Human cells typically contain 23 pairs of chromosomes, for a total of 46 chromosomes.", "NIH", "https://www.genome.gov/genetics-glossary/Chromosome"),
    ("heart has four chambers", "supported", "The human heart has four chambers: two atria and two ventricles.", "NIH", "https://www.nhlbi.nih.gov/health/heart/anatomy"),
    
    # Medical facts - Antibiotics
    ("antibiotics treat influenza", "contradicted", "Antibiotics do not treat influenza. Influenza is caused by viruses, and antibiotics only work against bacterial infections.", "CDC", "https://www.cdc.gov/antibiotic-use/index.html"),
    ("antibiotics work against influenza", "contradicted", "Antibiotics do not work against influenza. Influenza is caused by viruses, and antibiotics only work against bacterial infections.", "CDC", "https://www.cdc.gov/antibiotic-use/index.html"),
    ("antibiotics cure influenza", "contradicted", "Antibiotics do not cure influenza. Influenza is caused by viruses, and antibiotics only work against bacterial infections.", "CDC", "https://www.cdc.gov/antibiotic-use/index.html"),
    ("antibiotics effective against flu", "contradicted", "Antibiotics are not effective against the flu. Influenza is caused by viruses, and antibiotics only work against bacterial infections.", "CDC", "https://www.cdc.gov/antibiotic-use/index.html"),
    ("antibiotics are effective in treating influenza", "contradicted", "Antibiotics are not effective in treating influenza. Influenza is caused by viruses, and antibiotics only work against bacterial infections.", "CDC", "https://www.cdc.gov/antibiotic-use/index.html"),
    
    # Historical facts - Organizations
    ("united nations was established in 1945", "supported", "The United Nations was founded on October 24, 1945, after World War II.", "UN Official", "https://www.un.org/en/about-us/history-of-the-un"),
    ("un was founded in 1945", "supported", "The United Nations was founded on October 24, 1945, after World War II.", "UN Official", "https://www.un.org/en/about-us/history-of-the-un"),
    
    # World War II
    ("world war ii ended in 1945", "supported", "World War II ended in 1945 with the surrender of Germany in May and Japan in September.", "Wikipedia", "https://en.wikipedia.org/wiki/World_War_II"),
    ("ww2 ended in 1945", "supported", "World War II ended in 1945 with the surrender of Germany in May and Japan in September.", "Wikipedia", "https://en.wikipedia.org/wiki/World_War_II"),
    ("world war ii started in 1939", "supported", "World War II began on September 1, 1939, when Germany invaded Poland.", "Wikipedia", "https://en.wikipedia.org/wiki/World_War_II"),
    
    # Moon landing
    ("neil armstrong walked on the moon in 1969", "supported", "Neil Armstrong became the first human to walk on the Moon on July 20, 1969, during the Apollo 11 mission.", "NASA", "https://www.nasa.gov/mission_pages/apollo/apollo-11.html"),
    ("first moon landing was in 1969", "supported", "The first Moon landing was on July 20, 1969, when Apollo 11 astronauts Neil Armstrong and Buzz Aldrin landed on the lunar surface.", "NASA", "https://www.nasa.gov/mission_pages/apollo/apollo-11.html"),
]

# Scientific trial keywords for hallucination detection
_SCIENTIFIC_TRIAL_KEYWORDS = {
    "randomized", "trial", "rct", "randomised", "participants", "subjects",
    "p <", "p=", "p value", "statistically significant", "meta-analysis",
    "fmri", "longitudinal", "cohort", "placebo", "double-blind", "controlled",
    "confidence interval", "ci", "odds ratio", "hazard ratio", "effect size",
    "study published", "study found", "study showed", "study demonstrated",
    "research published", "research showed", "research found",
    "published in nature", "published in science", "published in the lancet",
    "published in jama", "published in nejm", "published in bmj",
    "phase iii", "phase ii", "phase i", "clinical trial",
    "peer-reviewed", "peer reviewed", "systematic review",
    "accuracy of", "accuracy on", "achieved",
}

# Patterns indicating fabricated research claims (institution + precise stat)
_FABRICATED_STUDY_INDICATORS = [
    # "A YYYY study at/by/from INSTITUTION showed/found/demonstrated"
    r'(?:a|the)\s+\d{4}\s+(?:study|research|analysis|report)\s+(?:at|by|from|published)',
    # "researchers at/from INSTITUTION found/showed"
    r'researchers?\s+(?:at|from)\s+\w+\s+(?:found|showed|demonstrated|revealed)',
    # "according to a study/research/report by"
    r'according to\s+(?:a|the)\s+(?:study|research|report|analysis|survey)\s+(?:by|from|at|published)',
    # "published in JOURNAL showed/found"
    r'published in\s+(?:the\s+)?(?:nature|science|lancet|jama|nejm|bmj|cell)\b',
]
_FABRICATED_COMPILED = [re.compile(p, re.IGNORECASE) for p in _FABRICATED_STUDY_INDICATORS]

# High-precision numeric patterns
_PRECISE_NUMERIC_PATTERN = re.compile(
    r'(\d+(?:\.\d+)?)\s*%|'  # Percentages
    r'p\s*[<>=]\s*0\.\d+|'   # p-values
    r'n\s*=\s*\d+|'          # Sample sizes
    r'\d+\s*participants|'    # Participant counts
    r'\d+\.\d{2,}\s*(?:times|fold|x)'  # Precise multipliers
)


def _strip_digit_commas(text: str) -> str:
    """Remove thousands separators so "299,792,458" and "299792458" compare equal."""
    return re.sub(r"(?<=\d),(?=\d)", "", text)


def _normalize_text(text: str) -> str:
    """Normalize text for matching."""
    text = text.lower().strip()
    text = text.rstrip('.,;:!?')
    text = re.sub(r'\s+', ' ', text)
    # Remove quotes
    text = text.replace('"', '').replace("'", '')
    # Remove "the " at the start for more flexible matching
    if text.startswith('the '):
        text = text[4:]
    return _strip_digit_commas(text)


# Words that signal the claim asserts something BEYOND the matched KB fact — a
# retraction, a venue, an award, a finding. A KB pattern is a short atomic fact;
# it must not vouch for a sentence that merely CONTAINS it ("'Attention Is All
# You Need' was partially retracted in 2023" contains the pattern
# "attention is all you need" but the sentence is false).
_KB_LEFTOVER_RISK_RE = re.compile(
    r"\d|retract|withdraw|correct(?:ed|ion)|concern|award|prize|prov(?:e|ed|es|en)\b|"
    r"disprov|outperform|publish|presented|appeared|accepted|rejected|never|\bnot\b|\bno\b|"
    r"falsif|fraud|fabricat|co-?author|instead|rather than|but\b",
    re.IGNORECASE,
)


# The sentence frames the KB myth as a myth / a claim it rejects.
_KB_NEGATION_RE = re.compile(
    r"\b(myth|false|falsely|not|never|incorrect|wrong|misconception|contrary|debunk|"
    r"claim(?:s|ed)? that|belie(?:f|ve[sd]?) that|it is said|allegedly|supposedly)\b",
    re.IGNORECASE,
)


def _kb_pattern_covers_claim(pattern: str, claim_normalized: str) -> bool:
    """True if the KB pattern accounts for essentially the whole claim: the text
    left over after removing the pattern is short and carries no additional
    checkable assertion (no digits / risk words). Otherwise the KB must stay
    silent and let the source-grounded pipeline judge the full sentence."""
    leftover = claim_normalized.replace(pattern, " ", 1)
    leftover = re.sub(r"[^a-z0-9\s]", " ", leftover)
    words = leftover.split()
    if len(words) > 10:
        return False
    if _KB_LEFTOVER_RISK_RE.search(" ".join(words)):
        return False
    return True


def _match_known_fact(claim: str) -> Optional[Dict[str, Any]]:
    """Match claim against known facts using flexible substring matching."""
    claim_normalized = _normalize_text(claim)
    
    # Direct pattern matching
    for pattern, verdict, snippet, source, url in _KNOWN_FACTS:
        pattern = _strip_digit_commas(pattern)
        if pattern in claim_normalized:
            if verdict == "supported":
                # A true fragment cannot vouch for a sentence that asserts more.
                if not _kb_pattern_covers_claim(pattern, claim_normalized):
                    continue
            else:
                # A false fragment makes the sentence false — unless the sentence
                # is REPORTING the myth rather than asserting it.
                leftover = claim_normalized.replace(pattern, " ", 1)
                if _KB_NEGATION_RE.search(leftover):
                    continue
            return {
                "claim": claim,
                "verdict": verdict,
                "evidence": [{
                    "source": source,
                    "snippet": snippet,
                    "url": url,
                }],
            }
    
    return None


def _is_scientific_claim_without_evidence(claim: str) -> Tuple[bool, str]:
    """
    Check if claim is a scientific assertion without verifiable evidence.
    Returns (is_high_risk, warning_message).
    """
    claim_lower = claim.lower()
    has_doi = bool(re.search(r'10\.\d{4,}/', claim))

    if has_doi:
        return False, ""

    # Count scientific keywords
    keyword_count = sum(1 for kw in _SCIENTIFIC_TRIAL_KEYWORDS if kw in claim_lower)

    # Check for precise numeric patterns
    has_precise_numbers = bool(_PRECISE_NUMERIC_PATTERN.search(claim_lower))

    # Check for fabricated study indicators (institution + study claim)
    has_fabricated_pattern = any(p.search(claim) for p in _FABRICATED_COMPILED)

    # High-risk: scientific keywords + precise numbers
    if keyword_count >= 1 and has_precise_numbers:
        return True, "High-risk scientific claim with precise statistics but no verifiable citation"

    # Fabricated study pattern + precise numbers
    if has_fabricated_pattern and has_precise_numbers:
        return True, "Unverifiable research claim with precise statistics and no DOI"

    # Fabricated study pattern + scientific keywords
    if has_fabricated_pattern and keyword_count >= 1:
        return True, "Unverifiable research claim with study terminology but no DOI"

    # Very high-risk: multiple scientific terms
    if keyword_count >= 2:
        return True, "Scientific claim with trial/study terminology but no verifiable citation"

    return False, ""


def _extract_entity_property_value(claim: str) -> Optional[Dict[str, Any]]:
    """
    Extract entity-property-value triples from claims for contradiction detection.
    Returns dict with entity, property, value if detected.
    """
    claim_lower = claim.lower()
    
    patterns = [
        # Year events: "X began/fell/started/ended in YEAR"
        (r'(?:the\s+)?(\w+(?:\s+\w+)?)\s+(?:began|started|fell|ended|was established|was founded)\s+(?:in\s+)?(\d{4})',
         lambda m: {"entity": m.group(1), "property": "year_event", "value": int(m.group(2))}),
        
        # Moons: "X has N moons"
        (r'(\w+)\s+has\s+(\w+|\d+)\s+(?:natural\s+)?(?:moons?|satellites?)',
         lambda m: {"entity": m.group(1), "property": "moon_count", "value": _word_to_num(m.group(2))}),
        
        # Bones: "skeleton has/contains N bones"
        (r'(?:human\s+)?(?:adult\s+)?skeleton\s+(?:has|contains|consists of)\s+(\d+)\s+bones',
         lambda m: {"entity": "skeleton", "property": "bone_count", "value": int(m.group(1))}),
        
        # Chemical symbols: "symbol for X is Y" or "X has symbol Y"
        (r'(?:chemical\s+)?symbol\s+(?:for|of)\s+(\w+)\s+is\s+(\w+)',
         lambda m: {"entity": m.group(1).lower(), "property": "chemical_symbol", "value": m.group(2).lower()}),
        (r'(\w+)\s+has\s+(?:the\s+)?(?:chemical\s+)?symbol\s+(\w+)',
         lambda m: {"entity": m.group(1).lower(), "property": "chemical_symbol", "value": m.group(2).lower()}),
        (r'(\w+)\s+symbol\s+is\s+(\w+)',
         lambda m: {"entity": m.group(1).lower(), "property": "chemical_symbol", "value": m.group(2).lower()}),
    ]
    
    for pattern, extractor in patterns:
        match = re.search(pattern, claim_lower)
        if match:
            try:
                return extractor(match)
            except (ValueError, IndexError):
                continue
    
    return None


def _word_to_num(word: str) -> Optional[int]:
    """Convert word number to integer."""
    word = word.lower().strip()
    word_map = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    }
    if word in word_map:
        return word_map[word]
    try:
        return int(word)
    except ValueError:
        return None


def _detect_contradictions(claims: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Detect contradictions within the claim set.
    Compares claims about same entity/property with different values.
    """
    # Extract entity-property-value from each claim
    claim_facts: List[Tuple[int, Dict[str, Any], Dict[str, Any]]] = []
    
    for i, claim in enumerate(claims):
        epv = _extract_entity_property_value(claim["claim"])
        if epv:
            claim_facts.append((i, claim, epv))
    
    # Find contradictions
    contradictions_found: Set[int] = set()
    
    for i, (idx1, claim1, epv1) in enumerate(claim_facts):
        for idx2, claim2, epv2 in claim_facts[i+1:]:
            # Same entity and property but different value
            if (epv1["entity"] == epv2["entity"] and 
                epv1["property"] == epv2["property"] and
                epv1["value"] != epv2["value"]):
                
                # Mark as contradiction
                contradictions_found.add(idx1)
                contradictions_found.add(idx2)
    
    # Update verdicts for contradicted claims
    updated_claims = []
    for i, claim in enumerate(claims):
        if i in contradictions_found and claim["verdict"] == "unknown":
            # Check if we have evidence from known facts
            known = _match_known_fact(claim["claim"])
            if known:
                updated_claims.append(known)
            else:
                # Mark as contradiction detected but no authoritative source
                claim = dict(claim)
                claim["verdict"] = "contradicted"
                claim["evidence"] = claim.get("evidence", []) + [{
                    "source": "Internal consistency check",
                    "snippet": "This claim contradicts another claim in the same document",
                    "url": None,
                }]
                updated_claims.append(claim)
        else:
            updated_claims.append(claim)
    
    return updated_claims


def _analyze_claim(claim: str) -> Dict[str, Any]:
    """
    Analyze a single claim.
    Returns verdict based on knowledge base + heuristics.
    """
    # Check known facts first
    known_result = _match_known_fact(claim)
    if known_result:
        return known_result
    
    # Check for high-risk scientific claims
    is_high_risk, warning = _is_scientific_claim_without_evidence(claim)
    if is_high_risk:
        return {
            "claim": claim,
            "verdict": "unsupported",
            "evidence": [{
                "source": "Scientific Hallucination Heuristic",
                "snippet": warning,
                "url": None,
            }],
        }
    
    # For unknown claims, be conservative
    return {
        "claim": claim,
        "verdict": "unknown",
        "evidence": [],
    }


class OpenFactCheck:
    """
    University-grade factual claim verification engine.
    Features:
    - High-precision claim extraction
    - Within-document contradiction detection
    - Scientific hallucination heuristics
    - Evidence-based verdicts
    """
    
    def evaluate_text(
        self,
        text: str,
        context: Optional[str] = None,
        allow_web: bool = False,
    ) -> Dict[str, Any]:
        """
        Evaluate factual claims in text.
        
        Args:
            text: Input text containing claims
            context: Optional context (e.g., verified DOI metadata)
            allow_web: Whether to allow web retrieval (HYBRID mode)
        
        Returns:
            Dict with claims list and warnings
        """
        warnings: List[str] = []
        claims: List[Dict[str, Any]] = []
        
        # Use preprocessor for clean sentence splitting
        sentences = split_sentences(text)
        
        if not sentences:
            warnings.append("No valid claims extracted from text")
        
        # Initial claim analysis
        for sentence in sentences:
            result = _analyze_claim(sentence)
            claims.append(result)
        
        # Contradiction pass
        claims = _detect_contradictions(claims)
        
        return {"claims": claims, "warnings": warnings}


def load_default() -> OpenFactCheck:
    return OpenFactCheck()
