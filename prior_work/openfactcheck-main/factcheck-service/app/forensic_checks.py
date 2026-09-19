"""
Forensic-integrity checks (ADDITIVE, deterministic, own response field).

The "data-sleuth" toolkit — the checks that fire ONLY when the arithmetic or a
cross-reference is provably broken, so they are zero-false-positive by
construction. None of them touch claims, verdicts, segmentation, or the
classifier; they emit their own ForensicFinding list.

  statcheck      recompute p from a reported test statistic (t/F/χ²/r/z + df) and
                 flag inconsistencies + decision errors (significance flips at .05).
  grim           a reported percentage of a stated count, or an integer-scale mean,
                 that is arithmetically impossible for that N.
  dangling_ref   "Table 7 / Figure 9" referenced in the text but never defined
                 (above the numbering ceiling the document actually establishes).
  retraction     in-text citation resolves to a retracted reference.

Retraction findings are built by the caller from the citation matrix (which
already carries is_retracted); everything else needs only the document text.
"""
import logging
import re
from typing import Any, Dict, List, Optional

from .numbered_citations import parse_reference_list
from .settings import settings
from .stats_pvalue import chi2_p, f_p, norm_p_two, r_p_two, t_p_two

logger = logging.getLogger(__name__)


def _finding(check: str, severity: str, title: str, detail: str,
             snippet: Optional[str] = None, **data: Any) -> Dict[str, Any]:
    return {
        "check": check,
        "severity": severity,      # error | warning | info
        "title": title,
        "detail": detail,
        "snippet": (snippet or "")[:240] or None,
        "data": data,
    }


def _ctx(text: str, start: int, end: int, pad: int = 50) -> str:
    return " ".join(text[max(0, start - pad):min(len(text), end + pad)].split())


# ── statcheck ───────────────────────────────────────────────────────────────
# A reported NHST result: a test statistic (with df where applicable) followed,
# within a short span, by its p-value. Anchored so the leading letter is not
# matched mid-word.
_NHST_RE = re.compile(
    r"(?<![A-Za-z])(?P<stat>t|F|r|z|χ2|χ²|chi2|X2)"
    r"\s*(?:\(\s*(?P<df1>\d+(?:\.\d+)?)\s*(?:,\s*(?P<df2>\d+(?:\.\d+)?)\s*)?\)\s*)?"
    r"(?:,?\s*[Nn]\s*=\s*(?P<N>\d+)\s*)?"
    r"(?P<scmp>[=<>])\s*(?P<sval>-?\d*\.\d+|-?\d+(?:\.\d+)?)"
    r"[^.\n;]{0,30}?"
    r"\bp\s*(?P<pcmp>[=<>])\s*(?P<pval>ns|\d?\.\d+|[01](?:\.0+)?)",
    re.IGNORECASE,
)


def _decimals(s: str) -> int:
    return len(s.split(".")[1]) if "." in s else 0


def _recompute_p(stat: str, sval: float, df1, df2, N) -> Optional[List[float]]:
    """Return candidate p-values (two-sided first, then one-sided where it makes
    sense). None when the statistic can't be recomputed (missing df)."""
    s = stat.lower()
    if s == "t":
        if df1 is None:
            return None
        two = t_p_two(sval, df1)
        return [two, two / 2.0]
    if s == "r":
        if df1 is None:
            return None
        two = r_p_two(sval, df1)
        return [two, two / 2.0]
    if s == "z":
        two = norm_p_two(sval)
        return [two, two / 2.0]
    if s == "f":
        if df1 is None or df2 is None:
            return None
        return [f_p(sval, df1, df2)]          # F is inherently one-tailed
    if s in ("χ2", "χ²", "chi2", "x2"):
        if df1 is None:
            return None
        return [chi2_p(sval, df1)]            # χ² is inherently one-tailed
    return None


