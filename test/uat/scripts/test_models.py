"""TC-MODEL — 模型管理自动化测试。"""
from __future__ import annotations

import httpx


def test_list_models(api_client: httpx.Client, project_id: int):
    """TC-MODEL-01：parse 后模型列表正确。"""
    resp = api_client.get(f"/api/projects/{project_id}/models")
    assert resp.status_code == 200
    models = resp.json()
    assert len(models) >= 1
    names = [m["name"] for m in models]
    assert "example" in names
    example = next(m for m in models if m["name"] == "example")
    assert example["resource_type"] == "model"
    assert example["materialized"] in ("view", "table")


def test_create_model(api_client: httpx.Client, project_id: int):
    """TC-MODEL-02：新建模型并重新解析。"""
    name = "uat_orders"
    sql = "SELECT 42 AS order_id\n"
    resp = api_client.post(
        f"/api/projects/{project_id}/models",
        json={"name": name, "sql": sql},
    )
    assert resp.status_code == 201
    model = resp.json()
    assert model["name"] == name

    # 列表中存在
    models = api_client.get(f"/api/projects/{project_id}/models").json()
    assert any(m["name"] == name for m in models)


def test_update_materialized(api_client: httpx.Client, project_id: int):
    """TC-MODEL-03：修改物化策略（view → table）。"""
    models = api_client.get(f"/api/projects/{project_id}/models").json()
    m = next(m for m in models if m["name"] == "uat_orders")

    resp = api_client.put(
        f"/api/projects/{project_id}/models/{m['id']}",
        json={"materialized": "table"},
    )
    assert resp.status_code == 200
    assert resp.json()["materialized"] == "table"


def test_delete_model(api_client: httpx.Client, project_id: int):
    """TC-MODEL-04：删除模型。"""
    models = api_client.get(f"/api/projects/{project_id}/models").json()
    m = next(m for m in models if m["name"] == "uat_orders")

    resp = api_client.delete(f"/api/projects/{project_id}/models/{m['id']}")
    assert resp.status_code == 200

    models_after = api_client.get(f"/api/projects/{project_id}/models").json()
    assert not any(x["name"] == "uat_orders" for x in models_after)
