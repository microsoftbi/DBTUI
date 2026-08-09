"""Test 资源接口：列表 + singular test 的创建/读取/删除。"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Project, Test
from ..schemas import MessageResponse, TestCreate, TestRead
from ._common import get_project_or_404, refresh_manifest

router = APIRouter(prefix="/api/projects/{project_id}/tests", tags=["tests"])


@router.get("", response_model=list[TestRead])
def list_tests(project_id: int, db: Session = Depends(get_db)):
    get_project_or_404(db, project_id)
    return db.scalars(
        select(Test).where(Test.project_id == project_id).order_by(Test.name)
    ).all()


@router.post("", response_model=TestRead, status_code=201)
def create_test(
    project_id: int, payload: TestCreate, db: Session = Depends(get_db)
):
    """创建 singular test：写入 tests/<name>.sql 并重新 parse。"""
    project = get_project_or_404(db, project_id)
    path = Path(project.path) / "tests" / f"{payload.name}.sql"
    if path.exists():
        raise HTTPException(status_code=409, detail=f"测试 {payload.name} 已存在")
    path.write_text(payload.sql, encoding="utf-8")
    refresh_manifest(db, project)
    test = db.scalar(
        select(Test).where(Test.project_id == project_id, Test.name == payload.name)
    )
    if test is None:
        raise HTTPException(status_code=400, detail="parse 后未找到该测试，请检查 SQL")
    return test


@router.get("/{test_id}/sql")
def get_test_sql(project_id: int, test_id: int, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    test = db.get(Test, test_id)
    if test is None or test.project_id != project_id:
        raise HTTPException(status_code=404, detail="测试不存在")
    path = Path(project.path) / test.file_path
    sql = path.read_text(encoding="utf-8") if path.exists() else ""
    return {
        "test_id": test.id,
        "name": test.name,
        "file_path": test.file_path,
        "type": test.type,
        "sql": sql,
    }


@router.delete("/{test_id}", response_model=MessageResponse)
def delete_test(project_id: int, test_id: int, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    test = db.get(Test, test_id)
    if test is None or test.project_id != project_id:
        raise HTTPException(status_code=404, detail="测试不存在")
    path = Path(project.path) / test.file_path
    if path.exists():
        path.unlink()
    refresh_manifest(db, project)
    return MessageResponse(message="测试已删除")
