"""Playwright 视觉回归测试配置与 fixtures。

运行方式：
    pytest test/uat/visual/ --visual-baseline
    # 或更新基线
    pytest test/uat/visual/ --visual-baseline --update-snapshots
"""
from __future__ import annotations

import os
from typing import AsyncGenerator

import httpx
import pytest
import pytest_asyncio
from playwright.async_api import Browser, BrowserContext, Page, async_playwright

BASE_URL = os.environ.get("DBT_UI_BASE_URL", "http://localhost:5173")
API_BASE_URL = os.environ.get("DBT_API_BASE_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def api_base_url() -> str:
    return API_BASE_URL


@pytest.fixture(scope="session")
def base_url() -> str:
    return BASE_URL


@pytest_asyncio.fixture(scope="session")
async def browser() -> AsyncGenerator[Browser, None]:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        yield browser
        await browser.close()


@pytest_asyncio.fixture
async def page(browser: Browser) -> AsyncGenerator[Page, None]:
    context: BrowserContext = await browser.new_context(
        viewport={"width": 1440, "height": 900},
        device_scale_factor=1,
    )
    page = await context.new_page()
    yield page
    await context.close()


@pytest_asyncio.fixture(scope="session")
async def visual_project(api_base_url: str) -> dict:
    """为视觉测试创建一个专用 sqlserver 项目并 parse，session 结束删除。"""
    import uuid

    name = f"visual_{uuid.uuid4().hex[:8]}"
    async with httpx.AsyncClient(base_url=api_base_url, timeout=60) as client:
        resp = await client.post(
            "/api/projects",
            json={"name": name, "adapter": "sqlserver", "description": "visual test project"},
        )
        assert resp.status_code == 201
        project = resp.json()
        # parse
        resp = await client.post(f"/api/projects/{project['id']}/parse")
        assert resp.status_code == 200
        # 跑一次 example 让状态有数据
        resp = await client.post(
            f"/api/projects/{project['id']}/runs",
            json={"run_type": "run", "selection": "example"},
        )
        assert resp.status_code == 202

        yield project

        await client.delete(f"/api/projects/{project['id']}")
