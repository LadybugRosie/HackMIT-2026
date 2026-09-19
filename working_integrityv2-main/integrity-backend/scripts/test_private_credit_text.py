#!/usr/bin/env python3
"""Test plagiarism v2 with the private credit news article text."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# Text from user (private credit article)
CONTENT = """For months, investors and analysts have kept a close eye on the shadowy corner of finance known as private credit, where alarm bells have stoked fears of a repeat of the 2008 financial crisis.

Whether those alarms amount to a handful of isolated bad bets or a more menacing systemic weakness in the $1.8 trillion sector is far from clear. But if the latter is even a remote possibility, it's worth understanding what the heck is going on.

A quick primer on 'private credit'
Very simply, the term refers to investors lending money directly to private businesses, bypassing banks. The borrowers — mostly smaller companies that banks would consider too risky or complex for a traditional loan — pay a higher interest rate in exchange for quick access to capital and flexible financing terms.

Here's how it usually works: Big asset managers (think Blackstone, better known for buying companies outright) pool funds from big investors like pensions or insurance companies looking for higher returns than they can find in, say, the bond market. Those private-credit funds lend money directly to businesses that may otherwise struggle to get loans.

It's not a new practice, but it became a much bigger business after the 2008 financial crisis, when governments tightened lending restrictions on banks.

Trouble is, private credit problems can quickly become public problems.

"You've got an opaque set of loans, in many cases, backing an opaque set of companies," Steve Sosnick, chief strategist at Interactive Brokers, told me. "You can come up with a scenario where it's unpleasant but relatively benign, but you can also come up with a scenario wherein a lot of mistakes are being papered over."

And while recent turmoil in private credit appears isolated, he said, the interconnected nature of financial markets would make a major blow-up everyone's problem if credit markets seize up and banks are forced to write down losses.

"That doesn't mean we're set up for a private credit disaster that will unfold the same way the subprime mortgage disaster unfolded," he said. At the same time, "there are echoes" of that earlier reckoning.

Blue Owl, Blackstone and Beyond
Blue Owl signage outside the Seagram Building at 375 Park Avenue in the Midtown East neighborhood of New York, on January 20.
Blue Owl signage outside the Seagram Building at 375 Park Avenue in the Midtown East neighborhood of New York, on January 20. Bing Guan/Bloomberg/Getty Images
In recent weeks, investors in private credit have been demanding their money back amid concerns that lenders overvalued loans tied to risky companies — many of which are software firms whose businesses may be disrupted by artificial intelligence. Some analysts expect AI to spark a wave of defaults among middle-market software and business service companies that became especially attractive to private lenders during the pandemic.

Much of the anxiety on Wall Street has focused on asset manager Blue Owl, which last month was hit with a surge of withdrawal requests, forcing it to halt redemptions and liquidate assets to repay its backers.

Although Blue Owl tried to reassure Wall Street that the decision was not a sign of weakness, the company's stock has taken a beating, falling 15% in the past two weeks. Bets that Blue Owl's stock will drop even more have also surged, with so-called short positions against the firm hitting an all-time high this week, according to data from analytics company S3 Partners."""


async def main():
    from app.services import plagiarism_v2

    print("=" * 60)
    print("PLAGIARISM V2 — Test run (private credit article)")
    print("=" * 60)
    print(f"Content length: {len(CONTENT)} chars, ~{len(CONTENT.split())} words")
    print()

    result = await plagiarism_v2.check_plagiarism_v2(
        content=CONTENT,
        check_internal=False,
        check_scholarly=True,
        check_web=True,
    )

    print("RESULT")
    print("-" * 60)
    print(f"Status:        {result.get('status', 'ok')}")
    print(f"Overall score: {result.get('overall_score', 0)}%")
    print(f"Duration:      {result.get('duration_ms', 0)} ms")
    print(f"Internal:      {result.get('internal_matches_count', 0)} matches")
    print(f"Scholarly:     {result.get('scholarly_matches_count', 0)} matches")
    print(f"Web:           {result.get('web_matches_count', 0)} matches")
    print()

    for label, key in [("Scholarly", "scholarly_matches"), ("Web", "web_matches")]:
        matches = result.get(key, [])
        if not matches:
            continue
        print(f"--- {label} matches (top 5) ---")
        for m in matches[:5]:
            title = (m.get("title") or m.get("url") or "?")[:70]
            score = m.get("similarity_score", 0)
            mtype = m.get("match_type", "")
            print(f"  {score}% ({mtype}): {title}")
        print()

    if result.get("overall_score", 0) >= 25:
        print("[EXPECTED] This text is likely from a news article; high web/scholarly match is normal.")
    else:
        print("[OK] Low overall score — engine ran successfully.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
