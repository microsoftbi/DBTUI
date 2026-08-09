"""TC-DAG — DAG 数据自动化测试。"""
from __future__ import annotations

import httpx


def test_dag_nodes_and_edges(api_client: httpx.Client, project_id: int):
    """TC-DAG-01：节点与边数量正确。"""
    resp = api_client.get(f"/api/projects/{project_id}/dag")
    assert resp.status_code == 200
    dag = resp.json()
    assert "nodes" in dag and "edges" in dag
    assert len(dag["nodes"]) >= 2  # 至少 1 model + 1 test
    assert len(dag["edges"]) >= 1  # 至少一条边


def test_dag_node_types(api_client: httpx.Client, project_id: int):
    """TC-DAG-02：节点类型（model / test）正确。"""
    dag = api_client.get(f"/api/projects/{project_id}/dag").json()
    types = {n["type"] for n in dag["nodes"]}
    assert "model" in types
    assert "test" in types


def test_dag_example_has_test_edge(api_client: httpx.Client, project_id: int):
    """example 模型 → not_null 测试的边存在。"""
    dag = api_client.get(f"/api/projects/{project_id}/dag").json()
    node_map = {n["id"]: n for n in dag["nodes"]}
    model_ids = [nid for nid, n in node_map.items() if n["type"] == "model"]
    test_ids = [nid for nid, n in node_map.items() if n["type"] == "test"]
    # 至少有一条 model → test 的边
    assert any(
        e["source"] in model_ids and e["target"] in test_ids
        for e in dag["edges"]
    )
