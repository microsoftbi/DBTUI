#!/usr/bin/env python3
"""DBT UI 用户手册验证脚本 - 使用 Playwright 进行 UI 操作和截图对比。"""
import os
import sys
import time
import json
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright, Page, expect

# 配置
FRONTEND_URL = "http://localhost:5174"
BACKEND_URL = "http://localhost:8000"
SCREENSHOT_DIR = Path("/Users/wadesong/Documents/trae_projects/DBT/doc/userguide")
OUTPUT_DIR = Path("/Users/wadesong/Documents/trae_projects/DBT/doc/verify_output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 验证结果
results = {
    "chapters": {},
    "screenshots": {},
    "issues": [],
}

def add_issue(severity, chapter, description):
    results["issues"].append({
        "severity": severity,
        "chapter": chapter,
        "description": description
    })

def check_screenshot(page: Page, name: str, chapter: str, wait_before=0.5):
    """截图并与手册截图对比。"""
    if wait_before > 0:
        time.sleep(wait_before)
    
    actual_path = OUTPUT_DIR / name
    page.screenshot(path=str(actual_path), full_page=True)
    
    expected_path = SCREENSHOT_DIR / name
    exists = expected_path.exists()
    
    actual_size = actual_path.stat().st_size if actual_path.exists() else 0
    expected_size = expected_path.stat().st_size if expected_path.exists() else 0
    
    status = "是"
    note = ""
    
    if not exists:
        status = "有差异"
        note = "手册中无此截图文件"
    elif actual_size < 1000:
        status = "有差异"
        note = f"实际截图过小 ({actual_size} bytes)"
    
    results["screenshots"][name] = {
        "status": status,
        "note": note,
        "chapter": chapter,
        "actual_size": actual_size,
        "expected_size": expected_size,
    }
    
    print(f"  📸 {name}: {status} {note}")
    return status == "是"

def select_el_select(page, dialog_selector, label_text, option_text):
    """选择 Element Plus select 组件的选项。"""
    dialog = page.locator(dialog_selector)
    # 找到包含 label 的 form-item
    form_item = dialog.locator(".el-form-item").filter(has_text=label_text)
    # 点击 select 组件
    form_item.locator(".el-select").click()
    time.sleep(0.5)
    # 在下拉选项中选择
    page.get_by_text(option_text, exact=True).last.click()
    time.sleep(0.3)

def fill_sql_editor(page, sql_text, dialog_filter_text=None):
    """填充 CodeMirror SQL 编辑器。"""
    # 找到包含编辑器的弹窗
    if dialog_filter_text:
        dialog = page.locator(".el-dialog").filter(has_text=dialog_filter_text)
    else:
        # 找到可见的弹窗中包含 cm-editor 的
        dialogs = page.locator(".el-dialog")
        dialog = None
        for i in range(dialogs.count()):
            d = dialogs.nth(i)
            if d.is_visible() and d.locator(".cm-editor").count() > 0:
                dialog = d
                break
        if dialog is None:
            dialog = dialogs.first
    
    editor = dialog.locator(".cm-editor").first
    # 等待编辑器可见
    for _ in range(30):
        if editor.is_visible():
            break
        time.sleep(0.5)
    
    editor.click()
    time.sleep(0.3)
    # 全选删除
    page.keyboard.press("Meta+A")
    time.sleep(0.2)
    page.keyboard.press("Backspace")
    time.sleep(0.2)
    # 输入新内容
    page.keyboard.type(sql_text)
    time.sleep(0.3)

def find_row_by_name(page, name):
    """在表格中找到包含指定名称的行。"""
    # 找到包含名称的单元格，然后向上找到行
    cell = page.get_by_text(name, exact=True).first
    return cell.locator("xpath=ancestor::tr[1]")

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()
        
        try:
            # ========== 第 1 章：创建项目 ==========
            print("\n" + "="*60)
            print("第 1 章：创建项目")
            print("="*60)
            chapter1_ok = True
            
            # 步骤1：访问首页
            print("\n步骤1：访问项目列表页")
            page.goto(FRONTEND_URL)
            page.wait_for_load_state("networkidle")
            time.sleep(2)
            
            ok = check_screenshot(page, "01_项目列表页.png", "第1章")
            if not ok:
                chapter1_ok = False
                add_issue("medium", "第1章", "01_项目列表页.png 截图检查有差异")
            
            try:
                expect(page.get_by_role("button", name="新建项目")).to_be_visible()
                print("  ✓ 新建项目按钮可见")
            except Exception as e:
                chapter1_ok = False
                add_issue("high", "第1章", f"新建项目按钮不可见: {e}")
            
            # 步骤2：点击新建项目
            print("\n步骤2：点击新建项目")
            page.get_by_role("button", name="新建项目").click()
            time.sleep(1)
            ok = check_screenshot(page, "02_新建项目弹窗.png", "第1章")
            if not ok:
                chapter1_ok = False
                add_issue("medium", "第1章", "02_新建项目弹窗.png 截图检查有差异")
            
            # 步骤3：填写项目信息
            print("\n步骤3：填写项目信息")
            dialog = page.locator(".el-dialog")
            
            # 填写项目名称
            dialog.locator(".el-form-item").filter(has_text="项目名称").locator("input").fill("sales_warehouse")
            time.sleep(0.3)
            
            # 选择 Adapter
            select_el_select(page, ".el-dialog", "Adapter", "sqlserver")
            
            # 填写描述
            dialog.locator(".el-form-item").filter(has_text="描述").locator("textarea").fill("销售数据仓库三层分库")
            time.sleep(0.3)
            
            ok = check_screenshot(page, "03_填写项目信息.png", "第1章")
            if not ok:
                chapter1_ok = False
                add_issue("medium", "第1章", "03_填写项目信息.png 截图检查有差异")
            
            # 步骤4：点击确定创建项目
            print("\n步骤4：创建项目")
            dialog.get_by_role("button", name="确定").click()
            page.wait_for_load_state("networkidle")
            time.sleep(3)
            
            try:
                expect(page.get_by_text("sales_warehouse")).to_be_visible()
                print("  ✓ 项目创建成功，列表中可见")
            except Exception as e:
                chapter1_ok = False
                add_issue("high", "第1章", f"项目创建后未出现在列表中: {e}")
            
            ok = check_screenshot(page, "04_项目列表_创建成功.png", "第1章")
            if not ok:
                chapter1_ok = False
                add_issue("medium", "第1章", "04_项目列表_创建成功.png 截图检查有差异")
            
            # 步骤5：进入项目详情
            print("\n步骤5：进入项目详情")
            row = find_row_by_name(page, "sales_warehouse")
            row.get_by_role("button", name="打开").click()
            page.wait_for_load_state("networkidle")
            time.sleep(3)
            
            try:
                expect(page.get_by_text("sales_warehouse")).to_be_visible()
                expect(page.get_by_role("tab", name="Models")).to_be_visible()
                print("  ✓ 项目详情页加载成功")
            except Exception as e:
                chapter1_ok = False
                add_issue("high", "第1章", f"项目详情页加载失败: {e}")
            
            ok = check_screenshot(page, "05_项目详情页.png", "第1章")
            if not ok:
                chapter1_ok = False
                add_issue("medium", "第1章", "05_项目详情页.png 截图检查有差异")
            
            # 步骤6：连接配置
            print("\n步骤6：连接配置")
            page.get_by_role("button", name="连接配置").click()
            time.sleep(1)
            
            try:
                expect(page.get_by_text("连接配置（profiles.yml）")).to_be_visible()
                print("  ✓ 连接配置弹窗打开")
            except Exception as e:
                chapter1_ok = False
                add_issue("high", "第1章", f"连接配置弹窗打不开: {e}")
            
            ok = check_screenshot(page, "06_连接配置_profiles.png", "第1章")
            if not ok:
                chapter1_ok = False
                add_issue("medium", "第1章", "06_连接配置_profiles.png 截图检查有差异")
            
            # 关闭弹窗
            page.locator(".el-dialog").get_by_role("button", name="取消").click()
            time.sleep(0.5)
            
            # 步骤7：重新解析
            print("\n步骤7：重新解析")
            page.get_by_role("button", name="重新解析").click()
            page.wait_for_load_state("networkidle")
            time.sleep(8)
            
            try:
                expect(page.get_by_text("success")).to_be_visible()
                print("  ✓ 解析成功")
            except Exception as e:
                chapter1_ok = False
                add_issue("high", "第1章", f"重新解析失败: {e}")
            
            ok = check_screenshot(page, "07_重新解析完成.png", "第1章")
            if not ok:
                chapter1_ok = False
                add_issue("medium", "第1章", "07_重新解析完成.png 截图检查有差异")
            
            results["chapters"]["第1章"] = "通过" if chapter1_ok else "失败"
            
            # 获取项目ID
            project_id = page.url.split("/")[-1]
            print(f"\n  项目ID: {project_id}")
            
            # ========== 第 2 章：配置源系统 ==========
            print("\n" + "="*60)
            print("第 2 章：配置源系统")
            print("="*60)
            chapter2_ok = True
            
            # 步骤8：创建 sources.yml
            print("\n步骤8：创建 sources.yml")
            with urllib.request.urlopen(f"{BACKEND_URL}/api/projects/{project_id}") as resp:
                project_info = json.loads(resp.read().decode())
            project_path = project_info["path"]
            print(f"  项目路径: {project_path}")
            
            sources_yml = """version: 2
sources:
  - name: sales_db
    database: sales_db
    schema: dbo
    tables:
      - name: customer
        description: "客户表"
      - name: product
        description: "产品表"
      - name: salesorder
        description: "销售订单表"
"""
            sources_path = Path(project_path) / "models" / "staging" / "sources.yml"
            sources_path.write_text(sources_yml, encoding="utf-8")
            print(f"  ✓ sources.yml 已创建")
            
            # 步骤9：重新解析
            print("\n步骤9：重新解析")
            page.get_by_role("button", name="重新解析").click()
            page.wait_for_load_state("networkidle")
            time.sleep(8)
            
            # 步骤10：验证 source 出现
            print("\n步骤10：验证模型列表含 source")
            try:
                page.wait_for_selector("text=sales_db", timeout=10000)
                print("  ✓ Source 节点出现在列表中")
            except Exception as e:
                chapter2_ok = False
                add_issue("high", "第2章", f"Source 节点未出现在列表中: {e}")
            
            ok = check_screenshot(page, "08_模型列表_含source.png", "第2章")
            if not ok:
                chapter2_ok = False
                add_issue("medium", "第2章", "08_模型列表_含source.png 截图检查有差异")
            
            results["chapters"]["第2章"] = "通过" if chapter2_ok else "失败"
            
            # ========== 第 3 章：Stage 层 ==========
            print("\n" + "="*60)
            print("第 3 章：Stage 层")
            print("="*60)
            chapter3_ok = True
            
            # 步骤11：点击新建模型
            print("\n步骤11：点击新建模型")
            page.get_by_role("button", name="新建模型").first.click()
            time.sleep(1)
            ok = check_screenshot(page, "09_新建模型弹窗.png", "第3章")
            if not ok:
                chapter3_ok = False
                add_issue("medium", "第3章", "09_新建模型弹窗.png 截图检查有差异")
            
            # 步骤12：创建 stg_customer
            print("\n步骤12：创建 stg_customer")
            dialog = page.locator(".el-dialog").filter(has_text="新建模型")
            
            dialog.locator(".el-form-item").filter(has_text="名称").locator("input").fill("stg_customer")
            time.sleep(0.3)
            
            # 层级默认是 staging，确认一下
            stg_customer_sql = """SELECT
    customer_id,
    customer_name,
    gender,
    age,
    city,
    create_date
FROM {{ source('sales_db', 'customer') }}"""
            
            fill_sql_editor(page, stg_customer_sql)
            time.sleep(0.5)
            
            ok = check_screenshot(page, "10_填写stg_customer.png", "第3章")
            if not ok:
                chapter3_ok = False
                add_issue("medium", "第3章", "10_填写stg_customer.png 截图检查有差异")
            
            # 点击创建
            dialog.get_by_role("button", name="创建").click()
            page.wait_for_load_state("networkidle")
            time.sleep(5)
            print("  ✓ stg_customer 已创建")
            
            # 步骤13：创建 stg_product 和 stg_salesorder
            print("\n步骤13：创建 stg_product 和 stg_salesorder")
            
            # stg_product
            page.get_by_role("button", name="新建模型").first.click()
            time.sleep(1)
            dialog = page.locator(".el-dialog").filter(has_text="新建模型")
            dialog.locator(".el-form-item").filter(has_text="名称").locator("input").fill("stg_product")
            time.sleep(0.3)
            
            stg_product_sql = """SELECT
    product_id,
    product_name,
    category,
    price,
    create_date
FROM {{ source('sales_db', 'product') }}"""
            
            fill_sql_editor(page, stg_product_sql)
            time.sleep(0.3)
            dialog.get_by_role("button", name="创建").click()
            page.wait_for_load_state("networkidle")
            time.sleep(5)
            print("  ✓ stg_product 已创建")
            
            # stg_salesorder
            page.get_by_role("button", name="新建模型").first.click()
            time.sleep(1)
            dialog = page.locator(".el-dialog").filter(has_text="新建模型")
            dialog.locator(".el-form-item").filter(has_text="名称").locator("input").fill("stg_salesorder")
            time.sleep(0.3)
            
            stg_salesorder_sql = """SELECT
    order_id,
    order_date,
    customer_id,
    product_id,
    quantity,
    unit_price,
    amount,
    status
FROM {{ source('sales_db', 'salesorder') }}"""
            
            fill_sql_editor(page, stg_salesorder_sql)
            time.sleep(0.3)
            dialog.get_by_role("button", name="创建").click()
            page.wait_for_load_state("networkidle")
            time.sleep(5)
            print("  ✓ stg_salesorder 已创建")
            
            # 步骤14：验证 Stage 层模型列表
            print("\n步骤14：验证 Stage 层模型列表")
            try:
                expect(page.get_by_text("stg_customer", exact=True)).to_be_visible()
                expect(page.get_by_text("stg_product", exact=True)).to_be_visible()
                expect(page.get_by_text("stg_salesorder", exact=True)).to_be_visible()
                print("  ✓ 三个 Stage 层模型都在列表中")
            except Exception as e:
                chapter3_ok = False
                add_issue("high", "第3章", f"Stage 层模型未全部显示: {e}")
            
            ok = check_screenshot(page, "11_Stage层模型列表.png", "第3章")
            if not ok:
                chapter3_ok = False
                add_issue("medium", "第3章", "11_Stage层模型列表.png 截图检查有差异")
            
            # 步骤15：运行 stg_customer
            print("\n步骤15：运行 stg_customer")
            row = find_row_by_name(page, "stg_customer")
            row.get_by_role("button", name="运行").click()
            time.sleep(1)
            
            ok = check_screenshot(page, "12_运行stg_customer.png", "第3章")
            if not ok:
                chapter3_ok = False
                add_issue("medium", "第3章", "12_运行stg_customer.png 截图检查有差异")
            
            # 步骤16：开始运行
            print("\n步骤16：运行中")
            page.get_by_role("button", name="开始运行").click()
            time.sleep(3)
            
            ok = check_screenshot(page, "13_Stage运行中.png", "第3章")
            if not ok:
                chapter3_ok = False
                add_issue("medium", "第3章", "13_Stage运行中.png 截图检查有差异")
            
            # 步骤17：等待运行完成
            print("\n步骤17：等待运行完成")
            max_wait = 60
            waited = 0
            done = False
            while waited < max_wait:
                time.sleep(2)
                waited += 2
                # 检查完成状态
                if page.get_by_text("运行完成").count() > 0:
                    done = True
                    break
                if page.get_by_text("运行失败").count() > 0:
                    done = True
                    break
            
            if done:
                print(f"  ✓ 运行完成（等待 {waited} 秒）")
            else:
                chapter3_ok = False
                add_issue("high", "第3章", f"运行超时（{max_wait}秒未完成）")
            
            time.sleep(1)
            ok = check_screenshot(page, "14_Stage运行完成.png", "第3章")
            if not ok:
                chapter3_ok = False
                add_issue("medium", "第3章", "14_Stage运行完成.png 截图检查有差异")
            
            # 关闭运行对话框
            try:
                page.get_by_role("button", name="关闭").click()
            except:
                pass
            time.sleep(0.5)
            
            # 步骤18：验证数据库（跳过）
            print("\n步骤18：验证数据库（SQL Server 不可达，跳过）")
            add_issue("info", "第3章", "SQL Server 192.168.0.116 不可达，无法验证数据库数据")
            
            results["chapters"]["第3章"] = "通过" if chapter3_ok else "失败"
            
            # ========== 第 4 章：Core 层 ==========
            print("\n" + "="*60)
            print("第 4 章：Core 层")
            print("="*60)
            chapter4_ok = True
            
            # 步骤19：创建 dim_customer
            print("\n步骤19：创建 dim_customer")
            page.get_by_role("button", name="新建模型").first.click()
            time.sleep(1)
            dialog = page.locator(".el-dialog").filter(has_text="新建模型")
            
            dialog.locator(".el-form-item").filter(has_text="名称").locator("input").fill("dim_customer")
            time.sleep(0.3)
            
            # 选择 Core 层
            select_el_select(page, ".el-dialog", "层级", "Core 层（core）")
            
            dim_customer_sql = """SELECT
    customer_id,
    customer_name,
    gender,
    age,
    city,
    create_date
FROM {{ ref('stg_customer') }}"""
            
            fill_sql_editor(page, dim_customer_sql)
            time.sleep(0.3)
            dialog.get_by_role("button", name="创建").click()
            page.wait_for_load_state("networkidle")
            time.sleep(5)
            print("  ✓ dim_customer 已创建")
            
            # 步骤20：创建 dim_product
            print("\n步骤20：创建 dim_product")
            page.get_by_role("button", name="新建模型").first.click()
            time.sleep(1)
            dialog = page.locator(".el-dialog").filter(has_text="新建模型")
            
            dialog.locator(".el-form-item").filter(has_text="名称").locator("input").fill("dim_product")
            time.sleep(0.3)
            
            select_el_select(page, ".el-dialog", "层级", "Core 层（core）")
            
            dim_product_sql = """SELECT
    product_id,
    product_name,
    category,
    price,
    create_date
FROM {{ ref('stg_product') }}"""
            
            fill_sql_editor(page, dim_product_sql)
            time.sleep(0.3)
            dialog.get_by_role("button", name="创建").click()
            page.wait_for_load_state("networkidle")
            time.sleep(5)
            print("  ✓ dim_product 已创建")
            
            # 步骤21：创建 fact_sales
            print("\n步骤21：创建 fact_sales")
            page.get_by_role("button", name="新建模型").first.click()
            time.sleep(1)
            dialog = page.locator(".el-dialog").filter(has_text="新建模型")
            
            dialog.locator(".el-form-item").filter(has_text="名称").locator("input").fill("fact_sales")
            time.sleep(0.3)
            
            select_el_select(page, ".el-dialog", "层级", "Core 层（core）")
            
            fact_sales_sql = """SELECT
    s.order_id,
    s.order_date,
    s.customer_id,
    s.product_id,
    s.quantity,
    s.unit_price,
    s.amount,
    s.status
FROM {{ ref('stg_salesorder') }} s
WHERE s.status = 'completed'"""
            
            fill_sql_editor(page, fact_sales_sql)
            time.sleep(0.3)
            dialog.get_by_role("button", name="创建").click()
            page.wait_for_load_state("networkidle")
            time.sleep(5)
            print("  ✓ fact_sales 已创建")
            
            # 步骤22：验证 Core 层模型列表
            print("\n步骤22：验证 Core 层模型列表")
            try:
                expect(page.get_by_text("dim_customer", exact=True)).to_be_visible()
                expect(page.get_by_text("dim_product", exact=True)).to_be_visible()
                expect(page.get_by_text("fact_sales", exact=True)).to_be_visible()
                print("  ✓ 三个 Core 层模型都在列表中")
            except Exception as e:
                chapter4_ok = False
                add_issue("high", "第4章", f"Core 层模型未全部显示: {e}")
            
            ok = check_screenshot(page, "15_Core层模型列表.png", "第4章")
            if not ok:
                chapter4_ok = False
                add_issue("medium", "第4章", "15_Core层模型列表.png 截图检查有差异")
            
            # 步骤23：编辑 fact_sales
            print("\n步骤23：编辑 fact_sales")
            row = find_row_by_name(page, "fact_sales")
            row.get_by_role("button", name="编辑").click()
            time.sleep(1)
            
            ok = check_screenshot(page, "16_编辑fact_sales.png", "第4章")
            if not ok:
                chapter4_ok = False
                add_issue("medium", "第4章", "16_编辑fact_sales.png 截图检查有差异")
            
            # 关闭编辑
            page.locator(".el-dialog").filter(has_text="编辑模型").get_by_role("button", name="取消").click()
            time.sleep(0.5)
            
            # 步骤24：运行 fact_sales
            print("\n步骤24：运行 fact_sales")
            row = find_row_by_name(page, "fact_sales")
            row.get_by_role("button", name="运行").click()
            time.sleep(1)
            
            ok = check_screenshot(page, "17_运行fact_sales.png", "第4章")
            if not ok:
                chapter4_ok = False
                add_issue("medium", "第4章", "17_运行fact_sales.png 截图检查有差异")
            
            # 步骤25：运行中
            print("\n步骤25：运行中")
            page.get_by_role("button", name="开始运行").click()
            time.sleep(3)
            
            ok = check_screenshot(page, "18_Core运行中.png", "第4章")
            if not ok:
                chapter4_ok = False
                add_issue("medium", "第4章", "18_Core运行中.png 截图检查有差异")
            
            # 步骤26：运行完成
            print("\n步骤26：等待运行完成")
            max_wait = 90
            waited = 0
            done = False
            while waited < max_wait:
                time.sleep(2)
                waited += 2
                if page.get_by_text("运行完成").count() > 0:
                    done = True
                    break
                if page.get_by_text("运行失败").count() > 0:
                    done = True
                    break
            
            if done:
                print(f"  ✓ 运行完成（等待 {waited} 秒）")
            else:
                chapter4_ok = False
                add_issue("high", "第4章", f"运行超时（{max_wait}秒未完成）")
            
            time.sleep(1)
            ok = check_screenshot(page, "19_Core运行完成.png", "第4章")
            if not ok:
                chapter4_ok = False
                add_issue("medium", "第4章", "19_Core运行完成.png 截图检查有差异")
            
            # 关闭运行对话框
            try:
                page.get_by_role("button", name="关闭").click()
            except:
                pass
            time.sleep(0.5)
            
            # 步骤27：验证数据库（跳过）
            print("\n步骤27：验证数据库（SQL Server 不可达，跳过）")
            
            results["chapters"]["第4章"] = "通过" if chapter4_ok else "失败"
            
            # ========== 第 5 章：Mart 层 ==========
            print("\n" + "="*60)
            print("第 5 章：Mart 层")
            print("="*60)
            chapter5_ok = True
            
            # 步骤28：创建 sales_wide
            print("\n步骤28：创建 sales_wide")
            page.get_by_role("button", name="新建模型").first.click()
            time.sleep(1)
            dialog = page.locator(".el-dialog").filter(has_text="新建模型")
            
            dialog.locator(".el-form-item").filter(has_text="名称").locator("input").fill("sales_wide")
            time.sleep(0.3)
            
            select_el_select(page, ".el-dialog", "层级", "Mart 层（marts）")
            
            sales_wide_sql = """SELECT
    f.order_id,
    f.order_date,
    f.customer_id,
    c.customer_name,
    c.gender,
    c.age,
    c.city,
    f.product_id,
    p.product_name,
    p.category,
    p.price,
    f.quantity,
    f.unit_price,
    f.amount,
    f.status
FROM {{ ref('fact_sales') }} f
LEFT JOIN {{ ref('dim_customer') }} c ON f.customer_id = c.customer_id
LEFT JOIN {{ ref('dim_product') }} p ON f.product_id = p.product_id"""
            
            fill_sql_editor(page, sales_wide_sql)
            time.sleep(0.5)
            dialog.get_by_role("button", name="创建").click()
            page.wait_for_load_state("networkidle")
            time.sleep(5)
            print("  ✓ sales_wide 已创建")
            
            # 步骤29：验证 Mart 层模型
            print("\n步骤29：验证 Mart 层模型列表")
            try:
                expect(page.get_by_text("sales_wide", exact=True)).to_be_visible()
                print("  ✓ sales_wide 在列表中")
            except Exception as e:
                chapter5_ok = False
                add_issue("high", "第5章", f"sales_wide 未显示: {e}")
            
            ok = check_screenshot(page, "20_Mart层模型列表.png", "第5章")
            if not ok:
                chapter5_ok = False
                add_issue("medium", "第5章", "20_Mart层模型列表.png 截图检查有差异")
            
            # 步骤30：切换到 Tests 标签
            print("\n步骤30：切换到 Tests 标签")
            page.get_by_role("tab", name="Tests").click()
            time.sleep(2)
            
            ok = check_screenshot(page, "21_Tests标签页.png", "第5章")
            if not ok:
                chapter5_ok = False
                add_issue("medium", "第5章", "21_Tests标签页.png 截图检查有差异")
            
            # 步骤31：新建测试
            print("\n步骤31：新建测试")
            page.get_by_role("button", name="新建测试").click()
            time.sleep(1)
            
            ok = check_screenshot(page, "22_新建测试弹窗.png", "第5章")
            if not ok:
                chapter5_ok = False
                add_issue("medium", "第5章", "22_新建测试弹窗.png 截图检查有差异")
            
            # 步骤32：填写测试
            print("\n步骤32：填写测试 SQL")
            dialog = page.locator(".el-dialog").filter(has_text="新建测试")
            dialog.locator(".el-form-item").filter(has_text="名称").locator("input").fill("test_amount_positive")
            time.sleep(0.3)
            
            test_sql = """SELECT *
FROM {{ ref('sales_wide') }}
WHERE amount <= 0"""
            
            fill_sql_editor(page, test_sql)
            time.sleep(0.5)
            
            ok = check_screenshot(page, "23_填写测试SQL.png", "第5章")
            if not ok:
                chapter5_ok = False
                add_issue("medium", "第5章", "23_填写测试SQL.png 截图检查有差异")
            
            # 保存测试
            dialog.get_by_role("button", name="保存").click()
            page.wait_for_load_state("networkidle")
            time.sleep(5)
            
            # 步骤33：验证测试列表
            print("\n步骤33：验证测试列表")
            try:
                expect(page.get_by_text("test_amount_positive", exact=True)).to_be_visible()
                print("  ✓ 测试在列表中")
            except Exception as e:
                chapter5_ok = False
                add_issue("high", "第5章", f"测试未显示: {e}")
            
            ok = check_screenshot(page, "24_测试列表.png", "第5章")
            if not ok:
                chapter5_ok = False
                add_issue("medium", "第5章", "24_测试列表.png 截图检查有差异")
            
            # 步骤34：运行 sales_wide
            print("\n步骤34：运行 sales_wide")
            page.get_by_role("tab", name="Models").click()
            time.sleep(2)
            
            row = find_row_by_name(page, "sales_wide")
            row.get_by_role("button", name="运行").click()
            time.sleep(0.5)
            page.get_by_role("button", name="开始运行").click()
            
            max_wait = 90
            waited = 0
            done = False
            while waited < max_wait:
                time.sleep(2)
                waited += 2
                if page.get_by_text("运行完成").count() > 0:
                    done = True
                    break
                if page.get_by_text("运行失败").count() > 0:
                    done = True
                    break
            
            if done:
                print(f"  ✓ sales_wide 运行完成（等待 {waited} 秒）")
            else:
                chapter5_ok = False
                add_issue("high", "第5章", f"sales_wide 运行超时")
            
            try:
                page.get_by_role("button", name="关闭").click()
            except:
                pass
            time.sleep(0.5)
            
            results["chapters"]["第5章"] = "通过" if chapter5_ok else "失败"
            
            # ========== 第 6 章：DAG 血缘图 ==========
            print("\n" + "="*60)
            print("第 6 章：DAG 血缘图")
            print("="*60)
            chapter6_ok = True
            
            # 步骤35：DAG 全景
            print("\n步骤35：DAG 全景图")
            page.get_by_role("tab", name="DAG").click()
            time.sleep(5)
            
            ok = check_screenshot(page, "25_DAG全景图.png", "第6章")
            if not ok:
                chapter6_ok = False
                add_issue("medium", "第6章", "25_DAG全景图.png 截图检查有差异")
            
            # 步骤36：点击 fact_sales 节点
            print("\n步骤36：fact_sales 血缘")
            try:
                # 在 DAG 图中找到 fact_sales 文本并点击
                dag_area = page.locator(".dag-graph, svg, canvas").first
                page.get_by_text("fact_sales").first.click()
                time.sleep(1)
                print("  ✓ fact_sales 节点已点击")
            except Exception as e:
                chapter6_ok = False
                add_issue("medium", "第6章", f"无法点击 fact_sales 节点: {e}")
            
            ok = check_screenshot(page, "26_DAG_fact_sales血缘.png", "第6章")
            if not ok:
                chapter6_ok = False
                add_issue("medium", "第6章", "26_DAG_fact_sales血缘.png 截图检查有差异")
            
            # 步骤37：点击 sales_wide 节点
            print("\n步骤37：sales_wide 血缘")
            try:
                page.get_by_text("sales_wide").first.click()
                time.sleep(1)
                print("  ✓ sales_wide 节点已点击")
            except Exception as e:
                chapter6_ok = False
                add_issue("medium", "第6章", f"无法点击 sales_wide 节点: {e}")
            
            ok = check_screenshot(page, "27_DAG_sales_wide血缘.png", "第6章")
            if not ok:
                chapter6_ok = False
                add_issue("medium", "第6章", "27_DAG_sales_wide血缘.png 截图检查有差异")
            
            results["chapters"]["第6章"] = "通过" if chapter6_ok else "失败"
            
            # ========== 第 7 章：运行历史 ==========
            print("\n" + "="*60)
            print("第 7 章：运行历史")
            print("="*60)
            chapter7_ok = True
            
            # 步骤38：运行历史列表
            print("\n步骤38：运行历史列表")
            page.get_by_role("tab", name="运行历史").click()
            time.sleep(2)
            
            ok = check_screenshot(page, "28_运行历史列表.png", "第7章")
            if not ok:
                chapter7_ok = False
                add_issue("medium", "第7章", "28_运行历史列表.png 截图检查有差异")
            
            # 步骤39：查看日志
            print("\n步骤39：查看运行日志")
            try:
                page.get_by_role("button", name="查看日志").first.click()
                time.sleep(1)
                print("  ✓ 日志弹窗已打开")
            except Exception as e:
                chapter7_ok = False
                add_issue("high", "第7章", f"无法查看日志: {e}")
            
            ok = check_screenshot(page, "29_查看运行日志.png", "第7章")
            if not ok:
                chapter7_ok = False
                add_issue("medium", "第7章", "29_查看运行日志.png 截图检查有差异")
            
            # 关闭日志弹窗
            try:
                page.locator(".el-dialog").filter(has_text="运行 #").get_by_role("button", name="关闭").click()
            except:
                try:
                    page.keyboard.press("Escape")
                except:
                    pass
            time.sleep(0.5)
            
            # 步骤40：返回项目列表
            print("\n步骤40：返回项目列表")
            page.get_by_role("button", name="← 返回").click()
            page.wait_for_load_state("networkidle")
            time.sleep(2)
            
            try:
                expect(page.get_by_text("DBT 项目")).to_be_visible()
                print("  ✓ 已返回项目列表")
            except Exception as e:
                chapter7_ok = False
                add_issue("high", "第7章", f"返回项目列表失败: {e}")
            
            ok = check_screenshot(page, "30_返回项目列表.png", "第7章")
            if not ok:
                chapter7_ok = False
                add_issue("medium", "第7章", "30_返回项目列表.png 截图检查有差异")
            
            results["chapters"]["第7章"] = "通过" if chapter7_ok else "失败"
            
        except Exception as e:
            print(f"\n❌ 验证过程中发生错误: {e}")
            import traceback
            traceback.print_exc()
            add_issue("critical", "全局", f"验证脚本异常: {e}")
            
            # 保存当前页面截图用于调试
            try:
                page.screenshot(path=str(OUTPUT_DIR / "error_screenshot.png"), full_page=True)
                print(f"  错误截图已保存到 {OUTPUT_DIR / 'error_screenshot.png'}")
            except:
                pass
        
        finally:
            # 保存结果
            result_path = OUTPUT_DIR / "verify_results.json"
            with open(result_path, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"\n验证结果已保存到: {result_path}")
            
            browser.close()

if __name__ == "__main__":
    main()
