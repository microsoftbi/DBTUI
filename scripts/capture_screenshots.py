"""
Playwright 截图采集脚本
用于采集分层配置和 Sources 管理界面的截图，替换用户手册中的占位符。

使用方法：
    1. 确保后端（8000端口）和前端（5173端口）已启动
    2. 确保存在一个名为 sales_warehouse 的 sqlserver 项目
    3. 运行：python scripts/capture_screenshots.py

截图输出目录：doc/userguide/
"""

import os
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, Page, expect

# ── 配置 ──────────────────────────────────────────────
FRONTEND_URL = "http://localhost:5173"
PROJECT_NAME = "sales_warehouse"  # 目标项目名称
OUTPUT_DIR = Path(__file__).parent.parent / "doc" / "userguide"
VIEWPORT = {"width": 1440, "height": 900}
WAIT_AFTER_ACTION = 800  # 每个操作后等待的毫秒数，让动画稳定
# ──────────────────────────────────────────────────────

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def wait(page: Page, ms: int = WAIT_AFTER_ACTION):
    """等待一段时间，让 UI 稳定。"""
    page.wait_for_timeout(ms)


def screenshot(page: Page, filename: str, full_page: bool = False):
    """截图并保存到输出目录。"""
    path = OUTPUT_DIR / filename
    page.screenshot(path=str(path), full_page=full_page)
    print(f"  ✓ 截图保存: {filename}")


def dialog_by_title(page: Page, title: str):
    """通过弹窗标题精确定位 el-dialog，避免 has_text 匹配到按钮文本。"""
    return page.locator(".el-dialog__header").filter(has_text=title).locator("../..")


def find_and_open_project(page: Page, project_name: str):
    """在项目列表中找到并打开指定项目。"""
    page.goto(FRONTEND_URL)
    page.wait_for_load_state("networkidle")
    wait(page, 1500)

    # 在表格中找到项目行，点击「打开」
    rows = page.locator("tbody tr")
    count = rows.count()
    for i in range(count):
        row = rows.nth(i)
        if project_name in row.inner_text():
            row.get_by_role("button", name="打开").click()
            page.wait_for_load_state("networkidle")
            wait(page, 2000)
            return

    raise RuntimeError(f"未找到项目: {project_name}")


# ═══════════════════════════════════════════════════════
#  分层配置截图
# ═══════════════════════════════════════════════════════

def capture_layer_screenshots(page: Page):
    """采集分层配置相关的所有截图。"""
    print("\n═══ 分层配置截图 ═══")

    # ── 07b: 分层配置入口（项目详情页顶部按钮） ──
    print("\n[07b] 分层配置入口")
    # 确保在 Models tab
    page.get_by_role("tab", name="Models").click()
    wait(page, 1000)
    screenshot(page, "07b_分层配置入口.png")

    # ── 07c: 分层配置列表弹窗 ──
    print("\n[07c] 分层配置列表")
    page.get_by_role("button", name="分层配置").click()
    wait(page, 1000)
    # 截取弹窗
    dialog = page.locator(".el-dialog").filter(has_text="分层配置")
    dialog.screenshot(path=str(OUTPUT_DIR / "07c_分层配置列表.png"))
    print(f"  ✓ 截图保存: 07c_分层配置列表.png")

    # ── 07d: 新增分层弹窗 ──
    print("\n[07d] 新增分层弹窗")
    dialog.get_by_role("button", name="新增分层").click()
    wait(page, 800)
    # 用标题精确匹配新增分层弹窗（避免匹配到父弹窗中的按钮文本）
    new_dialog = page.locator(".el-dialog__header").filter(has_text="新增分层").locator("../..")
    new_dialog.get_by_label("显示名称").fill("ODS 层")
    new_dialog.get_by_label("目录名").fill("ods")
    new_dialog.get_by_label("目标数据库").fill("ods_db")
    new_dialog.get_by_label("目标 Schema").fill("dbo")
    # 选择默认物化（el-select 需要点击外层 wrapper）
    new_dialog.locator(".el-form-item").filter(has_text="默认物化").locator(".el-select").click()
    page.get_by_role("option", name="view").click()
    wait(page, 500)
    new_dialog.screenshot(path=str(OUTPUT_DIR / "07d_新建分层弹窗.png"))
    print(f"  ✓ 截图保存: 07d_新建分层弹窗.png")
    # 关闭弹窗（取消）
    new_dialog.get_by_role("button", name="取消").click()
    wait(page, 500)

    # ── 07e: 编辑分层弹窗 ──
    print("\n[07e] 编辑分层弹窗")
    # 找到 staging 层的编辑按钮
    layer_dialog = page.locator(".el-dialog").filter(has_text="分层配置")
    # 在表格中找到 staging 行
    staging_row = layer_dialog.locator("tbody tr").filter(has_text="staging")
    staging_row.get_by_role("button", name="编辑").click()
    wait(page, 800)
    edit_dialog = dialog_by_title(page, "编辑分层")
    edit_dialog.screenshot(path=str(OUTPUT_DIR / "07e_编辑分层弹窗.png"))
    print(f"  ✓ 截图保存: 07e_编辑分层弹窗.png")
    # 关闭弹窗
    edit_dialog.get_by_role("button", name="取消").click()
    wait(page, 500)

    # 关闭分层配置弹窗（点击右上角 X）
    layer_dialog.locator(".el-dialog__close").click()
    wait(page, 500)


