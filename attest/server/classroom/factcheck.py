"""Citation and link verification.

Extracts DOIs, URLs and author-year citations from a submission, resolves DOIs against
Crossref (with a doi.org fallback) and checks URL reachability. Author-year citations
without an identifier are reported as `unverifiable` with their pairing to the reference
list — never as fabricated. Everything network-facing sits behind the Resolver protocol so
tests inject a fake and the pipeline degrades to `unreachable` instead of raising.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Protocol

DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>]+)", re.I)
URL_RE = re.compile(r"https?://[^\s<>\"'\)\]]+", re.I)
YEAR = r"(?:1[89]|20)\d{2}[a-z]?"
PAREN_RE = re.compile(r"\(([^()]*?\b" + YEAR + r"\b[^()]*)\)")
CITE_RE = re.compile(r"([A-Z][A-Za-z'’\-]+)(?:\s*(?:,|&|and)\s*[A-Z][A-Za-z'’\-]+)*(?:\s+et al\.?)?,?\s+(" + YEAR + r")")
NARR_RE = re.compile(r"\b([A-Z][A-Za-z'’\-]+)(?:\s+(?:and|&)\s+[A-Z][A-Za-z'’\-]+)?(?:\s+et al\.?)?\s+\((" + YEAR + r")\)")
REFS_HEAD_RE = re.compile(r"^\s*(references|works cited|bibliography|sources)\s*:?\s*$", re.I | re.M)
TRAIL = ".,;:)]}'\""
MAX_REFS = 40
BUDGET_S = 60.0


def clean_doi(raw: str) -> str:
    return raw.rstrip(TRAIL).lower()


def _year_of(s: str) -> str:
    m = re.search(r"\b(" + YEAR + r")\b", s)
    return m.group(1)[:4] if m else ""


def extract_references(text: str) -> Dict[str, Any]:
    heads = list(REFS_HEAD_RE.finditer(text))
    body, refs = (text[: heads[-1].start()], text[heads[-1].end():]) if heads else (text, "")

    dois: List[str] = []
    for m in DOI_RE.finditer(text):
        d = clean_doi(m.group(1))
        if d not in dois:
            dois.append(d)
    urls: List[str] = []
    for m in URL_RE.finditer(text):
        u = m.group(0).rstrip(TRAIL)
        if "doi.org/" in u.lower():
            continue  # folded into the DOI list above
        if u not in urls:
            urls.append(u)

    cites: List[Dict[str, Any]] = []
    seen = set()

    def add_cite(raw: str, surname: str, year: str) -> None:
        key = (surname.lower(), year[:4])
        if key in seen:
            return
        seen.add(key)
        cites.append({"raw": raw.strip(), "surname": surname, "year": year[:4]})

    for m in PAREN_RE.finditer(body):
        for part in m.group(1).split(";"):
            c = CITE_RE.search(part)
            if c:
                add_cite(part, c.group(1), c.group(2))
    for m in NARR_RE.finditer(body):
        add_cite(m.group(0), m.group(1), m.group(2))

    entries: List[Dict[str, Any]] = []
    for n, line in enumerate(l.strip() for l in refs.splitlines()):
        if len(line) < 12:
            continue
        surname_m = re.match(r"([A-Z][A-Za-z'’\-]+)", line)
        doi_m = DOI_RE.search(line)
        url_m = URL_RE.search(line)
        entries.append({
            "index": len(entries) + 1, "text": line,
            "surname": surname_m.group(1) if surname_m else "", "year": _year_of(line),
            "doi": clean_doi(doi_m.group(1)) if doi_m else None,
            "url": url_m.group(0).rstrip(TRAIL) if url_m and not doi_m else None,
        })

    matched_entries = set()
    for c in cites:
        hit = next((e for e in entries if e["surname"].lower() == c["surname"].lower() and e["year"] == c["year"]), None)
        c["matched_entry"] = hit["index"] if hit else None
        if hit:
            matched_entries.add(hit["index"])
    for e in entries:
        e["cited"] = e["index"] in matched_entries

    return {"dois": dois, "urls": urls, "author_year": cites, "entries": entries, "has_reference_list": bool(heads)}


# ---- resolution -----------------------------------------------------------------------------

class Resolver(Protocol):
    def doi(self, doi: str) -> Dict[str, Any]: ...
    def url(self, url: str) -> Dict[str, Any]: ...


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        return None


class HttpResolver:
    """Crossref + doi.org + plain HEAD/GET, stdlib only, every failure mapped to a status."""

    def __init__(self, timeout_s: float = 6.0, mailto: str = "") -> None:
        self.timeout_s = timeout_s
        self.ua = f"attest-classroom/0.1 (+https://github.com/LadybugRosie/HackMIT-2026{'; mailto:' + mailto if mailto else ''})"
        self._noredir = urllib.request.build_opener(_NoRedirect)

    def _get_json(self, url: str) -> Optional[Dict[str, Any]]:
        req = urllib.request.Request(url, headers={"User-Agent": self.ua, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout_s) as r:
            return json.load(r)

    def doi(self, doi: str) -> Dict[str, Any]:
        prefix = doi.split("/", 1)[0]
        try:
            # The DOI proxy tells us which registration agency (Crossref, DataCite, ...) owns the DOI,
            # and distinguishes an unknown prefix ("Invalid DOI") from an unknown suffix ("DOI does not exist").
            ra = self._get_json(f"https://doi.org/doiRA/{urllib.parse.quote(doi, safe='/')}")
            entry = ra[0] if isinstance(ra, list) and ra else {}
            agency = entry.get("RA")
            if not agency:
                status = (entry.get("status") or "").lower()
                if "invalid" in status:
                    return {"status": "invalid", "detail": f"DOI prefix {prefix} is not registered with any agency"}
                return {"status": "not_found", "detail": "DOI does not exist — no such record at any registry"}

            if agency.lower() == "crossref":
                try:
                    msg = self._get_json(f"https://api.crossref.org/works/{urllib.parse.quote(doi, safe='')}")["message"]
                    issued = (msg.get("issued") or {}).get("date-parts") or [[None]]
                    return {"status": "valid", "detail": "found in Crossref", "metadata": {
                        "title": (msg.get("title") or [""])[0],
                        "authors": [", ".join(filter(None, [a.get("family"), a.get("given")])) for a in msg.get("author", [])][:6],
                        "year": issued[0][0],
                        "venue": (msg.get("container-title") or [""])[0],
                        "type": msg.get("type"),
                        "url": msg.get("URL") or f"https://doi.org/{doi}",
                    }}
                except urllib.error.HTTPError as exc:
                    if exc.code != 404:
                        raise
                    return {"status": "valid", "detail": "registered with Crossref (metadata not indexed yet)", "metadata": None}

            if agency.lower() == "datacite":
                try:
                    attrs = self._get_json(f"https://api.datacite.org/dois/{urllib.parse.quote(doi, safe='')}")["data"]["attributes"]
                    return {"status": "valid", "detail": "found in DataCite", "metadata": {
                        "title": (attrs.get("titles") or [{}])[0].get("title", ""),
                        "authors": [c.get("name") or ", ".join(filter(None, [c.get("familyName"), c.get("givenName")]))
                                    for c in attrs.get("creators", [])][:6],
                        "year": attrs.get("publicationYear"),
                        "venue": attrs.get("publisher") or "",
                        "type": (attrs.get("types") or {}).get("resourceTypeGeneral"),
                        "url": attrs.get("url") or f"https://doi.org/{doi}",
                    }}
                except (urllib.error.HTTPError, KeyError, IndexError):
                    return {"status": "valid", "detail": "registered with DataCite (metadata unavailable)", "metadata": None}

            return {"status": "valid", "detail": f"registered with {agency}", "metadata": None}
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError) as exc:
            return {"status": "unreachable", "detail": f"could not reach registry: {getattr(exc, 'reason', exc)}"}

    def url(self, url: str) -> Dict[str, Any]:
        for method in ("HEAD", "GET"):
            req = urllib.request.Request(url, method=method, headers={"User-Agent": self.ua, "Range": "bytes=0-0"})
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_s) as r:
                    return {"status": "valid", "detail": f"HTTP {r.status}", "http_status": r.status, "final_url": r.geturl()}
            except urllib.error.HTTPError as exc:
                if exc.code in (404, 410):
                    return {"status": "not_found", "detail": f"HTTP {exc.code}", "http_status": exc.code}
                if exc.code == 405 and method == "HEAD":
                    continue
                return {"status": "unreachable", "detail": f"HTTP {exc.code}", "http_status": exc.code}
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
                return {"status": "unreachable", "detail": f"could not connect: {getattr(exc, 'reason', exc)}"}
        return {"status": "unreachable", "detail": "no response"}


class CachedResolver:
    def __init__(self, inner: Resolver, db, ttl_ms: int = 7 * 86_400_000) -> None:
        self.inner, self.db, self.ttl_ms = inner, db, ttl_ms
        self._mem: Dict[str, Dict[str, Any]] = {}

    def _cached(self, key: str, compute) -> Dict[str, Any]:
        if key in self._mem:
            return self._mem[key]
        now = int(time.time() * 1000)
        row = self.db.one("SELECT value_json, fetched_ms FROM factcheck_cache WHERE key = ?", (key,))
        if row and now - row["fetched_ms"] < self.ttl_ms:
            value = json.loads(row["value_json"])
        else:
            value = compute()
            if value.get("status") == "unreachable":  # transient: never cache, in memory or on disk
                return value
            self.db.exec("INSERT OR REPLACE INTO factcheck_cache (key, value_json, fetched_ms) VALUES (?,?,?)",
                         (key, json.dumps(value), now))
        self._mem[key] = value
        return value

    def doi(self, doi: str) -> Dict[str, Any]:
        return self._cached(f"doi:{doi}", lambda: self.inner.doi(doi))

    def url(self, url: str) -> Dict[str, Any]:
        return self._cached(f"url:{url}", lambda: self.inner.url(url))


# ---- the run --------------------------------------------------------------------------------

def run_factcheck(text: str, resolver: Resolver, max_refs: int = MAX_REFS, budget_s: float = BUDGET_S) -> Dict[str, Any]:
    ex = extract_references(text)
    started = time.monotonic()
    refs: List[Dict[str, Any]] = []

    def budget_left() -> bool:
        return time.monotonic() - started < budget_s

    resolvable = [("doi", d) for d in ex["dois"]] + [("url", u) for u in ex["urls"]]
    for n, (kind, raw) in enumerate(resolvable):
        if n >= max_refs:
            refs.append({"kind": kind, "raw": raw, "status": "unverifiable", "detail": f"over the {max_refs}-reference limit", "flags": []})
            continue
        if not budget_left():
            refs.append({"kind": kind, "raw": raw, "status": "unreachable", "detail": "time budget exhausted", "flags": []})
            continue
        res = resolver.doi(raw) if kind == "doi" else resolver.url(raw)
        ref = {"kind": kind, "raw": raw, "status": res["status"], "detail": res.get("detail", ""),
               "metadata": res.get("metadata"), "flags": []}
        meta = ref.get("metadata") or {}
        if meta.get("year") and meta.get("authors"):
            fam = meta["authors"][0].split(",")[0].lower()
            for c in ex["author_year"]:
                if c["surname"].lower() == fam and abs(int(c["year"]) - int(meta["year"])) > 1:
                    ref["flags"].append(f"year_mismatch: cited {c['year']}, published {meta['year']}")
        refs.append(ref)

    for c in ex["author_year"]:
        if c["matched_entry"]:
            entry = ex["entries"][c["matched_entry"] - 1]
            detail = f"matches reference #{c['matched_entry']}" + (f" (DOI {entry['doi']} checked above)" if entry["doi"] else " (no DOI/URL to verify)")
        else:
            detail = "no matching entry in the reference list" if ex["has_reference_list"] else "no reference list to check against"
        refs.append({"kind": "author_year", "raw": c["raw"], "status": "unverifiable", "detail": detail,
                     "matched_entry": c["matched_entry"], "flags": [] if c["matched_entry"] or not ex["has_reference_list"] else ["orphan"]})

    counts = {s: 0 for s in ("valid", "not_found", "invalid", "unreachable", "unverifiable")}
    for r in refs:
        counts[r["status"]] += 1
    summary = {"total": len(refs), **counts,
               "orphan_cites": sum(1 for r in refs if "orphan" in r["flags"]),
               "uncited_entries": sum(1 for e in ex["entries"] if not e["cited"]) if ex["has_reference_list"] else 0,
               "entries": len(ex["entries"]), "flags": sum(len(r["flags"]) for r in refs)}
    return {"checked_ms": int(time.time() * 1000), "summary": summary, "references": refs,
            "entries": ex["entries"], "has_reference_list": ex["has_reference_list"]}
