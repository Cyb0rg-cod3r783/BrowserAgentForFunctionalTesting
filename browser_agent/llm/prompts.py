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
