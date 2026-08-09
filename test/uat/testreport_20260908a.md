# DBT UI UAT 测试报告

> 报告编号：testreport_20260908a
> 测试时间：2026-08-09 16:24:09 ~ 2026-08-09 16:25:36
> 测试时长：87.9 秒
> 测试环境：前端 http://localhost:5173 / 后端 http://localhost:8000
> 适配器：sqlserver（dbt-core + dbt-sqlserver）
> 测试工具：Playwright + httpx（API + UI 自动化）

---

## 一、测试总览

- **总用例数**：28
- **通过**：28 ✅
- **失败**：0 ❌
- **通过率**：100.0%
- **截图数量**：24 张

## 二、各章测试结果

| 章节 | 用例数 | 通过 | 失败 | 通过率 |
|------|--------|------|------|--------|
| ✅ 第 1 章：项目管理 | 5 | 5 | 0 | 100.0% |
| ✅ 第 2 章：分层配置管理 | 5 | 5 | 0 | 100.0% |
| ✅ 第 3 章：Sources 管理 | 5 | 5 | 0 | 100.0% |
| ✅ 第 4 章：模型管理 | 4 | 4 | 0 | 100.0% |
| ✅ 第 5 章：测试管理 | 2 | 2 | 0 | 100.0% |
| ✅ 第 6 章：DAG 血缘图 | 2 | 2 | 0 | 100.0% |
| ✅ 第 7 章：运行与运行历史 | 4 | 4 | 0 | 100.0% |
| ✅ 第 8 章：连接配置 | 1 | 1 | 0 | 100.0% |

---

## 三、详细测试结果

### 第 1 章：项目管理

| 用例编号 | 用例名称 | 结果 | 备注 |
|----------|----------|------|------|
| TC-01-01 | 项目列表页正常加载 | ✅ 通过 | - |
| TC-01-02 | 新建项目弹窗正常打开 | ✅ 通过 | - |
| TC-01-03 | 创建 sqlserver 项目成功 | ✅ 通过 | - |
| TC-01-04 | profiles.yml sqlserver 配置正确 | ✅ 通过 | - |
| TC-01-05 | dbt_project.yml 三层分库配置完整 | ✅ 通过 | - |

**界面截图：**

![项目列表页](report_20260908a/screenshots/01_项目列表页.png)

<p align='center'><i>项目列表页</i></p>

![新建项目弹窗](report_20260908a/screenshots/02_新建项目弹窗.png)

<p align='center'><i>新建项目弹窗</i></p>

![项目创建成功](report_20260908a/screenshots/04_项目创建成功.png)

<p align='center'><i>项目创建成功</i></p>

---

### 第 2 章：分层配置管理

| 用例编号 | 用例名称 | 结果 | 备注 |
|----------|----------|------|------|
| TC-02-01 | 分层配置入口按钮存在 | ✅ 通过 | - |
| TC-02-02 | 分层配置列表显示三层 | ✅ 通过 | - |
| TC-02-03 | 新建分层（ODS 层）成功 | ✅ 通过 | - |
| TC-02-04 | 编辑分层（显示名称）成功 | ✅ 通过 | - |
| TC-02-05 | 删除分层成功 | ✅ 通过 | - |

**界面截图：**

![项目详情页](report_20260908a/screenshots/05_项目详情页.png)

<p align='center'><i>项目详情页</i></p>

![分层配置入口按钮](report_20260908a/screenshots/06_分层配置入口.png)

<p align='center'><i>分层配置入口按钮</i></p>

![分层配置列表](report_20260908a/screenshots/07_分层配置列表.png)

<p align='center'><i>分层配置列表</i></p>

![新建分层弹窗](report_20260908a/screenshots/08_新建分层弹窗.png)

<p align='center'><i>新建分层弹窗</i></p>

![填写分层信息](report_20260908a/screenshots/09_填写分层信息.png)

<p align='center'><i>填写分层信息</i></p>

![编辑分层弹窗](report_20260908a/screenshots/10_编辑分层弹窗.png)

<p align='center'><i>编辑分层弹窗</i></p>

---

### 第 3 章：Sources 管理

| 用例编号 | 用例名称 | 结果 | 备注 |
|----------|----------|------|------|
| TC-03-01 | Sources 标签页正常显示 | ✅ 通过 | - |
| TC-03-02 | 新建 Source 成功 | ✅ 通过 | - |
| TC-03-03 | Source 详情正常显示 | ✅ 通过 | - |
| TC-03-04 | 添加源表成功（2 张） | ✅ 通过 | - |
| TC-03-05 | 删除源表成功 | ✅ 通过 | - |

