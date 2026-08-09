"""分层配置管理路由 — 读写 dbt_project.yml 中的 models 分层配置。"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

import yaml
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from ..database import get_db
from ..models import Project
from ..schemas import LayerCreate, LayerDefinition, LayerUpdate
from ._common import get_project_or_404, refresh_manifest

router = APIRouter(prefix="/api/projects/{project_id}/layers", tags=["layers"])

MODELS_DIR = "models"
DBT_PROJECT_FILE = "dbt_project.yml"


def _project_yml_path(project: Project) -> Path:
    return Path(project.path) / DBT_PROJECT_FILE


def _models_dir(project: Project) -> Path:
    return Path(project.path) / MODELS_DIR


def _load_project_yml(project: Project) -> dict:
    """加载 dbt_project.yml。"""
    path = _project_yml_path(project)
    if not path.exists():
        raise HTTPException(status_code=404, detail="dbt_project.yml 不存在")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise HTTPException(status_code=400, detail=f"dbt_project.yml 解析失败: {exc}")
    return data


def _save_project_yml(project: Project, data: dict) -> None:
    """写回 dbt_project.yml。"""
    path = _project_yml_path(project)
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def _project_name(data: dict) -> str:
    """从 dbt_project.yml 获取项目名（models 下的第一级 key）。"""
    name = data.get("name", "")
    return name


def _models_config(data: dict) -> dict:
    """获取 models.<project_name> 下的配置字典。"""
    name = _project_name(data)
    models_section = (data.get("models") or {}).get(name) or {}
    return models_section


def _set_models_config(data: dict, config: dict) -> None:
    """设置 models.<project_name> 的配置。"""
    name = _project_name(data)
    if "models" not in data or not isinstance(data["models"], dict):
        data["models"] = {}
    data["models"][name] = config


def _is_layer_config(key: str, value: object) -> bool:
    """判断一个 key-value 对是否为分层配置（即目录配置）。

    规则：value 是 dict，且包含以 + 开头的配置键（如 +database、+materialized），
    或者 value 是 dict 且其下还有子目录（嵌套分层）。
    以 + 开头的 key 是配置项，不是目录。
    """
    if key.startswith("+"):
        return False
    if not isinstance(value, dict):
        return False
    # 有 + 开头的配置键 → 是分层配置
    if any(k.startswith("+") for k in value.keys()):
        return True
    # 有子目录（子 dict 也是分层）
    for k, v in value.items():
        if not k.startswith("+") and isinstance(v, dict):
            return True
    return False


def _parse_layer(name: str, config: dict, is_root: bool = False) -> LayerDefinition:
    """从 yml 配置字典解析出 LayerDefinition。"""
    meta = config.get("+meta", {}) if isinstance(config.get("+meta"), dict) else {}
    display_name = meta.get("display_name", "") if isinstance(meta, dict) else ""
    return LayerDefinition(
        name=name,
        display_name=display_name,
        database=config.get("+database", "") or "",
        schema=config.get("+schema", "") or "",
        materialized=config.get("+materialized", "view") or "view",
        is_root=is_root,
    )


def _layer_to_config(layer: LayerDefinition) -> dict:
    """把 LayerDefinition 转成 yml 配置字典。"""
    config: dict = {}
    if layer.database:
        config["+database"] = layer.database
    if layer.schema_:
        config["+schema"] = layer.schema_
    if layer.materialized:
        config["+materialized"] = layer.materialized
    if layer.display_name:
        config["+meta"] = {"display_name": layer.display_name}
    return config


# ---------- API ----------
@router.get("", response_model=list[LayerDefinition])
def list_layers(project_id: int, db: Session = Depends(get_db)) -> list[LayerDefinition]:
    """列出所有分层配置（含根目录）。"""
    project = get_project_or_404(db, project_id)
    data = _load_project_yml(project)
    models_cfg = _models_config(data)

    layers: list[LayerDefinition] = []

    # 根目录配置
    root_cfg = {k: v for k, v in models_cfg.items() if k.startswith("+")}
    root_layer = _parse_layer("", root_cfg, is_root=True)
    layers.append(root_layer)

    # 子目录分层
    for key, value in models_cfg.items():
        if _is_layer_config(key, value):
            layers.append(_parse_layer(key, value))

    return layers


@router.get("/{layer_name}", response_model=LayerDefinition)
def get_layer(
    project_id: int, layer_name: str, db: Session = Depends(get_db)
) -> LayerDefinition:
    """获取单个分层配置。layer_name 为空字符串表示根目录。"""
    project = get_project_or_404(db, project_id)
    data = _load_project_yml(project)
    models_cfg = _models_config(data)

    if not layer_name or layer_name == "__root__":
        root_cfg = {k: v for k, v in models_cfg.items() if k.startswith("+")}
        return _parse_layer("", root_cfg, is_root=True)

    if layer_name not in models_cfg or not _is_layer_config(
        layer_name, models_cfg[layer_name]
    ):
        raise HTTPException(status_code=404, detail=f"分层不存在: {layer_name}")

    return _parse_layer(layer_name, models_cfg[layer_name])


@router.post("", response_model=LayerDefinition)
def create_layer(
    project_id: int, body: LayerCreate, db: Session = Depends(get_db)
) -> LayerDefinition:
    """新建一个分层。"""
    project = get_project_or_404(db, project_id)
    data = _load_project_yml(project)
    models_cfg = _models_config(data)

    # 检查重名
    if body.name in models_cfg and _is_layer_config(body.name, models_cfg[body.name]):
        raise HTTPException(status_code=400, detail=f"分层已存在: {body.name}")

    # 检查目录是否已存在
    layer_dir = _models_dir(project) / body.name
    if layer_dir.exists():
        # 目录已存在但没有配置，允许添加配置
        pass

    # 写入配置
    layer_def = LayerDefinition(
        name=body.name,
        display_name=body.display_name,
        database=body.database,
        schema=body.schema_,
        materialized=body.materialized,
        is_root=False,
    )
    models_cfg[body.name] = _layer_to_config(layer_def)
    _set_models_config(data, models_cfg)
    _save_project_yml(project, data)

    # 创建目录（如果不存在）
    layer_dir.mkdir(parents=True, exist_ok=True)
    logger.info(
        f"[Layer create] 项目 {project.name}: 新建分层 {body.name}，"
        f"目录: {layer_dir.resolve()}"
    )

    refresh_manifest(db, project)
    return layer_def


@router.put("/{layer_name}", response_model=LayerDefinition)
def update_layer(
    project_id: int,
    layer_name: str,
    body: LayerUpdate,
    db: Session = Depends(get_db),
) -> LayerDefinition:
    """更新分层配置。name 变化时重命名目录。"""
    project = get_project_or_404(db, project_id)
    data = _load_project_yml(project)
    models_cfg = _models_config(data)

    is_root = not layer_name or layer_name == "__root__"

    if is_root:
        # 根目录：只更新配置，不能改名
        root_cfg = {k: v for k, v in models_cfg.items() if k.startswith("+")}
        layer = _parse_layer("", root_cfg, is_root=True)
    else:
        if layer_name not in models_cfg or not _is_layer_config(
            layer_name, models_cfg[layer_name]
        ):
            raise HTTPException(status_code=404, detail=f"分层不存在: {layer_name}")
        layer = _parse_layer(layer_name, models_cfg[layer_name])

    # 更新字段
    new_name = body.name if body.name is not None else layer.name
    if body.display_name is not None:
        layer.display_name = body.display_name
    if body.database is not None:
        layer.database = body.database
    if body.schema_ is not None:
        layer.schema_ = body.schema_
    if body.materialized is not None:
        layer.materialized = body.materialized

    if is_root:
        # 更新根目录配置
        new_config = _layer_to_config(layer)
        # 移除旧的 + 配置键
        for k in list(models_cfg.keys()):
            if k.startswith("+"):
                del models_cfg[k]
        # 写入新配置
        models_cfg.update(new_config)
        _set_models_config(data, models_cfg)
        _save_project_yml(project, data)
        refresh_manifest(db, project)
        return _parse_layer("", {k: v for k, v in models_cfg.items() if k.startswith("+")}, is_root=True)

    # 非根目录：处理重命名
    if new_name and new_name != layer_name:
        # 检查冲突
        if new_name in models_cfg and _is_layer_config(new_name, models_cfg[new_name]):
            raise HTTPException(
                status_code=400, detail=f"目标分层名已存在: {new_name}"
            )
        # 检查目录冲突
        new_dir = _models_dir(project) / new_name
        old_dir = _models_dir(project) / layer_name
        if new_dir.exists():
            raise HTTPException(
                status_code=400,
                detail=f"目标目录已存在: {new_name}，请先删除或重命名目标目录",
            )
        # 重命名目录
        if old_dir.exists():
            logger.info(
                f"[Layer rename] 项目 {project.name}: 目录重命名 "
                f"{old_dir.resolve()} → {new_dir.resolve()}"
            )
            shutil.move(str(old_dir), str(new_dir))
            logger.info(
                f"[Layer rename] 项目 {project.name}: 目录重命名完成 "
                f"{old_dir.resolve()} → {new_dir.resolve()}"
            )
        else:
            logger.info(
                f"[Layer rename] 项目 {project.name}: 原目录不存在，跳过移动 "
                f"(old={old_dir.resolve()}, new={new_dir.resolve()})"
            )
        # 更新 yml 中的 key
        models_cfg[new_name] = models_cfg.pop(layer_name)
        layer.name = new_name
        current_key = new_name
    else:
        current_key = layer_name

    # 更新配置内容
    models_cfg[current_key] = _layer_to_config(layer)
    _set_models_config(data, models_cfg)
    _save_project_yml(project, data)

    refresh_manifest(db, project)
    return layer


@router.delete("/{layer_name}")
def delete_layer(project_id: int, layer_name: str, db: Session = Depends(get_db)) -> dict:
    """删除一个分层配置（不删除目录和文件）。"""
    project = get_project_or_404(db, project_id)

    if not layer_name or layer_name == "__root__":
        raise HTTPException(status_code=400, detail="根目录不能删除")

    data = _load_project_yml(project)
    models_cfg = _models_config(data)

    if layer_name not in models_cfg or not _is_layer_config(
        layer_name, models_cfg[layer_name]
    ):
        raise HTTPException(status_code=404, detail=f"分层不存在: {layer_name}")

    # 只删除配置，不删除目录和文件
    del models_cfg[layer_name]
    _set_models_config(data, models_cfg)
    _save_project_yml(project, data)
    logger.info(
        f"[Layer delete] 项目 {project.name}: 删除分层配置 {layer_name} "
        f"(目录保留: {_models_dir(project) / layer_name})"
    )

    refresh_manifest(db, project)
    return {"message": "已删除"}
