"""
core/model_builder.py — Converts raw session events into structured ApplicationModel.
"""
import json
import re
import uuid
from datetime import datetime, date

from schema import (
    ApplicationModel, AppVersion, PageModel, ElementModel,
    UserFlow, FlowStep, ExpectedOutcome, LocatorSpec, ValidationRule
)
from utils.locators import generate_locators
from llm.prompts import ELEMENT_LABEL_PROMPT, FLOW_IDENTIFICATION_PROMPT


class ModelBuilder:
    async def build(
        self,
        session_data: dict,
        app_name: str,
        db,
        llm_client
    ) -> ApplicationModel:
        """
        Build a complete ApplicationModel from raw session data.
        
        Args:
            session_data: Dict returned by BrowserRecorder.stop_session()
            app_name: Name of the application being modeled
            db: Database instance for persistence
            llm_client: LLMClient for element labeling and flow analysis
        
        Returns:
            Complete ApplicationModel
        """
        base_url = session_data.get("start_url", "")
        events = session_data.get("events", [])
        navigations = session_data.get("navigations", [])

        # 1. Create Application entry
        app_id = str(uuid.uuid4())

        # 2. Create AppVersion entry
        today = date.today().isoformat()
        version = AppVersion(
            id=str(uuid.uuid4()),
            app_id=app_id,
            label=f"v1_{today}",
            created_at=datetime.utcnow(),
            is_active=True
        )

        # 3. Build pages from navigation log
        pages: list[PageModel] = []
        elements: list[ElementModel] = []
        url_to_page: dict[str, PageModel] = {}

        for nav in navigations:
            url = nav.get("url", "")
            if not url:
                continue

            # Deduplicate by URL
            if url in url_to_page:
                continue

            # Generate a URL pattern (regex-compatible)
            url_pattern = self._url_to_pattern(url, base_url)

            page = PageModel(
                id=str(uuid.uuid4()),
                version_id=version.id,
                url_pattern=url_pattern,
                title=nav.get("title") or "",
                purpose="",  # Will be set later
                accessibility_snapshot=nav.get("accessibility_snapshot") or {}
            )
            pages.append(page)
            url_to_page[url] = page

        # 4. Process elements from events — associate with page by URL
        # Build a map from URL to events
        # We'll use the navigation order to determine which URL was active
        nav_urls = [n.get("url", "") for n in navigations]

        for i, nav in enumerate(navigations):
            nav_url = nav.get("url", "")
            page = url_to_page.get(nav_url)
            if not page:
                continue

            # Get events that happened before the next navigation
            next_nav_time = None
            if i + 1 < len(navigations):
                next_nav_time = navigations[i + 1].get("timestamp")

            nav_time = nav.get("timestamp")
            
            # Get relevant events for this page
            page_events = self._events_for_page(events, nav_time, next_nav_time)

            # Process each unique element on this page
            seen_elements: set[str] = set()
            for event in page_events:
                elem_key = self._element_key(event)
                if elem_key in seen_elements:
                    # Still capture observed values
                    for elem in elements:
                        if elem.page_id == page.id and self._matches_event(elem, event):
                            val = event.get("value")
                            if val and val not in elem.observed_values:
                                elem.observed_values.append(val)
                    continue
                seen_elements.add(elem_key)

                # Skip events with no meaningful identification
                if not any([
                    event.get("aria_label"), event.get("placeholder"),
                    event.get("id"), event.get("name"), event.get("text_content")
                ]):
                    continue

                # Generate locators
                locators = generate_locators(event)
                if not locators:
                    continue

                # Call LLM for element labeling
                element_type = self._classify_element_type(event)
                label_result = await llm_client.generate(
                    ELEMENT_LABEL_PROMPT.format(
                        tag=event.get("tag") or "",
                        input_type=event.get("type_attr") or "",
                        element_id=event.get("id") or "",
                        name=event.get("name") or "",
                        placeholder=event.get("placeholder") or "",
                        aria_label=event.get("aria_label") or "",
                        text_content=event.get("text_content") or ""
                    ),
                    model="haiku",
                    expect_json=True
                )

                semantic_label = label_result.get("semantic_label", elem_key)
                validation_rules_raw = label_result.get("validation_rules", [])
                validation_rules = []
                for vr in validation_rules_raw:
                    if isinstance(vr, dict):
                        validation_rules.append(ValidationRule(
                            rule=vr.get("rule", ""),
                            typical_error=vr.get("typical_error")
                        ))

                observed_values = []
                val = event.get("value")
                if val:
                    observed_values.append(val)

                element = ElementModel(
                    id=str(uuid.uuid4()),
                    page_id=page.id,
                    element_type=element_type,
                    semantic_label=semantic_label,
                    locators=locators,
                    validation_rules=validation_rules,
                    observed_values=observed_values
                )
                elements.append(element)

        # 5. Group events into flows
        flows: list[UserFlow] = []
        for i, nav in enumerate(navigations):
            nav_url = nav.get("url", "")
            nav_time = nav.get("timestamp")
            next_nav_time = navigations[i + 1].get("timestamp") if i + 1 < len(navigations) else None

            flow_events = self._events_for_page(events, nav_time, next_nav_time)
            if not flow_events:
                continue

            page = url_to_page.get(nav_url)
            page_titles = list({n.get("title", "") for n in navigations if n.get("title")})

            # Call LLM for flow identification
            flow_result = await llm_client.generate(
                FLOW_IDENTIFICATION_PROMPT.format(
                    steps_json=json.dumps(flow_events[:30], indent=2),
                    page_titles=json.dumps(page_titles)
                ),
                model="sonnet",
                expect_json=True
            )

            # Convert flow events to FlowStep objects
            flow_steps = self._events_to_flow_steps(flow_events, elements, page)

            expected_outcome_raw = flow_result.get("expected_outcome", {})
            expected_outcome = ExpectedOutcome(
                type=expected_outcome_raw.get("type", "navigation"),
                url_pattern=expected_outcome_raw.get("url_pattern"),
                text=expected_outcome_raw.get("text")
            )

            # Determine next URL as expected navigation target
            if i + 1 < len(navigations):
                next_url = navigations[i + 1].get("url", "")
                if next_url and not expected_outcome.url_pattern:
                    expected_outcome.url_pattern = self._url_to_pattern(next_url, base_url)

            flow = UserFlow(
                id=str(uuid.uuid4()),
                version_id=version.id,
                name=flow_result.get("name", f"Flow {i + 1}"),
                description=flow_result.get("description", ""),
                start_url=nav_url,
                steps=flow_steps,
                expected_outcome=expected_outcome
            )
            flows.append(flow)

        # Assemble and return ApplicationModel
        app = ApplicationModel(
            id=app_id,
            name=app_name,
            base_url=base_url,
            version=version,
            pages=pages,
            elements=elements,
            flows=flows
        )

        # Persist to DB
        await db.save_application(app)
        await db.save_version(version)
        for page in pages:
            await db.save_page(page)
        for element in elements:
            await db.save_element(element)
        for flow in flows:
            await db.save_flow(flow)

        return app

    def _url_to_pattern(self, url: str, base_url: str) -> str:
        """Convert a URL to a simple regex pattern."""
        try:
            # Remove base_url prefix to get the path
            if base_url and url.startswith(base_url):
                path = url[len(base_url):]
            else:
                # Extract just the path from full URL
                from urllib.parse import urlparse
                parsed = urlparse(url)
                path = parsed.path or "/"

            # Escape regex special chars (except /)
            path = re.sub(r'([.?+*\[\](){}\\|^$])', r'\\\1', path)
            return f"^{path}"
        except Exception:
            return url

    def _events_for_page(
        self,
        events: list[dict],
        start_time: str | None,
        end_time: str | None
    ) -> list[dict]:
        """Filter events that occurred between two navigation timestamps."""
        if not start_time and not end_time:
            return events

        result = []
        for event in events:
            ts = event.get("timestamp")
            if ts is None:
                result.append(event)
                continue
            # Timestamps from JS are milliseconds since epoch
            # Navigation timestamps are ISO strings
            # Try to compare; if parsing fails, include the event
            try:
                if start_time:
                    start_ms = datetime.fromisoformat(start_time).timestamp() * 1000
                    if ts < start_ms:
                        continue
                if end_time:
                    end_ms = datetime.fromisoformat(end_time).timestamp() * 1000
                    if ts > end_ms:
                        continue
                result.append(event)
            except Exception:
                result.append(event)
        return result

    def _element_key(self, event: dict) -> str:
        """Generate a unique key for an element based on its attributes."""
        parts = [
            event.get("tag") or "",
            event.get("id") or "",
            event.get("name") or "",
            event.get("aria_label") or "",
            event.get("placeholder") or "",
        ]
        return "|".join(parts)

    def _matches_event(self, element: ElementModel, event: dict) -> bool:
        """Check if an element matches an event (for observed values tracking)."""
        key = self._element_key(event)
        # Rough match based on locators
        for loc in element.locators:
            if loc.strategy == "id" and loc.value == (event.get("id") or ""):
                return True
            if loc.strategy == "placeholder" and loc.value == (event.get("placeholder") or ""):
                return True
            if loc.strategy == "aria_label" and loc.value == (event.get("aria_label") or ""):
                return True
        return False

    def _classify_element_type(self, event: dict) -> str:
        """Classify an element type based on event attributes."""
        tag = (event.get("tag") or "").lower()
        type_attr = (event.get("type_attr") or "").lower()

        if tag == "input":
            if type_attr in ("checkbox",):
                return "checkbox"
            elif type_attr in ("radio",):
                return "radio"
            else:
                return "input"
        elif tag == "select":
            return "select"
        elif tag == "textarea":
            return "textarea"
        elif tag == "button":
            return "button"
        elif tag == "a":
            return "link"
        else:
            return "input"

    def _events_to_flow_steps(
        self,
        events: list[dict],
        elements: list[ElementModel],
        page: PageModel | None
    ) -> list[FlowStep]:
        """Convert raw events to FlowStep objects."""
        steps: list[FlowStep] = []
        sequence = 1

        for event in events:
            event_type = event.get("event_type", "")
            if event_type not in ("click", "input", "change", "submit"):
                continue

            # Find matching element
            matched_element_id = None
            for elem in elements:
                if page and elem.page_id != page.id:
                    continue
                if self._matches_event(elem, event):
                    matched_element_id = elem.id
                    break

            # Map event type to action
            action = "click"
            if event_type in ("input", "change"):
                action = "fill"
            elif event_type == "submit":
                action = "click"

            step = FlowStep(
                sequence=sequence,
                action=action,
                element_id=matched_element_id,
                value=event.get("value"),
                url=None
            )
            steps.append(step)
            sequence += 1

        return steps
