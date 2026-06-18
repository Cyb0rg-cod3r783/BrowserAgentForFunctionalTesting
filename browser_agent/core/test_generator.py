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
        happy_steps = [
            TestStep(
                sequence=s.sequence,
                action=s.action,
                element_id=s.element_id,
                value=s.value,
                url=s.url
            )
            for s in flow.steps
        ]

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

        # 2. LLM-generated negative + edge cases
        elements_summary = [
            {
                "id": e.id,
                "type": e.element_type,
                "label": e.semantic_label,
                "observed_values": e.observed_values[:3],
                "validation_rules": [vr.rule for vr in e.validation_rules]
            }
            for e in elements
            if e.page_id in {s.element_id for s in flow.steps if s.element_id}
            or True  # include all elements for context
        ][:10]  # Limit to 10 to avoid token overflow

        import json
        prompt = TEST_GENERATION_PROMPT.format(
            flow_name=flow.name,
            flow_steps_json=json.dumps(
                [s.model_dump() for s in flow.steps], indent=2
            ),
            elements_json=json.dumps(elements_summary, indent=2),
            expected_outcome_json=json.dumps(
                flow.expected_outcome.model_dump(), indent=2
            )
        )

        llm_result = await llm_client.generate(prompt, model="smart", expect_json=True)
        generated = llm_result.get("test_cases", [])

        for tc_data in generated:
            category = tc_data.get("category", "negative")
            if category == "happy_path":
                # Skip — we already built one above
                continue

            steps = []
            for step_data in tc_data.get("steps", []):
                steps.append(TestStep(
                    sequence=step_data.get("sequence", 1),
                    action=step_data.get("action", "fill"),
                    element_id=step_data.get("element_id"),
                    value=step_data.get("value"),
                    url=step_data.get("url")
                ))

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
