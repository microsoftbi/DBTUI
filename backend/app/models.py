"""SQLAlchemy ORM 模型。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Project(Base):
    """DBT 项目元数据（对应磁盘上的一个 dbt 项目目录）。"""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    # 磁盘上的绝对路径
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    adapter: Mapped[str] = mapped_column(String(64), default="postgres")
    description: Mapped[str] = mapped_column(Text, default="")
    dbt_version: Mapped[str] = mapped_column(String(64), default="")
    # 最近一次 parse 的状态
    parse_status: Mapped[str] = mapped_column(String(32), default="")
    parsed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Model(Base):
    """DBT 资源节点（model / seed / snapshot）。"""

    __tablename__ = "models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, index=True)
    unique_id: Mapped[str] = mapped_column(String(255), index=True)
    name: Mapped[str] = mapped_column(String(255))
    resource_type: Mapped[str] = mapped_column(String(64), default="model")
    file_path: Mapped[str] = mapped_column(String(1024), default="")
    materialized: Mapped[str] = mapped_column(String(64), default="view")
    database: Mapped[str] = mapped_column(String(255), default="")
    schema_name: Mapped[str] = mapped_column(String(255), default="")
    alias: Mapped[str] = mapped_column(String(255), default="")
    tags_json: Mapped[str] = mapped_column(Text, default="[]")
    description: Mapped[str] = mapped_column(Text, default="")
    compiled_code: Mapped[str] = mapped_column(Text, default="")
    # snapshot 特有配置（非 snapshot 节点为空）
    snapshot_strategy: Mapped[str] = mapped_column(String(32), default="")
    target_schema: Mapped[str] = mapped_column(String(255), default="")
    unique_key: Mapped[str] = mapped_column(String(255), default="")
    run_status: Mapped[str] = mapped_column(String(32), default="")
    run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Test(Base):
    """DBT 测试节点（singular / generic）。"""

    __tablename__ = "tests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, index=True)
    unique_id: Mapped[str] = mapped_column(String(255), index=True)
    name: Mapped[str] = mapped_column(String(255))
    type: Mapped[str] = mapped_column(String(32), default="generic")  # singular / generic
    severity: Mapped[str] = mapped_column(String(32), default="ERROR")
    file_path: Mapped[str] = mapped_column(String(1024), default="")
    tags_json: Mapped[str] = mapped_column(Text, default="[]")
    model_unique_id: Mapped[str] = mapped_column(String(255), default="")
    run_status: Mapped[str] = mapped_column(String(32), default="")
    run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Macro(Base):
    """DBT macro 节点。"""

    __tablename__ = "macros"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, index=True)
    unique_id: Mapped[str] = mapped_column(String(255), index=True)
    name: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(1024), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    macro_sql: Mapped[str] = mapped_column(Text, default="")


class Source(Base):
    """DBT source 节点。"""

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, index=True)
    unique_id: Mapped[str] = mapped_column(String(255), index=True)
    source_name: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(255))
    database: Mapped[str] = mapped_column(String(255), default="")
    schema_name: Mapped[str] = mapped_column(String(255), default="")
    identifier: Mapped[str] = mapped_column(String(255), default="")
    loader: Mapped[str] = mapped_column(String(64), default="")
    description: Mapped[str] = mapped_column(Text, default="")


class DagEdge(Base):
    """DAG 有向边（parent -> child）。"""

    __tablename__ = "dag_edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, index=True)
    parent_unique_id: Mapped[str] = mapped_column(String(255), index=True)
    child_unique_id: Mapped[str] = mapped_column(String(255), index=True)


class RunHistory(Base):
    """一次运行记录。"""

    __tablename__ = "run_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, index=True)
    run_type: Mapped[str] = mapped_column(String(32))  # run / test / compile / build
    selection: Mapped[str] = mapped_column(String(512), default="")
    status: Mapped[str] = mapped_column(String(32), default="")  # success / error / running
    log: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class RunResult(Base):
    """单个资源在一次运行中的结果。"""

    __tablename__ = "run_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, index=True)
    unique_id: Mapped[str] = mapped_column(String(255), index=True)
    status: Mapped[str] = mapped_column(String(32), default="")
    message: Mapped[str] = mapped_column(Text, default="")
    execution_time: Mapped[float] = mapped_column(default=0.0)
