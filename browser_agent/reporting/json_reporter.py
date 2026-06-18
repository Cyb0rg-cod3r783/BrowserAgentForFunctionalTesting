"""
reporting/json_reporter.py — Generates JSON test report for CI/CD.
"""
import json
from datetime import datetime
from pathlib import Path

from schema import TestResult


def generate_json_report(
    run_id: str,
    results: list[TestResult],
    output_path: str,
    app_name: str = ""
) -> None:
    """
    Generate a JSON test report.
    
    Args:
        run_id: The test run ID
        results: List of TestResult objects
        output_path: Where to write the JSON file
        app_name: Name of the application under test
    """
    total = len(results)
    passed = sum(1 for r in results if r.status == "passed")
    failed = sum(1 for r in results if r.status == "failed")
    errored = sum(1 for r in results if r.status == "errored")
    total_duration_ms = sum(r.duration_ms for r in results)

    report = {
        "run_id": run_id,
        "app": app_name,
        "generated_at": datetime.utcnow().isoformat(),
        "summary": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "errored": errored,
        },
        "duration_seconds": total_duration_ms / 1000,
        "test_results": [
            {
                "id": r.id,
                "test_case_id": r.test_case_id,
                "test_name": r.test_name,
                "category": r.category,
                "status": r.status,
                "duration_ms": r.duration_ms,
                "step_results": [
                    {
                        "sequence": s.sequence,
                        "action": s.action,
                        "element_label": s.element_label,
                        "status": s.status,
                        "locator_used": s.locator_used,
                        "error": s.error,
                    }
                    for s in r.step_results
                ],
                "assertion_results": r.assertion_results,
                "error_detail": r.error_detail,
            }
            for r in results
        ]
    }

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
