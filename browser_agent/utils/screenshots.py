"""
utils/screenshots.py — Screenshot capture with metadata.
"""
import os
import asyncio
from pathlib import Path
from datetime import datetime


async def capture_screenshot(page, screenshots_dir: str, label: str = "") -> str:
    """
    Capture a screenshot of the current page state.
    
    Args:
        page: Playwright page object
        screenshots_dir: Directory to save screenshots
        label: Optional label for the screenshot filename
    
    Returns:
        Absolute path to the saved screenshot
    """
    Path(screenshots_dir).mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    safe_label = "".join(c if c.isalnum() or c in "-_" else "_" for c in label)[:50]
    filename = f"{timestamp}_{safe_label}.png" if safe_label else f"{timestamp}.png"
    
    screenshot_path = str(Path(screenshots_dir) / filename)
    
    try:
        await page.screenshot(path=screenshot_path, full_page=False)
    except Exception as e:
        # If screenshot fails (e.g., page navigated), return empty path
        return ""
    
    return screenshot_path


def screenshot_to_base64(path: str) -> str:
    """
    Convert a screenshot file to a base64-encoded string for embedding in HTML.
    
    Args:
        path: Absolute path to the screenshot file
    
    Returns:
        Base64 encoded string, or empty string if file not found
    """
    import base64
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except (FileNotFoundError, IOError):
        return ""
