"""DBT 项目脚手架与命令封装服务。

- 脚手架：在磁盘生成标准 dbt 项目目录 + dbt_project.yml + profiles.yml
- 解析：执行 `dbt parse` 并解析 target/manifest.json
- 运行：封装 dbt CLI 子进程，支持逐行日志回调
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Callable

import yaml

from ..config import settings


# ---------- 工具 ----------
def slugify(name: str) -> str:
    """把项目名称转成适合做目录名的 slug。"""
    slug = re.sub(r"[^a-zA-Z0-9_\-]+", "-", name.strip()).strip("-").lower()
    return slug or "project"


def detect_dbt_version() -> str:
    """探测已安装的 dbt-core 版本，未安装返回空字符串。"""
    try:
        result = subprocess.run(
            [settings.dbt_bin, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # dbt-core 输出多行，第一行通常是 "Core:" 之前的内容，取 installed 版本
        output = result.stdout or ""
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("- installed:"):
                return line.split(":", 1)[1].strip()
        # 兼容 dbt-fusion 格式
        first_line = output.splitlines()[0] if output else ""
        return first_line.strip()
    except (FileNotFoundError, subprocess.SubprocessError):
        return ""


def _ensure_projects_root() -> Path:
    root = settings.projects_root
    root.mkdir(parents=True, exist_ok=True)
    return root


# ---------- 脚手架 ----------
def _profiles_yml(adapter: str, slug: str) -> str:
    """根据 adapter 生成 profiles.yml。

    - sqlserver: 三层分库（stage_db / core_db / mart_db），主连接指向 stage_db
    - 其它 adapter: 生成占位连接，用户可在 profiles 接口中配置
    """
    if adapter == "sqlserver":
        return (
            f"{slug}:\n"
            f"  target: dev\n"
            f"  outputs:\n"
            f"    dev:\n"
            f"      type: sqlserver\n"
            f"      driver: 'ODBC Driver 18 for SQL Server'\n"
            f"      server: 192.168.0.116\n"
            f"      port: 1433\n"
            f"      database: stage_db\n"
            f"      schema: dbo\n"
            f"      user: sa\n"
            f"      password: Passw0rd\n"
            f"      trust_cert: true\n"
            f"      threads: 4\n"
        )
    # 其它 adapter 生成占位连接，用户可在 profiles 接口中配置
    return (
        f"{slug}:\n"
        f"  target: dev\n"
        f"  outputs:\n"
        f"    dev:\n"
        f"      type: {adapter}\n"
        f"      host: localhost\n"
        f"      port: 5432\n"
        f"      user: user\n"
        f"      password: password\n"
        f"      dbname: {slug}\n"
        f"      schema: public\n"
        f"      threads: 4\n"
    )


def create_scaffold(name: str, adapter: str) -> tuple[Path, str]:
    """在 projects_root 下创建标准 dbt 项目结构，返回 (目录绝对路径, dbt_version)。"""
    root = _ensure_projects_root()
    slug = slugify(name)
    project_dir = root / slug

    if project_dir.exists():
        raise FileExistsError(f"项目目录已存在: {project_dir}")

    for sub in [
        "models/staging",
        "models/core",
        "models/marts",
        "macros",
        "seeds",
        "snapshots",
        "analyses",
        "tests",
        "logs",
        "target",
    ]:
        (project_dir / sub).mkdir(parents=True, exist_ok=True)

    (project_dir / "dbt_project.yml").write_text(
        _DEFAULT_DBT_PROJECT_YML.format(name=slug), encoding="utf-8"
    )
    (project_dir / "profiles.yml").write_text(
        _profiles_yml(adapter, slug), encoding="utf-8"
    )
    # 示例模型 + 示例 schema（含一个 generic test，便于演示 DAG）
    (project_dir / "models" / "example.sql").write_text(
        "SELECT 1 AS id\n", encoding="utf-8"
    )
    (project_dir / "models" / "schema.yml").write_text(
        _DEFAULT_SCHEMA_YML, encoding="utf-8"
    )
    (project_dir / "README.md").write_text(
        f"# {name}\n\n由 DBT UI 脚手架生成的项目。\n", encoding="utf-8"
    )

    return project_dir, detect_dbt_version()


def remove_scaffold(project_path: str) -> None:
    """删除磁盘上的项目目录（安全：仅允许删除 projects_root 下的目录）。"""
    path = Path(project_path).resolve()
    root = settings.projects_root.resolve()
    if not path.is_relative_to(root):
        raise PermissionError(f"禁止删除 projects_root 之外的目录: {path}")
    if path.exists():
        shutil.rmtree(path)


def set_model_materialized(project_path: str, model_name: str, materialized: str) -> None:
    """设置模型的物化策略：优先就地编辑已有的 schema yml，否则新建 <name>.yml。"""
    models_dir = Path(project_path) / "models"
    schema_files = sorted(models_dir.rglob("*.yml")) + sorted(models_dir.rglob("*.yaml"))
    target_file: Path | None = None
    for f in schema_files:
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        models = (data or {}).get("models") or []
        if any(m.get("name") == model_name for m in models):
            target_file = f
            break

    if target_file is not None:
        data = yaml.safe_load(target_file.read_text(encoding="utf-8"))
        for m in data.get("models") or []:
            if m.get("name") == model_name:
                config = m.setdefault("config", {})
                config["materialized"] = materialized
        target_file.write_text(
            yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )
    else:
        (models_dir / f"{model_name}.yml").write_text(
            "version: 2\n\n"
            "models:\n"
            f"  - name: {model_name}\n"
            "    config:\n"
            f"      materialized: {materialized}\n",
            encoding="utf-8",
        )


# ---------- 解析（dbt parse -> manifest） ----------
def parse_project(project_path: str) -> dict:
    """执行 dbt parse 并返回结构化结果。

    返回 {"ok": bool, "error": str, "manifest": {...}}
    manifest 含 models/tests/sources/edges。
    """
    path = Path(project_path)
    result = subprocess.run(
        [settings.dbt_bin, "parse"],
        cwd=path,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        return {"ok": False, "error": (result.stderr or result.stdout), "manifest": None}

    manifest_path = path / "target" / "manifest.json"
    if not manifest_path.exists():
        return {"ok": False, "error": "未找到 target/manifest.json", "manifest": None}

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {"ok": True, "error": "", "manifest": _extract_manifest(manifest)}


def __unique_key_str(val) -> str:
    """unique_key 可能是字符串或列表，统一转成逗号分隔字符串。"""
    if val is None:
        return ""
    if isinstance(val, list):
        return ",".join(str(v) for v in val)
    return str(val)


def _extract_manifest(manifest: dict) -> dict:
    """从原始 manifest 抽取 UI 需要的数据。"""
    models, tests, sources, macros, edges = [], [], [], [], []
    parent_map = manifest.get("parent_map", {})
    metadata = manifest.get("metadata", {}) or {}
    project_name = metadata.get("project_name", "")

    for unique_id, node in manifest.get("nodes", {}).items():
        config = node.get("config", {}) or {}
        common = {
            "unique_id": unique_id,
            "name": node.get("name", ""),
            "file_path": node.get("original_file_path", ""),
            "tags": node.get("tags", []),
        }
        rt = node.get("resource_type", "")
        if rt == "test":
            tests.append(
                {
                    **common,
                    "type": "singular" if node.get("test_metadata") is None else "generic",
                    "severity": config.get("severity", "ERROR"),
                    "model_unique_id": _test_model(unique_id, parent_map),
                }
            )
        else:
            models.append(
                {
                    **common,
                    "resource_type": rt,
                    "materialized": config.get("materialized", "view"),
                    "database": node.get("database", ""),
                    "schema": node.get("schema", ""),
                    "alias": node.get("alias", ""),
                    "description": node.get("description", ""),
                    "compiled_code": node.get("compiled_code", "")
                    or node.get("raw_code", ""),
                    # snapshot 特有配置
                    "snapshot_strategy": config.get("strategy", "") or "",
                    "target_schema": config.get("target_schema", "") or "",
                    "unique_key": __unique_key_str(config.get("unique_key")),
                }
            )

    for unique_id, src in manifest.get("sources", {}).items():
        sources.append(
            {
                "unique_id": unique_id,
                "source_name": src.get("source_name", ""),
                "name": src.get("name", ""),
                "database": src.get("database", ""),
                "schema": src.get("schema", ""),
                "identifier": src.get("identifier", ""),
                "loader": src.get("loader", ""),
                "description": src.get("description", ""),
            }
        )

    # 只提取当前项目自身的 macro（排除 dbt 内置和第三方包）
    for unique_id, macro in manifest.get("macros", {}).items():
        if macro.get("package_name") != project_name:
            continue
        macros.append(
            {
                "unique_id": unique_id,
                "name": macro.get("name", ""),
                "file_path": macro.get("original_file_path", ""),
                "description": macro.get("description", ""),
                "macro_sql": macro.get("macro_sql", "") or macro.get("raw_sql", ""),
            }
        )

    # parent_map[child] = [parents]，生成 parent -> child 边
    for child, parents in parent_map.items():
        for parent in parents:
            edges.append({"parent": parent, "child": child})

    return {
        "models": models,
        "tests": tests,
        "sources": sources,
        "macros": macros,
        "edges": edges,
    }


def _test_model(unique_id: str, parent_map: dict) -> str:
    """generic test 的父节点通常是对应的模型；singular test 需要从文件名推断。"""
    parents = parent_map.get(unique_id, [])
    for p in parents:
        if p.startswith("model."):
            return p
    return ""


# ---------- 运行（dbt CLI 子进程，逐行回调） ----------
# 运行中进程注册表，用于取消
_ACTIVE_PROCS: dict[int, subprocess.Popen] = {}
_CANCELLED: set[int] = set()
_lock = threading.Lock()


def _register_proc(run_id: int, proc: subprocess.Popen) -> None:
    with _lock:
        _ACTIVE_PROCS[run_id] = proc


def _unregister_proc(run_id: int) -> None:
    with _lock:
        _ACTIVE_PROCS.pop(run_id, None)


def cancel_proc(run_id: int) -> bool:
    """请求取消一个运行：标记并终止对应子进程。"""
    with _lock:
        _CANCELLED.add(run_id)
        proc = _ACTIVE_PROCS.get(run_id)
    if proc is not None:
        proc.terminate()
        return True
    return False


def run_dbt_streaming(
    project_path: str,
    args: list[str],
    line_callback: Callable[[str], None],
    run_id: int | None = None,
) -> dict:
    """执行 dbt 命令，逐行调用 line_callback 推送日志。

    返回 {"returncode": int, "results": [...], "cancelled": bool}。
    """
    path = Path(project_path)
    proc = subprocess.Popen(
        [settings.dbt_bin, *args],
        cwd=path,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    if run_id is not None:
        _register_proc(run_id, proc)
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            line_callback(line)
        proc.wait()
    finally:
        if run_id is not None:
            _unregister_proc(run_id)
            cancelled = run_id in _CANCELLED
            _CANCELLED.discard(run_id)
        else:
            cancelled = False
    return {
        "returncode": proc.returncode,
        "results": _parse_run_results(path),
        "cancelled": cancelled,
    }


def _parse_run_results(project_path: Path) -> list[dict]:
    results_file = project_path / "target" / "run_results.json"
    if not results_file.exists():
        return []
    try:
        data = json.loads(results_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    out = []
    for r in data.get("results", []):
        out.append(
            {
                "unique_id": r.get("unique_id", ""),
                "status": r.get("status", ""),
                "message": str(r.get("message", "")),
                "execution_time": float(r.get("execution_time", 0) or 0),
            }
        )
    return out


# ---------- 模板 ----------
_DEFAULT_DBT_PROJECT_YML = """\
# 由 DBT UI 生成的 dbt_project.yml
name: '{name}'
version: '1.0.0'
config-version: 2

profile: '{name}'

model-paths: ["models"]
analysis-paths: ["analyses"]
test-paths: ["tests"]
seed-paths: ["seeds"]
macro-paths: ["macros"]
snapshot-paths: ["snapshots"]

target-path: "target"
clean-targets:
  - "target"
  - "dbt_packages"

models:
  {name}:
    # Stage 层 — 贴源加载，写入 stage_db
    staging:
      +database: stage_db
      +materialized: table
    # Core 层 — 维度建模，写入 core_db
    core:
      +database: core_db
      +materialized: table
    # Mart 层 — 应用宽表，写入 mart_db
    marts:
      +database: mart_db
      +materialized: table
"""

_DEFAULT_SCHEMA_YML = """\
version: 2

models:
  - name: example
    description: "示例模型"
    columns:
      - name: id
        tests:
          - not_null
"""
