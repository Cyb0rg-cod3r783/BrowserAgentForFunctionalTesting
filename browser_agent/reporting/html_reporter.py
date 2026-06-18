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

        # Embed step screenshots
        for step in result_dict.get("step_results", []):
            step["screenshot_b64"] = ""
            if step.get("screenshot_path"):
                step["screenshot_b64"] = screenshot_to_base64(step["screenshot_path"])

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
