"""数据查看器接口：浏览数据库中的表/视图，查看 DDL 和数据预览。

仅支持 SQL Server 适配器。
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Project
from ._common import get_project_or_404

router = APIRouter(prefix="/api/projects/{project_id}/data-viewer", tags=["data-viewer"])

# 安全校验：数据库名、表名、schema 名只允许字母数字下划线和点
_SAFE_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_.]*$")


def _safe_name(name: str, label: str = "名称") -> str:
    """校验标识符安全性，防止 SQL 注入。"""
    if not name or not _SAFE_NAME_RE.match(name):
        raise HTTPException(status_code=400, detail=f"{label} 不合法: {name}")
    return name


def _load_profiles(project: Project) -> dict:
    """读取项目的 profiles.yml 并返回 dev target 配置。"""
    p = Path(project.path) / "profiles.yml"
    if not p.exists():
        raise HTTPException(status_code=400, detail="profiles.yml 不存在")
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"profiles.yml 解析失败: {exc}") from exc
    # 取第一个 profile 的 dev target
    profile_name = list(data.keys())[0]
    profile = data[profile_name]
    target = profile.get("target", "dev")
    outputs = profile.get("outputs", {})
    if target not in outputs:
        raise HTTPException(status_code=400, detail=f"profiles.yml 中找不到 target: {target}")
    return outputs[target]


def _get_conn(project: Project):
    """获取 pyodbc 连接（SQL Server）。"""
    if project.adapter != "sqlserver":
        raise HTTPException(status_code=400, detail="数据查看器仅支持 sqlserver 适配器")
    try:
        import pyodbc
    except ImportError as exc:
        raise HTTPException(status_code=500, detail="pyodbc 未安装，无法连接数据库") from exc

    cfg = _load_profiles(project)
    driver = cfg.get("driver", "ODBC Driver 18 for SQL Server")
    server = cfg.get("server", "")
    port = cfg.get("port", 1433)
    database = cfg.get("database", "")
    user = cfg.get("user", "")
    password = cfg.get("password", "")
    trust_cert = cfg.get("trust_cert", False)

    conn_str = (
        f"DRIVER={{{driver}}};"
        f"SERVER={server},{port};"
        f"DATABASE={database};"
        f"UID={user};"
        f"PWD={password};"
    )
    if trust_cert:
        conn_str += "TrustServerCertificate=yes;"

    try:
        conn = pyodbc.connect(conn_str)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"数据库连接失败: {exc}") from exc
    return conn


def _quote(name: str) -> str:
    """用方括号包裹 SQL Server 标识符。"""
    return "[" + name.replace("]", "]]") + "]"


# ---------- 数据库列表 ----------
@router.get("/databases")
def list_databases(project_id: int, db: Session = Depends(get_db)):
    """获取数据仓库中的数据库列表（从分层配置推断 + 主连接数据库）。"""
    project = get_project_or_404(db, project_id)
    if project.adapter != "sqlserver":
        raise HTTPException(status_code=400, detail="数据查看器仅支持 sqlserver 适配器")

    # 从 dbt_project.yml 读取分层配置中的 database
    dbt_project_file = Path(project.path) / "dbt_project.yml"
    databases: list[str] = []
    if dbt_project_file.exists():
        try:
            data = yaml.safe_load(dbt_project_file.read_text(encoding="utf-8"))
            models_cfg = (data.get("models") or {}).get(project.slug, {})
            for _key, val in models_cfg.items():
                if isinstance(val, dict) and val.get("+database"):
                    db_name = val["+database"]
                    if db_name not in databases:
                        databases.append(db_name)
        except Exception:
            pass

    # 加上 profiles.yml 中的主数据库（如果不在列表中）
    try:
        cfg = _load_profiles(project)
        main_db = cfg.get("database", "")
        if main_db and main_db not in databases:
            databases.insert(0, main_db)
    except Exception:
        pass

    return {"databases": databases}


# ---------- 表/视图列表 ----------
@router.get("/tables")
def list_tables(
    project_id: int,
    database: str = Query(..., description="数据库名"),
    table_type: str = Query("table", description="table 或 view", alias="type"),
    db: Session = Depends(get_db),
):
    """获取指定数据库下的表或视图列表。"""
    project = get_project_or_404(db, project_id)
    _safe_name(database, "数据库名")
    if table_type not in ("table", "view"):
        raise HTTPException(status_code=400, detail="type 必须是 table 或 view")

    conn = _get_conn(project)
    try:
        cursor = conn.cursor()
        # 切换数据库
        cursor.execute(f"USE {_quote(database)}")
        # 查询 INFORMATION_SCHEMA
        table_type_sql = "BASE TABLE" if table_type == "table" else "VIEW"
        cursor.execute(
            "SELECT TABLE_SCHEMA, TABLE_NAME "
            "FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_TYPE = ? "
            "ORDER BY TABLE_SCHEMA, TABLE_NAME",
            (table_type_sql,),
        )
        rows = cursor.fetchall()
        tables = [
            {"schema": row.TABLE_SCHEMA, "name": row.TABLE_NAME}
            for row in rows
        ]
        return {"tables": tables}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"查询失败: {exc}") from exc
    finally:
        conn.close()


# ---------- DDL 创建脚本 ----------
@router.get("/ddl")
def get_ddl(
    project_id: int,
    database: str = Query(..., description="数据库名"),
    table: str = Query(..., description="表名或视图名"),
    schema: str = Query("dbo", description="schema 名"),
    db: Session = Depends(get_db),
):
    """获取表/视图的创建脚本。"""
    project = get_project_or_404(db, project_id)
    _safe_name(database, "数据库名")
    _safe_name(schema, "Schema 名")
    _safe_name(table, "表名")

    conn = _get_conn(project)
    try:
        cursor = conn.cursor()
        cursor.execute(f"USE {_quote(database)}")

        # 先判断是表还是视图
        cursor.execute(
            "SELECT TABLE_TYPE FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?",
            (schema, table),
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"表/视图不存在: {schema}.{table}")

        obj_type = row.TABLE_TYPE  # BASE TABLE 或 VIEW

        if obj_type == "VIEW":
            # 视图：用 OBJECT_DEFINITION 获取创建脚本
            cursor.execute(
                f"SELECT OBJECT_DEFINITION(OBJECT_ID('{_quote(schema)}.{_quote(table)}')) AS ddl"
            )
            ddl_row = cursor.fetchone()
            ddl = ddl_row.ddl if ddl_row and ddl_row.ddl else ""
            if not ddl:
                # 备用：sp_helptext
                try:
                    cursor.execute(f"EXEC sp_helptext '{schema}.{table}'")
                    lines = [r.Text for r in cursor.fetchall()]
                    ddl = "".join(lines)
                except Exception:
                    ddl = f"-- 无法获取视图 {schema}.{table} 的定义"
        else:
            # 表：从 INFORMATION_SCHEMA.COLUMNS 拼接 CREATE TABLE
            cursor.execute(
                "SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, "
                "NUMERIC_PRECISION, NUMERIC_SCALE, IS_NULLABLE, COLUMN_DEFAULT "
                "FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ? "
                "ORDER BY ORDINAL_POSITION",
                (schema, table),
            )
            columns = cursor.fetchall()
            lines = [f"CREATE TABLE {_quote(schema)}.{_quote(table)} ("]
            col_defs = []
            for col in columns:
                dtype = col.DATA_TYPE
                # 处理带长度的类型
                if dtype in ("varchar", "nvarchar", "char", "nchar"):
                    length = col.CHARACTER_MAXIMUM_LENGTH
                    if length == -1:
                        dtype = f"{dtype}(MAX)"
                    elif length:
                        dtype = f"{dtype}({length})"
                elif dtype in ("decimal", "numeric"):
                    prec = col.NUMERIC_PRECISION
                    scale = col.NUMERIC_SCALE
                    if prec and scale is not None:
                        dtype = f"{dtype}({prec}, {scale})"
                nullable = "NULL" if col.IS_NULLABLE == "YES" else "NOT NULL"
                default = f" DEFAULT {col.COLUMN_DEFAULT}" if col.COLUMN_DEFAULT else ""
                col_defs.append(f"    {_quote(col.COLUMN_NAME)} {dtype} {nullable}{default}")
            lines.append(",\n".join(col_defs))
            lines.append(")")
            ddl = "\n".join(lines)

        return {"ddl": ddl, "type": "view" if obj_type == "VIEW" else "table"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"获取 DDL 失败: {exc}") from exc
    finally:
        conn.close()


# ---------- 数据预览 ----------
@router.get("/data")
def get_data(
    project_id: int,
    database: str = Query(..., description="数据库名"),
    table: str = Query(..., description="表名或视图名"),
    schema: str = Query("dbo", description="schema 名"),
    limit: int = Query(1000, description="返回行数上限，最大 1000"),
    db: Session = Depends(get_db),
):
    """获取表/视图的数据预览（最多 1000 行）。"""
    project = get_project_or_404(db, project_id)
    _safe_name(database, "数据库名")
    _safe_name(schema, "Schema 名")
    _safe_name(table, "表名")
    if limit <= 0 or limit > 1000:
        limit = 1000

    conn = _get_conn(project)
    try:
        cursor = conn.cursor()
        cursor.execute(f"USE {_quote(database)}")

        # 先查总数
        cursor.execute(
            f"SELECT COUNT(*) AS cnt FROM {_quote(schema)}.{_quote(table)}"
        )
        total = cursor.fetchone().cnt

        # 查询数据（TOP N）
        cursor.execute(
            f"SELECT TOP {limit} * FROM {_quote(schema)}.{_quote(table)}"
        )
        columns = [desc[0] for desc in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

        return {"columns": columns, "rows": rows, "total": total, "returned": len(rows)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"查询数据失败: {exc}") from exc
    finally:
        conn.close()
