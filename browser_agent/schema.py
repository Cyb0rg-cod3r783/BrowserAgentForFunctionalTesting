"""
All Pydantic v2 models for the Browser Agent system.
Do not add, remove, or rename any field.
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class LocatorSpec(BaseModel):
    strategy: str        # "aria_label" | "role" | "placeholder" | "text" |
                         # "id" | "css" | "xpath"
    value: str
    confidence: float    # 0.0 to 1.0


class ValidationRule(BaseModel):
    rule: str            # "required" | "email_format" | "min_length" |
                         # "max_length" | "numeric"
    param: Optional[str] = None
    typical_error: Optional[str] = None


class ElementModel(BaseModel):
    id: str
    page_id: str
    element_type: str    # "input" | "button" | "select" | "link" |
                         # "checkbox" | "radio" | "textarea"
    semantic_label: str  # LLM-generated: "Email address field"
    locators: list[LocatorSpec]
    validation_rules: list[ValidationRule]
    observed_values: list[str]


class PageModel(BaseModel):
    id: str
    version_id: str
    url_pattern: str     # regex: "^/login$" or "^/checkout"
    title: str
    purpose: str         # LLM-generated: "User authentication page"
    accessibility_snapshot: dict


class FlowStep(BaseModel):
    sequence: int
    action: str          # "fill" | "click" | "navigate" | "select" |
                         # "check" | "hover" | "clear"
    element_id: Optional[str] = None
    value: Optional[str] = None
    url: Optional[str] = None


class ExpectedOutcome(BaseModel):
    type: str            # "navigation" | "element_visible" | "text_present" |
                         # "element_absent"
    url_pattern: Optional[str] = None
    element_label: Optional[str] = None
    text: Optional[str] = None


class UserFlow(BaseModel):
    id: str
    version_id: str
    name: str            # LLM-generated: "User Login Flow"
    description: str
    start_url: str
    steps: list[FlowStep]
    expected_outcome: ExpectedOutcome


class TestStep(BaseModel):
    sequence: int
    action: str
    element_id: Optional[str] = None
    value: Optional[str] = None
    url: Optional[str] = None


class Assertion(BaseModel):
    type: str            # "url_contains" | "element_visible" | "text_equals" |
                         # "element_count" | "element_absent"
    expected: str
    element_label: Optional[str] = None


class TestCase(BaseModel):
    id: str
    flow_id: str
    name: str
    category: str        # "happy_path" | "negative" | "edge_case"
    steps: list[TestStep]
    assertions: list[Assertion]
    confidence: float
    generated_at: datetime


class StepResult(BaseModel):
    sequence: int
    action: str
    element_label: Optional[str] = None
    status: str          # "passed" | "failed" | "skipped"
    locator_used: Optional[str] = None
    error: Optional[str] = None
    screenshot_path: Optional[str] = None


class TestResult(BaseModel):
    id: str
    run_id: str
    test_case_id: str
    test_name: str
    category: str
    status: str          # "passed" | "failed" | "errored"
    duration_ms: int
    step_results: list[StepResult]
    assertion_results: list[dict]
    error_detail: Optional[str] = None
    failure_screenshot: Optional[str] = None


class AppVersion(BaseModel):
    id: str
    app_id: str
    label: str
    created_at: datetime
    is_active: bool


class ApplicationModel(BaseModel):
    id: str
    name: str
    base_url: str
    version: AppVersion
    pages: list[PageModel]
    elements: list[ElementModel]
    flows: list[UserFlow]
