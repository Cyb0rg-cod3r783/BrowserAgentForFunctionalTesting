"""
Step 4 verification — records a session then builds the ApplicationModel.
Run from: c:\Projects\Antigravity Browsing agent\browser_agent\
Usage: python -X utf8 test_step4.py

Phase 1: Records 20s session on login page (fill form + click login)
Phase 2: Builds ApplicationModel using LLM and prints summary
"""
import asyncio
import json
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(".env")
sys.stdout.reconfigure(encoding='utf-8')

from core.recorder import BrowserRecorder
from core.model_builder import ModelBuilder
from storage.db import Database
from llm.client import LLMClient


async def main():
    db = Database("./browser_agent.db")
    await db.initialize()
    llm = LLMClient()

    # ── Phase 1: Record ────────────────────────────────────────────────
    print("=" * 60)
    print("PHASE 1: Recording")
    print("  Browser opens at https://the-internet.herokuapp.com/login")
    print("  Fill in: tomsmith / SuperSecretPassword! then click Login")
    print("  Auto-closes in 20 seconds.")
    print("=" * 60)

    recorder = BrowserRecorder(
        "https://the-internet.herokuapp.com/login",
        "test_login_app",
        "./screenshots"
    )

    try:
        await asyncio.wait_for(recorder.start_session(), timeout=20)
    except (asyncio.TimeoutError, KeyboardInterrupt):
        pass

    session_data = await recorder.stop_session()

    events_count = len(session_data.get("events", []))
    nav_count = len(session_data.get("navigations", []))
    print(f"\nRecorded: {events_count} events, {nav_count} navigations")

    if events_count == 0:
        print("FAIL - No events captured. Run again and interact with the form.")
        return

    # Save session to JSON
    with open("session_test.json", "w", encoding="utf-8") as f:
        json.dump(session_data, f, indent=2, default=str)
    print("Session saved to session_test.json")

    # ── Phase 2: Build Model ──────────────────────────────────────────
    print("\n" + "=" * 60)
    print("PHASE 2: Building ApplicationModel (calling LLM...)")
    print("=" * 60)

    builder = ModelBuilder()
    app_model = await builder.build(session_data, "test_login_app", db, llm)

    # ── Summary ───────────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print("ApplicationModel Summary:")
    print(f"  App ID    : {app_model.id[:16]}...")
    print(f"  App Name  : {app_model.name}")
    print(f"  Base URL  : {app_model.base_url}")
    print(f"  Version   : {app_model.version.label}")
    print(f"\n  Pages     : {len(app_model.pages)}")
    for p in app_model.pages:
        print(f"    - {p.url_pattern} | '{p.title}'")

    print(f"\n  Elements  : {len(app_model.elements)}")
    for e in app_model.elements:
        print(f"    - [{e.element_type}] '{e.semantic_label}'")

    print(f"\n  Flows     : {len(app_model.flows)}")
    for f in app_model.flows:
        print(f"    - '{f.name}'")
        print(f"      steps: {len(f.steps)} | outcome: {f.expected_outcome.type}")

    print()

    # Assertions
    passed = True
    if len(app_model.pages) < 1:
        print("FAIL - Expected at least 1 page")
        passed = False
    if len(app_model.elements) < 2:
        print("FAIL - Expected at least 2 elements (username + password)")
        passed = False
    if len(app_model.flows) < 1:
        print("FAIL - Expected at least 1 flow")
        passed = False
    if app_model.flows and app_model.flows[0].name.lower().startswith("flow_"):
        print("FAIL - Flow name appears auto-generated, not LLM-generated")
        passed = False

    if passed:
        print("Model Builder OK")
    else:
        print("FAIL - Model Builder verification failed")


asyncio.run(main())
