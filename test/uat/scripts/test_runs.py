"""TC-RUN — 同步运行与历史自动化测试。"""
from __future__ import annotations

import httpx


def test_run_model_success(api_client: httpx.Client, project_id: int):
    """TC-RUN-01：同步运行模型成功。"""
    resp = api_client.post(
        f"/api/projects/{project_id}/runs",
        json={"run_type": "run", "selection": "example"},
    )
    assert resp.status_code == 202
    run = resp.json()
    assert run["run_type"] == "run"
    assert run["selection"] == "example"
    assert run["status"] == "success"
    assert run["finished_at"] is not None


def test_run_history_and_log(api_client: httpx.Client, project_id: int):
    """TC-RUN-02：运行历史与日志查看。"""
    history = api_client.get(f"/api/projects/{project_id}/runs").json()
    assert len(history) >= 1
    run_id = history[0]["id"]

    detail = api_client.get(f"/api/projects/{project_id}/runs/{run_id}")
    assert detail.status_code == 200
    data = detail.json()
    assert "run" in data
    assert "results" in data
    assert "log" in data
    assert len(data["log"]) > 0  # 日志非空


def test_run_test(api_client: httpx.Client, project_id: int):
    """运行测试成功。"""
    resp = api_client.post(
        f"/api/projects/{project_id}/runs",
        json={"run_type": "test", "selection": "example"},
    )
    assert resp.status_code == 202
    assert resp.json()["status"] in ("success", "pass")
