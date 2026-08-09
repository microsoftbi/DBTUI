# TC-MODEL — 模型管理测试用例

## 前置条件
- 已创建 sqlserver 项目并完成首次 parse
- 进入项目详情页 → Models 标签

---

### TC-MODEL-01 模型列表

| 项 | 内容 |
|---|---|
| 优先级 | P0 |
| 步骤 | 查看 Models 列表 |
| 预期 | 1. 至少有 `example` 模型<br>2. 物化策略显示为 `view`<br>3. 文件路径为 `models/example.sql` |

### TC-MODEL-02 新建模型

| 项 | 内容 |
|---|---|
| 优先级 | P0 |
| 步骤 | 1. 点击「新建模型」<br>2. 名称填 `orders`，SQL 填 `SELECT 42 AS order_id`<br>3. 点击「创建」 |
| 预期 | 1. 列表新增 `orders` 模型<br>2. DAG 中出现新节点 |

### TC-MODEL-03 编辑模型 SQL 与物化策略

| 项 | 内容 |
|---|---|
| 优先级 | P1 |
| 步骤 | 1. 点击 `orders` 的「编辑」<br>2. 修改 SQL 为 `SELECT 100 AS order_id`<br>3. 物化策略改为 `table`<br>4. 保存 |
| 预期 | 1. 保存成功提示<br>2. 列表中物化策略变为 `table`<br>3. 再次编辑可看到 SQL 已更新 |

### TC-MODEL-04 运行单个模型

| 项 | 内容 |
|---|---|
| 优先级 | P0 |
| 步骤 | 1. 点击 `orders` 的「运行」<br>2. 在运行对话框中点击「开始运行」<br>3. 等待完成 |
| 预期 | 1. 日志实时滚动输出<br>2. 运行成功（returncode 0）<br>3. 列表中状态变为 `success` |

### TC-MODEL-05 删除模型

| 项 | 内容 |
|---|---|
| 优先级 | P0 |
| 步骤 | 1. 点击 `orders` 的「删除」→ 确认<br>2. 查看列表与 DAG |
| 预期 | 1. 列表中 `orders` 消失<br>2. DAG 中对应节点消失 |
