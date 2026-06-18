"""
Step 5 verification — generates test cases from the ApplicationModel built in Step 4.
Run from: c:\Projects\Antigravity Browsing agent\browser_agent\
Usage: python -X utf8 test_step5.py

Uses the ApplicationModel already stored in browser_agent.db from Step 4.
Generates test cases and prints them with category breakdown.
"""
import asyncio
import sys
from dotenv import load_dotenv

load_dotenv(".env")
sys.stdout.reconfigure(encoding='utf-8')

from storage.db import Database
from core.test_generator import TestGenerator
from llm.client import LLMClient


async def main():
    db = Database("./browser_agent.db")
    await db.initialize()
    llm = LLMClient()

    # Load the most recently recorded app
    apps = await db.list_applications()
    if not apps:
        print("FAIL - No apps in DB. Run test_step4.py first.")
        return

    # Get the latest app (last in list)
    app_row = apps[-1]
    app_id = app_row["id"]
    app = await db.get_application(app_id)

    if not app:
        print("FAIL - Could not load app from DB.")
        return

    print(f"Using app: '{app.name}' (ID: {app.id[:16]}...)")
    print(f"Flows: {len(app.flows)}")
    print(f"Elements: {len(app.elements)}")

    if not app.flows:
        print("FAIL - No flows found. Re-run test_step4.py first.")
        return

    # Generate test cases for the first (login) flow
    generator = TestGenerator()
    flow = app.flows[0]
    print(f"\nGenerating tests for flow: '{flow.name}'")
    print("Calling LLM for negative + edge cases (may take 20-40s)...")
    print()

    test_cases = await generator.generate(flow, app.elements, llm)

    # Print all test cases and save them to the database
    print("=" * 60)
    print(f"Generated {len(test_cases)} test case(s):")
    print("=" * 60)

    for tc in test_cases:
        await db.save_test_case(tc)
        print(f"\n  [{tc.category.upper()}] {tc.name}")
        print(f"    Confidence : {tc.confidence:.2f}")
        print(f"    Steps      : {len(tc.steps)}")
        for s in tc.steps[:3]:
            val = f" = '{s.value[:20]}'" if s.value else ""
            print(f"      Step {s.sequence}: {s.action}{val}")
        if len(tc.steps) > 3:
            print(f"      ... ({len(tc.steps) - 3} more steps)")
        print(f"    Assertions : {len(tc.assertions)}")
        for a in tc.assertions:
            print(f"      - {a.type}: '{a.expected[:50]}'")

    # Category summary
    categories = {}
    for tc in test_cases:
        categories[tc.category] = categories.get(tc.category, 0) + 1

    print("\n" + "=" * 60)
    print("Category breakdown:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")

    # Assertions
    happy_count = categories.get("happy_path", 0)
    negative_count = categories.get("negative", 0)

    passed = True
    if happy_count != 1:
        print(f"\nFAIL - Expected exactly 1 happy_path, got {happy_count}")
        passed = False
    if negative_count < 3:
        print(f"\nFAIL - Expected at least 3 negative tests, got {negative_count}")
        passed = False

    if passed:
        print("\nTest Generator OK")
    else:
        print("\nFAIL - Test Generator verification failed")


asyncio.run(main())
