#!/usr/bin/env python3
"""
Cross-check: 1 baseline (Jane Austen) vs MANY large texts from different authors.
One student_id, many submission texts — expect only same-author (Austen) verified.
Run from integrity-backend: python3 scripts/test_stylometry_one_to_many.py
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

# 1 baseline → many texts. Project Gutenberg (public domain).
# Format: (url, start_marker_for_narrative, label)
GUTENBERG_ONE_TO_MANY = [
    ("https://www.gutenberg.org/files/1342/1342-0.txt", "It is a truth universally acknowledged, that a single man in possession", "Jane Austen — Pride and Prejudice (SAME author)"),
    ("https://www.gutenberg.org/files/1400/1400-0.txt", "My father's family name being Pirrip, and my Christian name Philip", "Charles Dickens — Great Expectations"),
    ("https://www.gutenberg.org/files/84/84-0.txt", "You will rejoice to hear that no disaster has accompanied the commencement of an enterprise", "Mary Shelley — Frankenstein"),
    ("https://www.gutenberg.org/files/76/76-0.txt", "You don't know about me without you have read a book by the name of The Adventures of Tom Sawyer", "Mark Twain — Huckleberry Finn"),
    ("https://www.gutenberg.org/files/174/174-0.txt", "The studio was filled with the rich odour of roses, and when the light summer wind stirred amidst the trees of the garden", "Oscar Wilde — Picture of Dorian Gray"),
]


def fetch_gutenberg(url: str) -> str:
    r = httpx.get(url, follow_redirects=True, timeout=30)
    r.raise_for_status()
    return r.text


def extract_narrative(text: str, start_marker: str, max_chars: int = 600_000) -> str:
    idx = text.find(start_marker)
    if idx == -1:
        return text[:max_chars]
    text = text[idx:idx + max_chars]
    text = re.sub(r"\[Illustration[^\]]*\]", " ", text, flags=re.I)
    text = re.sub(r"\[.*?\]", " ", text)
    text = re.sub(r"_{2,}", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def words_from_text(text: str, n: int) -> str:
    w = text.split()
    return " ".join(w[:n])


def verify_one(student_id: str, text: str) -> dict:
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
        return {"error": f"{r.status_code}", "text": r.text[:120]}
    return r.json()


def main():
    student_id = "bench-jane-austen-1342"  # 1 baseline: Jane Austen
    word_count = 3500  # single large length for all (2k–4k range)

    print("1-to-many cross-check: ONE baseline (Jane Austen) vs MANY large texts")
    print(f"  student_id: {student_id}")
    print(f"  submission length: {word_count} words each")
    print()

    # Fetch all texts
    samples = []
    for url, start_marker, label in GUTENBERG_ONE_TO_MANY:
        try:
            raw = fetch_gutenberg(url)
            prose = extract_narrative(raw, start_marker)
            text = words_from_text(prose, word_count)
            n = len(text.split())
            samples.append((label, text, n))
        except Exception as e:
            samples.append((label + f" [FETCH ERROR: {e}]", "", 0))

    # Verify each against the single baseline
    results = []
    for label, text, n in samples:
        if not text:
            results.append((label, n, None, "error", "N/A", "fetch failed"))
            continue
        try:
            data = verify_one(student_id, text)
            if "error" in data:
                results.append((label, n, None, "error", "N/A", data.get("text", data.get("error", ""))))
                continue
            score = data.get("score")
            verdict = data.get("verdict", data.get("final_verdict", "?"))
            confidence = data.get("confidence", "?")
            reason = (data.get("final_verdict_reason") or "")[:60]
            results.append((label, n, score, verdict, confidence, reason))
        except Exception as e:
            results.append((label, n, None, "error", "N/A", str(e)))

    # Report table
    print("=" * 90)
    print(f"  {'Author / Work':<52} {'Words':>6}  {'Score':>6}  {'Verdict':<10}  {'Confidence':<8}  Reason")
    print("=" * 90)
    for label, n, score, verdict, confidence, reason in results:
        sc = f"{score:.2f}" if score is not None else " — "
        print(f"  {label:<52} {n:>6}  {sc:>6}  {str(verdict):<10}  {str(confidence):<8}  {reason}")
    print("=" * 90)
    print()
    same_author = [r for r in results if "SAME author" in r[0]]
    others = [r for r in results if "SAME author" not in r[0] and r[2] is not None]
    if same_author:
        s = same_author[0]
        print(f"  Same author (Austen): score={s[2]}, verdict={s[3]} — {'PASS' if s[3] == 'verified' else 'FAIL'}")
    for r in others:
        if r[2] is not None:
            print(f"  Other author: {r[0][:40]}... — verdict={r[3]} — {'PASS (correctly flagged)' if r[3] == 'flagged' else 'FAIL'}")
    # Accuracy %
    correct = 0
    total = 0
    for r in results:
        if r[2] is None and "error" not in str(r[0]):
            continue
        if "SAME author" in r[0]:
            total += 1
            if r[3] == "verified":
                correct += 1
        else:
            total += 1
            if r[3] == "flagged":
                correct += 1
    pct = (100.0 * correct / total) if total else 0
    print()
    print(f"  Accuracy: {correct}/{total} = {pct:.1f}%")
    print("\nDone. Expected: 1 verified (Austen), all others flagged.")


if __name__ == "__main__":
    main()
