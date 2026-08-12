"""把 dbt parse 抽取的 manifest 数据同步进数据库。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete
from sqlalchemy.orm import Session

from ..models import DagEdge, Macro, Model, Project, Source, Test
from . import dbt_service


def sync_manifest(db: Session, project: Project) -> None:
    """对某个项目执行 parse 并全量同步 models/tests/sources/edges。"""
    result = dbt_service.parse_project(project.path)
    if not result["ok"]:
        project.parse_status = "error"
        project.parsed_at = datetime.utcnow()
        db.commit()
        raise RuntimeError(result["error"])

    m = result["manifest"]
    project.parse_status = "success"
    project.parsed_at = datetime.utcnow()

    pid = project.id
    # 先清空旧数据，再全量写入（保持与磁盘一致）
    for table in (Model, Test, Source, Macro, DagEdge):
        db.execute(delete(table).where(table.project_id == pid))

    for item in m["models"]:
        db.add(
            Model(
                project_id=pid,
                unique_id=item["unique_id"],
                name=item["name"],
                resource_type=item.get("resource_type", "model"),
                file_path=item.get("file_path", ""),
                materialized=item.get("materialized", "view"),
                database=item.get("database", ""),
                schema_name=item.get("schema", ""),
                alias=item.get("alias", ""),
                tags_json=__str_list(item.get("tags", [])),
                description=item.get("description", ""),
                compiled_code=item.get("compiled_code", ""),
            )
        )
    for item in m["tests"]:
        db.add(
            Test(
                project_id=pid,
                unique_id=item["unique_id"],
                name=item["name"],
                type=item.get("type", "generic"),
                severity=item.get("severity", "ERROR"),
                file_path=item.get("file_path", ""),
                tags_json=__str_list(item.get("tags", [])),
                model_unique_id=item.get("model_unique_id", ""),
            )
        )
    for item in m["sources"]:
        db.add(
            Source(
                project_id=pid,
                unique_id=item["unique_id"],
                source_name=item.get("source_name", ""),
                name=item.get("name", ""),
                database=item.get("database", ""),
                schema_name=item.get("schema", ""),
                identifier=item.get("identifier", ""),
                loader=item.get("loader", ""),
                description=item.get("description", ""),
            )
        )
    for item in m["macros"]:
        db.add(
            Macro(
                project_id=pid,
                unique_id=item["unique_id"],
                name=item["name"],
                file_path=item.get("file_path", ""),
                description=item.get("description", ""),
                macro_sql=item.get("macro_sql", ""),
            )
        )
    for edge in m["edges"]:
        db.add(
            DagEdge(
                project_id=pid,
                parent_unique_id=edge["parent"],
                child_unique_id=edge["child"],
            )
        )
    db.commit()


def __str_list(tags) -> str:
    import json

    return json.dumps(tags if isinstance(tags, list) else [])
