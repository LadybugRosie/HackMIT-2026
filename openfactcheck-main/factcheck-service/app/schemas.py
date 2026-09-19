from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class FactcheckRequest(BaseModel):
    text: str = Field(..., min_length=1)
    context: Optional[str] = None
    doc_id: Optional[str] = None
    include_evidence: bool = True
    include_reference_report: bool = True
    # "general" (default, student essay / AI report) or "published_paper"
    # (IEEE/journal audit — surfaces the Citation Support Matrix and conservative
    # review language). Numbered-citation alignment is auto-detected regardless.
    mode: str = "general"


class EvidenceItem(BaseModel):
    source: str
    snippet: str
    url: Optional[str] = None


class ConfidenceBreakdown(BaseModel):
    source_quality: int = 0
    evidence_strength: int = 0
    source_agreement: int = 0


class ConfidenceScore(BaseModel):
    score: int = 0
    breakdown: ConfidenceBreakdown = Field(default_factory=ConfidenceBreakdown)
    grade: str = "F"
    explanation: str = ""
    signals: Dict[str, Any] = Field(default_factory=dict)
    failure_mode: Optional[str] = None  # no_evidence_found | conflicting_evidence | partial_support
    severity: Optional[str] = None      # critical | high | medium | low
    domain: Optional[str] = None        # medical | legal | scientific | …


class FabricationFlagModel(BaseModel):
    kind: str
    detail: str
    span: Optional[str] = None
    candidate: Optional[str] = None
    score: float = 0.0
    sources_consulted: List[str] = Field(default_factory=list)


class CitationAlignmentModel(BaseModel):
    doi: str
    support: str  # supported | partial | overstated | unrelated | contradicted | unknown
    supporting_span: Optional[str] = None
    missing_aspects: List[str] = Field(default_factory=list)
    confidence: int = 0
    is_retracted: bool = False
    retraction_note: Optional[str] = None
    source_title: Optional[str] = None
    source_authors: List[str] = Field(default_factory=list)
    source_year: Optional[int] = None
    source_venue: Optional[str] = None
    claim_context: Optional[str] = None
    notes: Optional[str] = None
    sources_consulted: List[str] = Field(default_factory=list)
    # Set only for numbered citations: the in-text marker ("[14]") and the
    # reference-list number it resolved to.
    marker: Optional[str] = None
    cited_number: Optional[int] = None
    evidence_scope: Optional[str] = None  # abstract | metadata_only | not_retrieved


class TaxonomyModel(BaseModel):
    intrinsic_extrinsic: str  # intrinsic | extrinsic | n/a
    conflict_type: str        # input | context | reality | n/a
    primary_class: str
    notes: Optional[str] = None


class CascadeRootModel(BaseModel):
    index: int
    claim: str


class ClaimResult(BaseModel):
    claim: str
    verdict: str
    confidence: Optional[ConfidenceScore] = None
    reasoning: Optional[str] = None
    evidence: List[EvidenceItem] = Field(default_factory=list)
    fabrication_flags: List[FabricationFlagModel] = Field(default_factory=list)
    citation_alignment: List[CitationAlignmentModel] = Field(default_factory=list)
    taxonomy: Optional[TaxonomyModel] = None
    severity: Optional[str] = None
    cascade_root: Optional[CascadeRootModel] = None
    # Published-paper audit: zone label (RELATED_WORK_CLAIM | METHOD_CLAIM |
    # RESULT_CLAIM | AUTHOR_CLAIM) and whether an in-text citation was mapped to a
    # reference entry (drives the "no mapped citation" reason text).
    zone: Optional[str] = None
    citation_mapped: bool = False


class Summary(BaseModel):
    supported: int = 0
    unsupported: int = 0
    contradicted: int = 0
    unknown: int = 0
    author_claim: int = 0  # self-reported author/method/result claims (not externally verified)


class RiskOverview(BaseModel):
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0


class DOIMetadataResponse(BaseModel):
    title: Optional[str] = None
    authors: List[str] = Field(default_factory=list)
    year: Optional[int] = None
    venue: Optional[str] = None


class DOIResultResponse(BaseModel):
    doi: str
    status: str  # valid, not_found, invalid, mismatch, timeout, error
    registrar: Optional[str] = None  # crossref, datacite, unknown
    resolved_url: Optional[str] = None
    metadata: Optional[DOIMetadataResponse] = None
    note: Optional[str] = None


class URLResultResponse(BaseModel):
    url: str
    status: str  # ok, broken, timeout, error
    http_status: Optional[int] = None
    final_url: Optional[str] = None
    note: Optional[str] = None


class ReferenceSummary(BaseModel):
    total_dois: int = 0
    valid_dois: int = 0
    invalid_dois: int = 0
    total_urls: int = 0
    broken_urls: int = 0


class ReferenceReportResponse(BaseModel):
    dois: List[DOIResultResponse] = Field(default_factory=list)
    urls: List[URLResultResponse] = Field(default_factory=list)
    summary: ReferenceSummary = Field(default_factory=ReferenceSummary)