# ═══════════════════════════════════════════════════════
#  Sources 管理截图
# ═══════════════════════════════════════════════════════

def ensure_sales_db_source(page: Page):
    """确保存在 sales_db source，如果不存在则创建。"""
    page.get_by_role("tab", name="Sources").click()
    wait(page, 1500)

    # 检查左侧树中是否已有 sales_db
    tree = page.locator(".sources-tree")
    if "sales_db" in tree.inner_text():
        return  # 已存在

    # 不存在则创建
    page.get_by_role("button", name="新建数据源").click()
    wait(page, 800)
    dialog = dialog_by_title(page, "新建数据源")
    dialog.get_by_label("源名称").fill("sales_db")
    dialog.get_by_label("数据库").fill("sales_db")
    dialog.get_by_label("Schema").fill("dbo")
    dialog.get_by_label("加载器").fill("sqlserver")
    dialog.get_by_label("描述").fill("销售业务源系统")
    # 选择保存目录为 staging
    dialog.locator(".el-form-item").filter(has_text="保存目录").locator(".el-select").click()
    page.get_by_role("option", name="Stage 层（staging）").click()
    dialog.get_by_role("button", name="保存").click()
    wait(page, 2000)


def ensure_source_tables(page: Page):
    """确保 sales_db source 下有三张表。"""
    # 点击左侧树中的 sales_db 节点
    tree = page.locator(".sources-tree")
    tree.get_by_text("sales_db").first.click()
    wait(page, 1000)

    detail = page.locator(".sources-detail")
    detail_text = detail.inner_text()

    tables_needed = [
        ("customer", "客户表"),
        ("product", "产品表"),
        ("salesorder", "销售订单表"),
    ]

    for table_name, desc in tables_needed:
        if table_name not in detail_text:
            # 添加表
            detail.get_by_role("button", name="添加表").click()
            wait(page, 800)
            dialog = dialog_by_title(page, "添加表")
            dialog.get_by_label("表名").fill(table_name)
            dialog.get_by_label("描述").fill(desc)
            dialog.get_by_role("button", name="保存").click()
            wait(page, 1500)
            detail_text = detail.inner_text()


