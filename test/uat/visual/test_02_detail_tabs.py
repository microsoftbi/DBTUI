"""视觉回归测试：项目详情页各标签页。"""
from __future__ import annotations

from pathlib import Path

import pytest
from playwright.async_api import Page

SHOT_DIR = Path(__file__).resolve().parent / "screenshots"
SHOT_DIR.mkdir(parents=True, exist_ok=True)


@pytest.mark.asyncio(loop_scope="session")
async def test_detail_models_tab(page: Page, base_url: str, visual_project: dict):
    """项目详情 - Models 标签。"""
    await page.goto(f"{base_url}/projects/{visual_project['id']}")
    await page.wait_for_selector("h2")
    # 等待 Models 标签页可见元素加载
    await page.get_by_role("button", name="新建模型").wait_for(state="visible")
    await page.wait_for_timeout(500)
    await page.screenshot(path=str(SHOT_DIR / "detail-models.png"), full_page=True)


@pytest.mark.asyncio(loop_scope="session")
async def test_detail_tests_tab(page: Page, base_url: str, visual_project: dict):
    """项目详情 - Tests 标签。"""
    await page.goto(f"{base_url}/projects/{visual_project['id']}")
    await page.get_by_text("Tests", exact=True).click()
    await page.get_by_role("button", name="新建测试").wait_for(state="visible")
    await page.wait_for_timeout(300)
    await page.screenshot(path=str(SHOT_DIR / "detail-tests.png"), full_page=True)


@pytest.mark.asyncio(loop_scope="session")
async def test_detail_dag_tab(page: Page, base_url: str, visual_project: dict):
    """项目详情 - DAG 标签（节点着色与边）。"""
    await page.goto(f"{base_url}/projects/{visual_project['id']}")
    await page.get_by_text("DAG", exact=True).click()
    # 等待 SVG 节点渲染
    await page.wait_for_selector("svg g.node")
    await page.wait_for_timeout(500)
    await page.screenshot(path=str(SHOT_DIR / "detail-dag.png"), full_page=True)


@pytest.mark.asyncio(loop_scope="session")
async def test_detail_runs_tab(page: Page, base_url: str, visual_project: dict):
    """项目详情 - 运行历史标签。"""
    await page.goto(f"{base_url}/projects/{visual_project['id']}")
    await page.get_by_text("运行历史", exact=True).click()
    try:
        await page.get_by_role("button", name="查看日志").first.wait_for(
            state="visible", timeout=3000
        )
    except Exception:
        await page.wait_for_timeout(1000)
    await page.wait_for_timeout(300)
    await page.screenshot(path=str(SHOT_DIR / "detail-runs.png"), full_page=True)
