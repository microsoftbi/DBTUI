"""视觉回归测试：项目列表页。"""
from __future__ import annotations

from pathlib import Path

import pytest
from playwright.async_api import Page

SHOT_DIR = Path(__file__).resolve().parent / "screenshots"
SHOT_DIR.mkdir(parents=True, exist_ok=True)


@pytest.mark.asyncio(loop_scope="session")
async def test_project_list_empty(page: Page, base_url: str):
    """空项目列表页视觉。"""
    await page.goto(f"{base_url}/")
    await page.wait_for_selector("h1")
    await page.wait_for_timeout(300)
    await page.screenshot(path=str(SHOT_DIR / "project-list.png"), full_page=True)
