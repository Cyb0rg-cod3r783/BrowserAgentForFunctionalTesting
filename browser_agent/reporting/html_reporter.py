"""
reporting/html_reporter.py — Generates HTML test report using Jinja2.
Embeds failure screenshots as base64 inline images.
"""
import os
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from schema import TestResult
from utils.screenshots import screenshot_to_base64


async def generate_html_report(
    run_id: str,
    results: list[TestResult],
    db,
    output_path: str
) -> None:
    """
    Generate a self-contained HTML test report.
    
    Args:
        run_id: The test run ID
        results: List of TestResult objects
        db: Database instance (for fetching run metadata)
        output_path: Where to write the HTML file
    """
    # Get run metadata
    run_data = None
    try:
        # Try to get from DB by looking at results
        pass
    except Exception:
        pass

    # Calculate summary
    total = len(results)
    passed = sum(1 for r in results if r.status == "passed")
    failed = sum(1 for r in results if r.status == "failed")
    errored = sum(1 for r in results if r.status == "errored")
    total_duration_ms = sum(r.duration_ms for r in results)
    pass_rate = (passed / total * 100) if total > 0 else 0.0

    summary = {
        "total": total,
        "passed": passed,
        "failed": failed,
        "errored": errored,
        "duration_s": total_duration_ms / 1000
    }

    import aiosqlite
    import json

    # Pre-fetch all test case steps for this run's test cases
    test_case_steps = {}
    try:
        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            tc_ids = list(set(r.test_case_id for r in results))
            for tc_id in tc_ids:
                async with conn.execute("SELECT steps FROM test_cases WHERE id = ?", (tc_id,)) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        steps = json.loads(row["steps"])
                        # Map sequence -> value
                        test_case_steps[tc_id] = {s["sequence"]: s.get("value") for s in steps}
    except Exception:
        pass

    # Enrich results with base64 screenshots
    enriched_results = []
    for result in results:
        result_dict = result.model_dump()

        # Embed failure screenshot
        result_dict["failure_screenshot_b64"] = ""
        if result.failure_screenshot:
            result_dict["failure_screenshot_b64"] = screenshot_to_base64(
                result.failure_screenshot
            )

        # Embed step screenshots and values
        tc_steps = test_case_steps.get(result.test_case_id, {})
        for step in result_dict.get("step_results", []):
            step["screenshot_b64"] = ""
            if step.get("screenshot_path"):
                step["screenshot_b64"] = screenshot_to_base64(step["screenshot_path"])
            step["value"] = tc_steps.get(step["sequence"])

        # Add placeholder diagnosis (no LLM call here to keep it simple)
        result_dict["diagnosis"] = None
        if result.status != "passed" and result.error_detail:
            result_dict["diagnosis"] = {
                "likely_cause": "Test execution encountered an error.",
                "category": "bug",
                "suggested_action": "Review the error detail and check the application state."
            }

        enriched_results.append(result_dict)

    # Render template
    template_dir = Path(__file__).parent / "templates"
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    template = env.get_template("report.html")

    html_content = template.render(
        run_id=run_id,
        results=enriched_results,
        summary=summary,
        pass_rate=pass_rate,
        generated_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    )

    # Write output
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
