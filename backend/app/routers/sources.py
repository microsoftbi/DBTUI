"""Source 管理路由 — 读写 models/** 下的 sources.yml 文件。

支持在任意子目录下创建 sources.yml，每个 source 记录其所在的 subdir。
"""
from __future__ import annotations

from pathlib import Path

import yaml
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Project
from ..schemas import (
    SourceCreate,
    SourceDefinition,
    SourceTableCreate,
    SourceTableUpdate,
    SourceUpdate,
)
from ._common import get_project_or_404, refresh_manifest

router = APIRouter(prefix="/api/projects/{project_id}/sources", tags=["sources"])

MODELS_DIR = "models"
SOURCES_FILENAME = "sources.yml"


def _models_dir(project: Project) -> Path:
    return Path(project.path) / MODELS_DIR


def _find_all_sources_yml(project: Project) -> list[Path]:
    """扫描 models/ 下所有子目录，找到所有包含 sources 定义的 yml 文件。"""
    models = _models_dir(project)
    if not models.exists():
        return []
    files: list[Path] = []
    for yml_file in sorted(models.rglob("*.yml")) + sorted(models.rglob("*.yaml")):
        try:
            data = yaml.safe_load(yml_file.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        if isinstance(data, dict) and "sources" in data:
            files.append(yml_file)
    return files


def _subdir_of(project: Project, yml_path: Path) -> str:
    """计算 yml 文件相对于 models/ 的子目录（不含文件名）。"""
    rel = yml_path.parent.relative_to(_models_dir(project))
    return "" if str(rel) == "." else str(rel)


def _load_all_sources(project: Project) -> list[tuple[str, dict, Path]]:
    """加载所有 source，返回 [(subdir, source_dict, yml_path), ...]。"""
    result: list[tuple[str, dict, Path]] = []
    for yml_path in _find_all_sources_yml(project):
        try:
            data = yaml.safe_load(yml_path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        sources = data.get("sources", []) or []
        if not isinstance(sources, list):
            continue
        subdir = _subdir_of(project, yml_path)
        for src in sources:
            if isinstance(src, dict):
                result.append((subdir, src, yml_path))
    return result


def _to_source_def(subdir: str, src: dict) -> SourceDefinition:
    """把 yml 字典 + subdir 转成 SourceDefinition。"""
    tables_raw = src.get("tables", []) or []
    tables = []
    for t in tables_raw:
        if not isinstance(t, dict):
            continue
        tables.append(
            {
                "name": t.get("name", ""),
                "identifier": t.get("identifier", "") or t.get("name", ""),
                "description": t.get("description", ""),
            }
        )
    return SourceDefinition(
        source_name=src.get("name", ""),
        database=src.get("database", ""),
        schema=src.get("schema", ""),
        loader=src.get("loader", ""),
        description=src.get("description", ""),
        tables=tables,
        subdir=subdir,
    )


def _find_source(
    all_sources: list[tuple[str, dict, Path]], source_name: str
) -> tuple[int, str, dict, Path]:
    """按名称查找 source，返回 (索引, subdir, source_dict, yml_path)。找不到抛 404。"""
    for i, (subdir, src, yml_path) in enumerate(all_sources):
        if src.get("name") == source_name:
            return i, subdir, src, yml_path
    raise HTTPException(status_code=404, detail=f"Source 不存在: {source_name}")


def _find_table(tables: list[dict], table_name: str) -> tuple[int, dict]:
    """按名称查找表，返回 (索引, 字典)。找不到抛 404。"""
    for i, t in enumerate(tables):
        if t.get("name") == table_name:
            return i, t
    raise HTTPException(status_code=404, detail=f"表不存在: {table_name}")


def _write_sources_to_file(yml_path: Path, sources_in_file: list[dict]) -> None:
    """将 source 列表写回到指定的 yml 文件。"""
    yml_path.parent.mkdir(parents=True, exist_ok=True)
    data = {"version": 2, "sources": sources_in_file}
    yml_path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def _rebuild_file_from_all(
    project: Project,
    all_sources: list[tuple[str, dict, Path]],
    target_yml_path: Path,
) -> None:
    """根据 all_sources 重建某个 yml 文件的内容。

    从 all_sources 中筛选出属于 target_yml_path 的 source，写回文件。
    """
    sources_in_file = [
        src for (_, src, p) in all_sources if p == target_yml_path
    ]
    if sources_in_file:
        _write_sources_to_file(target_yml_path, sources_in_file)
    else:
        # 文件中没有 source 了，删除文件
        if target_yml_path.exists():
            target_yml_path.unlink()


# ---------- API ----------
@router.get("", response_model=list[SourceDefinition])
def list_sources(project_id: int, db: Session = Depends(get_db)) -> list[SourceDefinition]:
    """列出所有 source 定义（扫描所有子目录）。"""
    project = get_project_or_404(db, project_id)
    all_sources = _load_all_sources(project)
    return [_to_source_def(subdir, src) for subdir, src, _ in all_sources]


@router.get("/{source_name}", response_model=SourceDefinition)
def get_source(
    project_id: int, source_name: str, db: Session = Depends(get_db)
) -> SourceDefinition:
    """获取单个 source 详情。"""
    project = get_project_or_404(db, project_id)
    all_sources = _load_all_sources(project)
    _, subdir, src, _ = _find_source(all_sources, source_name)
    return _to_source_def(subdir, src)


@router.post("", response_model=SourceDefinition)
def create_source(
    project_id: int, body: SourceCreate, db: Session = Depends(get_db)
) -> SourceDefinition:
    """新建一个 source（可同时带表），保存到指定子目录。"""
    project = get_project_or_404(db, project_id)
    all_sources = _load_all_sources(project)

    # 检查重名
    if any(src.get("name") == body.source_name for _, src, _ in all_sources):
        raise HTTPException(status_code=400, detail=f"Source 已存在: {body.source_name}")

    new_src: dict = {"name": body.source_name}
    if body.database:
        new_src["database"] = body.database
    if body.schema_:
        new_src["schema"] = body.schema_
    if body.loader:
        new_src["loader"] = body.loader
    if body.description:
        new_src["description"] = body.description
    if body.tables:
        new_src["tables"] = []
        for t in body.tables:
            entry: dict = {"name": t.name}
            if t.identifier and t.identifier != t.name:
                entry["identifier"] = t.identifier
            if t.description:
                entry["description"] = t.description
            new_src["tables"].append(entry)

    # 写入对应子目录的 sources.yml
    subdir = body.subdir or ""
    yml_path = _models_dir(project) / subdir / SOURCES_FILENAME
    existing_in_file = [
        src for (sd, src, p) in all_sources if p == yml_path
    ]
    existing_in_file.append(new_src)
    _write_sources_to_file(yml_path, existing_in_file)

    refresh_manifest(db, project)
    return _to_source_def(subdir, new_src)


@router.put("/{source_name}", response_model=SourceDefinition)
def update_source(
    project_id: int,
    source_name: str,
    body: SourceUpdate,
    db: Session = Depends(get_db),
) -> SourceDefinition:
    """更新 source 基本信息，支持移动到其他子目录。"""
    project = get_project_or_404(db, project_id)
    all_sources = _load_all_sources(project)
    idx, subdir, src, old_yml_path = _find_source(all_sources, source_name)

    # 名称变更检查
    new_name = body.source_name or source_name
    if new_name != source_name:
        if any(s.get("name") == new_name for _, s, _ in all_sources):
            raise HTTPException(status_code=400, detail=f"Source 已存在: {new_name}")
        src["name"] = new_name

    # 基本字段更新
    if body.database is not None:
        if body.database:
            src["database"] = body.database
        else:
            src.pop("database", None)
    if body.schema_ is not None:
        if body.schema_:
            src["schema"] = body.schema_
        else:
            src.pop("schema", None)
    if body.loader is not None:
        if body.loader:
            src["loader"] = body.loader
        else:
            src.pop("loader", None)
    if body.description is not None:
        if body.description:
            src["description"] = body.description
        else:
            src.pop("description", None)

    # 子目录变更（移动到其他文件）
    new_subdir = body.subdir
    if new_subdir is not None and new_subdir != subdir:
        new_yml_path = _models_dir(project) / new_subdir / SOURCES_FILENAME
        # 从旧文件中移除
        old_sources = [s for (sd, s, p) in all_sources if p == old_yml_path and s.get("name") != new_name]
        if old_sources:
            _write_sources_to_file(old_yml_path, old_sources)
        else:
            if old_yml_path.exists():
                old_yml_path.unlink()
        # 添加到新文件
        new_sources = [s for (sd, s, p) in all_sources if p == new_yml_path and s.get("name") != new_name]
        new_sources.append(src)
        _write_sources_to_file(new_yml_path, new_sources)
        subdir = new_subdir
    else:
        # 写回原文件
        _rebuild_file_from_all(project, all_sources, old_yml_path)

    # 更新 all_sources 中的记录（用于 refresh 前的一致性，但实际会重新 parse）
    all_sources[idx] = (subdir, src, _models_dir(project) / subdir / SOURCES_FILENAME)

    refresh_manifest(db, project)
    return _to_source_def(subdir, src)


@router.delete("/{source_name}")
def delete_source(project_id: int, source_name: str, db: Session = Depends(get_db)) -> dict:
    """删除一个 source。"""
    project = get_project_or_404(db, project_id)
    all_sources = _load_all_sources(project)
    _, _, _, yml_path = _find_source(all_sources, source_name)

    # 从文件中移除
    remaining = [
        src for (_, src, p) in all_sources
        if p == yml_path and src.get("name") != source_name
    ]
    if remaining:
        _write_sources_to_file(yml_path, remaining)
    else:
        if yml_path.exists():
            yml_path.unlink()

    refresh_manifest(db, project)
    return {"message": "已删除"}


# ---------- 表管理 ----------
@router.post("/{source_name}/tables", response_model=SourceDefinition)
def add_table(
    project_id: int,
    source_name: str,
    body: SourceTableCreate,
    db: Session = Depends(get_db),
) -> SourceDefinition:
    """给 source 添加一张表。"""
    project = get_project_or_404(db, project_id)
    all_sources = _load_all_sources(project)
    idx, subdir, src, yml_path = _find_source(all_sources, source_name)

    tables = src.get("tables", []) or []
    if any(t.get("name") == body.name for t in tables):
        raise HTTPException(status_code=400, detail=f"表已存在: {body.name}")

    entry: dict = {"name": body.name}
    if body.identifier and body.identifier != body.name:
        entry["identifier"] = body.identifier
    if body.description:
        entry["description"] = body.description

    tables.append(entry)
    src["tables"] = tables
    all_sources[idx] = (subdir, src, yml_path)
    _rebuild_file_from_all(project, all_sources, yml_path)

    refresh_manifest(db, project)
    return _to_source_def(subdir, src)


@router.put("/{source_name}/tables/{table_name}", response_model=SourceDefinition)
def update_table(
    project_id: int,
    source_name: str,
    table_name: str,
    body: SourceTableUpdate,
    db: Session = Depends(get_db),
) -> SourceDefinition:
    """更新 source 中的表。"""
    project = get_project_or_404(db, project_id)
    all_sources = _load_all_sources(project)
    idx, subdir, src, yml_path = _find_source(all_sources, source_name)

    tables = src.get("tables", []) or []
    t_idx, table = _find_table(tables, table_name)

    if body.name and body.name != table_name:
        if any(t.get("name") == body.name for t in tables):
            raise HTTPException(status_code=400, detail=f"表已存在: {body.name}")
        table["name"] = body.name
    if body.identifier is not None:
        if body.identifier and body.identifier != table.get("name", ""):
            table["identifier"] = body.identifier
        else:
            table.pop("identifier", None)
    if body.description is not None:
        if body.description:
            table["description"] = body.description
        else:
            table.pop("description", None)

    tables[t_idx] = table
    src["tables"] = tables
    all_sources[idx] = (subdir, src, yml_path)
    _rebuild_file_from_all(project, all_sources, yml_path)

    refresh_manifest(db, project)
    return _to_source_def(subdir, src)


@router.delete("/{source_name}/tables/{table_name}", response_model=SourceDefinition)
def delete_table(
    project_id: int,
    source_name: str,
    table_name: str,
    db: Session = Depends(get_db),
) -> SourceDefinition:
    """删除 source 中的一张表。"""
    project = get_project_or_404(db, project_id)
    all_sources = _load_all_sources(project)
    idx, subdir, src, yml_path = _find_source(all_sources, source_name)

    tables = src.get("tables", []) or []
    t_idx, _ = _find_table(tables, table_name)
    tables.pop(t_idx)
    src["tables"] = tables
    all_sources[idx] = (subdir, src, yml_path)
    _rebuild_file_from_all(project, all_sources, yml_path)

    refresh_manifest(db, project)
    return _to_source_def(subdir, src)
