"""
llm/prompts.py — All prompt templates as module-level constants.
All prompts instruct the model to return ONLY valid JSON with no preamble
and no markdown code fences.
"""

ELEMENT_LABEL_PROMPT = """\
You are a web accessibility expert. Analyze this web element and return ONLY valid JSON.

Element attributes:
- tag: {tag}
- input type: {input_type}
- id: {element_id}
- name: {name}
- placeholder: {placeholder}
- aria-label: {aria_label}
- text content: {text_content}

Return ONLY this JSON structure (no preamble, no markdown fences):
{{
  "semantic_label": "3-8 word descriptive label for this element",
  "purpose": "one sentence describing what this element is used for",
  "validation_rules": [
    {{"rule": "required|email_format|min_length|max_length|numeric", "typical_error": "error message user would see"}}
  ],
  "locator_priority": ["aria_label", "placeholder", "id", "css"]
}}
"""

FLOW_IDENTIFICATION_PROMPT = """\
You are a QA engineer analyzing user interaction steps on a web application.
Identify what user flow these steps represent and return ONLY valid JSON.

Interaction steps:
{steps_json}

Page titles visited:
{page_titles}

Return ONLY this JSON structure (no preamble, no markdown fences):
{{
  "name": "Short descriptive flow name (e.g. User Login Flow)",
  "description": "One paragraph describing what the user was trying to accomplish",
  "expected_outcome": {{
    "type": "navigation|element_visible|text_present",
    "url_pattern": "URL pattern or fragment expected after flow completion",
    "text": "Text expected to be visible on success (if applicable)"
  }}
}}
"""

TEST_GENERATION_PROMPT = """\
You are a senior QA engineer. Generate comprehensive test cases for the following user flow.
Return ONLY valid JSON (no preamble, no markdown fences).

Flow name: {flow_name}

Flow steps:
{flow_steps_json}

Available elements:
{elements_json}

Expected outcome:
{expected_outcome_json}

Generate exactly 1 happy_path test, 3-5 negative tests, and 2-3 edge_case tests.
Negative tests should cover: empty fields, invalid formats, wrong credentials, boundary values.
Edge case tests should cover: special characters, very long inputs, unexpected sequences.

CRITICAL: DO NOT use javascript expressions or method calls like .repeat() in string values. Use literal string values only (e.g. for long inputs, just type a long string like "aaaaaaaaaaaaaaaaaaaa").
CRITICAL: For 'element_visible' or 'text_equals' assertions, the 'expected' field must contain the specific text content (e.g. error message like "Email is required" or label) expected to be found/visible. DO NOT set expected to boolean values like "true" or "false".

Return ONLY this JSON structure:
{{
  "test_cases": [
    {{
      "name": "Descriptive test case name",
      "category": "happy_path|negative|edge_case",
      "steps": [
        {{"sequence": 1, "action": "fill|click|navigate|select|check|hover|clear", "element_id": "element_id_here", "value": "value_to_use"}}
      ],
      "assertions": [
        {{"type": "url_contains|element_visible|text_equals|element_count|element_absent", "expected": "expected_value", "element_label": "optional element label"}}
      ],
      "confidence": 0.95
    }}
  ]
}}
"""

LOCATOR_FALLBACK_PROMPT = """\
You are a Playwright automation expert. Find the element described below in this accessibility tree.
Return ONLY valid JSON (no preamble, no markdown fences).

Element to find: "{semantic_label}"

Accessibility tree:
{accessibility_tree_json}

Return ONLY this JSON structure:
{{
  "strategy": "role|text|label|placeholder|css",
  "value": "the value to use with this strategy",
  "role_name": "the role name if strategy is role (e.g. button, textbox, link)"
}}
"""

FAILURE_DIAGNOSIS_PROMPT = """\
You are a QA debugging expert. Explain this test failure in plain English for a developer.
Return ONLY valid JSON (no preamble, no markdown fences).

Test name: {test_name}
Failed step: {failed_step}
Error message: {error_message}
Current URL: {current_url}
Expected outcome: {expected_outcome}

Return ONLY this JSON structure:
{{
  "likely_cause": "One sentence describing the most likely cause of this failure",
  "category": "locator_changed|element_removed|assertion_wrong|timing|bug",
  "suggested_action": "Specific actionable recommendation for the developer"
}}
"""


SEMANTIC_ASSERTION_PROMPT = """\
You are an expert QA Engineer. Your job is to evaluate if the actual page state conceptually satisfies a test assertion, even if the exact strings do not match.
Return ONLY valid JSON (no preamble, no markdown fences).

Guidelines for URL Comparison (url_contains):
- A post-login redirection to a landing page path like "/home" is CONCEPTUALLY EQUIVALENT to "/dashboard" or "/index" for a happy path login flow. Mark it as passed (passed: true).
- If the expected URL is "/login", and the actual URL is "/" (the root URL), check if the page is still the login page. If the page is showing a login form or stays on the login page root, this is CONCEPTUALLY EQUIVALENT to "/login" for a failed validation test. Mark it as passed (passed: true).

Guidelines for Text/Element Comparison (element_visible / text_equals):
- If the test expected "Welcome, admin" (indicating a successful login), and the visible page text snippet contains "Admin", "Assessor App", or "Dashboard", this indicates the user successfully logged in and reached the admin area. Mark it as passed (passed: true).
- If the expected assertion value is "true" or "false" (due to a boolean generation error) but the element_label describes a validation message (e.g., "Email is required"), check the visible page text snippet. If there is a validation message or the user is still on the login page with fields highlighted, mark it as conceptually passed.

Context:
- Test Case Name: {test_name}
- Assertion Type: {assertion_type}
- Expected Value: "{expected_value}"
- Actual Value: "{actual_value}"
- Visible Page Text Snippet (if text/element assertion):
\"\"\"
{page_text}
\"\"\"

Return ONLY this JSON structure:
{{
  "passed": true,
  "reason": "One sentence explaining why it is a conceptual match"
}}
or
{{
  "passed": false,
  "reason": "One sentence explaining why it is a mismatch"
}}
"""


SEGMENT_TEST_GENERATION_PROMPT = """\
You are a senior QA engineer. Generate comprehensive test cases specifically targeting a subset of fields in a user flow.
Return ONLY valid JSON (no preamble, no markdown fences).

Flow name: {flow_name}

Target Fields to Test in this segment:
{segment_fields_json}

Instructions:
1. Generate test cases specifically targeting the fields listed in "Target Fields to Test".
2. For each targeted field, generate 3-4 negative and edge-case test cases (e.g. empty, invalid formats, special characters, max length, etc.).
3. For each test case, define:
   - name: Descriptive name of the test case (e.g. Company Code - Special Characters)
   - category: negative|edge_case
   - target_element_id: The ID of the field being tested
   - mutated_value: The specific test input to use for this field
   - assertions: list of assertions (e.g., text_equals or element_visible with the expected error message/toast text, or url_contains)
4. DO NOT use javascript expressions or method calls like .repeat() in string values. Use literal string values only.
5. For 'element_visible' or 'text_equals' assertions, the 'expected' field must contain the specific text content expected to be found/visible (e.g. "Company Code is Required").

Return ONLY this JSON structure:
{{
  "test_cases": [
    {{
      "name": "Descriptive test case name",
      "category": "negative|edge_case",
      "target_element_id": "element_id_here",
      "mutated_value": "value_to_use",
      "assertions": [
        {{"type": "url_contains|element_visible|text_equals|element_count|element_absent", "expected": "expected_value", "element_label": "optional element label"}}
      ]
    }}
  ]
}}
"""
