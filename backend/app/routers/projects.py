"""项目 CRUD 接口。"""
from pathlib import Path

import yaml
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Project
from ..schemas import (
    MessageResponse,
    ProfileUpdate,
    ProjectCreate,
    ProjectRead,
    ProjectUpdate,
)
from ..services import dbt_service, sync_service
from ._common import get_project_or_404

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=list[ProjectRead])
def list_projects(db: Session = Depends(get_db)):
    """项目列表。"""
    return db.scalars(select(Project).order_by(Project.created_at.desc())).all()


@router.post("", response_model=ProjectRead, status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    """创建项目：在磁盘生成 dbt 脚手架，并写入数据库。"""
    # slug 唯一性校验
    slug = dbt_service.slugify(payload.name)
    if db.scalar(select(Project).where(Project.slug == slug)):
        raise HTTPException(status_code=409, detail=f"已存在同 slug 的项目: {slug}")

    try:
        project_dir, dbt_version = dbt_service.create_scaffold(payload.name, payload.adapter)
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    project = Project(
        name=payload.name,
        slug=slug,
        path=str(project_dir),
        adapter=payload.adapter,
        description=payload.description,
        dbt_version=dbt_version,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: int, db: Session = Depends(get_db)):
    """项目详情。"""
    return get_project_or_404(db, project_id)


@router.post("/{project_id}/parse", response_model=ProjectRead)
def parse_project(project_id: int, db: Session = Depends(get_db)):
    """执行 dbt parse 并把 models/tests/sources/edges 同步进库。"""
    project = get_project_or_404(db, project_id)
    try:
        sync_service.sync_manifest(db, project)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.refresh(project)
    return project


@router.get("/{project_id}/profiles")
def get_profiles(project_id: int, db: Session = Depends(get_db)):
    """返回 profiles.yml 内容（连接配置）。"""
    project = get_project_or_404(db, project_id)
    p = Path(project.path) / "profiles.yml"
    content = p.read_text(encoding="utf-8") if p.exists() else ""
    return {"content": content}


@router.put("/{project_id}/profiles", response_model=MessageResponse)
def save_profiles(project_id: int, payload: ProfileUpdate, db: Session = Depends(get_db)):
    """保存 profiles.yml 连接配置。"""
    project = get_project_or_404(db, project_id)
    try:
        yaml.safe_load(payload.content)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"YAML 格式错误: {exc}") from exc
    (Path(project.path) / "profiles.yml").write_text(payload.content, encoding="utf-8")
    return MessageResponse(message="连接配置已保存")


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: int, payload: ProjectUpdate, db: Session = Depends(get_db)
):
    """更新项目信息（名称/描述/adapter）。"""
    project = get_project_or_404(db, project_id)
    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"] != project.name:
        new_slug = dbt_service.slugify(data["name"])
        if db.scalar(select(Project).where(Project.slug == new_slug, Project.id != project_id)):
            raise HTTPException(status_code=409, detail=f"已存在同 slug 的项目: {new_slug}")
        project.slug = new_slug
    for field, value in data.items():
        if field != "name":
            setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", response_model=MessageResponse)
def delete_project(project_id: int, db: Session = Depends(get_db)):
    """删除项目：删除磁盘目录与数据库记录。"""
    project = get_project_or_404(db, project_id)
    try:
        dbt_service.remove_scaffold(project.path)
    except PermissionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.delete(project)
    db.commit()
    return MessageResponse(message="项目已删除")
