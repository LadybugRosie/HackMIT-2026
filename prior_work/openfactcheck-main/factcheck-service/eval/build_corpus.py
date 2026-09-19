"""
Build a ground-truth corpus of recent (2021-2025), highly-cited papers across
several disciplines from OpenAlex, into eval/corpus.db (SQLite).

Each paper gives us, for free, the two ingredients an eval needs:
  - abstract  -> real factual claims (test FALSE POSITIVES: engine must NOT flag true statements)
  - DOI       -> a pool of REAL valid DOIs (for "mismatched citation" injection)

Fabricated DOIs / wrong stats / hallucinated claims are synthesized later
(build_corpus_cases.py) on top of these real papers, giving perfect labels.

Usage:
    .venv/bin/python eval/build_corpus.py            # ~25 papers x ~10 fields
    PER_FIELD=30 .venv/bin/python eval/build_corpus.py
"""
from __future__ import annotations
import os, sqlite3, time
from pathlib import Path
import httpx

HERE = Path(__file__).resolve().parent
DB = HERE / "corpus.db"
MAILTO = os.environ.get("OPENALEX_MAILTO", "202052333@iiitvadodara.ac.in")
PER_FIELD = int(os.environ.get("PER_FIELD", "25"))

# Diverse spread of disciplines (matched by OpenAlex field display_name).
WANT_FIELDS = [
    "Computer Science", "Medicine", "Biochemistry, Genetics and Molecular Biology",
    "Physics and Astronomy", "Chemistry", "Psychology", "Economics, Econometrics and Finance",
    "Engineering", "Environmental Science", "Mathematics", "Neuroscience",
    "Social Sciences", "Materials Science",
]


def reconstruct_abstract(inv: dict) -> str:
    if not inv:
        return ""
    pos = {}
    for word, idxs in inv.items():
        for i in idxs:
            pos[i] = word
    return " ".join(pos[i] for i in sorted(pos))


def get_fields(client) -> dict:
    r = client.get("https://api.openalex.org/fields", params={"per_page": "50", "mailto": MAILTO}, timeout=30)
    r.raise_for_status()
    return {f["display_name"]: f["id"].rsplit("/", 1)[-1] for f in r.json()["results"]}


def fetch_field(client, field_id: str, n: int) -> list:
    r = client.get("https://api.openalex.org/works", params={
        "filter": f"publication_year:2021-2025,has_abstract:true,has_doi:true,primary_topic.field.id:fields/{field_id}",
        "per_page": str(min(n, 50)),
        "sort": "cited_by_count:desc",
        "select": "id,doi,title,publication_year,abstract_inverted_index,cited_by_count,primary_topic",
        "mailto": MAILTO,
    }, timeout=60)
    r.raise_for_status()
    return r.json()["results"]


def main():
    con = sqlite3.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS papers(
        openalex_id TEXT PRIMARY KEY, doi TEXT, title TEXT, year INTEGER,
        field TEXT, abstract TEXT, cited_by INTEGER)""")
    con.commit()

    with httpx.Client() as client:
        fmap = get_fields(client)
        total = 0
        for name in WANT_FIELDS:
            fid = fmap.get(name)
            if not fid:
                print(f"  ! field not found: {name}"); continue
            try:
                works = fetch_field(client, fid, PER_FIELD)
            except Exception as e:
                print(f"  ! {name}: fetch error {e}"); continue
            kept = 0
            for w in works:
                doi = (w.get("doi") or "").replace("https://doi.org/", "")
                abs = reconstruct_abstract(w.get("abstract_inverted_index"))
                if not doi or len(abs.split()) < 40:  # need a real DOI + substantive abstract
                    continue
                con.execute("INSERT OR REPLACE INTO papers VALUES(?,?,?,?,?,?,?)",
                    (w["id"], doi, w.get("title"), w.get("publication_year"),
                     name, abs, w.get("cited_by_count")))
                kept += 1
            con.commit()
            total += kept
            print(f"  {name:42} {kept:3} papers")
            time.sleep(0.4)  # be polite

    n = con.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
    print(f"\nDB: {DB}  |  total papers: {n}")
    con.close()


if __name__ == "__main__":
    main()
