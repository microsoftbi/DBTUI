"""运行接口：触发 run/test/compile/build，支持 WebSocket 实时日志流。"""
from __future__ import annotations

import asyncio
import json
import re
import subprocess
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import SessionLocal, get_db
from ..models import Model, Project, RunHistory, RunResult, Test
from ..schemas import MessageResponse, RunHistoryRead, RunResultRead, RunStart
from ..services import dbt_service
from ._common import get_project_or_404

router = APIRouter(prefix="/api/projects/{project_id}/runs", tags=["runs"])
ws_router = APIRouter(tags=["runs-ws"])


def _run_args(run_type: str, selection: str) -> list[str]:
    args = [run_type]
    if selection:
        args += ["--select", selection]
    return args


# dbt-fusion 结果行： "Succeeded [0.01s] model main.example (view)"
#                     "Passed [0.10s] test  not_null_example_id"
_STATUS_RE = re.compile(
    r"^\s*(Succeeded|Passed|Failed|Errored|Skipped|Warned)\s+\[\s*[\d.]+\s*s\]\s+"
    r"(model|test|seed|snapshot)\s+([^\s(]+)"
)
_STATUS_MAP = {
    "Succeeded": "success",
    "Passed": "pass",
    "Failed": "fail",
    "Errored": "error",
    "Skipped": "skipped",
    "Warned": "warn",
}


def _extract_node_status(line: str) -> tuple[str, str] | None:
    """从 dbt 结果行提取 (节点名, 状态)；无法识别返回 None。"""
    m = _STATUS_RE.match(line)
    if not m:
        return None
    keyword, rtype, name = m.groups()
    if rtype == "model":
        # model 行为 schema.name，取最后一节
        name = name.split(".")[-1]
    return name, _STATUS_MAP.get(keyword, keyword.lower())


