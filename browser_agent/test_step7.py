"""
Step 7 verification — generates a static HTML report from DB results.
Run from: c:\Projects\Antigravity Browsing agent\browser_agent\
Usage: python -X utf8 test_step7.py

Uses the results generated in Step 6 to output report.html.
"""
import asyncio
import os
import sys
from dotenv import load_dotenv

load_dotenv(".env")
sys.stdout.reconfigure(encoding='utf-8')

from storage.db import Database
# from reporting.generator import ReportGenerator (removed)


async def main():
    db = Database("./browser_agent.db")
    await db.initialize()

    # Load the latest app
    apps = await db.list_applications()
    if not apps:
        print("FAIL - No apps in DB. Run previous steps first.")
        return
    app = await db.get_application(apps[-1]["id"])

    print(f"Generating report for app: '{app.name}'...")

    # Load test cases
    test_cases = await db.get_test_cases_for_app(app.id)
    if not test_cases:
        print("FAIL - No test cases found.")
        return

    # Find the most recent run_id from results
    import aiosqlite
    async with aiosqlite.connect("./browser_agent.db") as db_conn:
        db_conn.row_factory = aiosqlite.Row
        async with db_conn.execute(
            "SELECT id FROM test_runs ORDER BY started_at DESC LIMIT 1"
        ) as cursor:
            row = await cursor.fetchone()
        
    if not row:
        print("FAIL - No test results found in DB. Run test_step6.py first.")
        return
        
    run_id = row["id"]
    print(f"Found run_id: {run_id}")

    # Generate HTML report
    from reporting.html_reporter import generate_html_report
    import json
    from schema import TestResult
    
    # We need to fetch the TestResult objects for the run_id
    test_cases_map = {tc.id: tc for tc in test_cases}
    results = []
    
    async with aiosqlite.connect("./browser_agent.db") as db_conn:
        db_conn.row_factory = aiosqlite.Row
        async with db_conn.execute("SELECT * FROM test_results WHERE run_id = ?", (run_id,)) as cursor:
            rows = await cursor.fetchall()
            for row in rows:
                result = TestResult(
                    id=row["id"],
                    test_case_id=row["test_case_id"],
                    test_name=test_cases_map.get(row["test_case_id"]).name if row["test_case_id"] in test_cases_map else "Unknown Test",
                    run_id=row["run_id"],
                    category=row["category"],
                    status=row["status"],
                    duration_ms=row["duration_ms"],
                    error_detail=row["error_detail"],
                    step_results=json.loads(row["step_results"] or "[]"),
                    assertion_results=json.loads(row["assertion_results"] or "[]"),
                    failure_screenshot=row["failure_screenshot"]
                )
                results.append(result)
            
    try:
        report_path = "./reports/report.html"
        await generate_html_report(run_id, results, db, output_path=report_path)
        print(f"\nReport generated successfully at: {report_path}")
        
        # Simple verification checks
        if os.path.exists(report_path):
            with open(report_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if run_id[:8] in content:
                    print("Report content verified.")
                    print("Reporting OK")
                else:
                    print("FAIL - Report generated but expected content missing.")
        else:
            print("FAIL - Report file not found after generation.")
            
    except Exception as e:
        print(f"FAIL - Report generation threw exception: {e}")
        import traceback
        traceback.print_exc()

asyncio.run(main())
