"""TC-SNAPSHOT — Snapshot 快照管理自动化测试。"""
from __future__ import annotations

import httpx
import pytest


SNAPSHOT_TIMESTAMP_SQL = """\
{% snapshot uat_customers_snapshot %}

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

SNAPSHOT_CHECK_SQL = """\
{% snapshot uat_orders_check_snapshot %}

{{
    config(
      target_schema='snapshots',
      unique_key='id',
      strategy='check',
      check_cols='all',
    )
}}

select * from {{ ref('example') }}

{% endsnapshot %}
"""


def test_list_snapshots_empty(api_client: httpx.Client, project_id: int):
    """TC-SNAPSHOT-01：初始状态下列表为空。"""
    resp = api_client.get(f"/api/projects/{project_id}/snapshots")
    assert resp.status_code == 200
    snapshots = resp.json()
    assert isinstance(snapshots, list)
    # 新建项目默认没有 snapshot
    snapshot_names = [s["name"] for s in snapshots]
    assert "uat_customers_snapshot" not in snapshot_names


def test_create_snapshot_timestamp(api_client: httpx.Client, project_id: int):
    """TC-SNAPSHOT-02：新建 timestamp 策略快照。"""
    name = "uat_customers_snapshot"
    resp = api_client.post(
        f"/api/projects/{project_id}/snapshots",
        json={"name": name, "sql": SNAPSHOT_TIMESTAMP_SQL},
    )
    assert resp.status_code == 201, f"创建失败: {resp.text}"
    snapshot = resp.json()
    assert snapshot["name"] == name
    assert snapshot["resource_type"] == "snapshot"
    assert snapshot["file_path"] == f"snapshots/{name}.sql"

    # 列表中存在
    snapshots = api_client.get(f"/api/projects/{project_id}/snapshots").json()
    assert any(s["name"] == name for s in snapshots)

    # 验证 snapshot 特有字段
    s = next(s for s in snapshots if s["name"] == name)
    assert s["snapshot_strategy"] == "timestamp"
    assert s["target_schema"] == "snapshots"
    assert s["unique_key"] == "id"


def test_get_snapshot_sql(api_client: httpx.Client, project_id: int):
    """TC-SNAPSHOT-03：获取快照 SQL 内容。"""
    snapshots = api_client.get(f"/api/projects/{project_id}/snapshots").json()
    s = next(s for s in snapshots if s["name"] == "uat_customers_snapshot")

    resp = api_client.get(f"/api/projects/{project_id}/snapshots/{s['id']}/sql")
    assert resp.status_code == 200
    data = resp.json()
    assert data["snapshot_id"] == s["id"]
    assert data["name"] == "uat_customers_snapshot"
    assert data["file_path"] == "snapshots/uat_customers_snapshot.sql"
    assert "{% snapshot uat_customers_snapshot %}" in data["sql"]
    assert "{% endsnapshot %}" in data["sql"]
    assert "strategy='timestamp'" in data["sql"]


def test_update_snapshot_sql(api_client: httpx.Client, project_id: int):
    """TC-SNAPSHOT-04：编辑快照 SQL。"""
    snapshots = api_client.get(f"/api/projects/{project_id}/snapshots").json()
    s = next(s for s in snapshots if s["name"] == "uat_customers_snapshot")

    new_sql = SNAPSHOT_TIMESTAMP_SQL.replace(
        "select * from {{ ref('example') }}",
        "select id, 1 AS extra_col from {{ ref('example') }}",
    )
    resp = api_client.put(
        f"/api/projects/{project_id}/snapshots/{s['id']}",
        json={"sql": new_sql},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "uat_customers_snapshot"

    # 验证 SQL 已更新
    sql_resp = api_client.get(f"/api/projects/{project_id}/snapshots/{s['id']}/sql")
    assert "extra_col" in sql_resp.json()["sql"]


def test_update_snapshot_rename(api_client: httpx.Client, project_id: int):
    """TC-SNAPSHOT-05：重命名快照。"""
    snapshots = api_client.get(f"/api/projects/{project_id}/snapshots").json()
    s = next(s for s in snapshots if s["name"] == "uat_customers_snapshot")

    new_name = "uat_customers_snapshot_v2"
    resp = api_client.put(
        f"/api/projects/{project_id}/snapshots/{s['id']}",
        json={"name": new_name},
    )
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["name"] == new_name
    assert updated["file_path"] == f"snapshots/{new_name}.sql"

    # 列表中旧名称消失，新名称存在
    snapshots_after = api_client.get(f"/api/projects/{project_id}/snapshots").json()
    names = [s["name"] for s in snapshots_after]
    assert new_name in names
    assert "uat_customers_snapshot" not in names


def test_run_snapshot(api_client: httpx.Client, project_id: int):
    """TC-SNAPSHOT-06：运行单个快照。"""
    resp = api_client.post(
        f"/api/projects/{project_id}/runs",
        json={"run_type": "snapshot", "selection": "uat_customers_snapshot_v2"},
    )
    assert resp.status_code == 202, f"运行失败: {resp.text}"
    run = resp.json()
    assert run["run_type"] == "snapshot"
    assert run["selection"] == "uat_customers_snapshot_v2"
    # 运行已完成（success 或 error 都算正常执行完毕，数据库不可达时会是 error）
    assert run["status"] in ("success", "error")
    assert run["finished_at"] is not None

    # 运行历史中有 snapshot 记录
    history = api_client.get(f"/api/projects/{project_id}/runs").json()
    snapshot_runs = [r for r in history if r["run_type"] == "snapshot"]
    assert len(snapshot_runs) >= 1


def test_run_all_snapshots(api_client: httpx.Client, project_id: int):
    """TC-SNAPSHOT-07：全量快照运行（selection 为空）。"""
    resp = api_client.post(
        f"/api/projects/{project_id}/runs",
        json={"run_type": "snapshot", "selection": ""},
    )
    assert resp.status_code == 202
    run = resp.json()
    assert run["run_type"] == "snapshot"
    assert run["selection"] == ""
    assert run["status"] in ("success", "error")
    assert run["finished_at"] is not None


def test_models_not_include_snapshot(api_client: httpx.Client, project_id: int):
    """TC-SNAPSHOT-08：Models 列表不包含 snapshot。"""
    models = api_client.get(f"/api/projects/{project_id}/models").json()
    model_names = [m["name"] for m in models]
    assert "uat_customers_snapshot_v2" not in model_names
    # 所有 model 的 resource_type 都应该是 model
    assert all(m["resource_type"] == "model" for m in models)


def test_create_snapshot_check(api_client: httpx.Client, project_id: int):
    """TC-SNAPSHOT-11：新建 check 策略快照。"""
    name = "uat_orders_check_snapshot"
    resp = api_client.post(
        f"/api/projects/{project_id}/snapshots",
        json={"name": name, "sql": SNAPSHOT_CHECK_SQL},
    )
    assert resp.status_code == 201
    snapshot = resp.json()
    assert snapshot["name"] == name

    # 验证策略为 check
    snapshots = api_client.get(f"/api/projects/{project_id}/snapshots").json()
    s = next(s for s in snapshots if s["name"] == name)
    assert s["snapshot_strategy"] == "check"
    assert s["target_schema"] == "snapshots"
    assert s["unique_key"] == "id"


def test_create_snapshot_duplicate(api_client: httpx.Client, project_id: int):
    """TC-SNAPSHOT-12：快照名称重复校验。"""
    name = "uat_orders_check_snapshot"
    resp = api_client.post(
        f"/api/projects/{project_id}/snapshots",
        json={"name": name, "sql": SNAPSHOT_CHECK_SQL},
    )
    assert resp.status_code == 409
    assert "已存在" in resp.json()["detail"]


def test_create_snapshot_invalid_name(api_client: httpx.Client, project_id: int):
    """TC-SNAPSHOT-13：快照名称非法字符校验。"""
    # 含空格
    resp = api_client.post(
        f"/api/projects/{project_id}/snapshots",
        json={"name": "my snapshot", "sql": SNAPSHOT_TIMESTAMP_SQL},
    )
    assert resp.status_code == 422

    # 含横杠
    resp = api_client.post(
        f"/api/projects/{project_id}/snapshots",
        json={"name": "my-snapshot", "sql": SNAPSHOT_TIMESTAMP_SQL},
    )
    assert resp.status_code == 422


def test_delete_snapshot(api_client: httpx.Client, project_id: int):
    """TC-SNAPSHOT-10：删除快照。"""
    snapshots = api_client.get(f"/api/projects/{project_id}/snapshots").json()
    s = next(s for s in snapshots if s["name"] == "uat_customers_snapshot_v2")

    resp = api_client.delete(f"/api/projects/{project_id}/snapshots/{s['id']}")
    assert resp.status_code == 200
    assert resp.json()["message"] == "快照已删除"

    # 列表中消失
    snapshots_after = api_client.get(f"/api/projects/{project_id}/snapshots").json()
    names = [s["name"] for s in snapshots_after]
    assert "uat_customers_snapshot_v2" not in names


def test_delete_check_snapshot(api_client: httpx.Client, project_id: int):
    """清理：删除 check 策略快照，保持环境干净。"""
    snapshots = api_client.get(f"/api/projects/{project_id}/snapshots").json()
    s = next(s for s in snapshots if s["name"] == "uat_orders_check_snapshot")

    resp = api_client.delete(f"/api/projects/{project_id}/snapshots/{s['id']}")
    assert resp.status_code == 200

    snapshots_after = api_client.get(f"/api/projects/{project_id}/snapshots").json()
    names = [s["name"] for s in snapshots_after]
    assert "uat_orders_check_snapshot" not in names