def _ls_names(project_path: str, run_type: str, selection: str) -> list[str]:
    """用 dbt ls 预判本次运行会涉及的节点名，用于运行中点亮。"""
    args = ["dbt", "ls", "--output", "json"]
    rt = {"run": "model", "compile": "model", "test": "test"}.get(run_type)
    if rt:
        args += ["--resource-type", rt]
    if selection:
        args += ["--select", selection]
    try:
        res = subprocess.run(
            args, cwd=project_path, capture_output=True, text=True, timeout=120
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return []
    names: list[str] = []
    for line in (res.stdout or "").splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                obj = json.loads(line)
                if obj.get("name"):
                    names.append(obj["name"])
            except json.JSONDecodeError:
                pass
    return names


def _apply_results(db: Session, project_id: int, run_id: int, results: list[dict]) -> None:
    """把运行结果写回 models/tests 的状态，并记录 run_results。"""
    for r in results:
        uid = r["unique_id"]
        status = r["status"]
        db.add(
            RunResult(
                run_id=run_id,
                unique_id=uid,
                status=status,
                message=r.get("message", ""),
                execution_time=r.get("execution_time", 0),
            )
        )
        # 更新资源状态
        model = db.scalar(
            select(Model).where(Model.project_id == project_id, Model.unique_id == uid)
        )
        if model:
            model.run_status = status
            model.run_at = datetime.utcnow()
            continue
        test = db.scalar(
            select(Test).where(Test.project_id == project_id, Test.unique_id == uid)
        )
        if test:
            test.run_status = status
            test.run_at = datetime.utcnow()
    db.commit()


# ---------- REST：同步运行 ----------
@router.post("", response_model=RunHistoryRead, status_code=202)
def start_run(project_id: int, payload: RunStart, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    run = RunHistory(
        project_id=project_id,
        run_type=payload.run_type,
        selection=payload.selection,
        status="running",
        started_at=datetime.utcnow(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    lines: list[str] = []
    result = dbt_service.run_dbt_streaming(
        project.path, _run_args(payload.run_type, payload.selection), lines.append,
        run_id=run.id,
    )
    run.status = (
        "cancelled"
        if result["cancelled"]
        else ("success" if result["returncode"] == 0 else "error")
    )
    run.log = "".join(lines)
    run.finished_at = datetime.utcnow()
    _apply_results(db, project_id, run.id, result["results"])
    return run


@router.post("/{run_id}/cancel", response_model=MessageResponse)
def cancel_run(project_id: int, run_id: int, db: Session = Depends(get_db)):
    """取消一个正在运行的 dbt 命令。"""
    run = db.get(RunHistory, run_id)
    if run is None or run.project_id != project_id:
        raise HTTPException(status_code=404, detail="运行记录不存在")
    dbt_service.cancel_proc(run_id)
    return MessageResponse(message="已请求取消")


@router.get("", response_model=list[RunHistoryRead])
def list_runs(project_id: int, db: Session = Depends(get_db)):
    get_project_or_404(db, project_id)
    return db.scalars(
        select(RunHistory)
        .where(RunHistory.project_id == project_id)
        .order_by(RunHistory.id.desc())
        .limit(100)
    ).all()


@router.get("/{run_id}")
def run_detail(project_id: int, run_id: int, db: Session = Depends(get_db)):
    run = db.get(RunHistory, run_id)
    if run is None or run.project_id != project_id:
        raise HTTPException(status_code=404, detail="运行记录不存在")
    results = db.scalars(
        select(RunResult).where(RunResult.run_id == run_id)
    ).all()
    return {
        "run": RunHistoryRead.model_validate(run),
        "results": [RunResultRead.model_validate(r) for r in results],
        "log": run.log,
    }


# ---------- WebSocket：实时日志流 ----------
@ws_router.websocket("/ws/projects/{project_id}/runs")
async def ws_run(websocket: WebSocket, project_id: int):
    await websocket.accept()
    db = SessionLocal()
    run: RunHistory | None = None
    try:
        project = db.get(Project, project_id)
        if project is None:
            await websocket.send_json({"type": "error", "message": "项目不存在"})
            await websocket.close()
            return

        payload = await websocket.receive_json()
        run_type = payload.get("run_type", "run")
        selection = payload.get("selection", "")

        run = RunHistory(
            project_id=project_id,
            run_type=run_type,
            selection=selection,
            status="running",
            started_at=datetime.utcnow(),
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        await websocket.send_json({"type": "start", "run_id": run.id})

        # 预判本次运行涉及的节点，前端据此点亮为“运行中”
        names = _ls_names(project.path, run_type, selection)
        if names:
            await websocket.send_json({"type": "running", "names": names})

        loop = asyncio.get_running_loop()
        q: asyncio.Queue = asyncio.Queue()

        def line_cb(line: str):
            loop.call_soon_threadsafe(q.put_nowait, line)

        async def pump():
            while True:
                line = await q.get()
                if line is None:
                    break
                await websocket.send_json({"type": "log", "line": line})
                status = _extract_node_status(line)
                if status:
                    await websocket.send_json(
                        {"type": "node_status", "name": status[0], "status": status[1]}
                    )

        pump_task = asyncio.create_task(pump())
        result = await loop.run_in_executor(
            None,
            lambda: dbt_service.run_dbt_streaming(
                project.path, _run_args(run_type, selection), line_cb, run_id=run.id
            ),
        )
        await q.put(None)
        await pump_task

        run.status = (
            "cancelled"
            if result["cancelled"]
            else ("success" if result["returncode"] == 0 else "error")
        )
        run.finished_at = datetime.utcnow()
        _apply_results(db, project_id, run.id, result["results"])

        await websocket.send_json(
            {
                "type": "done",
                "returncode": result["returncode"],
                "cancelled": result["cancelled"],
                "results": result["results"],
            }
        )
    except WebSocketDisconnect:
        # 客户端断连：终止子进程并标记运行状态
        if run is not None:
            dbt_service.cancel_proc(run.id)
            run.status = "cancelled"
            run.finished_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()
        try:
            await websocket.close()
        except Exception:
            pass
