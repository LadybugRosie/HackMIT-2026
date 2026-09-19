#!/usr/bin/env python3
"""
Test forensic stylometry /verify against large texts (2k–4k words).
Uses the 2 enrolled users in DB: fetches their stylometry_student_id,
then calls the forensic stylo API with long submission_text and prints score/verdict.
Run from repo root: python -m integrity-backend.scripts.test_stylometry_large_text
Or from integrity-backend: python scripts/test_stylometry_large_text.py
"""
import os
import sys

# Load .env from integrity-backend
script_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(script_dir)
env_path = os.path.join(backend_dir, ".env")
if os.path.isfile(env_path):
    from dotenv import load_dotenv
    load_dotenv(env_path)

import httpx

STYLOMETRY_V2_BASE = "https://forensicstylo.up.railway.app"


def make_large_text(target_words: int) -> str:
    """Build a text of ~target_words (varied sentences so it's not trivial)."""
    sentences = [
        "The quick brown fox jumps over the lazy dog and runs into the forest.",
        "Academic writing often requires clear structure and evidence-based arguments.",
        "Students should cite their sources and avoid plagiarism in all submissions.",
        "Different authors have distinct patterns in sentence length and word choice.",
        "Stylometry analyzes these patterns to infer authorship and verify identity.",
        "Long documents provide more signal for statistical comparison and verification.",
        "Baseline samples are used to build a profile of an author's writing style.",
        "Verification can return a score, a verdict, and optional confidence metrics.",
    ]
    words = []
    while len(words) < target_words:
        s = sentences[len(words) % len(sentences)]
        words.extend(s.split())
    return " ".join(words[:target_words])


def main():
    mongo_uri = os.getenv("MONGO_URI")
    db_name = os.getenv("DB_NAME", "editorrah_integrity")
    if not mongo_uri:
        print("MONGO_URI not set. Set it or run from integrity-backend with .env")
        sys.exit(1)

    try:
        from pymongo import MongoClient
    except ImportError:
        print("pymongo not installed. Install with: pip install pymongo")
        sys.exit(1)

    client = MongoClient(mongo_uri)
    db = client[db_name]
    users = list(db.users.find(
        {"stylometry_enrolled": True},
        {"email": 1, "stylometry_student_id": 1, "stylometry_baseline_words": 1, "stylometry_baseline_samples": 1}
    ))
    client.close()

    if not users:
        print("No users with stylometry_enrolled=True found in DB.")
        sys.exit(1)

    print(f"Found {len(users)} enrolled user(s). Testing verify with 2k and 4k word texts.\n")

    for word_count in [2000, 4000]:
        text = make_large_text(word_count)
        actual_words = len(text.split())
        print(f"--- Submission text length: {actual_words} words ---")

        for u in users:
            email = u.get("email", "?")
            student_id = u.get("stylometry_student_id") or u.get("email")
            baseline_words = u.get("stylometry_baseline_words", 0)
            baseline_samples = u.get("stylometry_baseline_samples", 0)
            print(f"\n  User: {email}")
            print(f"  student_id: {student_id}  (baseline: {baseline_samples} samples, ~{baseline_words} words)")

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
                    print(f"  -> API error: {r.status_code}  {r.text[:200]}")
                    continue
                data = r.json()
                score = data.get("score")
                verdict = data.get("verdict", data.get("final_verdict", "?"))
                confidence = data.get("confidence")
                print(f"  -> score: {score}  verdict: {verdict}  confidence: {confidence}")
                if data.get("final_verdict_reason"):
                    print(f"     reason: {data['final_verdict_reason']}")
                if "author_wins" in data or "impostor_wins" in data:
                    print(f"     author_wins: {data.get('author_wins')}  impostor_wins: {data.get('impostor_wins')}")
            except Exception as e:
                print(f"  -> error: {e}")

        print()

    print("Done.")


if __name__ == "__main__":
    main()
