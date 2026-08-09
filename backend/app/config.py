"""应用配置：路径与基础设置。"""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 后端根目录
BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DBT_UI_", env_file=".env", extra="ignore")

    # SQLite 数据库文件路径
    database_url: str = f"sqlite:///{BACKEND_DIR / 'dbt_ui.db'}"

    # dbt 项目根目录（UI 管理的所有项目都放在这里）
    projects_root: Path = BACKEND_DIR / "dbt_projects"

    # 允许的后端类型（adapter）
    allowed_adapters: list[str] = ["sqlserver", "postgres", "duckdb", "snowflake", "bigquery"]

    # dbt 可执行文件路径（Python 版 dbt-core）
    dbt_bin: str = "/opt/homebrew/bin/dbt"

    # CORS 允许的前端来源
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


settings = Settings()
