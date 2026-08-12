"""Macro 资源管理接口（读写磁盘 macros/**/*.sql 并重新 parse）。"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Macro, Project
from ..schemas import MacroCreate, MacroRead, MacroUpdate, MessageResponse
from ._common import get_project_or_404, refresh_manifest

router = APIRouter(prefix="/api/projects/{project_id}/macros", tags=["macros"])


def _macro_path(project: Project, filename: str) -> Path:
    return Path(project.path) / "macros" / filename


@router.get("", response_model=list[MacroRead])
def list_macros(project_id: int, db: Session = Depends(get_db)):
    get_project_or_404(db, project_id)
    return db.scalars(
        select(Macro).where(Macro.project_id == project_id).order_by(Macro.name)
    ).all()


@router.post("", response_model=MacroRead, status_code=201)
def create_macro(
    project_id: int, payload: MacroCreate, db: Session = Depends(get_db)
):
    project = get_project_or_404(db, project_id)
    filename = f"{payload.name}.sql"
    subdir = (payload.subdir or "").strip("/")
    macros_dir = Path(project.path) / "macros"
    target_dir = macros_dir / subdir if subdir else macros_dir
    # 安全校验：防止路径遍历
    target_dir = target_dir.resolve()
    macros_dir_resolved = macros_dir.resolve()
    if not str(target_dir).startswith(str(macros_dir_resolved)):
        raise HTTPException(status_code=400, detail="subdir 路径不合法")
    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / filename
    if file_path.exists():
        raise HTTPException(status_code=409, detail=f"macro {payload.name} 已存在")
    file_path.write_text(payload.sql, encoding="utf-8")
    refresh_manifest(db, project)
    macro = db.scalar(
        select(Macro).where(Macro.project_id == project_id, Macro.name == payload.name)
    )
    if macro is None:
        raise HTTPException(status_code=400, detail="parse 后未找到该 macro，请检查 SQL")
    return macro


@router.get("/{macro_id}/sql")
def get_macro_sql(project_id: int, macro_id: int, db: Session = Depends(get_db)):
    """返回 macro 磁盘上的原始 SQL 内容（供编辑器使用）。"""
    project = get_project_or_404(db, project_id)
    macro = db.get(Macro, macro_id)
    if macro is None or macro.project_id != project_id:
        raise HTTPException(status_code=404, detail="macro 不存在")
    path = Path(project.path) / macro.file_path
    sql = path.read_text(encoding="utf-8") if path.exists() else ""
    return {
        "macro_id": macro.id,
        "name": macro.name,
        "file_path": macro.file_path,
        "sql": sql,
    }


@router.put("/{macro_id}", response_model=MacroRead)
def update_macro(
    project_id: int, macro_id: int, payload: MacroUpdate, db: Session = Depends(get_db)
):
    project = get_project_or_404(db, project_id)
    macro = db.get(Macro, macro_id)
    if macro is None or macro.project_id != project_id:
        raise HTTPException(status_code=404, detail="macro 不存在")
    target_uid = macro.unique_id
    path = Path(project.path) / macro.file_path
    if payload.name and payload.name != macro.name:
        new_path = path.parent / f"{payload.name}.sql"
        if new_path.exists():
            raise HTTPException(status_code=409, detail=f"macro {payload.name} 已存在")
        path.rename(new_path)
        path = new_path
    if payload.sql is not None:
        path.write_text(payload.sql, encoding="utf-8")
    target_name = payload.name or macro.name
    refresh_manifest(db, project)
    # parse 会重建记录导致 id 变化，改用 unique_id / name 重新查找
    refreshed = db.scalar(
        select(Macro).where(Macro.project_id == project_id, Macro.unique_id == target_uid)
    )
    if refreshed is None:
        refreshed = db.scalar(
            select(Macro).where(Macro.project_id == project_id, Macro.name == target_name)
        )
    if refreshed is None:
        raise HTTPException(status_code=400, detail="重新解析后未找到该 macro")
    return refreshed


@router.delete("/{macro_id}", response_model=MessageResponse)
def delete_macro(project_id: int, macro_id: int, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    macro = db.get(Macro, macro_id)
    if macro is None or macro.project_id != project_id:
        raise HTTPException(status_code=404, detail="macro 不存在")
    path = Path(project.path) / macro.file_path
    if path.exists():
        path.unlink()
    refresh_manifest(db, project)
    return MessageResponse(message="macro 已删除")
