# DBT UI — UAT 测试计划

本目录包含 DBT UI 的用户验收测试（User Acceptance Testing）计划、测试用例与自动化脚本。

## 1. 测试范围

| 模块 | 覆盖内容 | 自动化 |
|---|---|---|
| 项目管理 | 创建 / 列表 / 详情 / 编辑 / 删除 / 连接配置 | ✅ |
| 模型管理 | 列表 / 新建 / 编辑 SQL / 物化策略 / 删除 | ✅ |
| 测试管理 | 列表 / 新建 singular / 删除 / 运行 | ✅ |
| DAG 可视化 | 节点与边 / 类型着色 / 搜索筛选 / 血缘高亮 | ✅ |
| 运行 | 同步运行 / 运行历史 / 日志查看 / 取消 | ✅ |
| WebSocket 实时流 | 日志流 / running 标记 / node_status 实时状态 / done | ✅ |
| **视觉回归** | 关键页面与弹窗像素级截图对比 | ✅（Playwright） |
| 前端 UI 交互 | 页面跳转、弹窗、表格操作 | ⚠️ 手工用例（未做 E2E） |

## 2. 测试环境

- **后端**：FastAPI 运行在 `http://localhost:8000`
- **前端**：Vite dev server 运行在 `http://localhost:5173`（仅手工测试需要）
- **dbt**：本机已安装 `dbt-core` 或 `dbt-fusion`，且 `duckdb` adapter 可用（自动化测试使用 duckdb 项目，免外部数据库）
- **Python**：3.9+

## 3. 测试数据

- 自动化测试会创建一个独立的 duckdb 项目（名称带 `uat_` 前缀），测试结束后自动清理。
- 不影响现有项目数据。

## 4. 执行方式

### 4.1 自动化测试（后端 API + WebSocket）

```bash
# 1. 安装测试依赖
cd test/uat
pip install -r requirements.txt

# 2. 确保后端已启动（8000 端口）
#    如未启动，在项目根目录执行：
#    source .venv/bin/activate && cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000

# 3. 运行全部用例
pytest -v

# 4. 运行单个模块
pytest -v test_projects.py
pytest -v test_runs_ws.py

# 5. 生成 HTML 报告（可选）
pytest --html=report.html --self-contained-html
```

### 4.2 手工测试（前端 UI）

详见 [cases/](cases/) 目录下的各模块用例文档。

### 4.3 视觉回归测试（Playwright）

详见 [visual/README.md](visual/README.md)。

```bash
cd visual

# 首次运行：生成基线截图
pytest --update-snapshots

# 日常回归：对比基线
pytest
```

覆盖 8 个视觉用例：项目列表、详情页 4 个标签（Models / Tests / DAG / 运行历史）、3 个弹窗（新建项目 / 运行 / 连接配置）。

## 5. 用例清单

| 编号 | 模块 | 用例 | 自动化 |
|---|---|---|---|
| TC-PROJ-01 | 项目 | 创建 duckdb 项目成功 | ✅ |
| TC-PROJ-02 | 项目 | 项目列表与详情 | ✅ |
| TC-PROJ-03 | 项目 | 编辑项目名称 / 描述 | ✅ |
| TC-PROJ-04 | 项目 | 连接配置读取与保存（YAML 校验） | ✅ |
| TC-PROJ-05 | 项目 | 删除项目（含磁盘目录清理） | ✅ |
| TC-MODEL-01 | 模型 | parse 后模型列表正确 | ✅ |
| TC-MODEL-02 | 模型 | 新建模型并重新解析 | ✅ |
| TC-MODEL-03 | 模型 | 修改物化策略（view→table） | ✅ |
| TC-MODEL-04 | 模型 | 删除模型 | ✅ |
| TC-TEST-01 | 测试 | generic 与 singular 测试列表 | ✅ |
| TC-TEST-02 | 测试 | 新建 singular test | ✅ |
| TC-TEST-03 | 测试 | 删除 singular test | ✅ |
| TC-DAG-01 | DAG | 节点与边数量正确 | ✅ |
| TC-DAG-02 | DAG | 节点类型着色（model/test） | ✅ |
| TC-RUN-01 | 运行 | 同步运行模型成功 | ✅ |
| TC-RUN-02 | 运行 | 运行历史与日志查看 | ✅ |
| TC-WS-01 | WebSocket | 日志流与 done 事件 | ✅ |
| TC-WS-02 | WebSocket | running 节点预判 | ✅ |
| TC-WS-03 | WebSocket | node_status 实时状态 | ✅ |
| TC-WS-04 | WebSocket | 取消运行 | ✅ |
| TC-VIS-01 | 视觉 | 项目列表页 | ✅ |
| TC-VIS-02 | 视觉 | 详情页 Models 标签 | ✅ |
| TC-VIS-03 | 视觉 | 详情页 Tests 标签 | ✅ |
| TC-VIS-04 | 视觉 | 详情页 DAG 标签 | ✅ |
| TC-VIS-05 | 视觉 | 详情页运行历史标签 | ✅ |
| TC-VIS-06 | 视觉 | 新建项目弹窗 | ✅ |
| TC-VIS-07 | 视觉 | 运行对话框 | ✅ |
| TC-VIS-08 | 视觉 | 连接配置弹窗 | ✅ |

## 6. 验收标准

- 所有自动化用例 100% 通过。
- 手工用例关键路径（项目创建 → 解析 → 运行 → DAG 查看）全部通过。
- 运行中 DAG 节点状态实时刷新（蓝色呼吸 → 最终状态）无明显卡顿（< 200ms 延迟）。
- 错误场景（非法 YAML、重复模型名、不存在资源）有明确提示。

## 7. 目录结构

```
test/uat/
├── README.md                 # 本文件（测试计划）
├── requirements.txt          # 测试依赖
├── conftest.py               # pytest 配置与公共 fixtures
├── cases/                    # 手工测试用例文档
│   ├── 01_projects.md
│   ├── 02_models.md
│   ├── 03_tests.md
│   ├── 04_dag.md
│   └── 05_runs.md
├── scripts/                  # 自动化测试脚本（API + WS）
│   ├── test_projects.py
│   ├── test_models.py
│   ├── test_tests.py
│   ├── test_dag.py
│   ├── test_runs.py
│   └── test_runs_ws.py
└── visual/                   # 视觉回归测试（Playwright）
    ├── README.md
    ├── pytest.ini
    ├── conftest.py
    ├── snapshots/              # 基线截图（运行 --update-snapshots 后生成）
    ├── test_01_project_list.py
    ├── test_02_detail_tabs.py
    └── test_03_dialogs.py
```
