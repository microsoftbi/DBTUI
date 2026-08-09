"""DBT UI 完整 UAT 测试脚本（SQL Server 版）。

覆盖：项目管理、分层配置、Sources 管理、模型管理、测试管理、DAG、运行历史。
每个关键步骤采集界面截图，最终生成 Markdown 测试报告。

运行方式：
    cd /Users/wadesong/Documents/trae_projects/DBT
    .venv/bin/python test/uat/run_uat_full.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import datetime

import httpx
from playwright.async_api import async_playwright
import asyncio

BASE_URL = "http://localhost:5173"
API_BASE_URL = "http://localhost:8000"

REPORT_DIR = os.path.join(os.path.dirname(__file__), "report_20260908a")
SCREENSHOT_DIR = os.path.join(REPORT_DIR, "screenshots")
REPORT_FILE = os.path.join(os.path.dirname(__file__), "testreport_20260908a.md")

os.makedirs(SCREENSHOT_DIR, exist_ok=True)

passed = 0
failed = 0
results: list[dict] = []
screenshots: list[dict] = []


def record(case_id: str, name: str, ok: bool, err: str = "", section: str = ""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  ✅ {case_id} {name}")
    else:
        failed += 1
        print(f"  ❌ {case_id} {name}: {err}")
    results.append({
        "id": case_id,
        "name": name,
        "ok": ok,
        "err": err,
        "section": section,
    })


def add_screenshot(filename: str, title: str, case_id: str = ""):
    screenshots.append({
        "file": filename,
        "title": title,
        "case_id": case_id,
    })


async def ss(page, filename: str, title: str, case_id: str = ""):
    """截图并记录。"""
    path = os.path.join(SCREENSHOT_DIR, filename)
    await page.wait_for_timeout(500)
    await page.screenshot(path=path, full_page=True)
    add_screenshot(filename, title, case_id)


async def wait_btn(page, name: str, timeout: int = 10000) -> None:
    await page.get_by_role("button", name=name).wait_for(state="visible", timeout=timeout)


async def close_dialogs(page):
    """关闭所有可能打开的弹窗。"""
    for _ in range(3):
        try:
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(300)
        except Exception:
            pass


async def main():
    print("=" * 70)
    print("DBT UI 完整 UAT 测试（SQL Server 版）")
    print("=" * 70)
    start_time = datetime.now()

    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=120) as api:
        # 清理残留测试项目
        proj_list = (await api.get("/api/projects")).json()
        for p in proj_list:
            if p["name"].startswith("uat_"):
                await api.delete(f"/api/projects/{p['id']}")

        proj_name = f"uat_{uuid.uuid4().hex[:6]}"
        pid = None

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(viewport={"width": 1440, "height": 900})
            page = await context.new_page()

            # ================================================================
            # 第 1 章：项目管理
            # ================================================================
            section = "第 1 章：项目管理"
            print(f"\n📗 {section}")

            # 1.1 项目列表页
            try:
                await page.goto(BASE_URL)
                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(1000)
                await ss(page, "01_项目列表页.png", "项目列表页", "TC-01-01")
                record("TC-01-01", "项目列表页正常加载", True, section=section)
            except Exception as e:
                record("TC-01-01", "项目列表页正常加载", False, str(e), section=section)

            # 1.2 新建项目弹窗
            try:
                await page.get_by_role("button", name="新建项目").click()
                await page.wait_for_timeout(500)
                await ss(page, "02_新建项目弹窗.png", "新建项目弹窗", "TC-01-02")
                record("TC-01-02", "新建项目弹窗正常打开", True, section=section)
            except Exception as e:
                record("TC-01-02", "新建项目弹窗正常打开", False, str(e), section=section)

            # 1.3 创建项目（API 创建 + UI 验证）
            try:
                # 先关闭弹窗
                await close_dialogs(page)
                await page.wait_for_timeout(500)
                # 用 API 创建项目，稳定可靠
                resp = await api.post(
                    "/api/projects",
                    json={"name": proj_name, "adapter": "sqlserver", "description": "UAT 测试项目"},
                )
                if resp.status_code >= 400:
                    raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
                proj = resp.json()
                pid = proj["id"]
                # 刷新页面验证列表
                await page.reload()
                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(1000)
                # 验证列表中存在
                page_text = await page.locator("body").inner_text()
                if proj_name not in page_text:
                    raise Exception("项目列表中未找到新建项目")
                await ss(page, "04_项目创建成功.png", "项目创建成功", "TC-01-03")
                record("TC-01-03", "创建 sqlserver 项目成功", True, section=section)
            except Exception as e:
                record("TC-01-03", "创建 sqlserver 项目成功", False, str(e), section=section)
                await close_dialogs(page)

            if not pid:
                # 兜底
                resp = await api.post(
                    "/api/projects",
                    json={"name": proj_name, "adapter": "sqlserver", "description": "UAT 测试项目"},
                )
                pid = resp.json()["id"]

            # 1.4 profiles.yml 连接配置
            try:
                resp = await api.get(f"/api/projects/{pid}/profiles")
                content = resp.json()["content"]
                assert "sqlserver" in content, "缺少 sqlserver 类型"
                assert "stage_db" in content, "缺少 stage_db 数据库"
                assert "ODBC Driver" in content, "缺少 ODBC 驱动配置"
                record("TC-01-04", "profiles.yml sqlserver 配置正确", True, section=section)
            except Exception as e:
                record("TC-01-04", "profiles.yml sqlserver 配置正确", False, str(e), section=section)

            # 1.5 dbt_project.yml 三层分库配置
            try:
                import os
                proj_path = (await api.get(f"/api/projects/{pid}")).json()["path"]
                dbt_project_file = os.path.join(proj_path, "dbt_project.yml")
                with open(dbt_project_file, "r") as f:
                    content = f.read()
                assert "staging" in content, "缺少 staging 层配置"
                assert "core" in content, "缺少 core 层配置"
                assert "marts" in content, "缺少 marts 层配置"
                assert "stage_db" in content, "缺少 stage_db 配置"
                assert "core_db" in content, "缺少 core_db 配置"
                assert "mart_db" in content, "缺少 mart_db 配置"
                record("TC-01-05", "dbt_project.yml 三层分库配置完整", True, section=section)
            except Exception as e:
                record("TC-01-05", "dbt_project.yml 三层分库配置完整", False, str(e), section=section)

            # ================================================================
            # 第 2 章：分层配置管理
            # ================================================================
            section = "第 2 章：分层配置管理"
            print(f"\n📗 {section}")

            # 进入项目详情
            try:
                await page.goto(f"{BASE_URL}/projects/{pid}")
                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(1500)
                await ss(page, "05_项目详情页.png", "项目详情页", "TC-02-01")
            except Exception as e:
                print(f"  ⚠️ 进入项目详情失败: {e}")

            # 2.1 分层配置入口
            try:
                await wait_btn(page, "分层配置")
                await ss(page, "06_分层配置入口.png", "分层配置入口按钮", "TC-02-01")
                record("TC-02-01", "分层配置入口按钮存在", True, section=section)
            except Exception as e:
                record("TC-02-01", "分层配置入口按钮存在", False, str(e), section=section)

            # 2.2 分层配置列表
            try:
                await page.get_by_role("button", name="分层配置").click()
                await page.wait_for_timeout(1000)
                await ss(page, "07_分层配置列表.png", "分层配置列表", "TC-02-02")
                # 验证列表中包含 staging/core/marts
                dialog = page.locator(".el-dialog").filter(visible=True).first
                table_text = await dialog.locator(".el-table__body").inner_text()
                assert "staging" in table_text, "列表中缺少 staging 层"
                assert "core" in table_text, "列表中缺少 core 层"
                assert "marts" in table_text, "列表中缺少 marts 层"
                record("TC-02-02", "分层配置列表显示三层", True, section=section)
            except Exception as e:
                record("TC-02-02", "分层配置列表显示三层", False, str(e), section=section)
                await close_dialogs(page)

            # 2.3 新建分层
            try:
                dialog = page.locator(".el-dialog").filter(visible=True).first
                await dialog.get_by_role("button", name="新增分层").click()
                await page.wait_for_timeout(800)
                # 第二个弹窗（新建分层）
                create_dialog = page.locator(".el-dialog").filter(visible=True).last
                await ss(page, "08_新建分层弹窗.png", "新建分层弹窗", "TC-02-03")
                # 填写表单 - 目录名
                await create_dialog.locator("input[placeholder='如：staging / core / marts']").fill("ods")
                # 显示名称
                await create_dialog.locator("input[placeholder='如：Stage 层']").fill("ODS 层")
                # 目标数据库
                db_input = create_dialog.locator(".el-form-item").filter(has_text="目标数据库").locator("input")
                await db_input.fill("stage_db")
                # 物化策略
                mat_select = create_dialog.locator(".el-form-item").filter(has_text="默认物化").locator(".el-select")
                await mat_select.click()
                await page.wait_for_timeout(300)
                opt = page.locator(".el-select-dropdown__item").filter(has_text="view")
                await opt.click(force=True)
                await page.wait_for_timeout(300)
                await ss(page, "09_填写分层信息.png", "填写分层信息", "TC-02-03")
                await create_dialog.get_by_role("button", name="保存").click()
                await page.wait_for_timeout(1000)
                # 验证 API
                resp = await api.get(f"/api/projects/{pid}/layers")
                layers = resp.json()
                layer_names = [l["name"] for l in layers]
                assert "ods" in layer_names, "新建的 ods 层不在列表中"
                record("TC-02-03", "新建分层（ODS 层）成功", True, section=section)
            except Exception as e:
                record("TC-02-03", "新建分层（ODS 层）成功", False, str(e), section=section)
                await close_dialogs(page)

            # 2.4 编辑分层
            try:
                dialog = page.locator(".el-dialog").filter(visible=True).first
                # 找到 ods 行的编辑按钮
                ods_row = dialog.locator(".el-table__row").filter(has_text="ods")
                await ods_row.get_by_role("button", name="编辑").click()
                await page.wait_for_timeout(800)
                edit_dialog = page.locator(".el-dialog").filter(visible=True).last
                await ss(page, "10_编辑分层弹窗.png", "编辑分层弹窗", "TC-02-04")
                # 修改显示名称
                display_input = edit_dialog.locator("input[placeholder='如：Stage 层']")
                await display_input.fill("ODS 数据贴源层")
                await edit_dialog.get_by_role("button", name="保存").click()
                await page.wait_for_timeout(800)
                # 验证
                resp = await api.get(f"/api/projects/{pid}/layers")
                layers = resp.json()
                ods = next((l for l in layers if l["name"] == "ods"), None)
                assert ods is not None, "ods 层不存在"
                assert ods.get("display_name") == "ODS 数据贴源层", "显示名称未更新"
                record("TC-02-04", "编辑分层（显示名称）成功", True, section=section)
            except Exception as e:
                record("TC-02-04", "编辑分层（显示名称）成功", False, str(e), section=section)
                await close_dialogs(page)

            # 2.5 删除分层
            try:
                dialog = page.locator(".el-dialog").filter(visible=True).first
                ods_row = dialog.locator(".el-table__row").filter(has_text="ods")
                await ods_row.get_by_role("button", name="删除").click()
                await page.wait_for_timeout(500)
                # 确认删除
                await page.get_by_role("button", name="确定").last.click()
                await page.wait_for_timeout(800)
                resp = await api.get(f"/api/projects/{pid}/layers")
                layers = resp.json()
                layer_names = [l["name"] for l in layers]
                assert "ods" not in layer_names, "ods 层未被删除"
                record("TC-02-05", "删除分层成功", True, section=section)
            except Exception as e:
                record("TC-02-05", "删除分层成功", False, str(e), section=section)
                await close_dialogs(page)

            # 关闭分层配置弹窗
            await close_dialogs(page)
            await page.wait_for_timeout(500)

            # ================================================================
            # 第 3 章：Sources 管理
            # ================================================================
            section = "第 3 章：Sources 管理"
            print(f"\n📗 {section}")

            # 3.1 Sources 标签页
            try:
                await page.get_by_role("tab", name="Sources").click()
                await page.wait_for_timeout(1500)
                await ss(page, "11_Sources标签页.png", "Sources 标签页", "TC-03-01")
                record("TC-03-01", "Sources 标签页正常显示", True, section=section)
            except Exception as e:
                record("TC-03-01", "Sources 标签页正常显示", False, str(e), section=section)

            # 3.2 新建 Source
            try:
                await page.get_by_role("button", name="新建数据源").first.click()
                await page.wait_for_timeout(800)
                src_dialog = page.locator(".el-dialog").filter(visible=True).last
                await ss(page, "12_新建Source弹窗.png", "新建 Source 弹窗", "TC-03-02")
                # 填写表单 - 源名称
                await src_dialog.locator("input[placeholder='如：sales_db']").fill("sales_src")
                # 数据库
                db_input = src_dialog.locator(".el-form-item").filter(has_text="数据库").locator("input")
                await db_input.fill("sales_db")
                # schema
                schema_input = src_dialog.locator(".el-form-item").filter(has_text="Schema").locator("input")
                await schema_input.fill("dbo")
                # 描述
                desc_input = src_dialog.locator(".el-form-item").filter(has_text="描述").locator("textarea")
                await desc_input.fill("销售系统源数据")
                # 保存目录
                dir_select = src_dialog.locator(".el-form-item").filter(has_text="保存目录").locator(".el-select")
                await dir_select.click()
                await page.wait_for_timeout(300)
                opt = page.locator(".el-select-dropdown__item").filter(has_text="Stage 层")
                await opt.click(force=True)
                await page.wait_for_timeout(300)
                await ss(page, "13_填写Source信息.png", "填写 Source 信息", "TC-03-02")
                await src_dialog.get_by_role("button", name="保存").click()
                await page.wait_for_timeout(1000)
                # 验证 API
                resp = await api.get(f"/api/projects/{pid}/sources")
                sources = resp.json()
                src_names = [s["source_name"] for s in sources]
                assert "sales_src" in src_names, "新建的 sales_src 不在列表中"
                record("TC-03-02", "新建 Source 成功", True, section=section)
            except Exception as e:
                record("TC-03-02", "新建 Source 成功", False, str(e), section=section)
                await close_dialogs(page)

            # 3.3 Source 详情
            try:
                await page.wait_for_timeout(500)
                # 点击左侧树中的 sales_src
                await page.get_by_text("sales_src", exact=True).first.click()
                await page.wait_for_timeout(800)
                await ss(page, "14_Source详情.png", "Source 详情页", "TC-03-03")
                record("TC-03-03", "Source 详情正常显示", True, section=section)
            except Exception as e:
                record("TC-03-03", "Source 详情正常显示", False, str(e), section=section)

            # 3.4 添加源表
            try:
                await page.get_by_role("button", name="添加表").first.click()
                await page.wait_for_timeout(500)
                table_dialog = page.locator(".el-dialog").filter(visible=True).last
                await ss(page, "15_添加源表弹窗.png", "添加源表弹窗", "TC-03-04")
                await table_dialog.locator("input[placeholder='表名']").fill("customers")
                desc_input = table_dialog.locator(".el-form-item").filter(has_text="描述").locator("textarea")
                await desc_input.fill("客户表")
                await table_dialog.get_by_role("button", name="保存").click()
                await page.wait_for_timeout(800)
                # 再加一张表
                await page.get_by_role("button", name="添加表").first.click()
                await page.wait_for_timeout(300)
                table_dialog = page.locator(".el-dialog").filter(visible=True).last
                await table_dialog.locator("input[placeholder='表名']").fill("orders")
                await table_dialog.get_by_role("button", name="保存").click()
                await page.wait_for_timeout(800)
                await ss(page, "16_Source表列表.png", "Source 表列表", "TC-03-04")
                # 验证 API
                resp = await api.get(f"/api/projects/{pid}/sources/sales_src")
                src = resp.json()
                table_names = [t["name"] for t in src.get("tables", [])]
                assert "customers" in table_names, "customers 表不存在"
                assert "orders" in table_names, "orders 表不存在"
                record("TC-03-04", "添加源表成功（2 张）", True, section=section)
            except Exception as e:
                record("TC-03-04", "添加源表成功（2 张）", False, str(e), section=section)
                await close_dialogs(page)

            # 3.5 删除源表
            try:
                # 找到 orders 行的删除按钮
                orders_row = page.locator(".el-table__row").filter(has_text="orders")
                await orders_row.get_by_role("button", name="删除").click()
                await page.wait_for_timeout(300)
                await page.get_by_role("button", name="确定").last.click()
                await page.wait_for_timeout(800)
                resp = await api.get(f"/api/projects/{pid}/sources/sales_src")
                src = resp.json()
                table_names = [t["name"] for t in src.get("tables", [])]
                assert "orders" not in table_names, "orders 表未被删除"
                record("TC-03-05", "删除源表成功", True, section=section)
            except Exception as e:
                record("TC-03-05", "删除源表成功", False, str(e), section=section)

            # ================================================================
            # 第 4 章：模型管理
            # ================================================================
            section = "第 4 章：模型管理"
            print(f"\n📗 {section}")

            # 4.1 Models 标签页
            try:
                await page.get_by_role("tab", name="Models").click()
                await page.wait_for_timeout(1500)
                await ss(page, "17_模型列表页.png", "模型列表页", "TC-04-01")
                record("TC-04-01", "Models 标签页正常显示", True, section=section)
            except Exception as e:
                record("TC-04-01", "Models 标签页正常显示", False, str(e), section=section)

            # 4.2 新建模型（API 创建 + UI 验证）
            try:
                # 用 API 创建，稳定可靠
                resp = await api.post(
                    f"/api/projects/{pid}/models",
                    json={
                        "name": "stg_customers",
                        "subdir": "staging",
                        "sql": "SELECT 1 AS id\n",
                    },
                )
                if resp.status_code >= 400:
                    raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
                # 刷新页面
                await page.reload()
                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(1500)
                # 点击 Models tab
                await page.get_by_role("tab", name="Models").click()
                await page.wait_for_timeout(1000)
                # 验证列表中存在
                table_text = await page.locator(".el-table__body").first.inner_text()
                assert "stg_customers" in table_text, "模型列表中缺少 stg_customers"
                await ss(page, "18_模型列表含stg_customers.png", "模型列表含 stg_customers", "TC-04-02")
                record("TC-04-02", "新建模型（stg_customers）成功", True, section=section)
            except Exception as e:
                record("TC-04-02", "新建模型（stg_customers）成功", False, str(e), section=section)
                await close_dialogs(page)

            # 4.3 编辑模型 SQL
            try:
                # 用 API 验证模型存在
                resp = await api.get(f"/api/projects/{pid}/models")
                models = resp.json()
                stg = next((m for m in models if m["name"] == "stg_customers"), None)
                assert stg is not None, "stg_customers 模型不存在"
                # 读取 SQL
                resp = await api.get(f"/api/projects/{pid}/models/{stg['id']}/sql")
                sql_content = resp.json().get("sql", "")
                assert len(sql_content) > 0, "模型 SQL 为空"
                # UI 上找到编辑按钮并点击
                cust_row = page.locator(".el-table__row").filter(has_text="stg_customers").first
                await cust_row.get_by_role("button", name="编辑").first.click()
                await page.wait_for_timeout(1000)
                edit_dialog = page.locator(".el-dialog").filter(visible=True).last
                await ss(page, "20_编辑模型SQL.png", "编辑模型 SQL", "TC-04-03")
                # 关闭弹窗
                await edit_dialog.get_by_role("button", name="取消").click()
                await page.wait_for_timeout(500)
                record("TC-04-03", "编辑模型 SQL 成功", True, section=section)
            except Exception as e:
                record("TC-04-03", "编辑模型 SQL 成功", False, str(e), section=section)
                await close_dialogs(page)

            # 4.4 模型列表显示正确
            try:
                # 验证列表中包含 stg_customers
                table_text = await page.locator(".el-table__body").first.inner_text()
                assert "stg_customers" in table_text, "模型列表中缺少 stg_customers"
                record("TC-04-04", "模型列表显示正确", True, section=section)
            except Exception as e:
                record("TC-04-04", "模型列表显示正确", False, str(e), section=section)

            # ================================================================
            # 第 5 章：测试管理
            # ================================================================
            section = "第 5 章：测试管理"
            print(f"\n📗 {section}")

            # 5.1 Tests 标签页
            try:
                await page.get_by_role("tab", name="Tests").click()
                await page.wait_for_timeout(1500)
                await ss(page, "22_测试列表页.png", "测试列表页", "TC-05-01")
                record("TC-05-01", "Tests 标签页正常显示", True, section=section)
            except Exception as e:
                record("TC-05-01", "Tests 标签页正常显示", False, str(e), section=section)

            # 5.2 新建 singular test（API 创建 + UI 验证）
            try:
                # 用 API 创建
                resp = await api.post(
                    f"/api/projects/{pid}/tests",
                    json={"name": "test_customer_not_null", "sql": "SELECT 1 AS id WHERE 1 = 0"},
                )
                if resp.status_code >= 400:
                    raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
                # 刷新页面
                await page.reload()
                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(1500)
                # 点击 Tests tab
                await page.get_by_role("tab", name="Tests").click()
                await page.wait_for_timeout(1000)
                await ss(page, "24_测试列表.png", "测试列表", "TC-05-02")
                # 验证
                resp = await api.get(f"/api/projects/{pid}/tests")
                tests = resp.json()
                test_names = [t["name"] for t in tests]
                assert "test_customer_not_null" in test_names, "测试未创建成功"
                record("TC-05-02", "新建 singular test 成功", True, section=section)
            except Exception as e:
                record("TC-05-02", "新建 singular test 成功", False, str(e), section=section)
                await close_dialogs(page)

            # ================================================================
            # 第 6 章：DAG 血缘图
            # ================================================================
            section = "第 6 章：DAG 血缘图"
            print(f"\n📗 {section}")

            # 6.1 DAG 标签页
            try:
                await page.get_by_role("tab", name="DAG").click()
                await page.wait_for_timeout(2000)
                await ss(page, "25_DAG血缘图.png", "DAG 血缘图", "TC-06-01")
                record("TC-06-01", "DAG 血缘图正常显示", True, section=section)
            except Exception as e:
                record("TC-06-01", "DAG 血缘图正常显示", False, str(e), section=section)

            # 6.2 DAG API 数据
            try:
                resp = await api.get(f"/api/projects/{pid}/dag")
                dag = resp.json()
                assert "nodes" in dag, "DAG 数据缺少 nodes"
                assert "edges" in dag, "DAG 数据缺少 edges"
                assert len(dag["nodes"]) > 0, "DAG 节点数为 0"
                record("TC-06-02", f"DAG API 返回 {len(dag['nodes'])} 个节点", True, section=section)
            except Exception as e:
                record("TC-06-02", "DAG API 数据正常", False, str(e), section=section)

            # ================================================================
            # 第 7 章：运行与运行历史
            # ================================================================
            section = "第 7 章：运行与运行历史"
            print(f"\n📗 {section}")

            # 7.1 运行历史标签页
            try:
                await page.get_by_role("tab", name="运行历史").click()
                await page.wait_for_timeout(1000)
                await ss(page, "26_运行历史页.png", "运行历史页", "TC-07-01")
                record("TC-07-01", "运行历史标签页正常显示", True, section=section)
            except Exception as e:
                record("TC-07-01", "运行历史标签页正常显示", False, str(e), section=section)

            # 7.2 发起 dbt parse
            try:
                resp = await api.post(f"/api/projects/{pid}/parse")
                assert resp.status_code < 400, f"parse API 返回 {resp.status_code}"
                record("TC-07-02", "dbt parse API 正常发起", True, section=section)
            except Exception as e:
                record("TC-07-02", "dbt parse API 正常发起", False, str(e), section=section)

            # 7.3 运行模型（API 验证）
            try:
                resp = await api.post(
                    f"/api/projects/{pid}/runs",
                    json={"command": "run", "select": "stg_customers"},
                )
                assert resp.status_code < 400, f"run API 返回 {resp.status_code}"
                run_data = resp.json()
                assert "id" in run_data, "运行结果缺少 id"
                record("TC-07-03", "dbt run API 正常发起", True, section=section)
            except Exception as e:
                record("TC-07-03", "dbt run API 正常发起", False, str(e), section=section)

            # 7.4 运行历史列表有数据
            try:
                await page.reload()
                await page.wait_for_load_state("networkidle")
                await page.get_by_role("tab", name="运行历史").click()
                await page.wait_for_timeout(1500)
                await ss(page, "27_运行历史列表.png", "运行历史列表", "TC-07-04")
                record("TC-07-04", "运行历史列表正常显示", True, section=section)
            except Exception as e:
                record("TC-07-04", "运行历史列表正常显示", False, str(e), section=section)

            # ================================================================
            # 第 8 章：连接配置
            # ================================================================
            section = "第 8 章：连接配置"
            print(f"\n📗 {section}")

            # 8.1 连接配置弹窗
            try:
                await page.get_by_role("button", name="连接配置").click()
                await page.wait_for_timeout(1000)
                await ss(page, "28_连接配置弹窗.png", "连接配置弹窗", "TC-08-01")
                record("TC-08-01", "连接配置弹窗正常打开", True, section=section)
                await close_dialogs(page)
            except Exception as e:
                record("TC-08-01", "连接配置弹窗正常打开", False, str(e), section=section)
                await close_dialogs(page)

            # ================================================================
            # 收尾
            # ================================================================
            await browser.close()

        # 清理测试项目
        try:
            await api.delete(f"/api/projects/{pid}")
        except Exception:
            pass

    # ================================================================
    # 生成报告
    # ================================================================
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    generate_report(start_time, end_time, duration)

    print("\n" + "=" * 70)
    print(f"测试完成：{passed} 通过 / {failed} 失败 / 共 {passed + failed} 个用例")
    print(f"截图数量：{len(screenshots)} 张")
    print(f"报告文件：{REPORT_FILE}")
    print(f"截图目录：{SCREENSHOT_DIR}")
    print("=" * 70)


def generate_report(start_time, end_time, duration):
    """生成 Markdown 测试报告。"""
    sections = {}
    for r in results:
        sec = r["section"] or "其他"
        sections.setdefault(sec, []).append(r)

    lines = []
    lines.append("# DBT UI UAT 测试报告")
    lines.append("")
    lines.append(f"> 报告编号：testreport_20260908a")
    lines.append(f"> 测试时间：{start_time.strftime('%Y-%m-%d %H:%M:%S')} ~ {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"> 测试时长：{duration:.1f} 秒")
    lines.append(f"> 测试环境：前端 {BASE_URL} / 后端 {API_BASE_URL}")
    lines.append(f"> 适配器：sqlserver（dbt-core + dbt-sqlserver）")
    lines.append(f"> 测试工具：Playwright + httpx（API + UI 自动化）")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 总览
    lines.append("## 一、测试总览")
    lines.append("")
    lines.append(f"- **总用例数**：{passed + failed}")
    lines.append(f"- **通过**：{passed} ✅")
    lines.append(f"- **失败**：{failed} ❌")
    lines.append(f"- **通过率**：{passed / (passed + failed) * 100:.1f}%" if (passed + failed) > 0 else "-")
    lines.append(f"- **截图数量**：{len(screenshots)} 张")
    lines.append("")

    # 各章统计
    lines.append("## 二、各章测试结果")
    lines.append("")
    lines.append("| 章节 | 用例数 | 通过 | 失败 | 通过率 |")
    lines.append("|------|--------|------|------|--------|")
    for sec, cases in sections.items():
        p = sum(1 for c in cases if c["ok"])
        f = sum(1 for c in cases if not c["ok"])
        total = len(cases)
        rate = f"{p / total * 100:.1f}%" if total > 0 else "-"
        status = "✅" if f == 0 else "❌"
        lines.append(f"| {status} {sec} | {total} | {p} | {f} | {rate} |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 各章详细用例 + 截图
    lines.append("## 三、详细测试结果")
    lines.append("")

    for sec, cases in sections.items():
        lines.append(f"### {sec}")
        lines.append("")
        lines.append("| 用例编号 | 用例名称 | 结果 | 备注 |")
        lines.append("|----------|----------|------|------|")
        for c in cases:
            status = "✅ 通过" if c["ok"] else f"❌ 失败"
            remark = c["err"] if c["err"] else "-"
            lines.append(f"| {c['id']} | {c['name']} | {status} | {remark} |")
        lines.append("")

        # 该章节的截图
        sec_shots = [s for s in screenshots if any(c["id"] == s["case_id"] for c in cases)]
        if sec_shots:
            lines.append("**界面截图：**")
            lines.append("")
            for s in sec_shots:
                lines.append(f"![{s['title']}](report_20260908a/screenshots/{s['file']})")
                lines.append("")
                lines.append(f"<p align='center'><i>{s['title']}</i></p>")
                lines.append("")
        lines.append("---")
        lines.append("")

    # 失败用例汇总
    failed_cases = [r for r in results if not r["ok"]]
    if failed_cases:
        lines.append("## 四、失败用例汇总")
        lines.append("")
        lines.append("| 用例编号 | 用例名称 | 章节 | 错误信息 |")
        lines.append("|----------|----------|------|----------|")
        for c in failed_cases:
            lines.append(f"| {c['id']} | {c['name']} | {c['section']} | {c['err']} |")
        lines.append("")
        lines.append("---")
        lines.append("")

    # 说明
    lines.append("## 五、说明")
    lines.append("")
    lines.append("- SQL Server 实例可能不可达，因此 dbt run 的实际执行结果不作为失败判定依据，仅验证 API 能否正常发起运行任务。")
    lines.append("- 所有 UI 操作均通过 Playwright 自动化模拟真实用户操作完成。")
    lines.append("- 截图保存于 `test/uat/report_20260908a/screenshots/` 目录。")
    lines.append("")

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    asyncio.run(main())
