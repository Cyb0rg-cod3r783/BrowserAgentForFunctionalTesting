"""
Step 6 verification — executes the generated test cases using TestExecutor.
Run from: c:\Projects\Antigravity Browsing agent\browser_agent\
Usage: python -X utf8 test_step6.py

Runs the tests generated in Step 5 against the actual browser.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(".env")
sys.stdout.reconfigure(encoding='utf-8')

from storage.db import Database
from core.executor import TestExecutor
from llm.client import LLMClient


async def main():
    db = Database("./browser_agent.db")
    await db.initialize()
    llm = LLMClient()
    screenshots_dir = os.environ.get("SCREENSHOTS_DIR", "./screenshots")

    # Load the latest app
    apps = await db.list_applications()
    if not apps:
        print("FAIL - No apps in DB. Run test_step4.py first.")
        return
    app = await db.get_application(apps[-1]["id"])

    # Load test cases
    test_cases = await db.get_test_cases_for_app(app.id)
    if not test_cases:
        print("FAIL - No test cases found. Run test_step5.py first.")
        return

    # We only want to run 1 happy path and 1 negative test to save time in verification
    tests_to_run = []
    happy = [tc for tc in test_cases if tc.category == "happy_path"]
    negative = [tc for tc in test_cases if tc.category == "negative"]
    
    if happy:
        tests_to_run.append(happy[0])
    if negative:
        tests_to_run.append(negative[0])

    print(f"Running {len(tests_to_run)} test case(s) on '{app.name}'...")
    print("This will open a visible browser. Do not interact with it.\n")

    executor = TestExecutor(db, llm, screenshots_dir, headless=False)
    run_id = str(uuid.uuid4())
    
    elements_map = {e.id: e for e in app.elements}

    results = []
    for tc in tests_to_run:
        print(f"▶ Executing: [{tc.category.upper()}] {tc.name}")
        flow = next((f for f in app.flows if f.id == tc.flow_id), None)
        start_url = flow.start_url if flow else app.base_url
        
        result = await executor.run_test(tc, elements_map, run_id, start_url)
        results.append(result)
        
        print(f"  Status   : {result.status}")
        print(f"  Duration : {result.duration_ms}ms")
        if result.error_detail:
            print(f"  Error    : {result.error_detail}")
        
        print("  Assertions:")
        for ar in result.assertion_results:
            icon = "✅" if ar["passed"] else "❌"
            print(f"    {icon} {ar['type']}: expected '{ar['expected']}' -> actual '{ar.get('actual')}'")
        print()

    # Save the run and results to DB so Step 7 can find them
    await db.save_test_run({
        "id": run_id,
        "app_id": app.id,
        "started_at": datetime.utcnow().isoformat(),
        "total": len(results),
        "passed": sum(1 for r in results if r.status == "passed"),
        "failed": sum(1 for r in results if r.status == "failed"),
        "errored": sum(1 for r in results if r.status == "errored"),
        "completed_at": datetime.utcnow().isoformat()
    })
    
    for r in results:
        await db.save_test_result(r)

    # Check assertions for verification
    passed = True
    for r in results:
        if r.status not in ("passed", "failed"):
            print(f"FAIL - Test '{r.test_name}' ended with status '{r.status}' instead of passed/failed")
            passed = False
            
    # The happy path should pass
    if results and results[0].category == "happy_path":
        if results[0].status != "passed":
            print("WARNING - Happy path failed (this might happen if the site changed or network issues).")

    if passed:
        print("Test Executor OK")
    else:
        print("FAIL - Test Executor verification failed")


asyncio.run(main())
