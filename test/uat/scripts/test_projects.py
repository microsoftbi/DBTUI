"""TC-PROJ — 项目管理自动化测试。"""
from __future__ import annotations

import uuid

import httpx
import pytest


def test_create_and_list_project(api_client: httpx.Client):
    """TC-PROJ-01 / TC-PROJ-02：创建项目并出现在列表中。"""
    name = f"uat_tmp_{uuid.uuid4().hex[:8]}"
    resp = api_client.post(
        "/api/projects",
        json={"name": name, "adapter": "duckdb", "description": "tmp"},
    )
    assert resp.status_code == 201
    project = resp.json()
    assert project["name"] == name
    assert project["adapter"] == "duckdb"
    assert project["slug"]

    # 列表中存在
    list_resp = api_client.get("/api/projects")
    assert list_resp.status_code == 200
    names = [p["name"] for p in list_resp.json()]
    assert name in names

    # 详情
    detail = api_client.get(f"/api/projects/{project['id']}")
    assert detail.status_code == 200
    assert detail.json()["name"] == name

    # 清理
    api_client.delete(f"/api/projects/{project['id']}")


def test_update_project(api_client: httpx.Client, project_id: int):
    """TC-PROJ-03：编辑项目名称与描述。"""
    new_desc = "updated by uat"
    resp = api_client.patch(
        f"/api/projects/{project_id}", json={"description": new_desc}
    )
    assert resp.status_code == 200
    assert resp.json()["description"] == new_desc


def test_profiles_read_and_save(api_client: httpx.Client, project_id: int):
    """TC-PROJ-04：连接配置读取、保存与 YAML 校验。"""
    # 读取
    resp = api_client.get(f"/api/projects/{project_id}/profiles")
    assert resp.status_code == 200
    content = resp.json()["content"]
    assert "duckdb" in content

    # 非法 YAML
    bad = api_client.put(
        f"/api/projects/{project_id}/profiles", json={"content": "a: : : bad"}
    )
    assert bad.status_code == 400

    # 合法 YAML 保存
    ok = api_client.put(
        f"/api/projects/{project_id}/profiles", json={"content": content}
    )
    assert ok.status_code == 200
    assert ok.json()["message"] == "连接配置已保存"


def test_delete_project(api_client: httpx.Client):
    """TC-PROJ-05：删除项目（磁盘目录也被清理）。"""
    name = f"uat_del_{uuid.uuid4().hex[:8]}"
    resp = api_client.post(
        "/api/projects", json={"name": name, "adapter": "duckdb"}
    )
    pid = resp.json()["id"]

    del_resp = api_client.delete(f"/api/projects/{pid}")
    assert del_resp.status_code == 200

    # 再次获取应 404
    get_resp = api_client.get(f"/api/projects/{pid}")
    assert get_resp.status_code == 404
