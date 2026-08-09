"""pytest 配置与公共 fixtures。

运行前请确保后端已启动在 http://localhost:8000。
"""
from __future__ import annotations

import os
import uuid

import httpx
import pytest

BASE_URL = os.environ.get("DBT_UI_BASE_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def api_client() -> httpx.Client:
    """同步 HTTP 客户端。"""
    with httpx.Client(base_url=BASE_URL, timeout=60) as client:
        yield client


@pytest.fixture(scope="session")
def uat_project(api_client: httpx.Client) -> dict:
    """创建一个 UAT 专用的 duckdb 项目，测试结束后删除。"""
    name = f"uat_demo_{uuid.uuid4().hex[:8]}"
    resp = api_client.post(
        "/api/projects",
        json={"name": name, "adapter": "duckdb", "description": "UAT test project"},
    )
    assert resp.status_code == 201, f"创建项目失败: {resp.text}"
    project = resp.json()

    # 先 parse 一次，保证后续用例有 DAG / models / tests 数据
    resp = api_client.post(f"/api/projects/{project['id']}/parse")
    assert resp.status_code == 200, f"parse 失败: {resp.text}"

    yield project

    # 清理
    api_client.delete(f"/api/projects/{project['id']}")


@pytest.fixture(scope="session")
def project_id(uat_project: dict) -> int:
    return uat_project["id"]


@pytest.fixture(scope="session")
def base_url() -> str:
    return BASE_URL