**界面截图：**

![Sources 标签页](report_20260908a/screenshots/11_Sources标签页.png)

<p align='center'><i>Sources 标签页</i></p>

![新建 Source 弹窗](report_20260908a/screenshots/12_新建Source弹窗.png)

<p align='center'><i>新建 Source 弹窗</i></p>

![填写 Source 信息](report_20260908a/screenshots/13_填写Source信息.png)

<p align='center'><i>填写 Source 信息</i></p>

![Source 详情页](report_20260908a/screenshots/14_Source详情.png)

<p align='center'><i>Source 详情页</i></p>

![添加源表弹窗](report_20260908a/screenshots/15_添加源表弹窗.png)

<p align='center'><i>添加源表弹窗</i></p>

![Source 表列表](report_20260908a/screenshots/16_Source表列表.png)

<p align='center'><i>Source 表列表</i></p>

---

### 第 4 章：模型管理

| 用例编号 | 用例名称 | 结果 | 备注 |
|----------|----------|------|------|
| TC-04-01 | Models 标签页正常显示 | ✅ 通过 | - |
| TC-04-02 | 新建模型（stg_customers）成功 | ✅ 通过 | - |
| TC-04-03 | 编辑模型 SQL 成功 | ✅ 通过 | - |
| TC-04-04 | 模型列表显示正确 | ✅ 通过 | - |

**界面截图：**

![模型列表页](report_20260908a/screenshots/17_模型列表页.png)

<p align='center'><i>模型列表页</i></p>

![模型列表含 stg_customers](report_20260908a/screenshots/18_模型列表含stg_customers.png)

<p align='center'><i>模型列表含 stg_customers</i></p>

![编辑模型 SQL](report_20260908a/screenshots/20_编辑模型SQL.png)

<p align='center'><i>编辑模型 SQL</i></p>

---

### 第 5 章：测试管理

| 用例编号 | 用例名称 | 结果 | 备注 |
|----------|----------|------|------|
| TC-05-01 | Tests 标签页正常显示 | ✅ 通过 | - |
| TC-05-02 | 新建 singular test 成功 | ✅ 通过 | - |

**界面截图：**

![测试列表页](report_20260908a/screenshots/22_测试列表页.png)

<p align='center'><i>测试列表页</i></p>

![测试列表](report_20260908a/screenshots/24_测试列表.png)

<p align='center'><i>测试列表</i></p>

---

### 第 6 章：DAG 血缘图

| 用例编号 | 用例名称 | 结果 | 备注 |
|----------|----------|------|------|
| TC-06-01 | DAG 血缘图正常显示 | ✅ 通过 | - |
| TC-06-02 | DAG API 返回 5 个节点 | ✅ 通过 | - |

**界面截图：**

![DAG 血缘图](report_20260908a/screenshots/25_DAG血缘图.png)

<p align='center'><i>DAG 血缘图</i></p>

---

### 第 7 章：运行与运行历史

| 用例编号 | 用例名称 | 结果 | 备注 |
|----------|----------|------|------|
| TC-07-01 | 运行历史标签页正常显示 | ✅ 通过 | - |
| TC-07-02 | dbt parse API 正常发起 | ✅ 通过 | - |
| TC-07-03 | dbt run API 正常发起 | ✅ 通过 | - |
| TC-07-04 | 运行历史列表正常显示 | ✅ 通过 | - |

**界面截图：**

![运行历史页](report_20260908a/screenshots/26_运行历史页.png)

<p align='center'><i>运行历史页</i></p>

![运行历史列表](report_20260908a/screenshots/27_运行历史列表.png)

<p align='center'><i>运行历史列表</i></p>

---

### 第 8 章：连接配置

| 用例编号 | 用例名称 | 结果 | 备注 |
|----------|----------|------|------|
| TC-08-01 | 连接配置弹窗正常打开 | ✅ 通过 | - |

**界面截图：**

![连接配置弹窗](report_20260908a/screenshots/28_连接配置弹窗.png)

<p align='center'><i>连接配置弹窗</i></p>

---

## 五、说明

- SQL Server 实例可能不可达，因此 dbt run 的实际执行结果不作为失败判定依据，仅验证 API 能否正常发起运行任务。
- 所有 UI 操作均通过 Playwright 自动化模拟真实用户操作完成。
- 截图保存于 `test/uat/report_20260908a/screenshots/` 目录。
