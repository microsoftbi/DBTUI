"""Model 资源管理接口（读写磁盘 models/**/*.sql 并重新 parse）。"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Model, Project
from ..schemas import MessageResponse, ModelCreate, ModelRead, ModelUpdate
from ..services import dbt_service
from ._common import get_project_or_404, refresh_manifest

router = APIRouter(prefix="/api/projects/{project_id}/models", tags=["models"])


def _model_path(project: Project, filename: str) -> Path:
    return Path(project.path) / "models" / filename


@router.get("", response_model=list[ModelRead])
def list_models(project_id: int, db: Session = Depends(get_db)):
    get_project_or_404(db, project_id)
    return db.scalars(
        select(Model).where(Model.project_id == project_id).order_by(Model.name)
    ).all()


@router.post("", response_model=ModelRead, status_code=201)
def create_model(
    project_id: int, payload: ModelCreate, db: Session = Depends(get_db)
):
    project = get_project_or_404(db, project_id)
    filename = f"{payload.name}.sql"
    # 支持子目录（如 staging / core / marts），对应不同数据库层
    subdir = (payload.subdir or "").strip("/")
    models_dir = Path(project.path) / "models"
    target_dir = models_dir / subdir if subdir else models_dir
    # 安全校验：防止路径遍历（subdir 已通过 schema pattern 校验，这里再兜底）
    target_dir = target_dir.resolve()
    models_dir_resolved = models_dir.resolve()
    if not str(target_dir).startswith(str(models_dir_resolved)):
        raise HTTPException(status_code=400, detail="subdir 路径不合法")
    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / filename
    if file_path.exists():
        raise HTTPException(status_code=409, detail=f"模型 {payload.name} 已存在")
    file_path.write_text(payload.sql, encoding="utf-8")
    refresh_manifest(db, project)
    model = db.scalar(
        select(Model).where(Model.project_id == project_id, Model.name == payload.name)
    )
    if model is None:
        raise HTTPException(status_code=400, detail="parse 后未找到该模型，请检查 SQL")
    return model


@router.get("/{model_id}/sql")
def get_model_sql(project_id: int, model_id: int, db: Session = Depends(get_db)):
    """返回模型磁盘上的原始 SQL 内容（供编辑器使用）。"""
    project = get_project_or_404(db, project_id)
    model = db.get(Model, model_id)
    if model is None or model.project_id != project_id:
        raise HTTPException(status_code=404, detail="模型不存在")
    path = Path(project.path) / model.file_path
    sql = path.read_text(encoding="utf-8") if path.exists() else ""
    return {
        "model_id": model.id,
        "name": model.name,
        "file_path": model.file_path,
        "materialized": model.materialized,
        "sql": sql,
    }


@router.put("/{model_id}", response_model=ModelRead)
def update_model(
    project_id: int, model_id: int, payload: ModelUpdate, db: Session = Depends(get_db)
):
    project = get_project_or_404(db, project_id)
    model = db.get(Model, model_id)
    if model is None or model.project_id != project_id:
        raise HTTPException(status_code=404, detail="模型不存在")
    target_uid = model.unique_id
    path = Path(project.path) / model.file_path
    if payload.name and payload.name != model.name:
        new_path = path.parent / f"{payload.name}.sql"
        if new_path.exists():
            raise HTTPException(status_code=409, detail=f"模型 {payload.name} 已存在")
        path.rename(new_path)
        path = new_path
    if payload.sql is not None:
        path.write_text(payload.sql, encoding="utf-8")
    target_name = payload.name or model.name
    if payload.materialized:
        dbt_service.set_model_materialized(project.path, target_name, payload.materialized)
    refresh_manifest(db, project)
    # parse 会重建记录导致 id 变化，改用 unique_id / name 重新查找
    refreshed = db.scalar(
        select(Model).where(Model.project_id == project_id, Model.unique_id == target_uid)
    )
    if refreshed is None:
        refreshed = db.scalar(
            select(Model).where(Model.project_id == project_id, Model.name == target_name)
        )
    if refreshed is None:
        raise HTTPException(status_code=400, detail="重新解析后未找到该模型")
    return refreshed


@router.delete("/{model_id}", response_model=MessageResponse)
def delete_model(project_id: int, model_id: int, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    model = db.get(Model, model_id)
    if model is None or model.project_id != project_id:
        raise HTTPException(status_code=404, detail="模型不存在")
    path = Path(project.path) / model.file_path
    if path.exists():
        path.unlink()
    refresh_manifest(db, project)
    return MessageResponse(message="模型已删除")
