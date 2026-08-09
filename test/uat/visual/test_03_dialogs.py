"""视觉回归测试：弹窗类组件。"""
from __future__ import annotations

from pathlib import Path

import pytest
from playwright.async_api import Page

SHOT_DIR = Path(__file__).resolve().parent / "screenshots"
SHOT_DIR.mkdir(parents=True, exist_ok=True)


async def _wait_dialog(page: Page) -> None:
    """等待真正可见的弹窗出现（Element Plus 会保留已关闭的 dialog 在 DOM 中）。"""
    await page.locator("div[role='dialog']").filter(visible=True).first.wait_for(
        state="visible", timeout=10000
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_new_project_dialog(page: Page, base_url: str):
    """新建项目弹窗视觉。"""
    await page.goto(f"{base_url}/")
    await page.get_by_role("button", name="新建项目").click()
    await _wait_dialog(page)
    await page.wait_for_timeout(200)
    await page.screenshot(path=str(SHOT_DIR / "dialog-new-project.png"), full_page=True)


@pytest.mark.asyncio(loop_scope="session")
async def test_run_dialog(page: Page, base_url: str, visual_project: dict):
    """运行对话框视觉（运行前状态）。"""
    await page.goto(f"{base_url}/projects/{visual_project['id']}")
    # 等待 Models 标签页加载（不要用 wait_for_selector("table")，Element Plus 有多个内部 table）
    await page.get_by_role("button", name="新建模型").wait_for(state="visible")
    # 点击第一个模型的"运行"
    await page.get_by_role("button", name="运行").first.click()
    await _wait_dialog(page)
    await page.wait_for_timeout(200)
    await page.screenshot(path=str(SHOT_DIR / "dialog-run.png"), full_page=True)


@pytest.mark.asyncio(loop_scope="session")
async def test_profiles_dialog(page: Page, base_url: str, visual_project: dict):
    """连接配置弹窗视觉。"""
    await page.goto(f"{base_url}/projects/{visual_project['id']}")
    await page.get_by_role("button", name="连接配置").click()
    await _wait_dialog(page)
    await page.wait_for_timeout(200)
    await page.screenshot(path=str(SHOT_DIR / "dialog-profiles.png"), full_page=True)
