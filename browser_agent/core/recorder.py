"""
core/recorder.py — Playwright launch + JS injection + event capture.
Implements BrowserRecorder: opens a headful browser and records user interactions.
"""
import asyncio
import json
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright, Page, Frame

from utils.screenshots import capture_screenshot


class BrowserRecorder:
    def __init__(self, start_url: str, app_name: str, screenshots_dir: str):
        self.start_url = start_url
        self.app_name = app_name
        self.screenshots_dir = screenshots_dir

        self._event_buffer: list[dict] = []
        self._navigation_log: list[dict] = []
        self._api_log: list[dict] = []
        self._dialog_log: list[dict] = []

        self._playwright = None
        self._browser = None
        self._context = None
        self._page: Page | None = None
        self._polling_task: asyncio.Task | None = None
        self._running = False

        # Load event_capture.js
        js_path = Path(__file__).parent.parent / "assets" / "event_capture.js"
        self._event_capture_js = js_path.read_text(encoding="utf-8")

    async def start_session(self):
        """Launch browser, inject JS, and start polling loop."""
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=False)
        self._context = await self._browser.new_context()
        self._page = await self._context.new_page()

        # Also add as init script so it runs fresh on every page load
        await self._context.add_init_script(self._event_capture_js)

        # Set up event hooks BEFORE navigating
        self._page.on("framenavigated", self._on_navigate)
        self._page.on("dialog", self._on_dialog)
        self._page.on("request", self._on_request)

        # Navigate to start URL
        await self._page.goto(self.start_url, wait_until="domcontentloaded")

        # Explicitly inject JS into the first page
        await self._safe_inject(self._page)

        # Start polling loop
        self._running = True
        self._polling_task = asyncio.create_task(self._poll_events())

        # Keep running until stopped externally
        while self._running:
            await asyncio.sleep(0.5)

    async def _safe_inject(self, page: Page):
        """Safely inject event_capture.js via page.evaluate()."""
        try:
            await page.evaluate(self._event_capture_js)
        except Exception:
            pass  # Page may be navigating — init_script will handle it

    async def _poll_events(self):
        """Poll every 500ms for captured events and drain the buffer."""
        while self._running:
            await self._drain_events()
            await asyncio.sleep(0.5)

    async def _drain_events(self):
        """Do a single drain of window.__capturedEvents."""
        try:
            if self._page and not self._page.is_closed():
                events = await self._page.evaluate(
                    "() => window.__capturedEvents || []"
                )
                if events:
                    self._event_buffer.extend(events)
                    await self._page.evaluate("() => { window.__capturedEvents = []; }")
        except Exception:
            pass  # Page may be navigating

    async def _on_navigate(self, frame: Frame):
        """Capture navigation events — main frame only."""
        try:
            # Only process main frame navigations
            if self._page and frame != self._page.main_frame:
                return

            url = self._page.url
            try:
                title = await self._page.title()
            except Exception:
                title = ""

            # Wait briefly for DOM to settle before injecting
            try:
                await asyncio.sleep(0.2)
                await self._safe_inject(self._page)
            except Exception:
                pass

            # Capture accessibility snapshot
            try:
                accessibility_snapshot = await self._page.accessibility.snapshot()
            except Exception:
                accessibility_snapshot = {}

            # Take screenshot
            screenshot_path = await capture_screenshot(
                self._page,
                self.screenshots_dir,
                label=f"nav_{len(self._navigation_log)}"
            )

            self._navigation_log.append({
                "url": url,
                "title": title,
                "accessibility_snapshot": accessibility_snapshot or {},
                "screenshot_path": screenshot_path,
                "timestamp": datetime.utcnow().isoformat()
            })
        except Exception:
            pass

    async def _on_dialog(self, dialog):
        """Auto-dismiss dialogs and log them."""
        try:
            self._dialog_log.append({
                "type": dialog.type,
                "message": dialog.message,
                "timestamp": datetime.utcnow().isoformat()
            })
            await dialog.dismiss()
        except Exception:
            pass

    async def _on_request(self, request):
        """Log API requests (only /api/ URLs to reduce noise)."""
        try:
            if "/api/" in request.url:
                self._api_log.append({
                    "method": request.method,
                    "url": request.url,
                    "timestamp": datetime.utcnow().isoformat()
                })
        except Exception:
            pass

    async def stop_session(self) -> dict:
        """Stop polling, do final drain, close browser, return session data."""
        self._running = False

        # Cancel the polling task
        if self._polling_task and not self._polling_task.done():
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass

        # Final drain — capture any events not yet polled
        await self._drain_events()

        # Close browser
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass

        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass

        return {
            "events": self._event_buffer,
            "navigations": self._navigation_log,
            "dialogs": self._dialog_log,
            "api_calls": self._api_log,
            "app_name": self.app_name,
            "start_url": self.start_url,
            "recorded_at": datetime.utcnow().isoformat()
        }

    async def save_session(self, output_path: str) -> dict:
        """Stop session and save to a JSON file."""
        session_data = await self.stop_session()
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(session_data, f, indent=2, default=str)
        return session_data
