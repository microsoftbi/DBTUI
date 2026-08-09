"""用户操作手册截图脚本 — 销售数据仓库完整案例。

案例背景：
  源系统 sales_db 有 customer / product / salesorder 三张表
  构建三层数据仓库：stage → core → mart

运行方式：
    cd /Users/wadesong/Documents/trae_projects/DBT
    .venv/bin/python doc/capture_userguide.py
"""
from __future__ import annotations

import asyncio
import shutil
import uuid
from pathlib import Path

import httpx
from playwright.async_api import async_playwright

BASE_URL = "http://localhost:5173"
API_BASE_URL = "http://localhost:8000"
SHOT_DIR = Path(__file__).resolve().parent / "userguide"

STEP = 0


async def shot(page, name: str) -> None:
    global STEP
    STEP += 1
    path = SHOT_DIR / f"{STEP:02d}_{name}.png"
    await page.screenshot(path=str(path), full_page=True)
    print(f"  📸 {STEP:02d}: {name} → {path.name}")


async def wait_btn(page, name: str) -> None:
    await page.get_by_role("button", name=name).wait_for(state="visible", timeout=10000)


async def wait_dialog(page) -> None:
    await page.locator("div[role='dialog']").filter(visible=True).first.wait_for(
        state="visible", timeout=10000
    )


async def reload_project(page, pid: int) -> None:
    """重新加载项目详情页，确保弹窗关闭。"""
    await page.goto(f"{BASE_URL}/projects/{pid}")
    await page.wait_for_selector("h2")
    await wait_btn(page, "新建模型")
    await page.wait_for_timeout(300)


async def create_model_via_api(api, pid: int, name: str, sql: str, subdir: str = "") -> None:
    """通过 API 创建模型（含子目录）。"""
    resp = await api.post(
        f"/api/projects/{pid}/models",
        json={"name": name, "sql": sql, "subdir": subdir},
    )
    if resp.status_code >= 400:
        print(f"  ⚠️ 创建模型 {name} 失败: {resp.text}")


