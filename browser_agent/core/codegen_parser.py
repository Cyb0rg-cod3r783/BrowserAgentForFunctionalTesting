"""
core/codegen_parser.py — Parses Playwright codegen JS output into structured steps.

Playwright codegen (npx playwright codegen --target javascript) produces code like:
    await page.goto('https://...');
    await page.getByRole('textbox', { name: 'Email ID' }).fill('admin@...');
    await page.getByRole('link', { name: 'Log in' }).click();
    await page.locator('#txtCP1_Contact').click();

This module converts that into a list of dicts our model_builder can consume.
"""
import re


def parse_playwright_js(js_code: str) -> list[dict]:
    """
    Parse Playwright JS codegen output into a list of structured step dicts.

    Each step is one of:
      {"step_type": "navigate", "url": "https://..."}
      {"step_type": "action", "locator_type": "role",      "role": "textbox", "name": "Email ID", "nth": None, "action": "fill",  "value": "admin@..."}
      {"step_type": "action", "locator_type": "role",      "role": "link",    "name": "Log in",   "nth": None, "action": "click", "value": None}
      {"step_type": "action", "locator_type": "id",        "selector": "txtCP1_Contact",           "nth": None, "action": "click", "value": None}
      {"step_type": "action", "locator_type": "css",       "selector": "input[name='x']",          "nth": None, "action": "click", "value": None}
      {"step_type": "action", "locator_type": "text",      "text": "Some visible text",            "nth": None, "action": "click", "value": None}
      {"step_type": "action", "locator_type": "aria_label","name": "Email ID",                     "nth": None, "action": "fill",  "value": "..."}
      {"step_type": "action", "locator_type": "placeholder","name": "Password",                    "nth": None, "action": "fill",  "value": "..."}
    """
    steps: list[dict] = []
    current_url = ""

    for raw_line in js_code.splitlines():
        line = raw_line.strip()

        # Only process 'await page.' lines
        if not line.startswith("await page."):
            continue

        # ── 1. page.goto ────────────────────────────────────────────────────
        m = re.match(r"await page\.goto\(['\"]([^'\"]+)['\"]\)", line)
        if m:
            current_url = m.group(1)
            steps.append({"step_type": "navigate", "url": current_url})
            continue

        # ── 2. page.getByRole('role', { name: '...' })[.first()/.nth(n)].<action>(args)
        m = re.match(
            r"await page\.getByRole\("
            r"['\"](\w+)['\"]"                         # role
            r",\s*\{"
            r"[^}]*\bname:\s*['\"]([^'\"]+)['\"]"     # name
            r"[^}]*\}"
            r"\)"
            r"(\.first\(\)|\.nth\(\d+\))?"             # optional nth/first
            r"\.([\w]+)"                               # action method
            r"\(([^)]*)\)",                            # action args
            line,
        )
        if m:
            role, name, nth_raw, action, args = m.groups()
            nth = _parse_nth(nth_raw)
            value = _extract_string_arg(args) if action == "fill" else None
            if action not in ("click", "fill", "check", "press", "dblclick", "hover"):
                continue
            steps.append({
                "step_type": "action",
                "locator_type": "role",
                "role": role,
                "name": name,
                "nth": nth,
                "action": action,
                "value": value,
                "url": current_url,
            })
            continue

        # ── 3. page.locator('selector')[.first()/.nth(n)].<action>(args)
        m = re.match(
            r"await page\.locator\(['\"]([^'\"]+)['\"]\)"
            r"(\.first\(\)|\.nth\(\d+\))?"
            r"\.([\w]+)"
            r"\(([^)]*)\)",
            line,
        )
        if m:
            selector, nth_raw, action, args = m.groups()
            nth = _parse_nth(nth_raw)
            value = _extract_string_arg(args) if action == "fill" else None
            if action not in ("click", "fill", "check", "press", "dblclick", "hover"):
                continue

            # Distinguish #id vs css vs xpath
            if selector.startswith("#"):
                locator_type = "id"
                selector = selector[1:]  # strip the '#'
            elif selector.startswith("//") or selector.startswith(".."):
                locator_type = "xpath"
            else:
                locator_type = "css"

            steps.append({
                "step_type": "action",
                "locator_type": locator_type,
                "selector": selector,
                "nth": nth,
                "action": action,
                "value": value,
                "url": current_url,
            })
            continue

        # ── 4. page.getByText('text')[.first()/.nth(n)].<action>(args)
        m = re.match(
            r"await page\.getByText\(['\"]([^'\"]+)['\"]\)"
            r"(\.first\(\)|\.nth\(\d+\))?"
            r"\.([\w]+)"
            r"\(([^)]*)\)",
            line,
        )
        if m:
            text, nth_raw, action, args = m.groups()
            nth = _parse_nth(nth_raw)
            if action not in ("click", "fill", "check", "press", "dblclick", "hover"):
                continue
            steps.append({
                "step_type": "action",
                "locator_type": "text",
                "text": text,
                "nth": nth,
                "action": action,
                "value": None,
                "url": current_url,
            })
            continue

        # ── 5. page.getByLabel('label')[.first()/.nth(n)].<action>(args)
        m = re.match(
            r"await page\.getByLabel\(['\"]([^'\"]+)['\"]\)"
            r"(\.first\(\)|\.nth\(\d+\))?"
            r"\.([\w]+)"
            r"\(([^)]*)\)",
            line,
        )
        if m:
            label, nth_raw, action, args = m.groups()
            nth = _parse_nth(nth_raw)
            value = _extract_string_arg(args) if action == "fill" else None
            if action not in ("click", "fill", "check", "press", "dblclick", "hover"):
                continue
            steps.append({
                "step_type": "action",
                "locator_type": "aria_label",
                "name": label,
                "nth": nth,
                "action": action,
                "value": value,
                "url": current_url,
            })
            continue

        # ── 6. page.getByPlaceholder('placeholder')[...].<action>(args)
        m = re.match(
            r"await page\.getByPlaceholder\(['\"]([^'\"]+)['\"]\)"
            r"(\.first\(\)|\.nth\(\d+\))?"
            r"\.([\w]+)"
            r"\(([^)]*)\)",
            line,
        )
        if m:
            placeholder, nth_raw, action, args = m.groups()
            nth = _parse_nth(nth_raw)
            value = _extract_string_arg(args) if action == "fill" else None
            if action not in ("click", "fill", "check", "press", "dblclick", "hover"):
                continue
            steps.append({
                "step_type": "action",
                "locator_type": "placeholder",
                "name": placeholder,
                "nth": nth,
                "action": action,
                "value": value,
                "url": current_url,
            })
            continue

    return steps


def _extract_string_arg(args: str) -> str | None:
    """Extract the first string argument from a function call args string."""
    args = args.strip()
    if not args:
        return None
    m = re.match(r"['\"](.+?)['\"]$", args) or re.match(r"['\"](.+?)['\"]", args)
    if m:
        return m.group(1)
    return None


def _parse_nth(nth_raw: str | None) -> int | None:
    """Parse .first() -> 0, .nth(N) -> N, None -> None."""
    if nth_raw is None:
        return None
    if "first" in nth_raw:
        return 0
    m = re.search(r"nth\((\d+)\)", nth_raw)
    if m:
        return int(m.group(1))
    return None
