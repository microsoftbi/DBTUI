"""用户操作手册截图脚本 — SQL Server 三层分库版本。

案例背景：
  源系统 SQL Server 上的 sales_db 数据库，三张业务表（customer/product/salesorder）
  构建三层数据仓库：stage_db → core_db → mart_db

运行方式：
    cd /Users/wadesong/Documents/trae_projects/DBT
    .venv/bin/python doc/capture_userguide_sqlserver.py
"""
from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

import httpx
from playwright.async_api import async_playwright

BASE_URL = "http://localhost:5174"
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
    await page.wait_for_timeout(500)


async def create_model_via_api(api, pid: int, name: str, sql: str, subdir: str = "") -> None:
    """通过 API 创建模型（含子目录）。"""
    resp = await api.post(
        f"/api/projects/{pid}/models",
        json={"name": name, "sql": sql, "subdir": subdir},
    )
    if resp.status_code >= 400:
        print(f"  ⚠️ 创建模型 {name} 失败: {resp.text}")
    else:
        print(f"  ✅ 模型 {name} 创建成功")


async def main():
    # 清理旧截图
    if SHOT_DIR.exists():
        shutil.rmtree(SHOT_DIR)
    SHOT_DIR.mkdir(parents=True)

    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=120) as api:
        # ---- 创建项目 ----
        proj_name = "sales_warehouse"
        resp = await api.post(
            "/api/projects",
            json={
                "name": proj_name,
                "adapter": "sqlserver",
                "description": "销售数据仓库三层分库",
            },
        )
        if resp.status_code >= 400:
            print(f"创建项目失败: {resp.text}")
            return
        project = resp.json()
        pid = project["id"]
        project_path = project["path"]
        print(f"项目已创建: {proj_name} (id={pid}, path={project_path})")

        # 首次解析
        resp = await api.post(f"/api/projects/{pid}/parse")
        if resp.status_code >= 400:
            print(f"首次解析失败: {resp.text}")

        async with async_playwright() as p:
            browser = await p.chromium.launch()
            context = await browser.new_context(
                viewport={"width": 1440, "height": 900}, device_scale_factor=1
            )
            page = await context.new_page()

            # ================================================================
            # 第 1 章：创建项目
            # ================================================================
            print("\n=== 第 1 章：创建项目 ===")

            # 1. 项目列表页（空状态）
            await page.goto(f"{BASE_URL}/")
            await page.wait_for_selector("h1")
            await page.wait_for_timeout(800)
            await shot(page, "项目列表页")

            # 2. 新建项目弹窗
            await page.get_by_role("button", name="新建项目").click()
            await wait_dialog(page)
            await page.wait_for_timeout(300)
            await shot(page, "新建项目弹窗")

            # 3. 填写项目信息（sqlserver 适配器）
            await page.get_by_label("项目名称").fill("sales_warehouse")
            # 选择适配器
            dialog = page.locator(".el-dialog").filter(visible=True).first
            await dialog.locator(".el-select").first.click()
            await page.wait_for_timeout(300)
            await page.locator(".el-select-dropdown__item:visible").filter(
                has_text="sqlserver"
            ).click()
            await page.wait_for_timeout(200)
            await page.get_by_label("描述").fill("销售数据仓库三层分库")
            await page.wait_for_timeout(300)
            await shot(page, "填写项目信息")

            # 关闭弹窗（不创建，我们用 API 创建的项目做演示）
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(500)

            # 4. 项目创建成功后的列表页
            await page.reload()
            await page.wait_for_selector("h1")
            await page.wait_for_timeout(800)
            await shot(page, "项目列表_创建成功")

            # 5. 点击打开，进入项目详情页（初始状态）
            await page.get_by_role("button", name="打开").first.click()
            await page.wait_for_selector("h2")
            await wait_btn(page, "新建模型")
            await page.wait_for_timeout(500)
            await shot(page, "项目详情页")

            # 6. 点击连接配置，显示 profiles.yml（sqlserver 配置）
            await page.get_by_role("button", name="连接配置").click()
            await wait_dialog(page)
            await page.wait_for_timeout(500)
            await shot(page, "连接配置_profiles")

            await page.keyboard.press("Escape")
            await page.wait_for_timeout(500)

            # 7. 重新解析成功
            await page.get_by_role("button", name="重新解析").click()
            await page.wait_for_timeout(3000)
            await shot(page, "重新解析完成")

            # ================================================================
            # 第 2 章：配置源系统（source 定义）
            # ================================================================
            print("\n=== 第 2 章：配置源系统 ===")

            # 8. 配置 source：在 models/staging/ 下创建 sources.yml（直接写文件）
            sources_yml = (
                "version: 2\n"
                "sources:\n"
                "  - name: sales_db\n"
                "    database: sales_db\n"
                "    schema: dbo\n"
                "    tables:\n"
                "      - name: customer\n"
                "        description: \"客户表\"\n"
                "      - name: product\n"
                "        description: \"产品表\"\n"
                "      - name: salesorder\n"
                "        description: \"销售订单表\"\n"
            )
            sources_path = Path(project_path) / "models" / "staging" / "sources.yml"
            sources_path.write_text(sources_yml, encoding="utf-8")
            print(f"  ✅ sources.yml 已写入: {sources_path}")

            # 重新解析
            resp = await api.post(f"/api/projects/{pid}/parse")
            if resp.status_code >= 400:
                print(f"  ⚠️ 解析失败: {resp.text}")

            # 9. 模型列表（显示 source 和初始模型）
            await reload_project(page, pid)
            await shot(page, "模型列表_含source")

            # ================================================================
            # 第 3 章：Stage 层 — 贴源加载
            # ================================================================
            print("\n=== 第 3 章：Stage 层 ===")

            # 10. 新建模型弹窗（创建 stg_customer）
            await page.get_by_role("button", name="新建模型").click()
            await wait_dialog(page)
            await page.wait_for_timeout(300)
            await shot(page, "新建模型弹窗")

            # 11. 填写 stg_customer SQL（从 source 加载）
            await page.get_by_label("名称").fill("stg_customer")
            dialog = page.locator(".el-dialog").filter(visible=True).first
            # 选择层级
            await dialog.locator(".el-select").first.click()
            await page.wait_for_timeout(300)
            await page.locator(".el-select-dropdown__item:visible").filter(
                has_text="Stage 层"
            ).click()
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
                "    gender,\n"
                "    age,\n"
                "    city,\n"
                "    create_date\n"
                "FROM {{ source('sales_db', 'customer') }}\n"
            )
            await page.wait_for_timeout(500)
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
                    "    gender,\n"
                    "    age,\n"
                    "    city,\n"
                    "    create_date\n"
                    "FROM {{ source('sales_db', 'customer') }}\n"
                ),
                "stg_product": (
                    "SELECT\n"
                    "    product_id,\n"
                    "    product_name,\n"
                    "    category,\n"
                    "    price,\n"
                    "    create_date\n"
                    "FROM {{ source('sales_db', 'product') }}\n"
                ),
                "stg_salesorder": (
                    "SELECT\n"
                    "    order_id,\n"
                    "    order_date,\n"
                    "    customer_id,\n"
                    "    product_id,\n"
                    "    quantity,\n"
                    "    unit_price,\n"
                    "    amount,\n"
                    "    status\n"
                    "FROM {{ source('sales_db', 'salesorder') }}\n"
                ),
            }

            for name, sql in stage_models.items():
                await create_model_via_api(api, pid, name, sql, "staging")

            # 12. Stage 层三个模型创建完成后的列表
            await reload_project(page, pid)
            await shot(page, "Stage层模型列表")

            # 13. 运行 stg_customer（运行对话框）
            stg_row = page.locator("tr").filter(has_text="stg_customer")
            await stg_row.get_by_role("button", name="运行").click()
            await wait_dialog(page)
            await page.wait_for_timeout(300)
            await shot(page, "运行stg_customer")

            # 14. 运行中（实时日志）
            await page.get_by_role("button", name="开始运行").click()
            await page.wait_for_selector(".log-line", timeout=15000)
            await page.wait_for_timeout(3000)
            await shot(page, "Stage运行中")

            # 15. 运行完成
            try:
                await page.get_by_text("运行完成", exact=False).wait_for(timeout=60000)
            except Exception:
                pass
            await page.wait_for_timeout(500)
            await shot(page, "Stage运行完成")

            await reload_project(page, pid)

            # ================================================================
            # 第 4 章：Core 层 — 维度建模
            # ================================================================
            print("\n=== 第 4 章：Core 层 ===")

            # 创建 core 层模型
            core_models = {
                "dim_customer": (
                    "SELECT\n"
                    "    customer_id,\n"
                    "    customer_name,\n"
                    "    gender,\n"
                    "    age,\n"
                    "    city,\n"
                    "    create_date\n"
                    "FROM {{ ref('stg_customer') }}\n"
                ),
                "dim_product": (
                    "SELECT\n"
                    "    product_id,\n"
                    "    product_name,\n"
                    "    category,\n"
                    "    price,\n"
                    "    create_date\n"
                    "FROM {{ ref('stg_product') }}\n"
                ),
                "fact_sales": (
                    "SELECT\n"
                    "    s.order_id,\n"
                    "    s.order_date,\n"
                    "    s.customer_id,\n"
                    "    s.product_id,\n"
                    "    s.quantity,\n"
                    "    s.unit_price,\n"
                    "    s.amount,\n"
                    "    s.status\n"
                    "FROM {{ ref('stg_salesorder') }} s\n"
                    "WHERE s.status = 'completed'\n"
                ),
            }

            for name, sql in core_models.items():
                await create_model_via_api(api, pid, name, sql, "core")

            # 16. Core 层模型列表
            await reload_project(page, pid)
            await shot(page, "Core层模型列表")

            # 17. 编辑 fact_sales SQL
            fact_row = page.locator("tr").filter(has_text="fact_sales")
            await fact_row.get_by_role("button", name="编辑").click()
            await wait_dialog(page)
            await page.wait_for_timeout(800)
            await shot(page, "编辑fact_sales")

            await page.keyboard.press("Escape")
            await page.wait_for_timeout(300)
            await reload_project(page, pid)

            # 18. 运行 fact_sales
            fact_row = page.locator("tr").filter(has_text="fact_sales")
            await fact_row.get_by_role("button", name="运行").click()
            await wait_dialog(page)
            await page.wait_for_timeout(300)
            await shot(page, "运行fact_sales")

            await page.get_by_role("button", name="开始运行").click()
            await page.wait_for_selector(".log-line", timeout=15000)
            await page.wait_for_timeout(3000)
            await shot(page, "Core运行中")

            try:
                await page.get_by_text("运行完成", exact=False).wait_for(timeout=60000)
            except Exception:
                pass
            await page.wait_for_timeout(500)
            await shot(page, "Core运行完成")

            await reload_project(page, pid)

            # ================================================================
            # 第 5 章：Mart 层 — 应用宽表 + 数据测试
            # ================================================================
            print("\n=== 第 5 章：Mart 层 ===")

            mart_sql = (
                "SELECT\n"
                "    f.order_id,\n"
                "    f.order_date,\n"
                "    f.customer_id,\n"
                "    c.customer_name,\n"
                "    c.gender,\n"
                "    c.age,\n"
                "    c.city,\n"
                "    f.product_id,\n"
                "    p.product_name,\n"
                "    p.category,\n"
                "    p.price,\n"
                "    f.quantity,\n"
                "    f.unit_price,\n"
                "    f.amount,\n"
                "    f.status\n"
                "FROM {{ ref('fact_sales') }} f\n"
                "LEFT JOIN {{ ref('dim_customer') }} c ON f.customer_id = c.customer_id\n"
                "LEFT JOIN {{ ref('dim_product') }} p ON f.product_id = p.product_id\n"
            )
            await create_model_via_api(api, pid, "sales_wide", mart_sql, "marts")

            # 19. Mart 层模型列表
            await reload_project(page, pid)
            await shot(page, "Mart层模型列表")

            # 20. 新建测试弹窗
            await page.get_by_text("Tests", exact=True).click()
            await wait_btn(page, "新建测试")
            await page.wait_for_timeout(300)
            await shot(page, "Tests标签页")

            await page.get_by_role("button", name="新建测试").click()
            await wait_dialog(page)
            await page.wait_for_timeout(300)
            await shot(page, "新建测试弹窗")

            # 21. 填写测试 SQL（测试 amount > 0）
            await page.get_by_label("名称").fill("test_amount_positive")
            test_editor = (
                page.locator(".el-dialog")
                .filter(visible=True)
                .first.locator(".sql-editor .cm-content")
            )
            await test_editor.click()
            await page.keyboard.press("Meta+A")
            await page.keyboard.press("Backspace")
            await test_editor.type(
                "SELECT *\n"
                "FROM {{ ref('sales_wide') }}\n"
                "WHERE amount <= 0\n"
            )
            await page.wait_for_timeout(500)
            await shot(page, "填写测试SQL")

            # 关闭弹窗，用 API 创建
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(300)

            await api.post(
                f"/api/projects/{pid}/tests",
                json={
                    "name": "test_amount_positive",
                    "sql": "SELECT *\nFROM {{ ref('sales_wide') }}\nWHERE amount <= 0\n",
                },
            )

            # 22. 测试列表
            await page.reload()
            await page.wait_for_selector("h2")
            await page.get_by_text("Tests", exact=True).click()
            await wait_btn(page, "新建测试")
            await page.wait_for_timeout(500)
            await shot(page, "测试列表")

            # ================================================================
            # 第 6 章：DAG 血缘图
            # ================================================================
            print("\n=== 第 6 章：DAG 血缘图 ===")

            await page.get_by_text("DAG", exact=True).click()
            await page.wait_for_selector(".dag-canvas svg", timeout=10000)
            await page.wait_for_timeout(1500)
            # 23. DAG 全景图
            await shot(page, "DAG全景图")

            # 24. DAG 选中 fact_sales 的血缘
            fact_node = page.locator("svg g.node").filter(has_text="fact_sales").first
            if await fact_node.count() > 0:
                await fact_node.click()
                await page.wait_for_timeout(800)
                await shot(page, "DAG_fact_sales血缘")

            # 25. DAG 选中 sales_wide 的血缘
            mart_node = page.locator("svg g.node").filter(has_text="sales_wide").first
            if await mart_node.count() > 0:
                await mart_node.click()
                await page.wait_for_timeout(800)
                await shot(page, "DAG_sales_wide血缘")

            # ================================================================
            # 第 7 章：运行历史与日志
            # ================================================================
            print("\n=== 第 7 章：运行历史 ===")

            await page.get_by_text("运行历史", exact=True).click()
            try:
                await page.get_by_role("button", name="查看日志").first.wait_for(
                    state="visible", timeout=10000
                )
            except Exception:
                await page.wait_for_timeout(1500)
            await page.wait_for_timeout(300)
            # 26. 运行历史列表
            await shot(page, "运行历史列表")

            # 27. 查看运行日志
            log_btn = page.get_by_role("button", name="查看日志").first
            if await log_btn.count() > 0:
                await log_btn.click()
                await wait_dialog(page)
                await page.wait_for_timeout(500)
                await shot(page, "查看运行日志")
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(300)

            # 28. 返回项目列表
            await page.get_by_role("button", name="返回").click()
            await page.wait_for_selector("h1")
            await page.wait_for_timeout(300)
            await shot(page, "返回项目列表")

            await browser.close()

        print(f"\n✅ 截图完成，共 {STEP} 张，保存到 {SHOT_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