def run_statcheck(text: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen = set()
    for m in _NHST_RE.finditer(text):
        try:
            stat = m.group("stat")
            sval = float(m.group("sval"))
            df1 = float(m.group("df1")) if m.group("df1") else None
            df2 = float(m.group("df2")) if m.group("df2") else None
            N = float(m.group("N")) if m.group("N") else None
            pcmp = m.group("pcmp")
            pval_raw = m.group("pval")
        except (TypeError, ValueError):
            continue
        cands = _recompute_p(stat, sval, df1, df2, N)
        if not cands or any(c != c for c in cands):   # None or NaN
            continue
        comp_two = cands[0]
        key = (round(sval, 4), df1, df2, pcmp, pval_raw)
        if key in seen:
            continue
        seen.add(key)

        if pval_raw.lower() == "ns":
            # "ns" = not significant. Inconsistent only if a candidate p < .05.
            if comp_two < 0.05 and (len(cands) < 2 or cands[1] < 0.05):
                out.append(_finding(
                    "statcheck", "error",
                    f"Reported non-significant, but {stat}={sval:g} gives p={comp_two:.4f}",
                    f"The result is reported as non-significant (ns), but the test "
                    f"statistic implies p={comp_two:.4f} (< .05) — a decision error.",
                    snippet=_ctx(text, m.start(), m.end()),
                    statistic=stat, value=sval, computed_p=round(comp_two, 5)))
            continue

        pval = float(pval_raw)
        dec = max(_decimals(pval_raw), 2)
        unit = 10 ** (-dec)

        if pcmp == "=":
            # consistent if any candidate rounds to within one unit of reported.
            dist = min(abs(round(c, dec) - pval) for c in cands)
            if dist > unit + 1e-9:
                # significance flip across .05 → decision error, else inconsistency.
                comp_sig = comp_two <= 0.05
                rep_sig = pval <= 0.05
                if comp_sig != rep_sig:
                    out.append(_finding(
                        "statcheck", "error",
                        f"Decision error: {stat}({_df_str(df1, df2)})={sval:g} ⇒ p={comp_two:.4f}, not p={pval_raw}",
                        f"The reported p={pval_raw} would make this "
                        f"{'significant' if rep_sig else 'non-significant'}, but the "
                        f"statistic gives p={comp_two:.4f} "
                        f"({'< .05' if comp_sig else '≥ .05'}) — the significance verdict flips.",
                        snippet=_ctx(text, m.start(), m.end()),
                        statistic=stat, value=sval, reported_p=pval_raw,
                        computed_p=round(comp_two, 5)))
                else:
                    out.append(_finding(
                        "statcheck", "warning",
                        f"p-value inconsistency: {stat}({_df_str(df1, df2)})={sval:g} ⇒ p≈{comp_two:.4f}, reported p={pval_raw}",
                        f"The reported p={pval_raw} does not match the recomputed "
                        f"p≈{comp_two:.4f} (both are on the same side of .05).",
                        snippet=_ctx(text, m.start(), m.end()),
                        statistic=stat, value=sval, reported_p=pval_raw,
                        computed_p=round(comp_two, 5)))
        elif pcmp == "<":
            # "p < X": inconsistent if every candidate is clearly ≥ X.
            if min(cands) > pval + unit:
                sev = "error" if (pval <= 0.05 < comp_two) else "warning"
                out.append(_finding(
                    "statcheck", sev,
                    f"p<{pval_raw} contradicted: {stat}({_df_str(df1, df2)})={sval:g} ⇒ p≈{comp_two:.4f}",
                    f"The text reports p<{pval_raw}, but the statistic gives p≈{comp_two:.4f}.",
                    snippet=_ctx(text, m.start(), m.end()),
                    statistic=stat, value=sval, reported_p="<" + pval_raw,
                    computed_p=round(comp_two, 5)))
        elif pcmp == ">":
            if max(cands) < pval - unit:
                sev = "error" if (comp_two <= 0.05 < pval) else "warning"
                out.append(_finding(
                    "statcheck", sev,
                    f"p>{pval_raw} contradicted: {stat}({_df_str(df1, df2)})={sval:g} ⇒ p≈{comp_two:.4f}",
                    f"The text reports p>{pval_raw}, but the statistic gives p≈{comp_two:.4f}.",
                    snippet=_ctx(text, m.start(), m.end()),
                    statistic=stat, value=sval, reported_p=">" + pval_raw,
                    computed_p=round(comp_two, 5)))
    return out


def _df_str(df1, df2) -> str:
    if df1 is None:
        return ""
    if df2 is None:
        return f"{df1:g}"
    return f"{df1:g},{df2:g}"


# ── GRIM ─────────────────────────────────────────────────────────────────────
# A percentage of a stated count must equal k/N for some integer k. If no integer
# k near the implied value reproduces the reported percentage, it is impossible.
_PCT_PATTERNS = [
    re.compile(r"(?P<k>\d+)\s*/\s*(?P<N>\d+)\s*\(\s*(?P<pct>\d{1,3}(?:\.\d+)?)\s*%\s*\)"),
    re.compile(r"(?P<k>\d+)\s+of\s+(?:the\s+)?(?P<N>\d+)\b[^.\n]{0,25}?\(\s*(?P<pct>\d{1,3}(?:\.\d+)?)\s*%\s*\)"),
    re.compile(r"(?P<pct>\d{1,3}(?:\.\d+)?)\s*%\s*\(\s*[nN]\s*=\s*(?P<N>\d+)\s*\)"),
    re.compile(r"(?P<pct>\d{1,3}(?:\.\d+)?)\s*%\s+of\s+(?:the\s+)?(?P<N>\d+)\b"),
]
# Integer-scale mean GRIM only runs when an explicit integer/Likert cue is present.
_SCALE_CUE_RE = re.compile(
    r"\bLikert\b|\b\d\s*[-–to]+\s*\d\s*(?:point|scale)\b|\b(?:point|item)\s+scale\b"
    r"|\brated?\s+(?:on|from)\b|\b1\s*[-–]\s*[5-9]\b|\bcount(?:s|ed)?\b",
    re.IGNORECASE,
)
_MEAN_RE = re.compile(
    r"\b[Mm]\s*=\s*(?P<mean>\d+\.\d+)[^.\n]{0,40}?\b[Nn]\s*=\s*(?P<N>\d+)\b")


def _pct_possible(pct: float, N: int, dec: int) -> bool:
    """Is `pct`% attainable as k/N (rounded to `dec` decimals) for some integer k?"""
    if N <= 0:
        return True
    base = round(pct * N / 100.0)
    for k in (base - 1, base, base + 1):
        if 0 <= k <= N and round(100.0 * k / N, dec) == round(pct, dec):
            return True
    return False


def run_grim(text: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen = set()
    for pat in _PCT_PATTERNS:
        for m in pat.finditer(text):
            gd = m.groupdict()
            try:
                N = int(gd["N"])
                pct_raw = gd["pct"]
                pct = float(pct_raw)
            except (TypeError, ValueError, KeyError):
                continue
            if N < 4 or N > 100000 or pct > 100:
                continue            # tiny N is ambiguous; huge N has no power
            dec = _decimals(pct_raw)
            key = (pct_raw, N)
            if key in seen:
                continue
            seen.add(key)
            if not _pct_possible(pct, N, dec):
                kfrac = gd.get("k")
                out.append(_finding(
                    "grim", "warning",
                    f"Impossible percentage: {pct_raw}% of N={N}",
                    f"No whole count out of {N} yields {pct_raw}% — the nearest are "
                    f"{round(100 * round(pct * N / 100) / N, dec)}% "
                    f"({round(pct * N / 100)}/{N}). The reported percentage is not "
                    f"arithmetically attainable for this denominator.",
                    snippet=_ctx(text, m.start(), m.end()),
                    percentage=pct, n=N, claimed_count=kfrac))
    # Integer-scale mean GRIM (gated on an explicit scale cue in the same window).
    for m in _MEAN_RE.finditer(text):
        window = text[max(0, m.start() - 120):m.end() + 60]
        if not _SCALE_CUE_RE.search(window):
            continue
        try:
            mean_raw = m.group("mean")
            mean = float(mean_raw)
            N = int(m.group("N"))
        except (TypeError, ValueError):
            continue
        if N < 2 or N > 1000:
            continue
        dec = _decimals(mean_raw)
        base = round(mean * N)
        ok = any(round(k / N, dec) == round(mean, dec) for k in (base - 1, base, base + 1))
        if not ok:
            out.append(_finding(
                "grim", "warning",
                f"Impossible mean: M={mean_raw}, N={N} (integer scale)",
                f"For integer-valued responses, the sum across {N} participants must "
                f"be a whole number, but M={mean_raw} implies a non-integer total "
                f"({mean_raw}×{N}={round(mean * N, 2)}).",
                snippet=_ctx(text, m.start(), m.end()),
                mean=mean, n=N))
    return out


# ── dangling cross-references ────────────────────────────────────────────────
_XREF_KINDS = [
    ("Table", re.compile(r"\bTable\s+(\d{1,3})\b"),
     re.compile(r"(?mi)^\s*Table\s+(\d{1,3})\b")),
    ("Figure", re.compile(r"\b(?:Figure|Fig\.?)\s+(\d{1,3})\b"),
     re.compile(r"(?mi)^\s*(?:Figure|Fig\.?)\s+(\d{1,3})\b")),
]


def run_dangling_refs(text: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for kind, ref_re, def_re in _XREF_KINDS:
        defined = {int(x.group(1)) for x in def_re.finditer(text)}
        if len(defined) < 2:
            continue                       # not enough to trust a numbering ceiling
        ceiling = max(defined)
        flagged = set()
        for m in ref_re.finditer(text):
            n = int(m.group(1))
            if n > ceiling and n not in flagged:
                flagged.add(n)
                out.append(_finding(
                    "dangling_ref", "warning",
                    f"{kind} {n} referenced but not present",
                    f"The text refers to {kind} {n}, but the document only defines "
                    f"{kind}s 1–{ceiling}. The reference has no target.",
                    snippet=_ctx(text, m.start(), m.end()),
                    kind=kind, number=n, max_defined=ceiling))
    return out


# ── orchestrator (text-only deterministic checks) ────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
# Bibliographic arithmetic and identifier FORMAT validation.
#
# Both are deterministic and offline. They are deliberately NEGATIVE-ONLY: they
# report an identifier that cannot possibly be well-formed, and never report one
# as good. A format-valid identifier still has to be resolved against a registry
# before anything may be called verified, so passing these checks says nothing.
# ─────────────────────────────────────────────────────────────────────────────

# A bare 'N-M' is not a page range: report numbers ('memorandum No. 44-12'),
# model numbers and date fragments all share the shape. Require an explicit
# pagination context, so a miss is possible but a false accusation is not.
_PAGE_RANGE_RE = re.compile(
    r'(?:pp?\.\s*|pages\s+|\d+\s*\(\s*[\dA-Za-z]+\s*\)\s*,\s*)'
    r'(\d{1,6})\s*[-–—]\s*(\d{1,6})\b',
    re.IGNORECASE,
)


def run_page_ranges(text: str) -> List[Dict[str, Any]]:
    """Start page after end page is impossible. Pure arithmetic."""
    out: List[Dict[str, Any]] = []
    for m in _PAGE_RANGE_RE.finditer(text):
        start, end = int(m.group(1)), int(m.group(2))
        # Abbreviated end pages are conventional: 436-44 means 436-444, and
        # 1735-80 means 1735-1780. Only compare when the end page has at least
        # as many digits as the start, otherwise the comparison is meaningless.
        if len(m.group(2)) < len(m.group(1)):
            continue
        if start > end:
            out.append(_finding(
                "page_range", "error", "Impossible page range",
                f"Start page {start} is after end page {end}.",
                snippet=_ctx(text, m.start(), m.end()),
                start_page=start, end_page=end,
            ))
    return out


_ARXIV_NEW_RE = re.compile(r'\barxiv[:\s]\s*(\d{4})\.(\d{4,5})(v\d+)?\b', re.IGNORECASE)
_ISBN_RE = re.compile(r'\bISBN[:\s]*((?:97[89][-\s]?)?[\d][-\s\dxX]{8,20})', re.IGNORECASE)
_PMID_RE = re.compile(r'\bPMID[:\s]*([0-9]{1,15})\b', re.IGNORECASE)
_NCT_RE = re.compile(r'\b(NCT\d{1,12})\b', re.IGNORECASE)
_PMCID_AS_DOI_RE = re.compile(r'doi\.org/(PMC\d+)', re.IGNORECASE)
_ISSN_AS_DOI_RE = re.compile(r'\bdoi[:\s]+(\d{4}-\d{3}[\dxX])\b', re.IGNORECASE)


def _isbn13_ok(digits: str) -> bool:
    if len(digits) != 13 or not digits.isdigit():
        return False
    total = sum((1 if i % 2 == 0 else 3) * int(d) for i, d in enumerate(digits))
    return total % 10 == 0


def run_identifier_formats(text: str) -> List[Dict[str, Any]]:
    """Flag identifiers that are structurally impossible. Never asserts validity."""
    out: List[Dict[str, Any]] = []

    for m in _ARXIV_NEW_RE.finditer(text):
        yy, mm = m.group(1)[:2], int(m.group(1)[2:])
        if not (1 <= mm <= 12):
            out.append(_finding(
                "identifier_format", "error", "Invalid arXiv identifier",
                f"arXiv IDs encode YYMM; month {mm:02d} does not exist.",
                snippet=_ctx(text, m.start(), m.end()), identifier=m.group(0)))

    for m in _ISBN_RE.finditer(text):
        raw = re.sub(r'[-\s]', '', m.group(1))
        if len(raw) == 13 and raw.isdigit() and not _isbn13_ok(raw):
            out.append(_finding(
                "identifier_format", "error", "Invalid ISBN checksum",
                f"ISBN-13 {raw} fails the mod-10 check-digit test.",
                snippet=_ctx(text, m.start(), m.end()), identifier=raw))

    for m in _PMID_RE.finditer(text):
        pmid = m.group(1)
        if pmid.startswith("0") or len(pmid) > 8:
            out.append(_finding(
                "identifier_format", "error", "Invalid PMID",
                "PMIDs are positive integers of at most 8 digits with no leading zeros.",
                snippet=_ctx(text, m.start(), m.end()), identifier=pmid))

    for m in _NCT_RE.finditer(text):
        nct = m.group(1).upper()
        if len(nct) != 11:
            out.append(_finding(
                "identifier_format", "error", "Invalid ClinicalTrials.gov identifier",
                f"NCT numbers are 'NCT' followed by 8 digits; got {len(nct) - 3}.",
                snippet=_ctx(text, m.start(), m.end()), identifier=nct))

    for m in _PMCID_AS_DOI_RE.finditer(text):
        out.append(_finding(
            "identifier_format", "error", "PMCID used as a DOI",
            f"{m.group(1)} is a PubMed Central ID; it will not resolve via doi.org.",
            snippet=_ctx(text, m.start(), m.end()), identifier=m.group(1)))

    for m in _ISSN_AS_DOI_RE.finditer(text):
        out.append(_finding(
            "identifier_format", "error", "ISSN used as a DOI",
            f"{m.group(1)} is an ISSN (a journal identifier), not a DOI.",
            snippet=_ctx(text, m.start(), m.end()), identifier=m.group(1)))

    return out


def run_forensic_text_checks(text: str) -> Dict[str, Any]:
    if not settings.ENABLE_FORENSIC_CHECKS or not text:
        return {"findings": [], "checks_run": [], "summary": {}}
    findings: List[Dict[str, Any]] = []
    for name, fn in (("statcheck", run_statcheck),
                     ("grim", run_grim),
                     ("dangling_ref", run_dangling_refs),
                     ("page_range", run_page_ranges),
                     ("identifier_format", run_identifier_formats)):
        try:
            findings.extend(fn(text))
        except Exception as e:  # noqa: BLE001
            logger.debug(f"forensic check {name} failed: {e}")
    return _report(findings, ["statcheck", "grim", "dangling_ref",
                              "page_range", "identifier_format"])


def retraction_findings(citation_matrix: Optional[List[Any]]) -> List[Dict[str, Any]]:
    """Build retraction findings from already-resolved citation-matrix rows
    (which carry is_retracted). No new network calls."""
    out: List[Dict[str, Any]] = []
    for row in citation_matrix or []:
        g = row.get if isinstance(row, dict) else (lambda k, d=None: getattr(row, k, d))
        if not g("is_retracted"):
            continue
        cite = g("citation") or g("reference") or "a cited reference"
        out.append(_finding(
            "retraction", "error",
            f"Citation {cite} is RETRACTED",
            f"In-text citation {cite} resolves to a reference that has been retracted "
            f"({g('note') or 'see registry'}). Citing retracted work is an integrity issue.",
            snippet=g("claim_snippet"),
            citation=cite, doi=g("doi")))
    return out


def _report(findings: List[Dict[str, Any]], checks_run: List[str]) -> Dict[str, Any]:
    summary: Dict[str, int] = {}
    for f in findings:
        summary[f["check"]] = summary.get(f["check"], 0) + 1
    return {"findings": findings, "checks_run": checks_run, "summary": summary}
