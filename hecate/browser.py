"""In-App Browser — cmux "Browser-Pane" für Hecate.
Headless Playwright-Screenshots für Dashboard-Demos, Validierung, Debugging."""

import base64
import subprocess
from pathlib import Path
from typing import Literal


def screenshot(
    url: str,
    output_path: Path | None = None,
    width: int = 1280,
    height: int = 720,
    full_page: bool = False,
    wait_ms: int = 2000,
) -> Path | None:
    """Macht einen Screenshot einer URL via Playwright (headless)."""
    if output_path is None:
        output_path = Path(f"/tmp/hecate-screenshot-{url.replace('://','_').replace('/','_')[:40]}.png")

    # Prüfe ob Playwright installiert
    try:
        subprocess.run(["python3", "-c", "import playwright"], capture_output=True, check=True)
    except subprocess.CalledProcessError:
        # Fallback: playwright installieren
        subprocess.run(["pip", "install", "playwright"], capture_output=True)
        subprocess.run(["playwright", "install", "chromium"], capture_output=True)

    script = f'''
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={{"width": {width}, "height": {height}}})
        await page.goto("{url}", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout({wait_ms})
        if {str(full_page).lower()}:
            await page.screenshot(path="{output_path}", full_page=True)
        else:
            await page.screenshot(path="{output_path}")
        await browser.close()

asyncio.run(main())
'''
    try:
        proc = subprocess.run(
            ["python3", "-c", script],
            capture_output=True, text=True, timeout=60
        )
        if proc.returncode == 0 and output_path.exists():
            return output_path
        return None
    except Exception:
        return None


def screenshot_to_base64(url: str, width: int = 1280, height: int = 720) -> str:
    """Screenshot als Base64-Data-URI (für Inline-Anzeige)."""
    path = screenshot(url, width=width, height=height)
    if path is None:
        return ""
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:image/png;base64,{b64}"


def validate_localhost(port: int, path: str = "/") -> tuple[bool, str]:
    """Prüft ob ein lokaler Dienst antwortet + Screenshot."""
    url = f"http://127.0.0.1:{port}{path}"
    img = screenshot(url, width=800, height=400, wait_ms=500)
    if img:
        return True, f"Screenshot: {img}"
    return False, "Keine Antwort / Screenshot fehlgeschlagen"
