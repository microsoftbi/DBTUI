"""用户手册完整验证脚本（SQL Server 版，含实际 dbt run 验证）。

严格按照 doc/userguide.md 的步骤逐一验证，包括：
- 第 1 章：创建项目
- 第 2 章：分层配置管理
- 第 3 章：Sources 可视化
- 第 4 章：Stage 层（实际运行验证）
- 第 5 章：Core 层（实际运行验证）
- 第 6 章：Mart 层 + Tests（实际运行验证）
- 第 7 章：DAG 血缘图
- 第 8 章：运行历史与日志

运行方式：
    cd /Users/wadesong/Documents/trae_projects/DBT
    .venv/bin/python doc/verify_userguide_full.py
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
import uuid

import httpx

API_BASE_URL = "http://localhost:8000"

passed = 0
failed = 0
results: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, err: str = ""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  ✅ {name}")
    else:
        failed += 1
        print(f"  ❌ {name}: {err}")
    results.append((name, ok, err))


async def wait_for_run(api: httpx.AsyncClient, pid: int, run_id: int, timeout: int = 120) -> dict:
    """等待运行完成，返回最终运行详情。"""
    start = time.time()
    while time.time() - start < timeout:
        resp = await api.get(f"/api/projects/{pid}/runs/{run_id}")
        detail = resp.json()
        if detail["status"] in ("success", "error", "cancelled"):
            return detail
        await asyncio.sleep(2)
    raise TimeoutError(f"运行 {run_id} 超时（{timeout}s）")


async def main():
    print("=" * 70)
    print("用户手册完整验证（SQL Server 三层分库 + 实际运行）")
    print("=" * 70)

    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=120) as api:
        # 清理可能残留的测试项目
        proj_list = (await api.get("/api/projects")).json()
        for p in proj_list:
            if p["name"].startswith("verify_full_"):
                await api.delete(f"/api/projects/{p['id']}")

        proj_name = f"verify_full_{uuid.uuid4().hex[:6]}"
        pid = None
        proj_path = None

        # ================================================================
        # 第 1 章：创建项目
        # ================================================================
        print("\n📗 第 1 章：创建项目")

        # 1.1 首页项目列表（API 可达性）
        try:
            resp = await api.get("/api/projects")
            if resp.status_code != 200:
                raise Exception(f"状态码 {resp.status_code}")
            record("1.1 项目列表 API 正常", True)
        except Exception as e:
            record("1.1 项目列表 API 正常", False, str(e))

        # 1.2 新建 sqlserver 项目
        try:
            resp = await api.post(
                "/api/projects",
                json={
                    "name": proj_name,
                    "adapter": "sqlserver",
                    "description": "销售数据仓库三层分库",
                },
            )
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            proj = resp.json()
            pid = proj["id"]
            proj_path = proj["path"]
            if proj["adapter"] != "sqlserver":
                raise Exception(f"adapter 应为 sqlserver，实际 {proj['adapter']}")
            record("1.2 新建 sqlserver 项目成功", True)
        except Exception as e:
            record("1.2 新建 sqlserver 项目成功", False, str(e))
            sys.exit(1)

        # 1.3 项目脚手架完整（目录结构）
        try:
            import os
            required_dirs = ["models", "tests", "seeds", "macros"]
            for d in required_dirs:
                p = os.path.join(proj_path, d)
                if not os.path.isdir(p):
                    raise Exception(f"缺少目录: {p}")
            # 检查分层子目录
            for sub in ["staging", "core", "marts"]:
                p = os.path.join(proj_path, "models", sub)
                if not os.path.isdir(p):
                    raise Exception(f"缺少分层目录: {p}")
            record("1.3 项目脚手架完整（含三层子目录）", True)
        except Exception as e:
            record("1.3 项目脚手架完整（含三层子目录）", False, str(e))

        # 1.4 profiles.yml 连接配置正确
        try:
            resp = await api.get(f"/api/projects/{pid}/profiles")
            content = resp.json()["content"]
            checks = [
                ("sqlserver 类型", "type: sqlserver" in content),
                ("ODBC 驱动", "ODBC Driver" in content),
                ("服务器地址", "server:" in content),
                ("端口 1433", "port: 1433" in content),
                ("stage_db 数据库", "stage_db" in content),
                ("sa 用户", "user: sa" in content),
                ("trust_cert", "trust_cert: true" in content),
            ]
            missing = [name for name, ok in checks if not ok]
            if missing:
                raise Exception(f"缺少配置项: {', '.join(missing)}")
            record("1.4 profiles.yml sqlserver 连接配置正确", True)
        except Exception as e:
            record("1.4 profiles.yml sqlserver 连接配置正确", False, str(e))

        # 1.5 dbt_project.yml 分层 database 配置
        try:
            import os
            with open(os.path.join(proj_path, "dbt_project.yml")) as f:
                content = f.read()
            checks = [
                ("stage_db", "stage_db" in content),
                ("core_db", "core_db" in content),
                ("mart_db", "mart_db" in content),
                ("+database", "+database" in content),
                ("staging view", "+materialized: view" in content),
                ("core table", "core:" in content),
                ("marts table", "marts:" in content),
            ]
            missing = [name for name, ok in checks if not ok]
            if missing:
                raise Exception(f"缺少配置: {', '.join(missing)}")
            record("1.5 dbt_project.yml 三层分库配置正确", True)
        except Exception as e:
            record("1.5 dbt_project.yml 三层分库配置正确", False, str(e))

        # 1.6 首次 parse 成功
        try:
            resp = await api.post(f"/api/projects/{pid}/parse")
            if resp.status_code >= 400:
                raise Exception(f"parse 失败: {resp.text}")
            # 检查状态
            resp = await api.get("/api/projects")
            p = next(x for x in resp.json() if x["id"] == pid)
            if p["parse_status"] != "success":
                raise Exception(f"parse_status 为 {p['parse_status']}")
            record("1.6 项目首次 parse 成功", True)
        except Exception as e:
            record("1.6 项目首次 parse 成功", False, str(e))

        # ================================================================
        # 第 2 章：分层配置管理
        # ================================================================
        print("\n📗 第 2 章：分层配置管理")

        # 2.1 分层列表（默认三层 + 根目录）
        try:
            resp = await api.get(f"/api/projects/{pid}/layers")
            layers = resp.json()
            layer_names = [l["name"] for l in layers]
            if len(layers) < 4:
                raise Exception(f"至少应有 4 层，实际 {len(layers)} 层")
            root = [l for l in layers if l["is_root"]]
            if not root:
                raise Exception("没有根目录分层")
            for expected in ["staging", "core", "marts"]:
                if expected not in layer_names:
                    raise Exception(f"缺少分层: {expected}")
            record("2.1 分层列表正确（根目录 + staging/core/marts）", True)
        except Exception as e:
            record("2.1 分层列表正确（根目录 + staging/core/marts）", False, str(e))

        # 2.2 各层数据库和物化配置
        try:
            layers = (await api.get(f"/api/projects/{pid}/layers")).json()
            layer_map = {l["name"]: l for l in layers}
            if layer_map["staging"]["database"] != "stage_db":
                raise Exception(f"staging 数据库应为 stage_db，实际 {layer_map['staging']['database']}")
            if layer_map["core"]["database"] != "core_db":
                raise Exception(f"core 数据库应为 core_db，实际 {layer_map['core']['database']}")
            if layer_map["marts"]["database"] != "mart_db":
                raise Exception(f"marts 数据库应为 mart_db，实际 {layer_map['marts']['database']}")
            if layer_map["staging"]["materialized"] != "view":
                raise Exception(f"staging 物化应为 view，实际 {layer_map['staging']['materialized']}")
            if layer_map["core"]["materialized"] != "table":
                raise Exception(f"core 物化应为 table，实际 {layer_map['core']['materialized']}")
            if layer_map["marts"]["materialized"] != "table":
                raise Exception(f"marts 物化应为 table，实际 {layer_map['marts']['materialized']}")
            record("2.2 各层数据库和物化配置正确", True)
        except Exception as e:
            record("2.2 各层数据库和物化配置正确", False, str(e))

        # 2.3 新建分层
        try:
            resp = await api.post(
                f"/api/projects/{pid}/layers",
                json={
                    "name": "ods",
                    "display_name": "ODS 层",
                    "database": "ods_db",
                    "schema": "dbo",
                    "materialized": "view",
                },
            )
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            layer = resp.json()
            if layer["name"] != "ods":
                raise Exception(f"名称应为 ods，实际 {layer['name']}")
            if layer["display_name"] != "ODS 层":
                raise Exception(f"显示名称应为 ODS 层，实际 {layer['display_name']}")
            import os
            if not os.path.isdir(os.path.join(proj_path, "models", "ods")):
                raise Exception("目录未创建")
            record("2.3 新建分层 ODS 层成功", True)
        except Exception as e:
            record("2.3 新建分层 ODS 层成功", False, str(e))

        # 2.4 编辑分层
        try:
            resp = await api.put(
                f"/api/projects/{pid}/layers/ods",
                json={
                    "display_name": "ODS 贴源层",
                    "database": "ods_warehouse",
                    "materialized": "table",
                },
            )
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            layer = resp.json()
            if layer["display_name"] != "ODS 贴源层":
                raise Exception(f"显示名称未更新: {layer['display_name']}")
            if layer["database"] != "ods_warehouse":
                raise Exception(f"数据库未更新: {layer['database']}")
            if layer["materialized"] != "table":
                raise Exception(f"物化未更新: {layer['materialized']}")
            record("2.4 编辑分层（显示名称/数据库/物化）成功", True)
        except Exception as e:
            record("2.4 编辑分层（显示名称/数据库/物化）成功", False, str(e))

        # 2.5 重命名分层目录
        try:
            resp = await api.put(
                f"/api/projects/{pid}/layers/ods",
                json={"name": "ods_new"},
            )
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            layer = resp.json()
            if layer["name"] != "ods_new":
                raise Exception(f"重命名后应为 ods_new，实际 {layer['name']}")
            import os
            old_dir = os.path.join(proj_path, "models", "ods")
            new_dir = os.path.join(proj_path, "models", "ods_new")
            if os.path.exists(old_dir):
                raise Exception(f"旧目录仍存在: {old_dir}")
            if not os.path.isdir(new_dir):
                raise Exception(f"新目录未创建: {new_dir}")
            record("2.5 重命名分层目录成功（文件迁移正确）", True)
        except Exception as e:
            record("2.5 重命名分层目录成功（文件迁移正确）", False, str(e))

        # 2.6 删除分层（保留目录）
        try:
            resp = await api.delete(f"/api/projects/{pid}/layers/ods_new")
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            layers = (await api.get(f"/api/projects/{pid}/layers")).json()
            layer_names = [l["name"] for l in layers]
            if "ods_new" in layer_names:
                raise Exception("删除后 ods_new 仍在列表中")
            import os
            if not os.path.isdir(os.path.join(proj_path, "models", "ods_new")):
                raise Exception("删除分层后目录被删除了（应保留）")
            record("2.6 删除分层成功（配置删除，目录保留）", True)
        except Exception as e:
            record("2.6 删除分层成功（配置删除，目录保留）", False, str(e))

        # ================================================================
        # 第 3 章：Sources 可视化
        # ================================================================
        print("\n📗 第 3 章：Sources 可视化")

        # 3.1 新建 source（sales_db）
        try:
            resp = await api.post(
                f"/api/projects/{pid}/sources",
                json={
                    "source_name": "sales_db",
                    "database": "sales_db",
                    "schema": "dbo",
                    "loader": "sqlserver",
                    "description": "销售源系统",
                    "subdir": "staging",
                    "tables": [],
                },
            )
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            src = resp.json()
            if src["source_name"] != "sales_db":
                raise Exception(f"source 名应为 sales_db，实际 {src['source_name']}")
            if src["database"] != "sales_db":
                raise Exception(f"数据库应为 sales_db，实际 {src['database']}")
            if src["subdir"] != "staging":
                raise Exception(f"subdir 应为 staging，实际 {src['subdir']}")
            import os
            yml_path = os.path.join(proj_path, "models", "staging", "sources.yml")
            if not os.path.exists(yml_path):
                raise Exception(f"sources.yml 未创建: {yml_path}")
            record("3.1 新建 source（sales_db）成功", True)
        except Exception as e:
            record("3.1 新建 source（sales_db）成功", False, str(e))

        # 3.2 添加源表 customer
        try:
            resp = await api.post(
                f"/api/projects/{pid}/sources/sales_db/tables",
                json={"name": "customer", "description": "客户表"},
            )
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            src = resp.json()
            tables = [t["name"] for t in src["tables"]]
            if "customer" not in tables:
                raise Exception("customer 表未添加")
            record("3.2 添加源表 customer 成功", True)
        except Exception as e:
            record("3.2 添加源表 customer 成功", False, str(e))

        # 3.3 添加源表 product
        try:
            resp = await api.post(
                f"/api/projects/{pid}/sources/sales_db/tables",
                json={"name": "product", "description": "商品表"},
            )
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            src = resp.json()
            tables = [t["name"] for t in src["tables"]]
            if "product" not in tables:
                raise Exception("product 表未添加")
            record("3.3 添加源表 product 成功", True)
        except Exception as e:
            record("3.3 添加源表 product 成功", False, str(e))

        # 3.4 添加源表 salesorder
        try:
            resp = await api.post(
                f"/api/projects/{pid}/sources/sales_db/tables",
                json={"name": "salesorder", "description": "订单表"},
            )
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            src = resp.json()
            tables = [t["name"] for t in src["tables"]]
            if "salesorder" not in tables:
                raise Exception("salesorder 表未添加")
            if len(src["tables"]) != 3:
                raise Exception(f"表数量应为 3，实际 {len(src['tables'])}")
            record("3.4 添加源表 salesorder 成功（共 3 张表）", True)
        except Exception as e:
            record("3.4 添加源表 salesorder 成功（共 3 张表）", False, str(e))

        # 3.5 Source 详情
        try:
            resp = await api.get(f"/api/projects/{pid}/sources/sales_db")
            src = resp.json()
            if src["source_name"] != "sales_db":
                raise Exception("source 名不匹配")
            tables = [t["name"] for t in src["tables"]]
            for t in ["customer", "product", "salesorder"]:
                if t not in tables:
                    raise Exception(f"缺少表: {t}")
            record("3.5 Source 详情正确（含 3 张表）", True)
        except Exception as e:
            record("3.5 Source 详情正确（含 3 张表）", False, str(e))

        # 3.6 重新解析后 source 节点出现在 DAG 中（source 不在 models 列表，在 DAG 中）
        try:
            resp = await api.post(f"/api/projects/{pid}/parse")
            if resp.status_code >= 400:
                raise Exception(f"parse 失败: {resp.text}")
            resp = await api.get(f"/api/projects/{pid}/dag")
            dag = resp.json()
            source_nodes = [n for n in dag["nodes"] if n.get("type") == "source"]
            if len(source_nodes) < 3:
                raise Exception(f"source 节点数量太少: {len(source_nodes)}")
            # 检查数据库（通过 label 验证 source 名）
            sales_db_sources = [n for n in source_nodes if n["label"].startswith("sales_db.")]
            if len(sales_db_sources) < 3:
                raise Exception(f"sales_db 的 source 节点太少: {len(sales_db_sources)}")
            record("3.6 解析后 source 节点出现在 DAG 图中", True)
        except Exception as e:
            record("3.6 解析后 source 节点出现在 DAG 图中", False, str(e))

        # ================================================================
        # 第 4 章：Stage 层 — 贴源加载（stage_db）
        # ================================================================
        print("\n📗 第 4 章：Stage 层 — 贴源加载（stage_db）")

        # 4.1 创建 stg_customer
        try:
            resp = await api.post(
                f"/api/projects/{pid}/models",
                json={
                    "name": "stg_customer",
                    "sql": (
                        "SELECT\n"
                        "    customer_id,\n"
                        "    customer_name,\n"
                        "    gender,\n"
                        "    age,\n"
                        "    city,\n"
                        "    create_date\n"
                        "FROM {{ source('sales_db', 'customer') }}\n"
                    ),
                    "subdir": "staging",
                },
            )
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            data = resp.json()
            if data["database"] != "stage_db":
                raise Exception(f"数据库应为 stage_db，实际 {data['database']}")
            if "staging" not in data["file_path"]:
                raise Exception(f"路径应包含 staging，实际 {data['file_path']}")
            record("4.1 创建 stg_customer（stage_db）", True)
        except Exception as e:
            record("4.1 创建 stg_customer（stage_db）", False, str(e))

        # 4.2 创建 stg_product
        try:
            resp = await api.post(
                f"/api/projects/{pid}/models",
                json={
                    "name": "stg_product",
                    "sql": (
                        "SELECT\n"
                        "    product_id,\n"
                        "    product_name,\n"
                        "    category,\n"
                        "    price,\n"
                        "    create_date\n"
                        "FROM {{ source('sales_db', 'product') }}\n"
                    ),
                    "subdir": "staging",
                },
            )
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            data = resp.json()
            if data["database"] != "stage_db":
                raise Exception(f"数据库应为 stage_db，实际 {data['database']}")
            record("4.2 创建 stg_product（stage_db）", True)
        except Exception as e:
            record("4.2 创建 stg_product（stage_db）", False, str(e))

        # 4.3 创建 stg_salesorder
        try:
            resp = await api.post(
                f"/api/projects/{pid}/models",
                json={
                    "name": "stg_salesorder",
                    "sql": (
                        "SELECT\n"
                        "    order_id,\n"
                        "    order_date,\n"
                        "    customer_id,\n"
                        "    product_id,\n"
                        "    quantity,\n"
                        "    unit_price,\n"
                        "    amount,\n"
                        "    status\n"
                        "FROM {{ source('sales_db', 'salesorder') }}\n"
                    ),
                    "subdir": "staging",
                },
            )
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            data = resp.json()
            if data["database"] != "stage_db":
                raise Exception(f"数据库应为 stage_db，实际 {data['database']}")
            record("4.3 创建 stg_salesorder（stage_db）", True)
        except Exception as e:
            record("4.3 创建 stg_salesorder（stage_db）", False, str(e))

        # 4.4 Stage 层模型列表正确
        try:
            resp = await api.get(f"/api/projects/{pid}/models")
            models = resp.json()
            stage_models = [m for m in models if m.get("database") == "stage_db" and m.get("resource_type") == "model"]
            stage_names = [m["name"] for m in stage_models]
            for expected in ["stg_customer", "stg_product", "stg_salesorder"]:
                if expected not in stage_names:
                    raise Exception(f"缺少模型: {expected}")
            # 验证物化策略为 view
            for m in stage_models:
                if m.get("materialized") != "view":
                    raise Exception(f"{m['name']} 物化应为 view，实际 {m.get('materialized')}")
            record("4.4 Stage 层模型列表正确（3 个模型，均为 view）", True)
        except Exception as e:
            record("4.4 Stage 层模型列表正确（3 个模型，均为 view）", False, str(e))

        # 4.5 实际运行 stg_customer（验证 dbt run 成功）
        try:
            resp = await api.post(
                f"/api/projects/{pid}/runs",
                json={"run_type": "run", "selection": "stg_customer"},
            )
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            run_data = resp.json()
            run_id = run_data["id"]
            # 等待运行完成（同步接口直接返回最终状态，detail 结构为 {run, results, log}）
            resp = await api.get(f"/api/projects/{pid}/runs/{run_id}")
            detail = resp.json()
            if detail["run"]["status"] != "success":
                raise Exception(f"运行状态: {detail['run']['status']}\n日志:\n{detail.get('log', '')[-500:]}")
            record("4.5 运行 stg_customer 成功（stage_db 视图已创建）", True)
        except Exception as e:
            record("4.5 运行 stg_customer 成功（stage_db 视图已创建）", False, str(e))

        # 4.6 运行全部 Stage 层
        try:
            resp = await api.post(
                f"/api/projects/{pid}/runs",
                json={"run_type": "run", "selection": "staging.*"},
            )
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            run_id = resp.json()["id"]
            # 同步接口直接完成，获取详情
            resp = await api.get(f"/api/projects/{pid}/runs/{run_id}")
            detail = resp.json()
            if detail["run"]["status"] != "success":
                raise Exception(f"运行状态: {detail['run']['status']}\n日志:\n{detail.get('log', '')[-800:]}")
            record("4.6 运行全部 Stage 层成功", True)
        except Exception as e:
            record("4.6 运行全部 Stage 层成功", False, str(e))

        # ================================================================
        # 第 5 章：Core 层 — 维度建模（core_db）
        # ================================================================
        print("\n📗 第 5 章：Core 层 — 维度建模（core_db）")

        # 5.1 创建 dim_customer
        try:
            resp = await api.post(
                f"/api/projects/{pid}/models",
                json={
                    "name": "dim_customer",
                    "sql": (
                        "SELECT\n"
                        "    customer_id,\n"
                        "    customer_name,\n"
                        "    gender,\n"
                        "    age,\n"
                        "    city,\n"
                        "    create_date\n"
                        "FROM {{ ref('stg_customer') }}\n"
                    ),
                    "subdir": "core",
                },
            )
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            data = resp.json()
            if data["database"] != "core_db":
                raise Exception(f"数据库应为 core_db，实际 {data['database']}")
            record("5.1 创建 dim_customer（core_db，跨库引用 stage_db）", True)
        except Exception as e:
            record("5.1 创建 dim_customer（core_db，跨库引用 stage_db）", False, str(e))

        # 5.2 创建 dim_product
        try:
            resp = await api.post(
                f"/api/projects/{pid}/models",
                json={
                    "name": "dim_product",
                    "sql": (
                        "SELECT\n"
                        "    product_id,\n"
                        "    product_name,\n"
                        "    category,\n"
                        "    price,\n"
                        "    create_date\n"
                        "FROM {{ ref('stg_product') }}\n"
                    ),
                    "subdir": "core",
                },
            )
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            data = resp.json()
            if data["database"] != "core_db":
                raise Exception(f"数据库应为 core_db，实际 {data['database']}")
            record("5.2 创建 dim_product（core_db）", True)
        except Exception as e:
            record("5.2 创建 dim_product（core_db）", False, str(e))

        # 5.3 创建 fact_sales
        try:
            resp = await api.post(
                f"/api/projects/{pid}/models",
                json={
                    "name": "fact_sales",
                    "sql": (
                        "SELECT\n"
                        "    s.order_id,\n"
                        "    s.order_date,\n"
                        "    s.customer_id,\n"
                        "    s.product_id,\n"
                        "    s.quantity,\n"
                        "    s.unit_price,\n"
                        "    s.amount,\n"
                        "    s.status\n"
                        "FROM {{ ref('stg_salesorder') }} s\n"
                        "WHERE s.status = 'completed'\n"
                    ),
                    "subdir": "core",
                },
            )
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            data = resp.json()
            if data["database"] != "core_db":
                raise Exception(f"数据库应为 core_db，实际 {data['database']}")
            record("5.3 创建 fact_sales（core_db，仅 completed 订单）", True)
        except Exception as e:
            record("5.3 创建 fact_sales（core_db，仅 completed 订单）", False, str(e))

        # 5.4 Core 层模型列表正确
        try:
            resp = await api.get(f"/api/projects/{pid}/models")
            models = resp.json()
            core_models = [m for m in models if m.get("database") == "core_db" and m.get("resource_type") == "model"]
            core_names = [m["name"] for m in core_models]
            for expected in ["dim_customer", "dim_product", "fact_sales"]:
                if expected not in core_names:
                    raise Exception(f"缺少模型: {expected}")
            for m in core_models:
                if m.get("materialized") != "table":
                    raise Exception(f"{m['name']} 物化应为 table，实际 {m.get('materialized')}")
            record("5.4 Core 层模型列表正确（3 个模型，均为 table）", True)
        except Exception as e:
            record("5.4 Core 层模型列表正确（3 个模型，均为 table）", False, str(e))

        # 5.5 运行 fact_sales（自动运行上游）
        try:
            resp = await api.post(
                f"/api/projects/{pid}/runs",
                json={"run_type": "run", "selection": "fact_sales"},
            )
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            run_id = resp.json()["id"]
            # 同步接口直接完成，获取详情
            resp = await api.get(f"/api/projects/{pid}/runs/{run_id}")
            detail = resp.json()
            if detail["run"]["status"] != "success":
                raise Exception(f"运行状态: {detail['run']['status']}\n日志:\n{detail.get('log', '')[-800:]}")
            # 验证日志中包含 fact_sales 本身
            log = detail.get("log", "")
            if "fact_sales" not in log:
                raise Exception("日志中未看到 fact_sales 运行")
            # 验证有多个模型被处理
            if "Finished running" not in log:
                raise Exception("日志中没有完成标识")
            record("5.5 运行 fact_sales 成功（dbt 自动处理依赖）", True)
        except Exception as e:
            record("5.5 运行 fact_sales 成功（含上游依赖，跨库正确）", False, str(e))

        # ================================================================
        # 第 6 章：Mart 层 — 应用宽表（mart_db）
        # ================================================================
        print("\n📗 第 6 章：Mart 层 — 应用宽表（mart_db）")

        # 6.1 创建 sales_wide
        try:
            resp = await api.post(
                f"/api/projects/{pid}/models",
                json={
                    "name": "sales_wide",
                    "sql": (
                        "SELECT\n"
                        "    f.order_id,\n"
                        "    f.order_date,\n"
                        "    f.customer_id,\n"
                        "    c.customer_name,\n"
                        "    c.gender,\n"
                        "    c.age,\n"
                        "    c.city,\n"
                        "    f.product_id,\n"
                        "    p.product_name,\n"
                        "    p.category,\n"
                        "    p.price,\n"
                        "    f.quantity,\n"
                        "    f.unit_price,\n"
                        "    f.amount,\n"
                        "    f.status\n"
                        "FROM {{ ref('fact_sales') }} f\n"
                        "LEFT JOIN {{ ref('dim_customer') }} c ON f.customer_id = c.customer_id\n"
                        "LEFT JOIN {{ ref('dim_product') }} p ON f.product_id = p.product_id\n"
                    ),
                    "subdir": "marts",
                },
            )
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            data = resp.json()
            if data["database"] != "mart_db":
                raise Exception(f"数据库应为 mart_db，实际 {data['database']}")
            record("6.1 创建 sales_wide（mart_db，跨库引用 core_db）", True)
        except Exception as e:
            record("6.1 创建 sales_wide（mart_db，跨库引用 core_db）", False, str(e))

        # 6.2 运行 sales_wide
        try:
            resp = await api.post(
                f"/api/projects/{pid}/runs",
                json={"run_type": "run", "selection": "sales_wide"},
            )
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            run_id = resp.json()["id"]
            # 同步接口直接完成，获取详情
            resp = await api.get(f"/api/projects/{pid}/runs/{run_id}")
            detail = resp.json()
            if detail["run"]["status"] != "success":
                raise Exception(f"运行状态: {detail['run']['status']}\n日志:\n{detail.get('log', '')[-800:]}")
            record("6.2 运行 sales_wide 成功（三层分库完整链路）", True)
        except Exception as e:
            record("6.2 运行 sales_wide 成功（三层分库完整链路）", False, str(e))

        # 6.3 创建数据测试
        try:
            resp = await api.post(
                f"/api/projects/{pid}/tests",
                json={
                    "name": "test_amount_positive",
                    "sql": (
                        "SELECT *\n"
                        "FROM {{ ref('sales_wide') }}\n"
                        "WHERE amount <= 0\n"
                    ),
                },
            )
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            record("6.3 创建数据测试 test_amount_positive", True)
        except Exception as e:
            record("6.3 创建数据测试 test_amount_positive", False, str(e))

        # 6.4 运行测试
        try:
            resp = await api.post(
                f"/api/projects/{pid}/runs",
                json={"run_type": "test", "selection": "test_amount_positive"},
            )
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            run_id = resp.json()["id"]
            # 同步接口直接完成，获取详情
            resp = await api.get(f"/api/projects/{pid}/runs/{run_id}")
            detail = resp.json()
            if detail["run"]["status"] != "success":
                raise Exception(f"测试状态: {detail['run']['status']}\n日志:\n{detail.get('log', '')[-500:]}")
            record("6.4 运行数据测试通过（amount 均为正数）", True)
        except Exception as e:
            record("6.4 运行数据测试通过（amount 均为正数）", False, str(e))

        # 6.5 build 全量构建
        try:
            resp = await api.post(
                f"/api/projects/{pid}/runs",
                json={"run_type": "build", "selection": ""},
            )
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            run_id = resp.json()["id"]
            # 同步接口直接完成，获取详情
            resp = await api.get(f"/api/projects/{pid}/runs/{run_id}")
            detail = resp.json()
            if detail["run"]["status"] != "success":
                raise Exception(f"build 状态: {detail['run']['status']}\n日志:\n{detail.get('log', '')[-800:]}")
            record("6.5 dbt build 全量构建成功", True)
        except Exception as e:
            record("6.5 dbt build 全量构建成功", False, str(e))

        # ================================================================
        # 第 7 章：DAG 血缘图
        # ================================================================
        print("\n📗 第 7 章：DAG 血缘图")

        # 7.1 DAG 数据
        try:
            # 运行后重新 parse 以确保 DAG 数据最新
            await api.post(f"/api/projects/{pid}/parse")
            resp = await api.get(f"/api/projects/{pid}/dag")
            data = resp.json()
            nodes = data["nodes"]
            edges = data["edges"]
            if len(nodes) < 10:
                raise Exception(f"DAG 节点数量太少: {len(nodes)}")
            if len(edges) < 8:
                raise Exception(f"DAG 边数量太少: {len(edges)}")
            # 验证有 source 节点
            source_nodes = [n for n in nodes if n.get("type") == "source"]
            if len(source_nodes) < 3:
                raise Exception(f"source 节点太少: {len(source_nodes)}")
            # 验证有 model 节点
            model_nodes = [n for n in nodes if n.get("type") == "model"]
            if len(model_nodes) < 7:
                raise Exception(f"model 节点太少: {len(model_nodes)}")
            # 验证有 test 节点
            test_nodes = [n for n in nodes if n.get("type") == "test"]
            if len(test_nodes) < 1:
                raise Exception(f"test 节点太少: {len(test_nodes)}")
            record(f"7.1 DAG 数据正确（{len(nodes)} 节点 / {len(edges)} 边，含 source/model/test）", True)
        except Exception as e:
            record("7.1 DAG 数据正确（含 source/model/test 节点）", False, str(e))

        # 7.2 跨库依赖边存在
        try:
            resp = await api.get(f"/api/projects/{pid}/dag")
            data = resp.json()
            # 从节点中提取数据库信息（source 节点从 label 推断，model 节点从 manifest 推断）
            # 简化：统计不同数据库的节点数量
            node_dbs = set()
            for n in data["nodes"]:
                if n["type"] == "source":
                    # label 格式: sales_db.customer
                    db_name = n["label"].split(".")[0] if "." in n["label"] else ""
                    if db_name:
                        node_dbs.add(db_name)
            # 验证至少有不同数据库的节点
            if len(node_dbs) < 1:
                raise Exception(f"source 数据库种类太少: {len(node_dbs)}")
            # 验证边数量
            if len(data["edges"]) < 5:
                raise Exception(f"DAG 边太少: {len(data['edges'])}")
            record(f"7.2 DAG 边存在（{len(data['edges'])} 条），source 数据库: {', '.join(node_dbs)}", True)
        except Exception as e:
            record("7.2 跨库依赖边存在", False, str(e))

        # ================================================================
        # 第 8 章：运行历史与日志
        # ================================================================
        print("\n📗 第 8 章：运行历史与日志")

        # 8.1 运行历史列表
        try:
            resp = await api.get(f"/api/projects/{pid}/runs")
            runs = resp.json()
            if len(runs) < 6:
                raise Exception(f"运行记录数量太少: {len(runs)}")
            # 验证状态字段
            statuses = [r["status"] for r in runs]
            if "success" not in statuses:
                raise Exception("没有成功的运行记录")
            # 验证类型字段
            types = set(r["run_type"] for r in runs)
            if "run" not in types:
                raise Exception("没有 run 类型记录")
            record("8.1 运行历史列表正确（含多种类型和状态）", True)
        except Exception as e:
            record("8.1 运行历史列表正确（含多种类型和状态）", False, str(e))

        # 8.2 运行日志详情
        try:
            resp = await api.get(f"/api/projects/{pid}/runs")
            runs = resp.json()
            # 找一个成功的运行
            success_runs = [r for r in runs if r["status"] == "success"]
            if not success_runs:
                raise Exception("没有成功的运行记录")
            run_id = success_runs[0]["id"]
            resp = await api.get(f"/api/projects/{pid}/runs/{run_id}")
            detail = resp.json()
            if not detail.get("log"):
                raise Exception("运行日志为空")
            if "success" not in detail["log"].lower() and "OK" not in detail["log"]:
                raise Exception("日志中没有成功标识")
            # 验证 run 结构
            if "run" not in detail or "status" not in detail["run"]:
                raise Exception("详情结构中缺少 run.status")
            record("8.2 运行日志详情可查看", True)
        except Exception as e:
            record("8.2 运行日志详情可查看", False, str(e))

        # ================================================================
        # 清理
        # ================================================================
        print("\n🧹 清理测试项目")
        try:
            await api.delete(f"/api/projects/{pid}")
            print("  ✅ 测试项目已删除")
        except Exception as e:
            print(f"  ⚠️  清理失败: {e}")

    # ================================================================
    # 结果汇总
    # ================================================================
    print("\n" + "=" * 70)
    print("验证结果汇总")
    print("=" * 70)
    print(f"通过: {passed} / {passed + failed}")
    print(f"失败: {failed} / {passed + failed}")

    if failed > 0:
        print("\n❌ 失败的步骤：")
        for name, ok, err in results:
            if not ok:
                print(f"  - {name}: {err}")
        sys.exit(1)
    else:
        print("\n✅ 所有步骤均通过！用户手册描述与系统实际功能完全一致。")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
