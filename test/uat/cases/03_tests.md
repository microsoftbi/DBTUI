# TC-TEST — 测试管理测试用例

## 前置条件
- 已创建 sqlserver 项目并完成首次 parse
- 进入项目详情页 → Tests 标签

---

### TC-TEST-01 测试列表

| 项 | 内容 |
|---|---|
| 优先级 | P0 |
| 步骤 | 查看 Tests 列表 |
| 预期 | 1. 至少有一个 generic test（如 `not_null_example_id`）<br>2. 类型列显示 `generic` |

### TC-TEST-02 新建 singular test

| 项 | 内容 |
|---|---|
| 优先级 | P0 |
| 步骤 | 1. 点击「新建测试」<br>2. 名称填 `assert_positive`，SQL 填 `SELECT * FROM {{ ref('example') }} WHERE id < 0`<br>3. 保存 |
| 预期 | 1. 列表新增 `assert_positive`<br>2. 类型为 `singular` |

### TC-TEST-03 运行测试

| 项 | 内容 |
|---|---|
| 优先级 | P0 |
| 步骤 | 1. 点击 `assert_positive` 的「运行」<br>2. 等待完成 |
| 预期 | 1. 测试运行成功（无失败行 = 通过）<br>2. 状态变为 `pass` 或 `success` |

### TC-TEST-04 删除 singular test

| 项 | 内容 |
|---|---|
| 优先级 | P1 |
| 步骤 | 1. 点击 `assert_positive` 的「删除」→ 确认 |
| 预期 | 列表中该测试消失，DAG 中对应节点消失 |