class BibliographyReportResponse(BaseModel):
    in_text_citations_count: int = 0
    bibliography_entries_count: int = 0
    in_text_dois_count: int = 0
    bibliography_dois_count: int = 0
    orphan_in_text: List[str] = Field(default_factory=list)
    uncited_entries: List[str] = Field(default_factory=list)


class CitationMatrixRow(BaseModel):
    """One row of the Citation Support Matrix (Published Paper Audit)."""
    citation: str                                  # "[14]"
    number: Optional[int] = None                   # reference-list number
    reference: Optional[str] = None                # resolved/parsed title or raw entry
    doi: Optional[str] = None
    doi_status: Optional[str] = None               # valid | not_found | invalid | mismatch | no_doi | unknown
    metadata_match: Optional[bool] = None          # reference title vs registry title
    used_correctly: Optional[bool] = None          # cited where the source is relevant
    supports_claim: Optional[str] = None           # supported | partial | overstated | unrelated | contradicted | unknown
    is_retracted: bool = False
    # supported | partial | unrelated | needs_review | contradicted | could_not_retrieve | unknown
    verdict: str = "unknown"
    confidence: int = 0
    note: Optional[str] = None
    claim_snippet: Optional[str] = None            # the citing sentence (per-citation pair)
    evidence_scope: Optional[str] = None           # abstract | metadata_only | not_retrieved
    citation_function: Optional[str] = None        # evidential | reference (tool/dataset/method/background/example)


class InternalConsistencyFinding(BaseModel):
    """One same-quantity numeric disagreement found inside the document."""
    verdict: str = "internal_mismatch"            # always internal_mismatch for a finding
    metric: Optional[str] = None                  # e.g. "accuracy"
    value_a: Optional[str] = None
    value_b: Optional[str] = None
    snippet_a: Optional[str] = None               # citing sentence A
    snippet_b: Optional[str] = None               # citing sentence B
    note: Optional[str] = None


class InternalConsistencyResult(BaseModel):
    """Internal numeric-consistency pass output (additive, separate from claims)."""
    status: str = "not_checked"                   # internal_mismatch | internally_consistent | not_checked
    findings: List[InternalConsistencyFinding] = Field(default_factory=list)
    checked: int = 0                              # figure-bearing sentences compared


class ForensicFinding(BaseModel):
    """One deterministic forensic-integrity finding."""
    check: str                                    # statcheck | grim | dangling_ref | retraction
    severity: str = "warning"                     # error | warning | info
    title: str
    detail: str
    snippet: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)


class ForensicReport(BaseModel):
    """Forensic-integrity pass output (additive, separate from claims)."""
    findings: List[ForensicFinding] = Field(default_factory=list)
    checks_run: List[str] = Field(default_factory=list)
    summary: Dict[str, int] = Field(default_factory=dict)   # finding count per check


class CitationCoverage(BaseModel):
    """Honest coverage headline for the published-paper audit: of the references
    actually cited in-text, how many we resolved to a real source, how many had
    an abstract for true content-alignment, and how many we could not retrieve.
    'unknown' / 'could not retrieve' means 'could NOT check', not 'clean'."""
    cited: int = 0            # cited references that entered the audit (matrix rows)
    resolved: int = 0         # resolved to a source (abstract or metadata)
    content_checked: int = 0  # had an abstract -> true content alignment
    not_retrieved: int = 0    # could not be resolved to any source


class AuditVerdict(BaseModel):
    """Top-line verdict that accounts for COVERAGE, so a document we could not
    actually verify is never reported as 'Looks Good'."""
    # looks_good | needs_review | limited_verification | no_content
    status: str = "looks_good"
    headline: str = ""
    is_low_coverage: bool = False  # True => UI must NOT show reassurance
    issues_found: int = 0          # CONFIRMED issues: contradicted source / fabricated DOI
    review_flags: int = 0          # softer: cited abstract may not show support (verify vs full text)


class FactcheckResponse(BaseModel):
    summary: Summary
    claims: List[ClaimResult]
    warnings: List[str] = Field(default_factory=list)
    reference_report: Optional[ReferenceReportResponse] = None
    bibliography_report: Optional[BibliographyReportResponse] = None
    risk_overview: Optional[RiskOverview] = None
    citation_matrix: List[CitationMatrixRow] = Field(default_factory=list)
    references_parsed: int = 0  # published-paper audit: reference entries parsed
    citation_coverage: Optional[CitationCoverage] = None  # how much could actually be checked
    verdict: Optional[AuditVerdict] = None                # coverage-aware top-line verdict
    # Internal numeric-consistency pass — own field, never mixed into `claims`.
    internal_consistency: Optional[InternalConsistencyResult] = None
    # Forensic-integrity checks (statcheck/GRIM/dangling-ref/retraction) — own field.
    forensic_checks: Optional[ForensicReport] = None
