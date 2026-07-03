"""
core/codegen_recorder.py — Wraps Playwright's built-in codegen tool.

Instead of injecting custom JS into every page, we delegate recording to
Playwright's own codegen which produces much more resilient locators
(getByRole, getByText, getByLabel) out of the box.

Usage in _learn():
    recorder = CodegenRecorder(start_url, app_name)
    js_code = await recorder.record()   # blocks until browser closes
    parsed_steps = parse_playwright_js(js_code)
"""
import asyncio
import os
import sys
import tempfile
from pathlib import Path


class CodegenRecorder:
    """Runs `playwright codegen --target javascript` and returns the captured JS."""

    def __init__(self, start_url: str, app_name: str):
        self.start_url = start_url
        self.app_name = app_name

    async def record(self) -> str:
        """
        Opens playwright codegen in a visible browser window.
        Blocks until the user closes the browser.
        Returns the generated JavaScript code as a string.
        """
        # Use a temp file so playwright can write the output
        with tempfile.NamedTemporaryFile(
            suffix=".js", delete=False, mode="w", encoding="utf-8"
        ) as tmp:
            output_path = tmp.name

        try:
            # Build the command
            # On Windows, `playwright` is invoked via the installed Python package
            cmd = [
                sys.executable, "-m", "playwright", "codegen",
                "--target", "javascript",
                "--output", output_path,
                self.start_url,
            ]

            print(f"\n[Codegen] Opening Playwright recorder for: {self.start_url}")
            print("[Codegen] Interact with the browser. Close it when done.\n")

            # Run as subprocess; wait for it to exit (user closes browser)
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.wait()

            # Read the output JS file
            js_path = Path(output_path)
            if js_path.exists() and js_path.stat().st_size > 0:
                return js_path.read_text(encoding="utf-8")
            else:
                return ""

        finally:
            # Clean up temp file
            try:
                os.unlink(output_path)
            except OSError:
                pass
