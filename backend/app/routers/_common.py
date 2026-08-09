"""路由共享工具函数。"""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Project
from ..services import sync_service


def get_project_or_404(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project


def refresh_manifest(db: Session, project: Project) -> None:
    """模型/测试文件变更后重新 parse 同步。"""
    try:
        sync_service.sync_manifest(db, project)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=f"重新解析失败: {exc}")
