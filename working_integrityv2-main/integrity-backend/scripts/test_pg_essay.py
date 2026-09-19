#!/usr/bin/env python3
"""Quick test: Run Paul Graham's 'Bus Ticket Theory of Genius' through plagiarism v2."""

import asyncio
import json
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from app.services.plagiarism_v2 import check_plagiarism_v2, set_collections

# We need MongoDB for internal checks — but we can test scholarly+web without it
# by passing check_internal=False. For a full test, connect to MongoDB.

TEXT = """The Bus Ticket Theory of Genius

November 2019

Everyone knows that to do great work you need both natural ability and determination. But there's a third ingredient that's not as well understood: an obsessive interest in a particular topic.

To explain this point I need to burn my reputation with some group of people, and I'm going to choose bus ticket collectors. There are people who collect old bus tickets. Like many collectors, they have an obsessive interest in the minutiae of what they collect. They can keep track of distinctions between different types of bus tickets that would be hard for the rest of us to remember. Because we don't care enough. What's the point of spending so much time thinking about old bus tickets?

Which leads us to the second feature of this kind of obsession: there is no point. A bus ticket collector's love is disinterested. They're not doing it to impress us or to make themselves rich, but for its own sake.

When you look at the lives of people who've done great work, you see a consistent pattern. They often begin with a bus ticket collector's obsessive interest in something that would have seemed pointless to most of their contemporaries. One of the most striking features of Darwin's book about his voyage on the Beagle is the sheer depth of his interest in natural history. His curiosity seems infinite. Ditto for Ramanujan, sitting by the hour working out on his slate what happens to series.

It's a mistake to think they were "laying the groundwork" for the discoveries they made later. There's too much intention in that metaphor. Like bus ticket collectors, they were doing it because they liked it.

But there is a difference between Ramanujan and a bus ticket collector. Series matter, and bus tickets don't.

If I had to put the recipe for genius into one sentence, that might be it: to have a disinterested obsession with something that matters.

Aren't I forgetting about the other two ingredients? Less than you might think. An obsessive interest in a topic is both a proxy for ability and a substitute for determination. Unless you have sufficient mathematical aptitude, you won't find series interesting. And when you're obsessively interested in something, you don't need as much determination: you don't need to push yourself as hard when curiosity is pulling you.

An obsessive interest will even bring you luck, to the extent anything can. Chance, as Pasteur said, favors the prepared mind, and if there's one thing an obsessed mind is, it's prepared.

The disinterestedness of this kind of obsession is its most important feature. Not just because it's a filter for earnestness, but because it helps you discover new ideas.

The paths that lead to new ideas tend to look unpromising. If they looked promising, other people would already have explored them. How do the people who do great work discover these paths that others overlook? The popular story is that they simply have better vision: because they're so talented, they see paths that others miss. But if you look at the way great discoveries are made, that's not what happens. Darwin didn't pay closer attention to individual species than other people because he saw that this would lead to great discoveries, and they didn't. He was just really, really interested in such things.

Darwin couldn't turn it off. Neither could Ramanujan. They didn't discover the hidden paths that they did because they seemed promising, but because they couldn't help it. That's what allowed them to follow paths that someone who was merely ambitious would have ignored.

What rational person would decide that the way to write great novels was to begin by spending several years creating an imaginary elvish language, like Tolkien, or visiting New York slaughterhouses, like Upton Sinclair? And yet that's the kind of thing great minds do. They don't do it because they're intentionally laying the groundwork for some grand plan; they do it because the subject matter fascinates them, and they can't help themselves."""


async def main():
    t0 = time.time()
    print("Running plagiarism v2 check on Paul Graham essay (scholarly + web)...")
    print(f"Text length: {len(TEXT)} chars\n")

    result = await check_plagiarism_v2(
        content=TEXT,
        title="The Bus Ticket Theory of Genius",
        check_internal=False,   # no MongoDB needed
        check_scholarly=True,
        check_web=True,
    )

    elapsed = time.time() - t0
    print(f"\nCompleted in {elapsed:.1f}s")
    print(f"Overall score: {result.get('overall_score', 'N/A')}")
    print(f"Scholarly matches: {result.get('scholarly_matches_count', 0)}")
    print(f"Web matches: {result.get('web_matches_count', 0)}")
    print(f"Check ID: {result.get('check_id', 'N/A')}")

    for key in ("scholarly_matches", "web_matches"):
        matches = result.get(key, [])
        if matches:
            print(f"\n--- {key} ---")
            for m in matches[:5]:
                print(f"  Score: {m.get('similarity_score', 0):.1f}%  "
                      f"Title: {m.get('title', m.get('url', 'N/A'))[:80]}")

    # Dump full result
    print("\n--- Full JSON ---")
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
