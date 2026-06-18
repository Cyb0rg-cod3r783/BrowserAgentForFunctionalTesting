"""
core/verifier.py — Evaluates test assertions against the current page state.
"""
from schema import Assertion


async def evaluate_assertions(page, assertions: list[Assertion]) -> list[dict]:
    """
    Evaluate a list of test assertions against the current page.
    
    Args:
        page: Playwright page object
        assertions: List of Assertion objects to evaluate
    
    Returns:
        List of dicts: {"type": ..., "expected": ..., "actual": ..., "passed": bool}
    """
    results = []

    for assertion in assertions:
        result = {
            "type": assertion.type,
            "expected": assertion.expected,
            "actual": None,
            "passed": False
        }

        try:
            if assertion.type == "url_contains":
                current_url = page.url
                result["actual"] = current_url
                result["passed"] = assertion.expected in current_url

            elif assertion.type == "element_visible":
                # Try to find by text first, then by label
                try:
                    locator = page.get_by_text(assertion.expected, exact=False)
                    visible = await locator.is_visible()
                except Exception:
                    visible = False

                if not visible and assertion.element_label:
                    try:
                        locator = page.get_by_label(assertion.element_label)
                        visible = await locator.is_visible()
                    except Exception:
                        visible = False

                result["actual"] = "visible" if visible else "not visible"
                result["passed"] = visible

            elif assertion.type == "text_equals":
                # expected format: "selector:::expected_text"
                if ":::" in assertion.expected:
                    selector, expected_text = assertion.expected.split(":::", 1)
                    try:
                        actual_text = await page.locator(selector.strip()).text_content()
                        result["actual"] = actual_text
                        result["passed"] = (actual_text or "").strip() == expected_text.strip()
                    except Exception as e:
                        result["actual"] = f"error: {e}"
                        result["passed"] = False
                else:
                    # Treat as text search
                    try:
                        locator = page.get_by_text(assertion.expected, exact=True)
                        visible = await locator.is_visible()
                        result["actual"] = "visible" if visible else "not found"
                        result["passed"] = visible
                    except Exception as e:
                        result["actual"] = f"error: {e}"
                        result["passed"] = False

            elif assertion.type == "element_count":
                # expected format: "selector:::count"
                if ":::" in assertion.expected:
                    selector, count_str = assertion.expected.split(":::", 1)
                    try:
                        actual_count = await page.locator(selector.strip()).count()
                        result["actual"] = str(actual_count)
                        result["passed"] = actual_count == int(count_str.strip())
                    except Exception as e:
                        result["actual"] = f"error: {e}"
                        result["passed"] = False
                else:
                    result["actual"] = "invalid format (use selector:::count)"
                    result["passed"] = False

            elif assertion.type == "element_absent":
                try:
                    locator = page.get_by_text(assertion.expected, exact=False)
                    visible = await locator.is_visible()
                except Exception:
                    visible = False

                result["actual"] = "absent" if not visible else "present"
                result["passed"] = not visible

            else:
                result["actual"] = f"unknown assertion type: {assertion.type}"
                result["passed"] = False

        except Exception as e:
            result["actual"] = f"error: {str(e)}"
            result["passed"] = False

        results.append(result)

    return results
