"""
core/test_generator.py — Derives TestCase objects from UserFlows using LLM.
"""
import uuid
from datetime import datetime

from schema import (
    UserFlow, ElementModel, TestCase, TestStep, Assertion
)
from llm.prompts import TEST_GENERATION_PROMPT


class TestGenerator:
    async def generate(
        self,
        flow: UserFlow,
        elements: list[ElementModel],
        llm_client
    ) -> list[TestCase]:
        """
        Generate test cases for a given user flow.
        
        Steps:
        1. Build the happy_path test directly from flow.steps (no LLM)
        2. Call LLM for negative + edge case tests
        3. Return all test cases with uuid IDs
        
        Args:
            flow: The UserFlow to generate tests for
            elements: Available elements (for context)
            llm_client: LLMClient for test generation
        
        Returns:
            List of TestCase objects
        """
        test_cases: list[TestCase] = []

        # 1. Happy path — built directly from flow steps
        # Clean up redundant clicks on inputs followed by fills in the flow steps
        cleaned_flow_steps = []
        for i, s in enumerate(flow.steps):
            if s.action == "click" and i + 1 < len(flow.steps):
                next_s = flow.steps[i + 1]
                if next_s.element_id == s.element_id and next_s.action == "fill":
                    # Skip this click step!
                    continue
            cleaned_flow_steps.append(s)

        # Build happy_steps with re-indexed sequence numbers
        happy_steps = []
        for seq, s in enumerate(cleaned_flow_steps, 1):
            happy_steps.append(TestStep(
                sequence=seq,
                action=s.action,
                element_id=s.element_id,
                value=s.value,
                url=s.url
            ))

        # Build assertion from expected outcome
        happy_assertions = self._outcome_to_assertions(flow)

        happy_test = TestCase(
            id=str(uuid.uuid4()),
            flow_id=flow.id,
            name=f"{flow.name} — Happy Path",
            category="happy_path",
            steps=happy_steps,
            assertions=happy_assertions,
            confidence=0.95,
            generated_at=datetime.utcnow()
        )
        test_cases.append(happy_test)

        # 2. Segment-based negative + edge cases generation
        import json
        import asyncio
        from llm.prompts import SEGMENT_TEST_GENERATION_PROMPT

        # Map element_id -> ElementModel for quick lookup
        element_map = {e.id: e for e in elements}

        # Identify input-like elements from flow steps to target
        input_elements = []
        seen_element_ids = set()
        
        for step in flow.steps:
            if step.element_id and step.element_id in element_map:
                el = element_map[step.element_id]
                # Target interactive inputs for mutations
                if el.id not in seen_element_ids and el.element_type in (
                    "textbox", "textarea", "combobox", "checkbox", 
                    "input", "password", "select"
                ):
                    input_elements.append(el)
                    seen_element_ids.add(el.id)

        # Fallback: if no interactive inputs identified, use any elements from steps
        if not input_elements:
            for step in flow.steps:
                if step.element_id and step.element_id in element_map and step.element_id not in seen_element_ids:
                    input_elements.append(element_map[step.element_id])
                    seen_element_ids.add(step.element_id)

        # Split input elements into segments of 3 fields each
        segment_size = 3
        segments = [input_elements[i:i + segment_size] for i in range(0, len(input_elements), segment_size)]

        # If no segments, create a single fallback segment with whatever is available
        if not segments:
            segments = [input_elements] if input_elements else [[e for e in elements[:3]]]

        # Deduplication sets
        seen_fingerprints = set()
        # Add the happy path test fingerprint first
        happy_fingerprint = tuple((s.element_id, s.value) for s in happy_steps if s.element_id)
        seen_fingerprints.add(happy_fingerprint)

        for idx, segment in enumerate(segments):
            if not segment:
                continue

            # Rate limit guard: 15-second delay between API calls to stay well within Groq's 12K TPM and 30 RPM
            if idx > 0:
                await asyncio.sleep(15)

            segment_fields_summary = [
                {
                    "id": e.id,
                    "type": e.element_type,
                    "label": e.semantic_label,
                    "observed_values": e.observed_values[:3] if e.observed_values else [],
                    "validation_rules": [vr.rule for vr in e.validation_rules] if e.validation_rules else []
                }
                for e in segment
            ]

            # Build a compact, human-readable list of happy path steps to save ~80% of tokens
            flow_steps_summary = []
            for s in flow.steps:
                el_label = element_map[s.element_id].semantic_label if s.element_id and s.element_id in element_map else "Unknown"
                flow_steps_summary.append(
                    f"Step {s.sequence}: {s.action} on field '{el_label}' (Element ID: {s.element_id or 'None'}) with value '{s.value or ''}'"
                )

            prompt = SEGMENT_TEST_GENERATION_PROMPT.format(
                flow_name=flow.name,
                flow_steps_json="\n".join(flow_steps_summary),
                segment_fields_json=json.dumps(segment_fields_summary, indent=2)
            )

            try:
                llm_result = await llm_client.generate(prompt, model="smart", expect_json=True)
                generated = llm_result.get("test_cases", [])
            except Exception as le:
                # Log error and continue to other segments so we don't crash the whole generation
                print(f"Error generating tests for segment {idx}: {le}")
                continue

            for tc_data in generated:
                category = tc_data.get("category", "negative")
                if category == "happy_path":
                    continue

                target_id = tc_data.get("target_element_id")
                mutated_value = tc_data.get("mutated_value")

                if not target_id:
                    continue

                # Reconstruct steps programmatically based on the happy path
                steps = []
                
                # Check sequence of log in click action to identify login fields
                login_btn_seq = None
                for s in happy_steps:
                    el = element_map.get(s.element_id)
                    if el and el.element_type in ("link", "button") and el.semantic_label and ("login" in el.semantic_label.lower() or "log in" in el.semantic_label.lower()):
                        login_btn_seq = s.sequence
                        break
                    elif s.action == "click" and el and el.semantic_label and ("login" in el.semantic_label.lower() or "log in" in el.semantic_label.lower()):
                        login_btn_seq = s.sequence
                        break

                target_seq = None
                for s in happy_steps:
                    if s.element_id == target_id:
                        target_seq = s.sequence
                        break

                is_login_field = False
                if login_btn_seq is not None and target_seq is not None:
                    if target_seq < login_btn_seq:
                        is_login_field = True

                # Build mutated steps sequence
                for hs in happy_steps:
                    val = mutated_value if hs.element_id == target_id else hs.value
                    steps.append(TestStep(
                        sequence=hs.sequence,
                        action=hs.action,
                        element_id=hs.element_id,
                        value=val,
                        url=hs.url
                    ))
                    # Stop right after login action if it's a login validation test
                    if is_login_field and login_btn_seq is not None and hs.sequence == login_btn_seq:
                        break

                # Fingerprint deduplication: check if we already have a test case mutating the exact same values
                tc_fingerprint = tuple((s.element_id, s.value) for s in steps if s.element_id)
                if tc_fingerprint in seen_fingerprints:
                    continue
                seen_fingerprints.add(tc_fingerprint)

                assertions = []
                for assert_data in tc_data.get("assertions", []):
                    assertions.append(Assertion(
                        type=assert_data.get("type", "url_contains"),
                        expected=str(assert_data.get("expected", "")),
                        element_label=assert_data.get("element_label")
                    ))

                test_case = TestCase(
                    id=str(uuid.uuid4()),
                    flow_id=flow.id,
                    name=tc_data.get("name", f"{flow.name} — Test Case"),
                    category=category,
                    steps=steps,
                    assertions=assertions,
                    confidence=float(tc_data.get("confidence", 0.7)),
                    generated_at=datetime.utcnow()
                )
                test_cases.append(test_case)

        return test_cases


    def _outcome_to_assertions(self, flow: UserFlow) -> list[Assertion]:
        """Convert a flow's expected outcome to test assertions."""
        assertions = []
        outcome = flow.expected_outcome

        if outcome.url_pattern:
            assertions.append(Assertion(
                type="url_contains",
                expected=outcome.url_pattern.lstrip("^").rstrip("$"),
                element_label=None
            ))

        if outcome.text:
            assertions.append(Assertion(
                type="element_visible",
                expected=outcome.text,
                element_label=outcome.element_label
            ))

        return assertions
