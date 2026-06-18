"""
Diagnostic script — tests if JS injection and event capture works at all.
Run from: c:\Projects\Antigravity Browsing agent\browser_agent\
Usage: python test_diag.py
"""
import asyncio
import sys
from pathlib import Path
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8')


async def test():
    js_path = Path("assets/event_capture.js")
    event_js = js_path.read_text(encoding="utf-8")

    print("Starting diagnostic...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        # 1. Navigate
        await page.goto("https://the-internet.herokuapp.com/login", wait_until="domcontentloaded")
        print("OK - Page loaded")

        # 2. Inject JS directly (no 'return' keyword in evaluate!)
        try:
            await page.evaluate(event_js)
            print("OK - JS injected via evaluate()")
        except Exception as e:
            print(f"FAIL - JS injection failed: {e}")

        # 3. Check if __capturedEvents exists (use arrow function, not bare return)
        arr_type = await page.evaluate("() => typeof window.__capturedEvents")
        print(f"   window.__capturedEvents type = {arr_type}")

        attached = await page.evaluate("() => !!window.__listenersAttached")
        print(f"   window.__listenersAttached = {attached}")

        # 4. Simulate a click programmatically on username field
        print("\nSimulating click on #username...")
        await page.click("#username")
        await asyncio.sleep(0.3)

        events_after_click = await page.evaluate("() => window.__capturedEvents.length")
        print(f"   Events after programmatic click: {events_after_click}")

        # 5. Simulate typing
        print("Simulating typing 'tomsmith'...")
        await page.fill("#username", "tomsmith")
        await asyncio.sleep(0.3)

        events_after_fill = await page.evaluate("() => window.__capturedEvents.length")
        print(f"   Events after fill: {events_after_fill}")

        # 6. Show raw events
        raw = await page.evaluate("() => JSON.stringify(window.__capturedEvents.slice(0,3))")
        print(f"   Raw events sample: {raw[:400]}")

        print("\n--- Result ---")
        if events_after_fill > 0:
            print("PASS - JS event capture WORKS - polling task was the issue (now fixed)")
        else:
            print("FAIL - JS event capture FAILS - issue with JS injection or site CSP")

        await asyncio.sleep(2)
        await browser.close()


asyncio.run(test())
