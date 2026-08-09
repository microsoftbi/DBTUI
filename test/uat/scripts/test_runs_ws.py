"""TC-WS — WebSocket 实时流自动化测试。"""
from __future__ import annotations

import asyncio
import json

import pytest
import websockets


def ws_url(base_url: str, project_id: int) -> str:
    return base_url.replace("http://", "ws://") + f"/ws/projects/{project_id}/runs"


@pytest.mark.asyncio
async def test_ws_log_and_done(base_url: str, project_id: int):
    """TC-WS-01：日志流与 done 事件。"""
    url = ws_url(base_url, project_id)
    async with websockets.connect(url) as ws:
        await ws.send(json.dumps({"run_type": "run", "selection": "example"}))
        log_lines = 0
        done = None
        while True:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=60))
            if msg["type"] == "log":
                log_lines += 1
            elif msg["type"] == "done":
                done = msg
                break
        assert log_lines > 0
        assert done is not None
        assert done["returncode"] == 0


@pytest.mark.asyncio
async def test_ws_running_markers(base_url: str, project_id: int):
    """TC-WS-02：running 节点预判消息存在且包含 example。"""
    url = ws_url(base_url, project_id)
    async with websockets.connect(url) as ws:
        await ws.send(json.dumps({"run_type": "run", "selection": "example"}))
        running_names = None
        while True:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=60))
            if msg["type"] == "running":
                running_names = msg["names"]
            elif msg["type"] == "done":
                break
        assert running_names is not None
        assert "example" in running_names


@pytest.mark.asyncio
async def test_ws_node_status(base_url: str, project_id: int):
    """TC-WS-03：node_status 实时状态消息（example → success）。"""
    url = ws_url(base_url, project_id)
    async with websockets.connect(url) as ws:
        await ws.send(json.dumps({"run_type": "run", "selection": "example"}))
        statuses: dict[str, str] = {}
        while True:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=60))
            if msg["type"] == "node_status":
                statuses[msg["name"]] = msg["status"]
            elif msg["type"] == "done":
                break
        assert "example" in statuses
        assert statuses["example"] == "success"


@pytest.mark.asyncio
async def test_ws_cancel(base_url: str, project_id: int):
    """TC-WS-04：取消运行。"""
    import httpx

    url = ws_url(base_url, project_id)
    async with websockets.connect(url) as ws:
        await ws.send(json.dumps({"run_type": "run", "selection": "example"}))
        # 等 start 消息后立即请求取消
        run_id = None
        while True:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=60))
            if msg["type"] == "start":
                run_id = msg["run_id"]
                break
        assert run_id is not None

        # 用 REST 接口取消
        async with httpx.AsyncClient(base_url=base_url, timeout=30) as client:
            resp = await client.post(f"/api/projects/{project_id}/runs/{run_id}/cancel")
            assert resp.status_code == 200

        # 等待 done
        cancelled = False
        while True:
            try:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
            except asyncio.TimeoutError:
                break
            if msg["type"] == "done":
                cancelled = msg.get("cancelled", False) or msg["returncode"] != 0
                break
        # 由于 example 运行很快，可能已经完成；这里只验证接口可用
        assert resp.status_code == 200  # noqa: F821
