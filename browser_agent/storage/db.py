"""
storage/db.py — All async SQLite CRUD operations.
Uses aiosqlite with JSON serialization for complex fields.
"""
import json
import uuid
import asyncio
import aiosqlite
from pathlib import Path
from datetime import datetime
from typing import Optional

from schema import (
    ApplicationModel, AppVersion, PageModel, ElementModel,
    UserFlow, TestCase, TestResult, ExpectedOutcome,
    FlowStep, TestStep, Assertion, StepResult, LocatorSpec, ValidationRule
)


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()

    async def initialize(self):
        """Create tables from schema.sql if they don't exist."""
        schema_path = Path(__file__).parent / "schema.sql"
        schema_sql = schema_path.read_text(encoding="utf-8")

        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(schema_sql)
            await db.commit()

    async def _get_conn(self) -> aiosqlite.Connection:
        """Get or create a persistent connection."""
        if self._conn is None:
            self._conn = await aiosqlite.connect(self.db_path)
            self._conn.row_factory = aiosqlite.Row
        return self._conn

    async def close(self):
        if self._conn:
            await self._conn.close()
            self._conn = None

    # ─── Applications ────────────────────────────────────────────────

    async def save_application(self, app: ApplicationModel) -> None:
        """Save or update an application record."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT OR REPLACE INTO applications (id, name, base_url)
                   VALUES (?, ?, ?)""",
                (app.id, app.name, app.base_url)
            )
            await db.commit()

    async def get_application(self, app_id: str) -> Optional[ApplicationModel]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM applications WHERE id = ?", (app_id,)
            ) as cursor:
                row = await cursor.fetchone()
        if not row:
            return None
        return await self._load_full_app(dict(row))

    async def get_application_by_name(self, name: str) -> Optional[ApplicationModel]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM applications WHERE name = ?", (name,)
            ) as cursor:
                row = await cursor.fetchone()
        if not row:
            return None
        return await self._load_full_app(dict(row))

    async def list_applications(self) -> list[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM applications") as cursor:
                rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def _load_full_app(self, app_row: dict) -> ApplicationModel:
        """Load a complete ApplicationModel from DB."""
        app_id = app_row["id"]
        version = await self.get_active_version(app_id)
        if version is None:
            versions = await self.list_versions(app_id)
            version = versions[0] if versions else AppVersion(
                id=str(uuid.uuid4()), app_id=app_id, label="v1",
                created_at=datetime.utcnow(), is_active=True
            )

        pages = await self._get_pages_for_version(version.id)
        elements: list[ElementModel] = []
        for page in pages:
            page_elements = await self.get_elements_for_page(page.id)
            elements.extend(page_elements)

        flows = await self.get_flows_for_version(version.id)

        return ApplicationModel(
            id=app_id,
            name=app_row["name"],
            base_url=app_row["base_url"],
            version=version,
            pages=pages,
            elements=elements,
            flows=flows,
        )

    # ─── App Versions ────────────────────────────────────────────────

    async def save_version(self, version: AppVersion) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT OR REPLACE INTO app_versions
                   (id, app_id, label, created_at, is_active)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    version.id, version.app_id, version.label,
                    version.created_at.isoformat(),
                    1 if version.is_active else 0
                )
            )
            await db.commit()

    async def set_active_version(self, app_id: str, version_id: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE app_versions SET is_active = 0 WHERE app_id = ?",
                (app_id,)
            )
            await db.execute(
                "UPDATE app_versions SET is_active = 1 WHERE id = ?",
                (version_id,)
            )
            await db.commit()

    async def get_active_version(self, app_id: str) -> Optional[AppVersion]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM app_versions WHERE app_id = ? AND is_active = 1",
                (app_id,)
            ) as cursor:
                row = await cursor.fetchone()
        if not row:
            return None
        return self._row_to_version(dict(row))

    async def list_versions(self, app_id: str) -> list[AppVersion]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM app_versions WHERE app_id = ? ORDER BY created_at DESC",
                (app_id,)
            ) as cursor:
                rows = await cursor.fetchall()
        return [self._row_to_version(dict(r)) for r in rows]

    def _row_to_version(self, row: dict) -> AppVersion:
        created = row.get("created_at")
        if isinstance(created, str):
            try:
                created = datetime.fromisoformat(created)
            except ValueError:
                created = datetime.utcnow()
        elif created is None:
            created = datetime.utcnow()
        return AppVersion(
            id=row["id"],
            app_id=row["app_id"],
            label=row["label"],
            created_at=created,
            is_active=bool(row.get("is_active", 0))
        )

    # ─── Pages ───────────────────────────────────────────────────────

    async def save_page(self, page: PageModel) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT OR REPLACE INTO pages
                   (id, version_id, url_pattern, title, purpose, accessibility_snapshot)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    page.id, page.version_id, page.url_pattern,
                    page.title, page.purpose,
                    json.dumps(page.accessibility_snapshot)
                )
            )
            await db.commit()

    async def _get_pages_for_version(self, version_id: str) -> list[PageModel]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM pages WHERE version_id = ?", (version_id,)
            ) as cursor:
                rows = await cursor.fetchall()
        return [self._row_to_page(dict(r)) for r in rows]

    def _row_to_page(self, row: dict) -> PageModel:
        snap = row.get("accessibility_snapshot")
        if isinstance(snap, str):
            try:
                snap = json.loads(snap)
            except Exception:
                snap = {}
        return PageModel(
            id=row["id"],
            version_id=row["version_id"],
            url_pattern=row["url_pattern"],
            title=row.get("title") or "",
            purpose=row.get("purpose") or "",
            accessibility_snapshot=snap or {}
        )

    # ─── Elements ────────────────────────────────────────────────────

    async def save_element(self, element: ElementModel) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT OR REPLACE INTO elements
                   (id, page_id, element_type, semantic_label, locators,
                    validation_rules, observed_values)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    element.id, element.page_id, element.element_type,
                    element.semantic_label,
                    json.dumps([loc.model_dump() for loc in element.locators]),
                    json.dumps([vr.model_dump() for vr in element.validation_rules]),
                    json.dumps(element.observed_values)
                )
            )
            await db.commit()

    async def get_elements_for_page(self, page_id: str) -> list[ElementModel]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM elements WHERE page_id = ?", (page_id,)
            ) as cursor:
                rows = await cursor.fetchall()
        return [self._row_to_element(dict(r)) for r in rows]

    async def get_element(self, element_id: str) -> Optional[ElementModel]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM elements WHERE id = ?", (element_id,)
            ) as cursor:
                row = await cursor.fetchone()
        if not row:
            return None
        return self._row_to_element(dict(row))

    def _row_to_element(self, row: dict) -> ElementModel:
        locators_raw = json.loads(row.get("locators") or "[]")
        vr_raw = json.loads(row.get("validation_rules") or "[]")
        ov_raw = json.loads(row.get("observed_values") or "[]")
        return ElementModel(
            id=row["id"],
            page_id=row["page_id"],
            element_type=row["element_type"],
            semantic_label=row["semantic_label"],
            locators=[LocatorSpec(**l) for l in locators_raw],
            validation_rules=[ValidationRule(**v) for v in vr_raw],
            observed_values=ov_raw
        )

    # ─── Flows ───────────────────────────────────────────────────────

    async def save_flow(self, flow: UserFlow) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT OR REPLACE INTO user_flows
                   (id, version_id, name, description, start_url, steps, expected_outcome)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    flow.id, flow.version_id, flow.name, flow.description,
                    flow.start_url,
                    json.dumps([s.model_dump() for s in flow.steps]),
                    json.dumps(flow.expected_outcome.model_dump())
                )
            )
            await db.commit()

    async def get_flows_for_version(self, version_id: str) -> list[UserFlow]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM user_flows WHERE version_id = ?", (version_id,)
            ) as cursor:
                rows = await cursor.fetchall()
        return [self._row_to_flow(dict(r)) for r in rows]

    def _row_to_flow(self, row: dict) -> UserFlow:
        steps_raw = json.loads(row.get("steps") or "[]")
        outcome_raw = json.loads(row.get("expected_outcome") or "{}")
        return UserFlow(
            id=row["id"],
            version_id=row["version_id"],
            name=row["name"],
            description=row.get("description") or "",
            start_url=row["start_url"],
            steps=[FlowStep(**s) for s in steps_raw],
            expected_outcome=ExpectedOutcome(**outcome_raw)
        )

    # ─── Test Cases ──────────────────────────────────────────────────

    async def save_test_case(self, tc: TestCase) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT OR REPLACE INTO test_cases
                   (id, flow_id, name, category, steps, assertions,
                    confidence, generated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    tc.id, tc.flow_id, tc.name, tc.category,
                    json.dumps([s.model_dump() for s in tc.steps]),
                    json.dumps([a.model_dump() for a in tc.assertions]),
                    tc.confidence,
                    tc.generated_at.isoformat()
                )
            )
            await db.commit()

    async def get_test_cases_for_app(self, app_id: str) -> list[TestCase]:
        """Get all test cases for an app by joining through user_flows and app_versions."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """SELECT tc.* FROM test_cases tc
                   JOIN user_flows uf ON tc.flow_id = uf.id
                   JOIN app_versions av ON uf.version_id = av.id
                   WHERE av.app_id = ? AND av.is_active = 1""",
                (app_id,)
            ) as cursor:
                rows = await cursor.fetchall()
        return [self._row_to_test_case(dict(r)) for r in rows]

    def _row_to_test_case(self, row: dict) -> TestCase:
        steps_raw = json.loads(row.get("steps") or "[]")
        assertions_raw = json.loads(row.get("assertions") or "[]")
        gen_at = row.get("generated_at")
        if isinstance(gen_at, str):
            try:
                gen_at = datetime.fromisoformat(gen_at)
            except ValueError:
                gen_at = datetime.utcnow()
        elif gen_at is None:
            gen_at = datetime.utcnow()
        return TestCase(
            id=row["id"],
            flow_id=row["flow_id"],
            name=row["name"],
            category=row["category"],
            steps=[TestStep(**s) for s in steps_raw],
            assertions=[Assertion(**a) for a in assertions_raw],
            confidence=row.get("confidence") or 0.0,
            generated_at=gen_at
        )

    # ─── Test Runs ───────────────────────────────────────────────────

    async def save_test_run(self, run: dict) -> str:
        run_id = run.get("id") or str(uuid.uuid4())
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT OR REPLACE INTO test_runs
                   (id, app_id, started_at, completed_at, total, passed, failed, errored)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    run_id,
                    run.get("app_id", ""),
                    run.get("started_at", datetime.utcnow().isoformat()),
                    run.get("completed_at"),
                    run.get("total", 0),
                    run.get("passed", 0),
                    run.get("failed", 0),
                    run.get("errored", 0),
                )
            )
            await db.commit()
        return run_id

    async def update_test_run(self, run_id: str, **kwargs) -> None:
        if not kwargs:
            return
        set_clauses = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [run_id]
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                f"UPDATE test_runs SET {set_clauses} WHERE id = ?", values
            )
            await db.commit()

    async def save_test_result(self, result: TestResult) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT OR REPLACE INTO test_results
                   (id, run_id, test_case_id, test_name, category, status,
                    duration_ms, step_results, assertion_results,
                    error_detail, failure_screenshot)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    result.id, result.run_id, result.test_case_id,
                    result.test_name, result.category, result.status,
                    result.duration_ms,
                    json.dumps([sr.model_dump() for sr in result.step_results]),
                    json.dumps(result.assertion_results),
                    result.error_detail,
                    result.failure_screenshot
                )
            )
            await db.commit()

    async def get_results_for_run(self, run_id: str) -> list[TestResult]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM test_results WHERE run_id = ?", (run_id,)
            ) as cursor:
                rows = await cursor.fetchall()
        return [self._row_to_test_result(dict(r)) for r in rows]

    async def get_last_run(self, app_id: str) -> Optional[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """SELECT * FROM test_runs WHERE app_id = ?
                   ORDER BY started_at DESC LIMIT 1""",
                (app_id,)
            ) as cursor:
                row = await cursor.fetchone()
        return dict(row) if row else None

    def _row_to_test_result(self, row: dict) -> TestResult:
        sr_raw = json.loads(row.get("step_results") or "[]")
        ar_raw = json.loads(row.get("assertion_results") or "[]")
        return TestResult(
            id=row["id"],
            run_id=row["run_id"],
            test_case_id=row["test_case_id"],
            test_name=row.get("test_name") or "",
            category=row.get("category") or "",
            status=row["status"],
            duration_ms=row.get("duration_ms") or 0,
            step_results=[StepResult(**s) for s in sr_raw],
            assertion_results=ar_raw,
            error_detail=row.get("error_detail"),
            failure_screenshot=row.get("failure_screenshot")
        )
