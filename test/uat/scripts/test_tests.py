"""TC-TEST — 测试管理自动化测试。"""
from __future__ import annotations

import httpx


def test_list_tests(api_client: httpx.Client, project_id: int):
    """TC-TEST-01：generic 与 singular 测试列表。"""
    resp = api_client.get(f"/api/projects/{project_id}/tests")
    assert resp.status_code == 200
    tests = resp.json()
    # 至少有一个 generic test（来自 schema.yml 的 not_null）
    generic = [t for t in tests if t["type"] == "generic"]
    assert len(generic) >= 1


def test_create_singular_test(api_client: httpx.Client, project_id: int):
    """TC-TEST-02：新建 singular test。"""
    name = "uat_assert_positive"
    sql = "SELECT * FROM {{ ref('example') }} WHERE id < 0\n"
    resp = api_client.post(
        f"/api/projects/{project_id}/tests",
        json={"name": name, "sql": sql},
    )
    assert resp.status_code == 201
    test = resp.json()
    assert test["name"] == name
    assert test["type"] == "singular"

    # 列表中存在
    tests = api_client.get(f"/api/projects/{project_id}/tests").json()
    assert any(t["name"] == name for t in tests)


def test_delete_singular_test(api_client: httpx.Client, project_id: int):
    """TC-TEST-03：删除 singular test。"""
    tests = api_client.get(f"/api/projects/{project_id}/tests").json()
    t = next(t for t in tests if t["name"] == "uat_assert_positive")

    resp = api_client.delete(f"/api/projects/{project_id}/tests/{t['id']}")
    assert resp.status_code == 200

    tests_after = api_client.get(f"/api/projects/{project_id}/tests").json()
    assert not any(x["name"] == "uat_assert_positive" for x in tests_after)
