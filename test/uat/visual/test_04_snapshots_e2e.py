"""TC-SNAPSHOT-E2E — Snapshot 前端 E2E 交互测试。

覆盖完整用户流程：进入标签页 → 新建快照 → 验证列表 → 编辑 → 运行 → 删除
"""
from __future__ import annotations

import re

import pytest
from playwright.async_api import Page, expect

SNAPSHOT_NAME = "e2e_customers_snapshot"
SNAPSHOT_SQL = """\
{% snapshot e2e_customers_snapshot %}

{{
    config(
      target_schema='snapshots',
      unique_key='id',
      strategy='timestamp',
      updated_at='updated_at',
    )
}}

select * from {{ ref('example') }}

{% endsnapshot %}
"""


@pytest.mark.asyncio(loop_scope="session")
async def test_e2e_snapshots_tab_empty(page: Page, base_url: str, visual_project: dict):
    """E2E-01：Snapshots 标签页空状态。"""
    await page.goto(f"{base_url}/projects/{visual_project['id']}")

    # 点击 Snapshots 标签
    await page.get_by_text("Snapshots", exact=True).click()

    # 验证工具栏
    await expect(page.get_by_role("button", name="新建快照")).to_be_visible()

    # 验证空状态
    await expect(page.get_by_text("暂无快照")).to_be_visible()


@pytest.mark.asyncio(loop_scope="session")
async def test_e2e_create_snapshot(page: Page, base_url: str, visual_project: dict):
    """E2E-02：新建快照。"""
    await page.goto(f"{base_url}/projects/{visual_project['id']}")
    await page.get_by_text("Snapshots", exact=True).click()
    await page.get_by_role("button", name="新建快照").wait_for(state="visible")

    # 点击新建
    await page.get_by_role("button", name="新建快照").click()

    # 等待弹窗
    dialog = page.locator("div[role='dialog']").filter(visible=True).first
    await dialog.wait_for(state="visible")

    # 填写名称
    name_input = dialog.get_by_label("名称")
    await name_input.fill(SNAPSHOT_NAME)

    # 填写 SQL（通过 CodeMirror 比较复杂，这里用 evaluate 直接设置 model value）
    # 先点击 SQL 编辑器区域使其获得焦点，然后用键盘输入
    sql_editor = dialog.locator(".cm-editor").first
    await sql_editor.click()
    # 全选删除默认内容
    await page.keyboard.press("Meta+A")
    await page.keyboard.press("Backspace")
    # 粘贴新内容
    await page.keyboard.type(SNAPSHOT_SQL, delay=10)

    # 点击创建
    await dialog.get_by_role("button", name="创建").click()

    # 等待弹窗关闭
    await expect(dialog).not_to_be_visible()

    # 验证列表中出现新快照
    tab_panel = page.get_by_role("tabpanel", name="Snapshots")
    await expect(tab_panel.get_by_text(SNAPSHOT_NAME)).to_be_visible()

    # 验证策略列显示 timestamp
    await expect(tab_panel.get_by_text("timestamp")).to_be_visible()

    # 验证目标 Schema 列
    await expect(tab_panel.get_by_text("snapshots", exact=True)).to_be_visible()


@pytest.mark.asyncio(loop_scope="session")
async def test_e2e_snapshot_not_in_models(page: Page, base_url: str, visual_project: dict):
    """E2E-03：snapshot 不出现在 Models 列表中。"""
    await page.goto(f"{base_url}/projects/{visual_project['id']}")
    await page.get_by_text("Models", exact=True).click()
    await page.wait_for_timeout(500)

    # 在 Models 页面中不应找到 snapshot 名称
    tab_panel = page.get_by_role("tabpanel", name="Models")
    content = await tab_panel.inner_text()
    assert SNAPSHOT_NAME not in content


@pytest.mark.asyncio(loop_scope="session")
async def test_e2e_edit_snapshot(page: Page, base_url: str, visual_project: dict):
    """E2E-04：编辑快照（修改 SQL）。"""
    await page.goto(f"{base_url}/projects/{visual_project['id']}")
    await page.get_by_text("Snapshots", exact=True).click()
    tab_panel = page.get_by_role("tabpanel", name="Snapshots")
    await tab_panel.get_by_text(SNAPSHOT_NAME).wait_for(state="visible")

    # 找到对应行的编辑按钮并点击
    row = page.locator("tr").filter(has_text=SNAPSHOT_NAME)
    await row.get_by_role("button", name="编辑").click()

    # 等待弹窗
    dialog = page.locator("div[role='dialog']").filter(visible=True).first
    await dialog.wait_for(state="visible")

    # 验证标题包含快照名
    await expect(dialog.get_by_text(re.compile(r"编辑快照.*" + SNAPSHOT_NAME))).to_be_visible()

    # 修改 SQL（添加注释）
    sql_editor = dialog.locator(".cm-editor").first
    await sql_editor.click()
    await page.keyboard.press("Meta+A")
    await page.keyboard.press("Backspace")
    modified_sql = SNAPSHOT_SQL.replace(
        "select * from {{ ref('example') }}",
        "-- E2E modified\nselect id from {{ ref('example') }}",
    )
    await page.keyboard.type(modified_sql, delay=10)

    # 点击保存
    await dialog.get_by_role("button", name="保存").click()

    # 等待弹窗关闭
    await expect(dialog).not_to_be_visible()

    # 验证列表中快照仍然存在
    await expect(tab_panel.get_by_text(SNAPSHOT_NAME)).to_be_visible()


