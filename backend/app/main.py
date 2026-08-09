"""FastAPI 应用入口。"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import models
from .config import settings
from .database import Base, engine
from .routers import dag, layers, models as models_router, projects, runs, sources, tests


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时建表，并确保项目根目录存在
    Base.metadata.create_all(bind=engine)
    settings.projects_root.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="DBT UI", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router)
app.include_router(models_router.router)
app.include_router(tests.router)
app.include_router(sources.router)
app.include_router(layers.router)
app.include_router(dag.router)
app.include_router(runs.router)
app.include_router(runs.ws_router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