def capture_sources_screenshots(page: Page):
    """采集 Sources 管理相关的所有截图。"""
    print("\n═══ Sources 管理截图 ═══")

    # 切换到 Sources tab
    page.get_by_role("tab", name="Sources").click()
    wait(page, 1500)

    # 确保有测试数据
    ensure_sales_db_source(page)
    ensure_source_tables(page)

    # ── 08: Sources 标签页（全景，选中 sales_db） ──
    print("\n[08] Sources 标签页")
    # 点击 sales_db 让详情显示出来
    tree = page.locator(".sources-tree")
    tree.get_by_text("sales_db").first.click()
    wait(page, 1000)
    screenshot(page, "08_Sources标签页.png")

    # ── 08a: 新建数据源弹窗 ──
    print("\n[08a] 新建数据源弹窗")
    page.get_by_role("button", name="新建数据源").click()
    wait(page, 800)
    dialog = dialog_by_title(page, "新建数据源")
    # 填写表单（不提交）
    dialog.get_by_label("源名称").fill("crm_db")
    dialog.get_by_label("数据库").fill("crm_db")
    dialog.get_by_label("Schema").fill("dbo")
    dialog.get_by_label("加载器").fill("sqlserver")
    dialog.get_by_label("描述").fill("CRM 系统源数据")
    dialog.locator(".el-form-item").filter(has_text="保存目录").locator(".el-select").click()
    page.get_by_role("option", name="Stage 层（staging）").click()
    wait(page, 500)
    dialog.screenshot(path=str(OUTPUT_DIR / "08a_新建Source弹窗.png"))
    print(f"  ✓ 截图保存: 08a_新建Source弹窗.png")
    dialog.get_by_role("button", name="取消").click()
    wait(page, 500)

    # ── 08b: Source 详情 ──
    print("\n[08b] Source 详情")
    tree = page.locator(".sources-tree")
    tree.get_by_text("sales_db").first.click()
    wait(page, 800)
    # 截取右侧详情区域
    detail = page.locator(".sources-detail")
    detail.screenshot(path=str(OUTPUT_DIR / "08b_Source详情.png"))
    print(f"  ✓ 截图保存: 08b_Source详情.png")

    # ── 08c: 添加源表弹窗 ──
    print("\n[08c] 添加源表弹窗")
    detail.get_by_role("button", name="添加表").click()
    wait(page, 800)
    dialog = dialog_by_title(page, "添加表")
    dialog.get_by_label("表名").fill("employee")
    dialog.get_by_label("描述").fill("员工表")
    wait(page, 500)
    dialog.screenshot(path=str(OUTPUT_DIR / "08c_添加源表弹窗.png"))
    print(f"  ✓ 截图保存: 08c_添加源表弹窗.png")
    dialog.get_by_role("button", name="取消").click()
    wait(page, 500)

    # ── 08d: Source 表列表（完整三张表） ──
    print("\n[08d] Source 表列表")
    # 截取表列表部分
    detail.locator(".tables-section").screenshot(
        path=str(OUTPUT_DIR / "08d_Source表列表.png")
    )
    print(f"  ✓ 截图保存: 08d_Source表列表.png")

    # ── 08e: 模型列表含 source ──
    print("\n[08e] 模型列表含 source")
    page.get_by_role("tab", name="Models").click()
    wait(page, 2000)
    screenshot(page, "08e_模型列表_含source.png")


# ═══════════════════════════════════════════════════════
#  Snapshot 管理截图
# ═══════════════════════════════════════════════════════

def close_any_dialog(page: Page):
    """关闭页面上残留的任何 el-dialog（右上角 X），避免拦截点击。"""
    # 自顶向下（最后弹出的在最后）依次关闭
    overlays = page.locator(".el-overlay")
    n = overlays.count()
    for i in range(n):
        # 每次都处理最后一个 overlay，避免 stale reference
        overlay = page.locator(".el-overlay").last
        dialog = overlay.locator(".el-dialog").last
        if dialog.count() > 0:
            close_btn = dialog.locator(".el-dialog__close").first
            if close_btn.is_visible():
                try:
                    close_btn.click()
                    wait(page, 400)
                except Exception:
                    try:
                        page.keyboard.press("Escape")
                        wait(page, 400)
                    except Exception:
                        pass


