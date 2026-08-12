"""Pydantic 请求/响应模型。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------- Project ----------
class ProjectBase(BaseModel):
    name: str = Field(min_length=1, max_length=255, description="项目名称")
    adapter: str = Field(default="postgres", description="数据源类型")
    description: str = Field(default="", description="项目描述")


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    adapter: Optional[str] = None
    description: Optional[str] = None


class ProjectRead(ProjectBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    path: str
    dbt_version: str
    parse_status: str
    parsed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


# ---------- Model ----------
class ModelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    unique_id: str
    name: str
    resource_type: str
    file_path: str
    materialized: str
    database: str
    schema_name: str
    alias: str
    tags_json: str
    description: str
    compiled_code: str
    run_status: str
    run_at: Optional[datetime] = None


class ModelCreate(BaseModel):
    """前端新建模型（写入磁盘 models/**/*.sql）。"""

    name: str = Field(min_length=1, max_length=255, pattern=r"^[a-zA-Z0-9_]+$")
    sql: str = Field(default="SELECT 1 AS id;\n")
    subdir: str = Field(default="", pattern=r"^[a-zA-Z0-9_/]*$")


class ModelUpdate(BaseModel):
    name: Optional[str] = Field(default=None, pattern=r"^[a-zA-Z0-9_]+$")
    sql: Optional[str] = None
    description: Optional[str] = None
    materialized: Optional[str] = None


# ---------- Test ----------
class TestCreate(BaseModel):
    """创建 singular test。"""

    name: str = Field(min_length=1, max_length=255, pattern=r"^[a-zA-Z0-9_]+$")
    sql: str = Field(default="SELECT * FROM {{ ref('example') }} WHERE 1 = 0\n")


class TestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    unique_id: str
    name: str
    type: str
    severity: str
    file_path: str
    tags_json: str
    model_unique_id: str
    run_status: str
    run_at: Optional[datetime] = None


# ---------- Macro ----------
class MacroRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    unique_id: str
    name: str
    file_path: str
    description: str
    macro_sql: str


class MacroCreate(BaseModel):
    """新建 macro（写入磁盘 macros/**/*.sql）。"""

    name: str = Field(min_length=1, max_length=255, pattern=r"^[a-zA-Z0-9_]+$")
    sql: str = Field(
        default="{% macro example_macro() %}\n  SELECT 1\n{% endmacro %}\n"
    )
    subdir: str = Field(default="", pattern=r"^[a-zA-Z0-9_/]*$")


class MacroUpdate(BaseModel):
    name: Optional[str] = Field(default=None, pattern=r"^[a-zA-Z0-9_]+$")
    sql: Optional[str] = None
    description: Optional[str] = None


# ---------- DAG ----------
class DagNode(BaseModel):
    id: str  # unique_id
    label: str
    type: str  # model / test / source / seed / snapshot
    status: str
    materialized: Optional[str] = None
    run_at: Optional[datetime] = None


class DagEdgeOut(BaseModel):
    source: str
    target: str


class DagOut(BaseModel):
    nodes: list[DagNode]
    edges: list[DagEdgeOut]


# ---------- Run ----------
class RunStart(BaseModel):
    run_type: str = Field(default="run", pattern="^(run|test|compile|build)$")
    selection: str = Field(default="", description="dbt --select 表达式")


class RunResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    unique_id: str
    status: str
    message: str
    execution_time: float


class RunHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    run_type: str
    selection: str
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


# ---------- Source ----------
class SourceTable(BaseModel):
    """source 下的一张表。"""

    name: str = Field(min_length=1, max_length=255, pattern=r"^[a-zA-Z0-9_]+$")
    identifier: str = Field(default="", description="物理表名，默认同 name")
    description: str = Field(default="")


class SourceDefinition(BaseModel):
    """一个 source 定义（对应 sources.yml 中 sources 数组的一项）。"""

    source_name: str = Field(min_length=1, max_length=255, pattern=r"^[a-zA-Z0-9_]+$")
    database: str = Field(default="", description="数据库名")
    schema_: str = Field(default="", alias="schema", description="schema 名")
    loader: str = Field(default="")
    description: str = Field(default="")
    tables: list[SourceTable] = Field(default_factory=list)
    subdir: str = Field(default="", description="所在子目录（相对于 models/）")


class SourceCreate(BaseModel):
    """新建 source。"""

    source_name: str = Field(min_length=1, max_length=255, pattern=r"^[a-zA-Z0-9_]+$")
    database: str = Field(default="")
    schema_: str = Field(default="", alias="schema")
    loader: str = Field(default="")
    description: str = Field(default="")
    tables: list[SourceTable] = Field(default_factory=list)
    subdir: str = Field(default="staging", pattern=r"^[a-zA-Z0-9_/]*$")


class SourceUpdate(BaseModel):
    """更新 source 基本信息（不含表）。"""

    source_name: Optional[str] = Field(
        default=None, min_length=1, max_length=255, pattern=r"^[a-zA-Z0-9_]+$"
    )
    database: Optional[str] = None
    schema_: Optional[str] = Field(default=None, alias="schema")
    loader: Optional[str] = None
    description: Optional[str] = None
    subdir: Optional[str] = Field(
        default=None, pattern=r"^[a-zA-Z0-9_/]*$", description="移动到其他子目录"
    )


class SourceTableCreate(BaseModel):
    """给 source 添加一张表。"""

    name: str = Field(min_length=1, max_length=255, pattern=r"^[a-zA-Z0-9_]+$")
    identifier: str = Field(default="")
    description: str = Field(default="")


class SourceTableUpdate(BaseModel):
    """更新 source 中的表。"""

    name: Optional[str] = Field(
        default=None, min_length=1, max_length=255, pattern=r"^[a-zA-Z0-9_]+$"
    )
    identifier: Optional[str] = None
    description: Optional[str] = None


# ---------- Layer（分层配置） ----------
class LayerDefinition(BaseModel):
    """一个分层配置（对应 dbt_project.yml 中 models 下的一个目录）。"""

    name: str = Field(description="目录名，如 staging / core / marts")
    display_name: str = Field(default="", description="显示名称，如 Stage 层")
    database: str = Field(default="", description="+database 配置")
    schema_: str = Field(default="", alias="schema", description="+schema 配置")
    materialized: str = Field(default="view", description="+materialized 配置")
    is_root: bool = Field(default=False, description="是否为根目录（models/ 本身）")


class LayerCreate(BaseModel):
    """新建分层。"""

    name: str = Field(min_length=1, max_length=255, pattern=r"^[a-zA-Z0-9_]+$")
    display_name: str = Field(default="")
    database: str = Field(default="")
    schema_: str = Field(default="", alias="schema")
    materialized: str = Field(default="view")


class LayerUpdate(BaseModel):
    """更新分层配置。name 变化时会重命名目录。"""

    name: Optional[str] = Field(
        default=None, min_length=1, max_length=255, pattern=r"^[a-zA-Z0-9_]+$"
    )
    display_name: Optional[str] = None
    database: Optional[str] = None
    schema_: Optional[str] = Field(default=None, alias="schema")
    materialized: Optional[str] = None


# ---------- 通用响应 ----------
class MessageResponse(BaseModel):
    message: str


class ProfileUpdate(BaseModel):
    content: str = Field(description="profiles.yml 完整内容")
