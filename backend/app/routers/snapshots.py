"""Snapshot 资源管理接口（读写磁盘 snapshots/*.sql 并重新 parse）。"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Model, Project
from ..schemas import MessageResponse, SnapshotCreate, SnapshotRead, SnapshotUpdate
from ._common import get_project_or_404, refresh_manifest

router = APIRouter(prefix="/api/projects/{project_id}/snapshots", tags=["snapshots"])


def _snapshot_path(project: Project, filename: str) -> Path:
    return Path(project.path) / "snapshots" / filename


@router.get("", response_model=list[SnapshotRead])
def list_snapshots(project_id: int, db: Session = Depends(get_db)):
    get_project_or_404(db, project_id)
    return db.scalars(
        select(Model).where(
            Model.project_id == project_id,
            Model.resource_type == "snapshot",
        ).order_by(Model.name)
    ).all()


@router.post("", response_model=SnapshotRead, status_code=201)
def create_snapshot(
    project_id: int, payload: SnapshotCreate, db: Session = Depends(get_db)
):
    project = get_project_or_404(db, project_id)
    filename = f"{payload.name}.sql"
    snapshots_dir = Path(project.path) / "snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    file_path = snapshots_dir / filename
    if file_path.exists():
        raise HTTPException(status_code=409, detail=f"快照 {payload.name} 已存在")
    file_path.write_text(payload.sql, encoding="utf-8")
    refresh_manifest(db, project)
    snapshot = db.scalar(
        select(Model).where(
            Model.project_id == project_id,
            Model.name == payload.name,
            Model.resource_type == "snapshot",
        )
    )
    if snapshot is None:
        raise HTTPException(status_code=400, detail="parse 后未找到该快照，请检查 SQL")
    return snapshot


@router.get("/{snapshot_id}/sql")
def get_snapshot_sql(project_id: int, snapshot_id: int, db: Session = Depends(get_db)):
    """返回快照磁盘上的原始 SQL 内容（供编辑器使用）。"""
    project = get_project_or_404(db, project_id)
    snapshot = db.get(Model, snapshot_id)
    if snapshot is None or snapshot.project_id != project_id or snapshot.resource_type != "snapshot":
        raise HTTPException(status_code=404, detail="快照不存在")
    path = Path(project.path) / snapshot.file_path
    sql = path.read_text(encoding="utf-8") if path.exists() else ""
    return {
        "snapshot_id": snapshot.id,
        "name": snapshot.name,
        "file_path": snapshot.file_path,
        "sql": sql,
    }


@router.put("/{snapshot_id}", response_model=SnapshotRead)
def update_snapshot(
    project_id: int, snapshot_id: int, payload: SnapshotUpdate, db: Session = Depends(get_db)
):
    project = get_project_or_404(db, project_id)
    snapshot = db.get(Model, snapshot_id)
    if snapshot is None or snapshot.project_id != project_id or snapshot.resource_type != "snapshot":
        raise HTTPException(status_code=404, detail="快照不存在")
    target_uid = snapshot.unique_id
    path = Path(project.path) / snapshot.file_path
    if payload.sql is not None:
        sql_content = payload.sql
    else:
        sql_content = path.read_text(encoding="utf-8") if path.exists() else ""

    if payload.name and payload.name != snapshot.name:
        new_path = path.parent / f"{payload.name}.sql"
        if new_path.exists():
            raise HTTPException(status_code=409, detail=f"快照 {payload.name} 已存在")
        # snapshot 名称由 {% snapshot name %} 标签决定，重命名需同步修改 SQL 内容
        import re
        sql_content = re.sub(
            r"{%\s*snapshot\s+" + re.escape(snapshot.name) + r"\s*%}",
            f"{{% snapshot {payload.name} %}}",
            sql_content,
            count=1,
        )
        sql_content = re.sub(
            r"{%\s*endsnapshot\s*%}",
            "{% endsnapshot %}",
            sql_content,
            count=1,
        )
        if path.exists():
            path.rename(new_path)
        path = new_path

    path.write_text(sql_content, encoding="utf-8")
    target_name = payload.name or snapshot.name
    refresh_manifest(db, project)
    # parse 会重建记录导致 id 变化，改用 unique_id / name 重新查找
    refreshed = db.scalar(
        select(Model).where(
            Model.project_id == project_id,
            Model.unique_id == target_uid,
            Model.resource_type == "snapshot",
        )
    )
    if refreshed is None:
        refreshed = db.scalar(
            select(Model).where(
                Model.project_id == project_id,
                Model.name == target_name,
                Model.resource_type == "snapshot",
            )
        )
    if refreshed is None:
        raise HTTPException(status_code=400, detail="重新解析后未找到该快照")
    return refreshed


@router.delete("/{snapshot_id}", response_model=MessageResponse)
def delete_snapshot(project_id: int, snapshot_id: int, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    snapshot = db.get(Model, snapshot_id)
    if snapshot is None or snapshot.project_id != project_id or snapshot.resource_type != "snapshot":
        raise HTTPException(status_code=404, detail="快照不存在")
    path = Path(project.path) / snapshot.file_path
    if path.exists():
        path.unlink()
    refresh_manifest(db, project)
    return MessageResponse(message="快照已删除")