def ensure_snapshot_data(page: Page):
    """确保 Snapshots 标签页下有示例快照，不存在则创建。"""
    close_any_dialog(page)
    page.get_by_role("tab", name="Snapshots").click()
    wait(page, 1500)

    tab_panel = page.get_by_role("tabpanel", name="Snapshots")
    if "snap_customer" in tab_panel.inner_text():
        return  # 已存在

    # 点击新建快照
    page.get_by_role("button", name="新建快照").click()
    wait(page, 800)

    dialog = dialog_by_title(page, "新建快照")
    dialog.get_by_label("名称").fill("snap_customer")

    sql = """{% snapshot snap_customer %}

{{
    config(
      target_schema='snapshots',
      unique_key='customer_id',
      strategy='check',
      check_cols=['customer_level', 'phone'],
    )
}}

select
    customer_id,
    customer_name,
    customer_level,
    phone,
    region
from {{ ref('stg_customer') }}

{% endsnapshot %}
"""
    sql_editor = dialog.locator(".cm-editor").first
    sql_editor.click()
    page.keyboard.press("Meta+A")
    page.keyboard.press("Backspace")
    for line in sql.splitlines(keepends=True):
        page.keyboard.type(line, delay=5)

    dialog.get_by_role("button", name="创建").click()
    # 创建完成后弹窗应自动关闭；列表中出现 snap_customer 即代表成功
    tab_panel = page.get_by_role("tabpanel", name="Snapshots")
    try:
        tab_panel.get_by_text("snap_customer").wait_for(state="visible", timeout=15000)
    except Exception:
        page.screenshot(path=str(OUTPUT_DIR / "ensure_snapshot_failed.png"), full_page=True)
        raise
    wait(page, 1500)


def capture_snapshot_screenshots(page: Page):
    """采集 Snapshot 管理相关的所有截图（41/42/43）。"""
    print("\n═══ Snapshot 管理截图 ═══")

    # 准备测试数据（至少有 1 条快照）
    ensure_snapshot_data(page)

    # ── 41: Snapshots 标签页（列表有数据） ──
    print("\n[41] Snapshots 标签页")
    close_any_dialog(page)
    page.get_by_role("tab", name="Snapshots").click()
    wait(page, 1500)
    screenshot(page, "41_snapshots_tab.png")

    # ── 42: 新建快照弹窗（预填示例） ──
    print("\n[42] 新建快照弹窗")
    page.get_by_role("button", name="新建快照").click()
    wait(page, 800)
    dialog = dialog_by_title(page, "新建快照")
    # 填写示例表单但不提交
    dialog.get_by_label("名称").fill("snap_product")
    sample_sql = """{% snapshot snap_product %}

{{
    config(
      target_schema='snapshots',
      unique_key='product_id',
      strategy='timestamp',
      updated_at='updated_at',
    )
}}

select
    product_id,
    product_name,
    category,
    price,
    updated_at
from {{ ref('stg_product') }}

{% endsnapshot %}
"""
    sql_editor = dialog.locator(".cm-editor").first
    sql_editor.click()
    page.keyboard.press("Meta+A")
    page.keyboard.press("Backspace")
    for line in sample_sql.splitlines(keepends=True):
        page.keyboard.type(line, delay=5)
    wait(page, 800)
    dialog.screenshot(path=str(OUTPUT_DIR / "42_new_snapshot_dialog.png"))
    print(f"  ✓ 截图保存: 42_new_snapshot_dialog.png")
    # 取消关闭
    dialog.get_by_role("button", name="取消").click()
    wait(page, 500)

    # ── 43: 运行 Snapshot 对话框 ──
    print("\n[43] 运行 Snapshot 对话框")
    close_any_dialog(page)
    page.get_by_role("tab", name="Snapshots").click()
    wait(page, 1500)
    tab_panel = page.get_by_role("tabpanel", name="Snapshots")
    row = tab_panel.locator("tbody tr").filter(has_text="snap_customer")
    row.get_by_role("button", name="运行").click()
    wait(page, 1000)
    # 运行对话框标题为"运行"
    run_dialog = dialog_by_title(page, "运行")
    run_dialog.screenshot(path=str(OUTPUT_DIR / "43_run_snapshot.png"))
    print(f"  ✓ 截图保存: 43_run_snapshot.png")
    # 关闭对话框（右上角 X）
    close_btn = run_dialog.locator(".el-dialog__close")
    if close_btn.count() > 0:
        close_btn.click()
    wait(page, 500)