@pytest.mark.asyncio(loop_scope="session")
async def test_e2e_run_snapshot(page: Page, base_url: str, visual_project: dict):
    """E2E-05：运行单个快照。"""
    await page.goto(f"{base_url}/projects/{visual_project['id']}")
    await page.get_by_text("Snapshots", exact=True).click()
    tab_panel = page.get_by_role("tabpanel", name="Snapshots")
    await tab_panel.get_by_text(SNAPSHOT_NAME).wait_for(state="visible")

    # 点击运行按钮
    row = page.locator("tr").filter(has_text=SNAPSHOT_NAME)
    await row.get_by_role("button", name="运行").click()

    # 等待运行对话框
    dialog = page.locator("div[role='dialog']").filter(visible=True).first
    await dialog.wait_for(state="visible")

    # 验证运行类型是 snapshot
    select = dialog.locator(".el-select").first
    await expect(select).to_contain_text("snapshot")

    # 点击开始
    await dialog.get_by_role("button", name="开始").click()

    # 等待运行完成（等待"成功"或"失败"出现在日志中，或按钮变为可再次点击）
    await page.wait_for_timeout(2000)

    # 等待运行结束（开始按钮重新可用，或出现关闭按钮状态）
    try:
        await dialog.get_by_role("button", name="开始").wait_for(state="visible", timeout=30000)
    except Exception:
        pass

    # 关闭对话框
    close_btn = dialog.get_by_role("button", name=re.compile("关闭|取消"))
    if await close_btn.count() > 0:
        await close_btn.first.click()

    # 验证运行状态列有值
    await page.wait_for_timeout(500)
    row = page.locator("tr").filter(has_text=SNAPSHOT_NAME)
    status_tag = row.locator(".el-tag")
    await expect(status_tag.first).to_be_visible()


@pytest.mark.asyncio(loop_scope="session")
async def test_e2e_run_dialog_has_snapshot_option(page: Page, base_url: str, visual_project: dict):
    """E2E-06：运行对话框下拉中有 snapshot 选项。"""
    await page.goto(f"{base_url}/projects/{visual_project['id']}")
    await page.get_by_text("Snapshots", exact=True).click()
    tab_panel = page.get_by_role("tabpanel", name="Snapshots")
    await tab_panel.get_by_text(SNAPSHOT_NAME).wait_for(state="visible")

    # 点击运行打开对话框
    row = page.locator("tr").filter(has_text=SNAPSHOT_NAME)
    await row.get_by_role("button", name="运行").click()

    dialog = page.locator("div[role='dialog']").filter(visible=True).first
    await dialog.wait_for(state="visible")

    # 点击下拉框展开选项
    select = dialog.locator(".el-select").first
    await select.click()

    # 验证下拉列表中有 snapshot 选项
    dropdown = page.locator(".el-select-dropdown").filter(visible=True).first
    await expect(dropdown.get_by_text("snapshot", exact=True)).to_be_visible()

    # 关闭下拉
    await page.keyboard.press("Escape")

    # 关闭对话框
    close_btn = dialog.get_by_role("button", name=re.compile("关闭|取消"))
    if await close_btn.count() > 0:
        await close_btn.first.click()


@pytest.mark.asyncio(loop_scope="session")
async def test_e2e_delete_snapshot(page: Page, base_url: str, visual_project: dict):
    """E2E-07：删除快照。"""
    await page.goto(f"{base_url}/projects/{visual_project['id']}")
    await page.get_by_text("Snapshots", exact=True).click()
    tab_panel = page.get_by_role("tabpanel", name="Snapshots")
    await tab_panel.get_by_text(SNAPSHOT_NAME).wait_for(state="visible")

    # 点击删除按钮
    row = page.locator("tr").filter(has_text=SNAPSHOT_NAME)
    await row.get_by_role("button", name="删除").click()

    # 等待确认弹窗
    confirm_dialog = page.locator("div[role='dialog']").filter(visible=True).first
    await confirm_dialog.wait_for(state="visible")

    # 点击确定
    await confirm_dialog.get_by_role("button", name="确定").click()

    # 等待确认弹窗关闭
    await expect(confirm_dialog).not_to_be_visible()

    # 验证列表中快照消失
    await page.wait_for_timeout(1000)
    await expect(tab_panel.get_by_text(SNAPSHOT_NAME)).not_to_be_visible()

    # 验证空状态提示出现
    await expect(tab_panel.get_by_text("暂无快照")).to_be_visible()