async def main():
    # 清理旧截图
    if SHOT_DIR.exists():
        shutil.rmtree(SHOT_DIR)
    SHOT_DIR.mkdir(parents=True)

    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=120) as api:
        # ---- 创建项目 ----
        proj_name = f"sales_wh_{uuid.uuid4().hex[:6]}"
        resp = await api.post(
            "/api/projects",
            json={
                "name": proj_name,
                "adapter": "duckdb",
                "description": "销售数据仓库 — 三层架构演示项目",
            },
        )
        project = resp.json()
        pid = project["id"]
        await api.post(f"/api/projects/{pid}/parse")
        print(f"项目已创建: {proj_name} (id={pid})")

        # ---- 准备源数据：在 duckdb 中创建源表 ----
        # 通过 profiles 配置指向同一个 duckdb 文件，用 seed 或直接 SQL 建表
        # 这里我们用 dbt seed 方式 — 先创建 seed CSV 文件
        # 为简化，直接通过 API 创建模型并运行

        async with async_playwright() as p:
            browser = await p.chromium.launch()
            context = await browser.new_context(
                viewport={"width": 1440, "height": 900}, device_scale_factor=1
            )
            page = await context.new_page()

            # ================================================================
            # 第 1 章：项目创建
            # ================================================================
            print("\n=== 第 1 章：项目创建 ===")

            # 1.1 项目列表页
            await page.goto(f"{BASE_URL}/")
            await page.wait_for_selector("h1")
            await page.wait_for_timeout(800)
            await shot(page, "项目列表页")

            # 1.2 新建项目弹窗
            await page.get_by_role("button", name="新建项目").click()
            await wait_dialog(page)
            await page.wait_for_timeout(300)
            await shot(page, "新建项目弹窗")

            # 1.3 填写项目信息
            await page.get_by_label("名称").fill("sales_warehouse")
            await page.get_by_label("描述").fill("销售数据仓库 — 三层架构（stage/core/mart）")
            await page.wait_for_timeout(200)
            await shot(page, "填写项目信息")

            # 1.4 关闭弹窗（不创建，避免列表混乱 — 我们用 API 创建的项目做演示）
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(300)

            # 1.5 进入项目详情
            await page.goto(f"{BASE_URL}/projects/{pid}")
            await page.wait_for_selector("h2")
            await wait_btn(page, "新建模型")
            await page.wait_for_timeout(500)
            await shot(page, "项目详情页")

            # 1.6 连接配置
            await page.get_by_role("button", name="连接配置").click()
            await wait_dialog(page)
            await page.wait_for_timeout(300)
            await shot(page, "连接配置_profiles")

            await page.keyboard.press("Escape")
            await page.wait_for_timeout(500)

            # 1.7 重新解析
            await page.get_by_role("button", name="重新解析").click()
            await page.wait_for_timeout(2000)
            await shot(page, "重新解析完成")

            # ================================================================
            # 第 2 章：Stage 层 — 源数据加载
            # ================================================================
            print("\n=== 第 2 章：Stage 层 ===")

            # 2.1 模型列表（初始状态）
            await shot(page, "模型列表_初始")

            # 2.2 新建 stg_customer
            await page.get_by_role("button", name="新建模型").click()
            await wait_dialog(page)
            await page.wait_for_timeout(300)
            await shot(page, "新建模型弹窗")

            # 填写 stg_customer
            await page.get_by_label("名称").fill("stg_customer")
            # 选择层级
            dialog = page.locator(".el-dialog").filter(visible=True).first
            await dialog.locator(".el-select").first.click()
            await page.wait_for_timeout(300)
            await page.locator(".el-select-dropdown__item:visible").filter(has_text="Stage 层").click()
            await page.wait_for_timeout(200)
            # 清空 SQL 编辑器并写入新内容
            sql_editor = dialog.locator(".sql-editor .cm-content")
            await sql_editor.click()
            await page.keyboard.press("Meta+A")
            await page.keyboard.press("Backspace")
            await sql_editor.type(
                "SELECT\n"
                "    customer_id,\n"
                "    customer_name,\n"
                "    email,\n"
                "    city,\n"
                "    created_at\n"
                "FROM {{ ref('raw_customer') }}\n"
            )
            await page.wait_for_timeout(300)
            await shot(page, "填写stg_customer")

            # 关闭弹窗（我们通过 API 批量创建，这里只做演示截图）
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(300)

            # ---- 通过 API 批量创建 stage 层模型 ----
            stage_models = {
                "stg_customer": (
                    "SELECT\n"
                    "    customer_id,\n"
                    "    customer_name,\n"
                    "    email,\n"
                    "    city,\n"
                    "    created_at\n"
                    "FROM {{ ref('raw_customer') }}\n"
                ),
                "stg_product": (
                    "SELECT\n"
                    "    product_id,\n"
                    "    product_name,\n"
                    "    category,\n"
                    "    price\n"
                    "FROM {{ ref('raw_product') }}\n"
                ),
                "stg_salesorder": (
                    "SELECT\n"
                    "    order_id,\n"
                    "    customer_id,\n"
                    "    product_id,\n"
                    "    quantity,\n"
                    "    order_date,\n"
                    "    amount\n"
                    "FROM {{ ref('raw_salesorder') }}\n"
                ),
            }

            # 先创建 raw 表（作为源数据，用 seed 模拟）
            raw_models = {
                "raw_customer": (
                    "SELECT 1 AS customer_id, 'Alice' AS customer_name, 'alice@example.com' AS email, 'Beijing' AS city, '2024-01-01' AS created_at\n"
                    "UNION ALL SELECT 2, 'Bob', 'bob@example.com', 'Shanghai', '2024-01-02'\n"
                    "UNION ALL SELECT 3, 'Charlie', 'charlie@example.com', 'Guangzhou', '2024-01-03'\n"
                ),
                "raw_product": (
                    "SELECT 1 AS product_id, 'Laptop' AS product_name, 'Electronics' AS category, 5999.0 AS price\n"
                    "UNION ALL SELECT 2, 'Mouse', 'Electronics', 99.0\n"
                    "UNION ALL SELECT 3, 'Desk', 'Furniture', 899.0\n"
                ),
                "raw_salesorder": (
                    "SELECT 1 AS order_id, 1 AS customer_id, 1 AS product_id, 2 AS quantity, '2024-01-10' AS order_date, 11998.0 AS amount\n"
                    "UNION ALL SELECT 2, 1, 2, 5, '2024-01-10', 495.0\n"
                    "UNION ALL SELECT 3, 2, 1, 1, '2024-01-11', 5999.0\n"
                    "UNION ALL SELECT 4, 2, 3, 2, '2024-01-12', 1798.0\n"
                    "UNION ALL SELECT 5, 3, 2, 10, '2024-01-13', 990.0\n"
                ),
            }

            for name, sql in raw_models.items():
                await create_model_via_api(api, pid, name, sql, "raw")
            for name, sql in stage_models.items():
                await create_model_via_api(api, pid, name, sql, "stage")

            # 刷新页面看 stage 层
            await reload_project(page, pid)
            await shot(page, "Stage层模型列表")

            # 2.3 运行 stage 层
            await page.get_by_role("button", name="运行").first.click()
            await wait_dialog(page)
            await page.wait_for_timeout(300)
            await shot(page, "运行Stage模型")

            await page.get_by_role("button", name="开始运行").click()
            await page.wait_for_selector(".log-line", timeout=15000)
            await page.wait_for_timeout(2000)
            await shot(page, "Stage运行中")

            try:
                await page.get_by_text("运行完成", exact=False).wait_for(timeout=30000)
            except Exception:
                pass
            await page.wait_for_timeout(500)
            await shot(page, "Stage运行完成")

            await reload_project(page, pid)

            # ================================================================
            # 第 3 章：Core 层 — 维度与事实表
            # ================================================================
            print("\n=== 第 3 章：Core 层 ===")

            # 创建 core 层模型
            core_models = {
                "dim_customer": (
                    "SELECT\n"
                    "    customer_id,\n"
                    "    customer_name,\n"
                    "    email,\n"
                    "    city\n"
                    "FROM {{ ref('stg_customer') }}\n"
                ),
                "dim_product": (
                    "SELECT\n"
                    "    product_id,\n"
                    "    product_name,\n"
                    "    category,\n"
                    "    price\n"
                    "FROM {{ ref('stg_product') }}\n"
                ),
                "fact_sales": (
                    "SELECT\n"
                    "    o.order_id,\n"
                    "    o.customer_id,\n"
                    "    o.product_id,\n"
                    "    o.quantity,\n"
                    "    o.order_date,\n"
                    "    o.amount,\n"
                    "    c.city AS customer_city,\n"
                    "    p.category AS product_category\n"
                    "FROM {{ ref('stg_salesorder') }} o\n"
                    "LEFT JOIN {{ ref('stg_customer') }} c ON o.customer_id = c.customer_id\n"
                    "LEFT JOIN {{ ref('stg_product') }} p ON o.product_id = p.product_id\n"
                ),
            }

            for name, sql in core_models.items():
                await create_model_via_api(api, pid, name, sql, "core")

            await reload_project(page, pid)
            await shot(page, "Core层模型列表")

            # 3.1 编辑 fact_sales 查看 SQL
            # 找到 fact_sales 行的编辑按钮
            fact_row = page.locator("tr").filter(has_text="fact_sales")
            await fact_row.get_by_role("button", name="编辑").click()
            await wait_dialog(page)
            await page.wait_for_timeout(500)
            await shot(page, "编辑fact_sales")

            await page.keyboard.press("Escape")
            await page.wait_for_timeout(300)
            await reload_project(page, pid)

            # 3.2 运行 core 层（运行 fact_sales 会连带运行上游）
            fact_row = page.locator("tr").filter(has_text="fact_sales")
            await fact_row.get_by_role("button", name="运行").click()
            await wait_dialog(page)
            await page.wait_for_timeout(300)
            await shot(page, "运行Core层")

            await page.get_by_role("button", name="开始运行").click()
            await page.wait_for_selector(".log-line", timeout=15000)
            await page.wait_for_timeout(3000)
            await shot(page, "Core运行中")

            try:
                await page.get_by_text("运行完成", exact=False).wait_for(timeout=30000)
            except Exception:
                pass
            await page.wait_for_timeout(500)
            await shot(page, "Core运行完成")

            await reload_project(page, pid)

            # ================================================================
            # 第 4 章：Mart 层 — 宽表
            # ================================================================
            print("\n=== 第 4 章：Mart 层 ===")

            mart_sql = (
                "SELECT\n"
                "    f.order_id,\n"
                "    f.order_date,\n"
                "    f.customer_id,\n"
                "    c.customer_name,\n"
                "    c.email,\n"
                "    c.city AS customer_city,\n"
                "    f.product_id,\n"
                "    p.product_name,\n"
                "    p.category AS product_category,\n"
                "    p.price AS unit_price,\n"
                "    f.quantity,\n"
                "    f.amount\n"
                "FROM {{ ref('fact_sales') }} f\n"
                "LEFT JOIN {{ ref('dim_customer') }} c ON f.customer_id = c.customer_id\n"
                "LEFT JOIN {{ ref('dim_product') }} p ON f.product_id = p.product_id\n"
            )
            await create_model_via_api(api, pid, "mart_sales_summary", mart_sql, "marts")

            await reload_project(page, pid)
            await shot(page, "Mart层模型列表")

            # 4.1 新建测试
            await page.get_by_text("Tests", exact=True).click()
            await wait_btn(page, "新建测试")
            await page.wait_for_timeout(300)
            await shot(page, "Tests标签页")

            await page.get_by_role("button", name="新建测试").click()
            await wait_dialog(page)
            await page.wait_for_timeout(300)
            await shot(page, "新建测试弹窗")

            # 填写测试
            await page.get_by_label("名称").fill("test_amount_positive")
            test_editor = page.locator(".el-dialog").filter(visible=True).first.locator(".sql-editor .cm-content")
            await test_editor.click()
            await page.keyboard.press("Meta+A")
            await page.keyboard.press("Backspace")
            await test_editor.type(
                "SELECT *\n"
                "FROM {{ ref('mart_sales_summary') }}\n"
                "WHERE amount <= 0\n"
            )
            await page.wait_for_timeout(300)
            await shot(page, "填写测试SQL")

            # 关闭弹窗，用 API 创建
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(300)

            await api.post(
                f"/api/projects/{pid}/tests",
                json={
                    "name": "test_amount_positive",
                    "sql": "SELECT *\nFROM {{ ref('mart_sales_summary') }}\nWHERE amount <= 0\n",
                },
            )
            await api.post(f"/api/projects/{pid}/parse")

            await page.reload()
            await page.wait_for_selector("h2")
            await page.get_by_text("Tests", exact=True).click()
            await wait_btn(page, "新建测试")
            await page.wait_for_timeout(500)
            await shot(page, "测试列表")

            # ================================================================
            # 第 5 章：DAG 血缘图
            # ================================================================
            print("\n=== 第 5 章：DAG 血缘图 ===")

            await page.get_by_text("DAG", exact=True).click()
            await page.wait_for_selector(".dag-canvas svg", timeout=10000)
            await page.wait_for_timeout(1500)
            await shot(page, "DAG全景图")

            # 点击 fact_sales 节点
            fact_node = page.locator("svg g.node").filter(has_text="fact_sales").first
            if await fact_node.count() > 0:
                await fact_node.click()
                await page.wait_for_timeout(500)
                await shot(page, "DAG_fact_sales血缘")

            # 点击 mart_sales_summary 节点
            mart_node = page.locator("svg g.node").filter(has_text="mart_sales_summary").first
            if await mart_node.count() > 0:
                await mart_node.click()
                await page.wait_for_timeout(500)
                await shot(page, "DAG_mart宽表血缘")

            # ================================================================
            # 第 6 章：运行历史
            # ================================================================
            print("\n=== 第 6 章：运行历史 ===")

            await page.get_by_text("运行历史", exact=True).click()
            try:
                await page.get_by_role("button", name="查看日志").first.wait_for(
                    state="visible", timeout=10000
                )
            except Exception:
                await page.wait_for_timeout(1500)
            await page.wait_for_timeout(300)
            await shot(page, "运行历史列表")

            # 查看日志
            log_btn = page.get_by_role("button", name="查看日志").first
            if await log_btn.count() > 0:
                await log_btn.click()
                await wait_dialog(page)
                await page.wait_for_timeout(500)
                await shot(page, "查看运行日志")
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(300)

            # ================================================================
            # 第 7 章：返回项目列表
            # ================================================================
            print("\n=== 第 7 章：返回 ===")

            await page.get_by_role("button", name="返回").click()
            await page.wait_for_selector("h1")
            await page.wait_for_timeout(300)
            await shot(page, "返回项目列表")

            await browser.close()

        # 清理测试项目
        await api.delete(f"/api/projects/{pid}")
        print(f"\n✅ 截图完成，共 {STEP} 张，保存到 {SHOT_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