# ═══════════════════════════════════════════════════════
#  重拍旧截图（因新增分层配置按钮、Sources tab 导致界面变化）
# ═══════════════════════════════════════════════════════

def capture_legacy_screenshots(page: Page):
    """重新采集因界面变化而需要更新的旧截图。"""
    print("\n═══ 重拍旧截图 ═══")

    # ── 05: 项目详情页（Models tab，显示分层配置按钮和 Sources tab） ──
    print("\n[05] 项目详情页")
    page.get_by_role("tab", name="Models").click()
    wait(page, 1500)
    screenshot(page, "05_项目详情页.png")

    # ── 09: 新建模型弹窗（层级选择器从 layers 动态生成） ──
    print("\n[09] 新建模型弹窗")
    page.get_by_role("button", name="新建模型").click()
    wait(page, 1000)
    dialog = dialog_by_title(page, "新建模型")
    dialog.screenshot(path=str(OUTPUT_DIR / "09_新建模型弹窗.png"))
    print(f"  ✓ 截图保存: 09_新建模型弹窗.png")
    # 不关闭，继续填内容拍下一张

    # ── 10: 填写 stg_customer ──
    print("\n[10] 填写 stg_customer")
    dialog.get_by_label("名称").fill("stg_customer")
    wait(page, 800)
    dialog.screenshot(path=str(OUTPUT_DIR / "10_填写stg_customer.png"))
    print(f"  ✓ 截图保存: 10_填写stg_customer.png")
    # 取消关闭
    dialog.get_by_role("button", name="取消").click()
    wait(page, 500)

    # ── 11: Stage 层模型列表 ──
    print("\n[11] Stage 层模型列表")
    page.get_by_role("tab", name="Models").click()
    wait(page, 2000)
    screenshot(page, "11_Stage层模型列表.png")

    # ── 15: Core 层模型列表 ──
    print("\n[15] Core 层模型列表")
    # 直接截图（模型列表包含所有层，Core 模型也在里面）
    screenshot(page, "15_Core层模型列表.png")

    # ── 20: Mart 层模型列表 ──
    print("\n[20] Mart 层模型列表")
    screenshot(page, "20_Mart层模型列表.png")

    # ── 21: Tests 标签页 ──
    print("\n[21] Tests 标签页")
    page.get_by_role("tab", name="Tests").click()
    wait(page, 1500)
    screenshot(page, "21_Tests标签页.png")

    # ── 25: DAG 全景图 ──
    print("\n[25] DAG 全景图")
    page.get_by_role("tab", name="DAG").click()
    wait(page, 2000)
    screenshot(page, "25_DAG全景图.png")

    # ── 28: 运行历史列表 ──
    print("\n[28] 运行历史列表")
    page.get_by_role("tab", name="运行历史").click()
    wait(page, 1500)
    screenshot(page, "28_运行历史列表.png")


# ═══════════════════════════════════════════════════════
#  主函数
# ═══════════════════════════════════════════════════════

def main():
    print(f"前端地址: {FRONTEND_URL}")
    print(f"目标项目: {PROJECT_NAME}")
    print(f"输出目录: {OUTPUT_DIR.resolve()}")
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # 有头模式，方便观察
        context = browser.new_context(
            viewport=VIEWPORT,
            locale="zh-CN",
        )
        page = context.new_page()

        try:
            # 打开项目
            print(f"打开项目: {PROJECT_NAME}")
            find_and_open_project(page, PROJECT_NAME)

            # 采集分层配置截图
            capture_layer_screenshots(page)

            # 采集 Sources 截图
            capture_sources_screenshots(page)

            # 采集 Snapshot 截图
            capture_snapshot_screenshots(page)

            # 重拍因界面变化需要更新的旧截图
            capture_legacy_screenshots(page)

            print("\n" + "=" * 50)
            print("所有截图采集完成！")
            print(f"输出目录: {OUTPUT_DIR.resolve()}")
            print("=" * 50)

        finally:
            browser.close()


if __name__ == "__main__":
    main()
