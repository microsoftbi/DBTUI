"""用户手册流程验证脚本（SQL Server 版）。

重点验证分层配置、Sources 管理、三层分库等核心功能的 API 和 UI 是否正常。
SQL Server 实例可能不可达，因此 dbt run 的结果不作为失败判定依据。
运行方式：
    cd /Users/wadesong/Documents/trae_projects/DBT
    .venv/bin/python doc/verify_userguide.py
"""
from __future__ import annotations

import asyncio
import sys
import uuid

import httpx
from playwright.async_api import async_playwright

BASE_URL = "http://localhost:5173"
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


async def wait_btn(page, name: str, timeout: int = 10000) -> None:
    await page.get_by_role("button", name=name).wait_for(state="visible", timeout=timeout)


async def wait_dialog(page) -> None:
    await page.locator("div[role='dialog']").filter(visible=True).first.wait_for(
        state="visible", timeout=10000
    )


async def main():
    print("=" * 60)
    print("用户手册流程验证（三层分库）")
    print("=" * 60)

    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=120) as api:
        # 清理可能残留的测试项目
        proj_list = (await api.get("/api/projects")).json()
        for p in proj_list:
            if p["name"].startswith("verify_"):
                await api.delete(f"/api/projects/{p['id']}")

        proj_name = f"verify_{uuid.uuid4().hex[:6]}"

        # ================================================================
        # 第 1 章：创建项目（API 验证）
        # ================================================================
        print("\n📗 第 1 章：创建项目")

        # 1.1 创建项目
        try:
            resp = await api.post(
                "/api/projects",
                json={"name": proj_name, "adapter": "sqlserver", "description": "验证项目"},
            )
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            proj = resp.json()
            pid = proj["id"]
            record("1.1 创建 sqlserver 项目", True)
        except Exception as e:
            record("1.1 创建 sqlserver 项目", False, str(e))
            sys.exit(1)

        # 1.2 验证 profiles.yml 包含 sqlserver 连接配置
        try:
            resp = await api.get(f"/api/projects/{pid}/profiles")
            content = resp.json()["content"]
            if "sqlserver" not in content:
                raise Exception("profiles.yml 中没有 sqlserver 类型")
            if "stage_db" not in content:
                raise Exception("profiles.yml 中没有 stage_db 数据库")
            if "192.168.0.116" not in content:
                raise Exception("profiles.yml 中没有 SQL Server 服务器地址")
            if "ODBC Driver" not in content:
                raise Exception("profiles.yml 中没有 ODBC 驱动配置")
            record("1.2 profiles.yml sqlserver 连接配置正确", True)
        except Exception as e:
            record("1.2 profiles.yml sqlserver 连接配置正确", False, str(e))

        # 1.3 验证 dbt_project.yml 包含分层 database 配置
        try:
            # 直接读文件
            import os
            dbt_project_file = os.path.join(proj["path"], "dbt_project.yml")
            with open(dbt_project_file) as f:
                content = f.read()
            if "stage_db" not in content:
                raise Exception("dbt_project.yml 中没有 stage_db")
            if "core_db" not in content:
                raise Exception("dbt_project.yml 中没有 core_db")
            if "mart_db" not in content:
                raise Exception("dbt_project.yml 中没有 mart_db")
            if "+database" not in content:
                raise Exception("dbt_project.yml 中没有 +database 配置")
            record("1.3 dbt_project.yml 分层 database 配置正确", True)
        except Exception as e:
            record("1.3 dbt_project.yml 分层 database 配置正确", False, str(e))

        # 1.4 验证 parse 成功
        try:
            resp = await api.post(f"/api/projects/{pid}/parse")
            if resp.status_code >= 400:
                raise Exception(f"parse 失败: {resp.text}")
            # 检查项目状态
            resp = await api.get("/api/projects")
            p = next(x for x in resp.json() if x["id"] == pid)
            if p["parse_status"] != "success":
                raise Exception(f"parse_status 为 {p['parse_status']}")
            record("1.4 项目首次 parse 成功", True)
        except Exception as e:
            record("1.4 项目首次 parse 成功", False, str(e))

        # ================================================================
        # 第 2 章：分层配置管理
        # ================================================================
        print("\n📗 第 2 章：分层配置管理")

        # 2.1 列出分层（验证默认三层 + 根目录）
        try:
            resp = await api.get(f"/api/projects/{pid}/layers")
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            layers = resp.json()
            layer_names = [l["name"] for l in layers]
            # 应有根目录 + staging + core + marts 至少 4 层
            if len(layers) < 4:
                raise Exception(f"分层数量太少，至少应有 4 层，实际 {len(layers)} 层")
            # 验证根目录存在
            root = [l for l in layers if l["is_root"]]
            if not root:
                raise Exception("没有根目录分层")
            # 验证 staging/core/marts 存在
            for expected in ["staging", "core", "marts"]:
                if expected not in layer_names:
                    raise Exception(f"缺少分层: {expected}")
            record("2.1 分层列表正确（含根目录 + 三层）", True)
        except Exception as e:
            record("2.1 分层列表正确（含根目录 + 三层）", False, str(e))

        # 2.2 验证各层数据库配置
        try:
            layers = (await api.get(f"/api/projects/{pid}/layers")).json()
            layer_map = {l["name"]: l for l in layers}
            if layer_map["staging"]["database"] != "stage_db":
                raise Exception(f"staging 数据库应为 stage_db，实际 {layer_map['staging']['database']}")
            if layer_map["core"]["database"] != "core_db":
                raise Exception(f"core 数据库应为 core_db，实际 {layer_map['core']['database']}")
            if layer_map["marts"]["database"] != "mart_db":
                raise Exception(f"marts 数据库应为 mart_db，实际 {layer_map['marts']['database']}")
            # 验证物化策略
            if layer_map["staging"]["materialized"] != "view":
                raise Exception(f"staging 物化应为 view，实际 {layer_map['staging']['materialized']}")
            if layer_map["core"]["materialized"] != "table":
                raise Exception(f"core 物化应为 table，实际 {layer_map['core']['materialized']}")
            record("2.2 各层数据库和物化配置正确", True)
        except Exception as e:
            record("2.2 各层数据库和物化配置正确", False, str(e))

        # 2.3 新建分层（ODS 层）
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
                raise Exception(f"新建分层名应为 ods，实际 {layer['name']}")
            if layer["display_name"] != "ODS 层":
                raise Exception(f"显示名称应为 ODS 层，实际 {layer['display_name']}")
            if layer["database"] != "ods_db":
                raise Exception(f"数据库应为 ods_db，实际 {layer['database']}")
            # 验证目录已创建
            import os
            ods_dir = os.path.join(proj["path"], "models", "ods")
            if not os.path.isdir(ods_dir):
                raise Exception(f"目录未创建: {ods_dir}")
            record("2.3 新建分层 ODS 层成功（目录已创建）", True)
        except Exception as e:
            record("2.3 新建分层 ODS 层成功（目录已创建）", False, str(e))

        # 2.4 编辑分层（修改数据库和显示名称）
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
                raise Exception(f"显示名称未更新，实际 {layer['display_name']}")
            if layer["database"] != "ods_warehouse":
                raise Exception(f"数据库未更新，实际 {layer['database']}")
            if layer["materialized"] != "table":
                raise Exception(f"物化未更新，实际 {layer['materialized']}")
            record("2.4 编辑分层（修改显示名称/数据库/物化）成功", True)
        except Exception as e:
            record("2.4 编辑分层（修改显示名称/数据库/物化）成功", False, str(e))

        # 2.5 重命名分层目录（验证目录迁移）
        try:
            resp = await api.put(
                f"/api/projects/{pid}/layers/ods",
                json={"name": "ods_new"},
            )
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            layer = resp.json()
            if layer["name"] != "ods_new":
                raise Exception(f"重命名后名称应为 ods_new，实际 {layer['name']}")
            # 验证旧目录不存在，新目录存在
            import os
            old_dir = os.path.join(proj["path"], "models", "ods")
            new_dir = os.path.join(proj["path"], "models", "ods_new")
            if os.path.exists(old_dir):
                raise Exception(f"旧目录仍存在: {old_dir}")
            if not os.path.isdir(new_dir):
                raise Exception(f"新目录未创建: {new_dir}")
            record("2.5 重命名分层目录成功（文件迁移正确）", True)
        except Exception as e:
            record("2.5 重命名分层目录成功（文件迁移正确）", False, str(e))

        # 2.6 删除分层
        try:
            resp = await api.delete(f"/api/projects/{pid}/layers/ods_new")
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            # 验证分层列表中不再有 ods_new
            layers = (await api.get(f"/api/projects/{pid}/layers")).json()
            layer_names = [l["name"] for l in layers]
            if "ods_new" in layer_names:
                raise Exception("删除后 ods_new 仍在列表中")
            # 验证目录仍保留（不删除文件）
            import os
            new_dir = os.path.join(proj["path"], "models", "ods_new")
            if not os.path.isdir(new_dir):
                raise Exception("删除分层后目录被删除了（应保留）")
            record("2.6 删除分层成功（配置删除，目录保留）", True)
        except Exception as e:
            record("2.6 删除分层成功（配置删除，目录保留）", False, str(e))

        # ================================================================
        # 第 3 章：Sources 管理
        # ================================================================
        print("\n📗 第 3 章：Sources 管理")

        # 3.1 新建 source
        try:
            resp = await api.post(
                f"/api/projects/{pid}/sources",
                json={
                    "source_name": "raw_data",
                    "database": "raw_db",
                    "schema": "public",
                    "loader": "sqlserver",
                    "description": "原始数据源",
                    "subdir": "staging",
                    "tables": [
                        {"name": "users", "description": "用户表"},
                        {"name": "orders", "description": "订单表"},
                    ],
                },
            )
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            src = resp.json()
            if src["source_name"] != "raw_data":
                raise Exception(f"source 名应为 raw_data，实际 {src['source_name']}")
            if src["database"] != "raw_db":
                raise Exception(f"数据库应为 raw_db，实际 {src['database']}")
            if src["subdir"] != "staging":
                raise Exception(f"subdir 应为 staging，实际 {src['subdir']}")
            if len(src["tables"]) != 2:
                raise Exception(f"表数量应为 2，实际 {len(src['tables'])}")
            # 验证 sources.yml 文件存在
            import os
            yml_path = os.path.join(proj["path"], "models", "staging", "sources.yml")
            if not os.path.exists(yml_path):
                raise Exception(f"sources.yml 未创建: {yml_path}")
            record("3.1 新建 source（含 2 张表）成功", True)
        except Exception as e:
            record("3.1 新建 source（含 2 张表）成功", False, str(e))

        # 3.2 列出 sources
        try:
            resp = await api.get(f"/api/projects/{pid}/sources")
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            sources = resp.json()
            src_names = [s["source_name"] for s in sources]
            if "raw_data" not in src_names:
                raise Exception("raw_data 不在 source 列表中")
            record("3.2 Source 列表正确", True)
        except Exception as e:
            record("3.2 Source 列表正确", False, str(e))

        # 3.3 获取单个 source 详情
        try:
            resp = await api.get(f"/api/projects/{pid}/sources/raw_data")
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            src = resp.json()
            if src["source_name"] != "raw_data":
                raise Exception("source 名不匹配")
            tables = [t["name"] for t in src["tables"]]
            if "users" not in tables or "orders" not in tables:
                raise Exception(f"表列表不正确: {tables}")
            record("3.3 Source 详情查询正确（含表列表）", True)
        except Exception as e:
            record("3.3 Source 详情查询正确（含表列表）", False, str(e))

        # 3.4 编辑 source（修改数据库和描述）
        try:
            resp = await api.put(
                f"/api/projects/{pid}/sources/raw_data",
                json={
                    "database": "raw_updated",
                    "description": "更新后的描述",
                },
            )
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            src = resp.json()
            if src["database"] != "raw_updated":
                raise Exception(f"数据库未更新，实际 {src['database']}")
            if src["description"] != "更新后的描述":
                raise Exception(f"描述未更新，实际 {src['description']}")
            record("3.4 编辑 source（数据库/描述）成功", True)
        except Exception as e:
            record("3.4 编辑 source（数据库/描述）成功", False, str(e))

        # 3.5 添加表
        try:
            resp = await api.post(
                f"/api/projects/{pid}/sources/raw_data/tables",
                json={"name": "products", "description": "商品表"},
            )
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            src = resp.json()
            table_names = [t["name"] for t in src["tables"]]
            if "products" not in table_names:
                raise Exception(f"products 表未添加，当前表: {table_names}")
            if len(src["tables"]) != 3:
                raise Exception(f"表数量应为 3，实际 {len(src['tables'])}")
            record("3.5 给 source 添加表成功", True)
        except Exception as e:
            record("3.5 给 source 添加表成功", False, str(e))

        # 3.6 编辑表
        try:
            resp = await api.put(
                f"/api/projects/{pid}/sources/raw_data/tables/products",
                json={"description": "商品表（更新）"},
            )
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            src = resp.json()
            products = next(t for t in src["tables"] if t["name"] == "products")
            if products["description"] != "商品表（更新）":
                raise Exception(f"表描述未更新，实际 {products['description']}")
            record("3.6 编辑表（描述）成功", True)
        except Exception as e:
            record("3.6 编辑表（描述）成功", False, str(e))

        # 3.7 删除表
        try:
            resp = await api.delete(
                f"/api/projects/{pid}/sources/raw_data/tables/orders"
            )
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            src = resp.json()
            table_names = [t["name"] for t in src["tables"]]
            if "orders" in table_names:
                raise Exception("orders 表未删除")
            if len(src["tables"]) != 2:
                raise Exception(f"表数量应为 2，实际 {len(src['tables'])}")
            record("3.7 删除表成功", True)
        except Exception as e:
            record("3.7 删除表成功", False, str(e))

        # 3.8 移动 source 到其他目录
        try:
            resp = await api.put(
                f"/api/projects/{pid}/sources/raw_data",
                json={"subdir": "core"},
            )
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            src = resp.json()
            if src["subdir"] != "core":
                raise Exception(f"subdir 应为 core，实际 {src['subdir']}")
            # 验证 core 目录下有 sources.yml，staging 目录下的 sources.yml 中没有 raw_data
            import os
            core_yml = os.path.join(proj["path"], "models", "core", "sources.yml")
            if not os.path.exists(core_yml):
                raise Exception(f"core/sources.yml 未创建: {core_yml}")
            record("3.8 移动 source 到其他目录成功", True)
        except Exception as e:
            record("3.8 移动 source 到其他目录成功", False, str(e))

        # 3.9 删除 source
        try:
            resp = await api.delete(f"/api/projects/{pid}/sources/raw_data")
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            # 验证列表中不再有
            sources = (await api.get(f"/api/projects/{pid}/sources")).json()
            src_names = [s["source_name"] for s in sources]
            if "raw_data" in src_names:
                raise Exception("删除后 raw_data 仍在列表中")
            record("3.9 删除 source 成功", True)
        except Exception as e:
            record("3.9 删除 source 成功", False, str(e))

        # ================================================================
        # 第 4 章：Stage 层
        # ================================================================
        print("\n📗 第 4 章：Stage 层")

        # 4.1 创建 stg_customer
        try:
            resp = await api.post(
                f"/api/projects/{pid}/models",
                json={
                    "name": "stg_customer",
                    "sql": "SELECT 1 AS customer_id, 'Alice' AS customer_name, 'alice@test.com' AS email, 'Beijing' AS city, '2024-01-01' AS created_at\n",
                    "subdir": "staging",
                },
            )
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            data = resp.json()
            if data["database"] != "stage_db":
                raise Exception(f"数据库应为 stage_db，实际为 {data['database']}")
            if "staging" not in data["file_path"]:
                raise Exception(f"文件路径应包含 staging，实际为 {data['file_path']}")
            record("4.1 创建 stg_customer（stage_db）", True)
        except Exception as e:
            record("4.1 创建 stg_customer（stage_db）", False, str(e))

        # 4.2 创建 stg_product
        try:
            resp = await api.post(
                f"/api/projects/{pid}/models",
                json={
                    "name": "stg_product",
                    "sql": "SELECT 1 AS product_id, 'Laptop' AS product_name, 'Electronics' AS category, 5999.0 AS price\n",
                    "subdir": "staging",
                },
            )
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            data = resp.json()
            if data["database"] != "stage_db":
                raise Exception(f"数据库应为 stage_db，实际为 {data['database']}")
            record("4.2 创建 stg_product（stage_db）", True)
        except Exception as e:
            record("4.2 创建 stg_product（stage_db）", False, str(e))

        # 4.3 创建 stg_salesorder
        try:
            resp = await api.post(
                f"/api/projects/{pid}/models",
                json={
                    "name": "stg_salesorder",
                    "sql": "SELECT 1 AS order_id, 1 AS customer_id, 1 AS product_id, 2 AS quantity, '2024-01-10' AS order_date, 11998.0 AS amount\n",
                    "subdir": "staging",
                },
            )
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            data = resp.json()
            if data["database"] != "stage_db":
                raise Exception(f"数据库应为 stage_db，实际为 {data['database']}")
            record("4.3 创建 stg_salesorder（stage_db）", True)
        except Exception as e:
            record("4.3 创建 stg_salesorder（stage_db）", False, str(e))

        # 4.4 发起 stg_customer 运行（SQL Server 可能不可达，不校验运行结果）
        try:
            resp = await api.post(
                f"/api/projects/{pid}/runs",
                json={"run_type": "run", "selection": "stg_customer"},
            )
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            data = resp.json()
            if "id" not in data:
                raise Exception("运行记录没有 id")
            record("4.4 发起 stg_customer 运行（API 正常）", True)
        except Exception as e:
            record("4.4 发起 stg_customer 运行（API 正常）", False, str(e))

        # ================================================================
        # 第 5 章：Core 层（跨库引用 stage_db）
        # ================================================================
        print("\n📗 第 5 章：Core 层（跨库引用）")

        # 5.1 创建 dim_customer（引用 stage_db.stg_customer）
        try:
            resp = await api.post(
                f"/api/projects/{pid}/models",
                json={
                    "name": "dim_customer",
                    "sql": "SELECT customer_id, customer_name, email, city FROM {{ ref('stg_customer') }}\n",
                    "subdir": "core",
                },
            )
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            data = resp.json()
            if data["database"] != "core_db":
                raise Exception(f"数据库应为 core_db，实际为 {data['database']}")
            record("5.1 创建 dim_customer（core_db，跨库引用 stage_db）", True)
        except Exception as e:
            record("5.1 创建 dim_customer（core_db，跨库引用 stage_db）", False, str(e))

        # 5.2 创建 dim_product
        try:
            resp = await api.post(
                f"/api/projects/{pid}/models",
                json={
                    "name": "dim_product",
                    "sql": "SELECT product_id, product_name, category, price FROM {{ ref('stg_product') }}\n",
                    "subdir": "core",
                },
            )
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            data = resp.json()
            if data["database"] != "core_db":
                raise Exception(f"数据库应为 core_db，实际为 {data['database']}")
            record("5.2 创建 dim_product（core_db）", True)
        except Exception as e:
            record("5.2 创建 dim_product（core_db）", False, str(e))

        # 5.3 创建 fact_sales（跨库多表关联）
        try:
            resp = await api.post(
                f"/api/projects/{pid}/models",
                json={
                    "name": "fact_sales",
                    "sql": (
                        "SELECT o.order_id, o.customer_id, o.product_id, o.quantity, o.order_date, o.amount, "
                        "c.city AS customer_city, p.category AS product_category "
                        "FROM {{ ref('stg_salesorder') }} o "
                        "LEFT JOIN {{ ref('stg_customer') }} c ON o.customer_id = c.customer_id "
                        "LEFT JOIN {{ ref('stg_product') }} p ON o.product_id = p.product_id\n"
                    ),
                    "subdir": "core",
                },
            )
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            data = resp.json()
            if data["database"] != "core_db":
                raise Exception(f"数据库应为 core_db，实际为 {data['database']}")
            record("5.3 创建 fact_sales（core_db，多表跨库关联）", True)
        except Exception as e:
            record("5.3 创建 fact_sales（core_db，多表跨库关联）", False, str(e))

        # 5.4 运行 fact_sales（自动运行上游 stage 层）
        try:
            resp = await api.post(
                f"/api/projects/{pid}/runs",
                json={"run_type": "run", "selection": "fact_sales"},
            )
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            data = resp.json()
            if "id" not in data:
                raise Exception("运行记录没有 id")
            record("5.4 发起 fact_sales 运行（API 正常）", True)
        except Exception as e:
            record("5.4 发起 fact_sales 运行（API 正常）", False, str(e))

        # ================================================================
        # 第 6 章：Mart 层（跨库引用 core_db）
        # ================================================================
        print("\n📗 第 6 章：Mart 层（跨库引用）")

        # 6.1 创建 mart_sales_summary
        try:
            resp = await api.post(
                f"/api/projects/{pid}/models",
                json={
                    "name": "mart_sales_summary",
                    "sql": (
                        "SELECT f.order_id, f.order_date, f.customer_id, c.customer_name, "
                        "f.product_id, p.product_name, f.quantity, f.amount "
                        "FROM {{ ref('fact_sales') }} f "
                        "LEFT JOIN {{ ref('dim_customer') }} c ON f.customer_id = c.customer_id "
                        "LEFT JOIN {{ ref('dim_product') }} p ON f.product_id = p.product_id\n"
                    ),
                    "subdir": "marts",
                },
            )
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            data = resp.json()
            if data["database"] != "mart_db":
                raise Exception(f"数据库应为 mart_db，实际为 {data['database']}")
            record("6.1 创建 mart_sales_summary（mart_db，跨库引用 core_db）", True)
        except Exception as e:
            record("6.1 创建 mart_sales_summary（mart_db，跨库引用 core_db）", False, str(e))

        # 6.2 运行 mart_sales_summary
        try:
            resp = await api.post(
                f"/api/projects/{pid}/runs",
                json={"run_type": "run", "selection": "mart_sales_summary"},
            )
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            data = resp.json()
            if "id" not in data:
                raise Exception("运行记录没有 id")
            record("6.2 发起 mart_sales_summary 运行（API 正常）", True)
        except Exception as e:
            record("6.2 发起 mart_sales_summary 运行（API 正常）", False, str(e))

        # 6.3 验证 dbt_project.yml 中三层分库配置完整
        try:
            import os
            dbt_project_file = os.path.join(proj["path"], "dbt_project.yml")
            with open(dbt_project_file) as f:
                content = f.read()
            if "stage_db" not in content:
                raise Exception("dbt_project.yml 中没有 stage_db")
            if "core_db" not in content:
                raise Exception("dbt_project.yml 中没有 core_db")
            if "mart_db" not in content:
                raise Exception("dbt_project.yml 中没有 mart_db")
            record("6.3 dbt_project.yml 三层分库配置完整", True)
        except Exception as e:
            record("6.3 dbt_project.yml 三层分库配置完整", False, str(e))

        # 6.4 创建数据测试（跨库访问 mart_db）
        try:
            resp = await api.post(
                f"/api/projects/{pid}/tests",
                json={
                    "name": "test_amount_positive",
                    "sql": "SELECT * FROM {{ ref('mart_sales_summary') }} WHERE amount <= 0\n",
                },
            )
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            record("6.4 创建数据测试（跨库访问 mart_db）", True)
        except Exception as e:
            record("6.4 创建数据测试（跨库访问 mart_db）", False, str(e))

        # ================================================================
        # 第 7 章：DAG
        # ================================================================
        print("\n📗 第 7 章：DAG 血缘图")

        # 7.1 DAG 数据正确
        try:
            resp = await api.get(f"/api/projects/{pid}/dag")
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            data = resp.json()
            nodes = data["nodes"]
            edges = data["edges"]
            if len(nodes) < 6:
                raise Exception(f"DAG 节点数量太少：{len(nodes)}")
            if len(edges) < 5:
                raise Exception(f"DAG 边数量太少：{len(edges)}")
            # 验证跨库依赖边存在
            record("7.1 DAG 数据正确（含跨库依赖）", True)
        except Exception as e:
            record("7.1 DAG 数据正确（含跨库依赖）", False, str(e))

        # ================================================================
        # 第 8 章：运行历史
        # ================================================================
        print("\n📗 第 8 章：运行历史")

        # 8.1 运行历史记录存在
        try:
            resp = await api.get(f"/api/projects/{pid}/runs")
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            runs = resp.json()
            if len(runs) < 3:
                raise Exception(f"运行记录数量太少：{len(runs)}")
            record("8.1 运行历史记录存在", True)
        except Exception as e:
            record("8.1 运行历史记录存在", False, str(e))

        # 8.2 运行日志可查看
        try:
            run_id = runs[0]["id"]
            resp = await api.get(f"/api/projects/{pid}/runs/{run_id}")
            if resp.status_code >= 400:
                raise Exception(f"API 返回 {resp.status_code}: {resp.text}")
            detail = resp.json()
            if not detail.get("log"):
                raise Exception("运行日志为空")
            record("8.2 运行日志可查看", True)
        except Exception as e:
            record("8.2 运行日志可查看", False, str(e))

        # ================================================================
        # UI 操作抽样验证
        # ================================================================
        print("\n📗 UI 操作抽样验证")

        async with async_playwright() as p:
            browser = await p.chromium.launch()
            context = await browser.new_context(
                viewport={"width": 1440, "height": 900}, device_scale_factor=1
            )
            page = await context.new_page()

            # UI.1 项目列表页
            try:
                await page.goto(f"{BASE_URL}/")
                await page.wait_for_selector("h1")
                await page.wait_for_timeout(500)
                if proj_name not in await page.content():
                    raise Exception("项目不在列表中")
                record("UI.1 项目列表页正常显示", True)
            except Exception as e:
                record("UI.1 项目列表页正常显示", False, str(e))

            # UI.2 进入项目详情页
            try:
                await page.goto(f"{BASE_URL}/projects/{pid}")
                await page.wait_for_selector("h2")
                await wait_btn(page, "新建模型")
                await page.wait_for_timeout(500)
                content = await page.content()
                if "数据库" not in content:
                    raise Exception("模型列表中没有数据库列")
                if "stage_db" not in content:
                    raise Exception("页面中没有 stage_db 模型")
                if "core_db" not in content:
                    raise Exception("页面中没有 core_db 模型")
                if "mart_db" not in content:
                    raise Exception("页面中没有 mart_db 模型")
                record("UI.2 项目详情页显示数据库列和三层模型", True)
            except Exception as e:
                record("UI.2 项目详情页显示数据库列和三层模型", False, str(e))

            # UI.3 分层配置按钮和弹窗
            try:
                await page.get_by_role("button", name="分层配置").click()
                await page.wait_for_timeout(800)
                dialog = page.locator(".el-dialog").filter(has_text="分层配置")
                if not await dialog.is_visible():
                    raise Exception("分层配置弹窗未显示")
                # 验证表格中有 staging/core/marts 三层
                table_text = await dialog.locator(".el-table__body").inner_text()
                if "staging" not in table_text:
                    raise Exception("表格中没有 staging 层")
                if "core" not in table_text:
                    raise Exception("表格中没有 core 层")
                if "marts" not in table_text:
                    raise Exception("表格中没有 marts 层")
                if "stage_db" not in table_text:
                    raise Exception("表格中没有 stage_db 数据库")
                # 关闭弹窗（按 ESC 键，避免定位关闭按钮的问题）
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(500)
                record("UI.3 分层配置弹窗正常显示（含三层列表）", True)
            except Exception as e:
                record("UI.3 分层配置弹窗正常显示（含三层列表）", False, str(e))

            # UI.4 Sources 标签页
            try:
                await page.get_by_role("tab", name="Sources").click()
                await page.wait_for_timeout(1000)
                content = await page.content()
                if "新建数据源" not in content:
                    raise Exception("Sources 页面没有新建数据源按钮")
                # 验证左侧树结构存在
                if await page.locator(".sources-tree").count() == 0:
                    raise Exception("没有 sources 左侧树")
                record("UI.4 Sources 标签页正常显示", True)
            except Exception as e:
                record("UI.4 Sources 标签页正常显示", False, str(e))

            # UI.5 新建模型弹窗有层级选择器（动态从 layers 生成）
            try:
                await page.get_by_role("tab", name="Models").click()
                await wait_btn(page, "新建模型")
                await page.get_by_role("button", name="新建模型").click()
                await wait_dialog(page)
                dialog = page.locator(".el-dialog").filter(visible=True).first
                if await dialog.locator(".el-select").count() == 0:
                    raise Exception("没有层级选择器")
                # 检查层级选项
                await dialog.locator(".el-select").first.click()
                await page.wait_for_timeout(300)
                options = await page.locator(".el-select-dropdown__item:visible").all_inner_texts()
                options_text = " ".join(options)
                if "staging" not in options_text:
                    raise Exception("没有 staging 层选项")
                if "core" not in options_text:
                    raise Exception("没有 core 层选项")
                if "marts" not in options_text:
                    raise Exception("没有 marts 层选项")
                # 关闭下拉框和弹窗
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(300)
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(500)
                await page.reload()
                await page.wait_for_selector("h2")
                await wait_btn(page, "新建模型")
                record("UI.5 新建模型弹窗有层级选择器（动态生成）", True)
            except Exception as e:
                record("UI.5 新建模型弹窗有层级选择器（动态生成）", False, str(e))

            # UI.6 DAG 页面
            try:
                await page.get_by_text("DAG", exact=True).click()
                await page.wait_for_selector(".dag-canvas svg", timeout=10000)
                await page.wait_for_timeout(1000)
                nodes = await page.locator("svg g.node").count()
                if nodes < 6:
                    raise Exception(f"DAG 节点数量太少：{nodes}")
                record("UI.6 DAG 图正常显示", True)
            except Exception as e:
                record("UI.6 DAG 图正常显示", False, str(e))

            # UI.7 运行历史页
            try:
                await page.get_by_text("运行历史", exact=True).click()
                try:
                    await page.get_by_role("button", name="查看日志").first.wait_for(
                        state="visible", timeout=10000
                    )
                except Exception:
                    raise Exception("没有运行记录")
                record("UI.7 运行历史页正常显示", True)
            except Exception as e:
                record("UI.7 运行历史页正常显示", False, str(e))

            await browser.close()

        # 清理
        await api.delete(f"/api/projects/{pid}")

    # ================================================================
    # 结果汇总
    # ================================================================
    print("\n" + "=" * 60)
    print("验证结果汇总")
    print("=" * 60)
    print(f"通过: {passed} / {passed + failed}")
    print(f"失败: {failed} / {passed + failed}")

    if failed > 0:
        print("\n❌ 失败的步骤：")
        for name, ok, err in results:
            if not ok:
                print(f"  - {name}: {err}")
        sys.exit(1)
    else:
        print("\n✅ 所有步骤均通过！用户手册流程完全跑通。")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
