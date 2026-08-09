"""DAG 数据接口：从数据库组装节点与边。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import DagEdge, Model, Source, Test
from ..schemas import DagEdgeOut, DagNode, DagOut
from ._common import get_project_or_404

router = APIRouter(prefix="/api/projects/{project_id}/dag", tags=["dag"])


@router.get("", response_model=DagOut)
def get_dag(project_id: int, db: Session = Depends(get_db)):
    get_project_or_404(db, project_id)

    nodes: list[DagNode] = []

    for model in db.scalars(
        select(Model).where(Model.project_id == project_id)
    ).all():
        nodes.append(
            DagNode(
                id=model.unique_id,
                label=model.name,
                type=model.resource_type,
                status=model.run_status,
                materialized=model.materialized,
                run_at=model.run_at,
            )
        )
    for test in db.scalars(
        select(Test).where(Test.project_id == project_id)
    ).all():
        nodes.append(
            DagNode(
                id=test.unique_id,
                label=test.name,
                type="test",
                status=test.run_status,
                run_at=test.run_at,
            )
        )
    for src in db.scalars(
        select(Source).where(Source.project_id == project_id)
    ).all():
        nodes.append(
            DagNode(
                id=src.unique_id,
                label=f"{src.source_name}.{src.name}",
                type="source",
                status="",
            )
        )

    edges = [
        DagEdgeOut(source=e.parent_unique_id, target=e.child_unique_id)
        for e in db.scalars(
            select(DagEdge).where(DagEdge.project_id == project_id)
        ).all()
    ]
    return DagOut(nodes=nodes, edges=edges)
