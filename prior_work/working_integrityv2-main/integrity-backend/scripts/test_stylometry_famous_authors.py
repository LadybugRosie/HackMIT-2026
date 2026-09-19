#!/usr/bin/env python3
"""
Evaluate forensic stylometry using famous-author texts from Project Gutenberg.
- Jane Austen (Pride and Prejudice): same author as baseline → expect verified / high score.
- Charles Dickens (Great Expectations): different author → expect flagged / low score.
Run from integrity-backend: python3 scripts/test_stylometry_famous_authors.py
"""
import os
import re
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(script_dir)
env_path = os.path.join(backend_dir, ".env")
if os.path.isfile(env_path):
    from dotenv import load_dotenv
    load_dotenv(env_path)

import httpx

STYLOMETRY_V2_BASE = "https://forensicstylo.up.railway.app"

# Project Gutenberg plain-text URLs (public domain)
GUTENBERG = {
    "jane_austen": "https://www.gutenberg.org/files/1342/1342-0.txt",   # Pride and Prejudice
    "charles_dickens": "https://www.gutenberg.org/files/1400/1400-0.txt",  # Great Expectations
}


def fetch_gutenberg(url: str) -> str:
    r = httpx.get(url, follow_redirects=True, timeout=30)
    r.raise_for_status()
    return r.text


def extract_narrative(text: str, start_marker: str, max_chars: int = 500_000) -> str:
    """Get narrative prose: from start_marker to end, strip [Illustration], etc."""
    idx = text.find(start_marker)
    if idx == -1:
        return text[:max_chars]
    text = text[idx:idx + max_chars]
    # Remove common Gutenberg artifacts
    text = re.sub(r"\[Illustration[^\]]*\]", " ", text, flags=re.I)
    text = re.sub(r"\[.*?\]", " ", text)
    text = re.sub(r"_{2,}", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def words_from_text(text: str, n: int) -> str:
    """First n words from text."""
    w = text.split()
    return " ".join(w[:n])


def main():
    mongo_uri = os.getenv("MONGO_URI")
    db_name = os.getenv("DB_NAME", "editorrah_integrity")
    if not mongo_uri:
        print("MONGO_URI not set. Run from integrity-backend with .env")
        sys.exit(1)

    try:
        from pymongo import MongoClient
    except ImportError:
        print("pymongo not installed. pip install pymongo")
        sys.exit(1)

    client = MongoClient(mongo_uri)
    db = client[db_name]
    users = list(db.users.find(
        {"stylometry_enrolled": True, "stylometry_student_id": {"$exists": True, "$ne": None}},
        {"email": 1, "stylometry_student_id": 1, "stylometry_baseline_words": 1, "stylometry_baseline_samples": 1}
    ))
    client.close()

    # Only test users that exist on the forensic API (we'll discover 404s)
    student_id = None
    for u in users:
        sid = u.get("stylometry_student_id")
        if sid and sid != u.get("email"):
            student_id = sid
            break
    if not student_id:
        student_id = "bench-jane-austen-1342"  # known demo student

    print("Fetching famous-author texts from Project Gutenberg...")
    austen_raw = fetch_gutenberg(GUTENBERG["jane_austen"])
    dickens_raw = fetch_gutenberg(GUTENBERG["charles_dickens"])

    austen_start = "It is a truth universally acknowledged, that a single man in possession"
    dickens_start = "My father's family name being Pirrip, and my Christian name Philip"

    austen_prose = extract_narrative(austen_raw, austen_start)
    dickens_prose = extract_narrative(dickens_raw, dickens_start)

    for word_count in [2000, 4000]:
        austen_sample = words_from_text(austen_prose, word_count)
        dickens_sample = words_from_text(dickens_prose, word_count)
        n_a = len(austen_sample.split())
        n_d = len(dickens_sample.split())

        print(f"\n{'='*60}")
        print(f"  Submission length: ~{word_count} words (Austen: {n_a}, Dickens: {n_d})")
        print(f"  student_id: {student_id}")
        print(f"{'='*60}")

        for label, text in [
            ("Jane Austen (Pride and Prejudice) — SAME author as baseline", austen_sample),
            ("Charles Dickens (Great Expectations) — DIFFERENT author", dickens_sample),
        ]:
            print(f"\n  {label}")
            try:
                with httpx.Client(timeout=120) as http:
                    r = http.post(
                        f"{STYLOMETRY_V2_BASE}/verify",
                        json={
                            "student_id": student_id,
                            "submission_text": text,
                            "skip_ai_detection": True,
                            "iterations": 100,
                        },
                    )
                if r.status_code != 200:
                    print(f"    -> API error: {r.status_code}  {r.text[:150]}")
                    continue
                data = r.json()
                score = data.get("score")
                verdict = data.get("verdict", data.get("final_verdict", "?"))
                confidence = data.get("confidence")
                reason = data.get("final_verdict_reason", "")
                aw = data.get("author_wins")
                iw = data.get("impostor_wins")
                print(f"    -> score: {score}  verdict: {verdict}  confidence: {confidence}")
                if reason:
                    print(f"       reason: {reason}")
                if aw is not None or iw is not None:
                    print(f"       author_wins: {aw}  impostor_wins: {iw}")
            except Exception as e:
                print(f"    -> error: {e}")

    print("\nDone. Expected: Austen → verified/high score; Dickens → flagged/low score.")


if __name__ == "__main__":
    main()
