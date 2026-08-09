"""端到端 UAT 测试脚本 — 按手工用例步骤操作，每步截图。

截图保存到 ../20260808a/ 目录。
运行方式：
    cd test/uat/visual
    pytest test_uat_e2e.py -v
"""
from __future__ import annotations

import os
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from playwright.async_api import Page, expect

SCREENSHOT_DIR = Path(__file__).resolve().parent.parent / "20260808a"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

step_counter = 0


async def shot(page: Page, name: str) -> None:
    """截图并按序号命名。"""
    global step_counter
    step_counter += 1
    path = SCREENSHOT_DIR / f"{step_counter:02d}_{name}.png"
    await page.screenshot(path=str(path), full_page=True)
    print(f"  📸 截图 {step_counter:02d}: {name} → {path.name}")


@pytest_asyncio.fixture(scope="session", autouse=True)
async def uat_project(api_base_url: str) -> dict:
    """创建 UAT 报告专用项目。"""
    import uuid

    name = f"report_{uuid.uuid4().hex[:6]}"
    async with httpx.AsyncClient(base_url=api_base_url, timeout=60) as client:
        resp = await client.post(
            "/api/projects",
            json={"name": name, "adapter": "sqlserver", "description": "UAT 报告演示项目"},
        )
        assert resp.status_code == 201
        project = resp.json()
        # parse 一次
        await client.post(f"/api/projects/{project['id']}/parse")
        yield project
        await client.delete(f"/api/projects/{project['id']}")


@pytest.mark.asyncio(loop_scope="session")
async def test_uat_full_flow(page: Page, base_url: str, uat_project: dict):
    """完整 UAT 流程：项目列表 → 详情 → 模型 → 测试 → DAG → 运行 → 历史。"""
    pid = uat_project["id"]

    # ===== 1. 项目列表页 =====
    await page.goto(f"{base_url}/")
    await page.wait_for_selector("h1")
    await page.wait_for_timeout(300)
    await shot(page, "项目列表页")

    # ===== 2. 点击新建项目弹窗 =====
    await page.get_by_role("button", name="新建项目").click()
    await page.locator("div[role='dialog']").filter(visible=True).first.wait_for(state="visible", timeout=10000)
    await page.wait_for_timeout(200)
    await shot(page, "新建项目弹窗")
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(200)

    # ===== 3. 进入项目详情 =====
    await page.goto(f"{base_url}/projects/{pid}")
    await page.wait_for_selector("h2")
    await page.get_by_role("button", name="新建模型").wait_for(state="visible")
    await page.wait_for_timeout(500)
    await shot(page, "项目详情_Models标签")

    # ===== 4. 新建模型 =====
    await page.get_by_role("button", name="新建模型").click()
    await page.locator("div[role='dialog']").filter(visible=True).first.wait_for(state="visible", timeout=10000)
    await page.wait_for_timeout(200)
    await shot(page, "新建模型弹窗")
    # 填名字
    name_input = page.locator("input[placeholder='模型名（不含 .sql）']")
    await name_input.fill("uat_e2e_orders")
    await page.wait_for_timeout(200)
    await shot(page, "填写模型信息")
    await page.get_by_role("button", name="创建").click()
    # 等待弹窗关闭（模型创建+解析完成）
    await page.locator("div[role='dialog'][aria-label='新建模型']").first.wait_for(state="hidden", timeout=20000)
    await page.wait_for_timeout(500)
    await shot(page, "模型创建成功")

    # ===== 5. Tests 标签 =====
    await page.get_by_text("Tests", exact=True).click()
    await page.get_by_role("button", name="新建测试").wait_for(state="visible")
    await page.wait_for_timeout(300)
    await shot(page, "Tests标签")

    # ===== 6. 新建 singular test =====
    await page.get_by_role("button", name="新建测试").click()
    await page.locator("div[role='dialog']").filter(visible=True).first.wait_for(state="visible", timeout=10000)
    await page.wait_for_timeout(200)
    await shot(page, "新建测试弹窗")
    await page.locator("input[placeholder='测试名（不含 .sql）']").fill("uat_e2e_positive")
    await page.wait_for_timeout(200)
    await shot(page, "填写测试信息")
    await page.get_by_role("button", name="保存").click()
    # 等待测试弹窗关闭
    await page.locator("div[role='dialog'][aria-label='新建测试']").first.wait_for(state="hidden", timeout=20000)
    await page.wait_for_timeout(500)
    await shot(page, "测试创建成功")

    # ===== 7. DAG 标签 =====
    await page.get_by_text("DAG", exact=True).click()
    await page.wait_for_selector("svg g.node")
    await page.wait_for_timeout(800)
    await shot(page, "DAG血缘图")

    # ===== 8. 点击节点查看血缘 =====
    svg_nodes = page.locator("svg g.node")
    count = await svg_nodes.count()
    assert count > 0
    await svg_nodes.first.click()
    await page.wait_for_timeout(300)
    await shot(page, "DAG选中节点_血缘高亮")

    # ===== 9. 连接配置弹窗 =====
    await page.get_by_role("button", name="连接配置").click()
    await page.locator("div[role='dialog']").filter(visible=True).first.wait_for(state="visible", timeout=10000)
    await page.wait_for_timeout(300)
    await shot(page, "连接配置弹窗")
    await page.keyboard.press("Escape")
    await page.locator("div[role='dialog'][aria-label='连接配置（profiles.yml）']").first.wait_for(state="hidden", timeout=10000)
    await page.wait_for_timeout(200)

    # ===== 10. 运行模型 =====
    await page.get_by_text("Models", exact=True).click()
    await page.get_by_role("button", name="新建模型").wait_for(state="visible")
    await page.wait_for_timeout(300)
    # 找到 uat_e2e_orders 行的运行按钮
    row = page.locator("tr", has_text="uat_e2e_orders")
    await row.get_by_role("button", name="运行").first.click()
    await page.locator("div[role='dialog']").filter(visible=True).first.wait_for(state="visible", timeout=10000)
    await page.wait_for_timeout(200)
    await shot(page, "运行对话框")
    await page.get_by_role("button", name="开始运行").click()
    await page.wait_for_timeout(2000)
    await shot(page, "运行中_日志实时输出")
    # 等运行完成
    await page.wait_for_selector("text=运行完成", timeout=30000)
    await page.wait_for_timeout(300)
    await shot(page, "运行成功")
    await page.keyboard.press("Escape")
    await page.locator("div[role='dialog'][aria-label='运行']").first.wait_for(state="hidden", timeout=10000)
    await page.wait_for_timeout(300)

    # ===== 11. 运行历史 =====
    await page.get_by_text("运行历史", exact=True).click()
    await page.get_by_role("button", name="查看日志").first.wait_for(state="visible", timeout=10000)
    await page.wait_for_timeout(300)
    await shot(page, "运行历史")

    # ===== 12. 查看日志 =====
    await page.get_by_role("button", name="查看日志").first.click()
    await page.locator("div[role='dialog']").filter(visible=True).first.wait_for(state="visible", timeout=10000)
    await page.wait_for_timeout(300)
    await shot(page, "查看运行日志")

    print(f"\n✅ UAT 端到端流程完成，共截图 {step_counter} 张 → {SCREENSHOT_DIR}")
