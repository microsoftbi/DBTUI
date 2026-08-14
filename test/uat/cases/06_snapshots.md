# TC-SNAPSHOT — Snapshot 快照管理测试用例

## 前置条件
- 已创建 sqlserver 项目并完成首次 parse
- 进入项目详情页 → Snapshots 标签
- 项目中至少有一个 model（如 `example`），可作为 snapshot 的数据来源

---

### TC-SNAPSHOT-01 Snapshots 标签页与空列表

| 项 | 内容 |
|---|---|
| 优先级 | P0 |
| 步骤 | 1. 进入项目详情页<br>2. 点击「Snapshots」标签 |
| 预期 | 1. 标签页正常切换，无报错<br>2. 列表显示空状态提示「暂无快照（请先解析）」<br>3. 顶部工具栏显示「共 0 个快照」和「新建快照」按钮 |

### TC-SNAPSHOT-02 新建快照（timestamp 策略）

| 项 | 内容 |
|---|---|
| 优先级 | P0 |
| 步骤 | 1. 点击「新建快照」按钮<br>2. 名称填 `uat_customers_snapshot`<br>3. SQL 填写完整的 snapshot 模板（timestamp 策略，引用 `example` 模型）<br>4. 点击「创建」 |
| 预期 | 1. 弹窗关闭，列表中新增 `uat_customers_snapshot`<br>2. 策略列显示 `timestamp`（绿色 tag）<br>3. 目标 Schema 列显示 `snapshots`<br>4. 唯一键列显示 `id`<br>5. 文件路径为 `snapshots/uat_customers_snapshot.sql` |

### TC-SNAPSHOT-03 查看快照 SQL

| 项 | 内容 |
|---|---|
| 优先级 | P1 |
| 步骤 | 1. 调用 GET `/snapshots/{id}/sql` 接口 |
| 预期 | 1. 返回 snapshot_id、name、file_path、sql 字段<br>2. SQL 内容与创建时一致，包含 `{% snapshot %}` 和 `{% endsnapshot %}` 标签 |

### TC-SNAPSHOT-04 编辑快照（修改 SQL）

| 项 | 内容 |
|---|---|
| 优先级 | P0 |
| 步骤 | 1. 点击 `uat_customers_snapshot` 的「编辑」<br>2. 修改 SQL（如添加注释或调整字段）<br>3. 点击「保存」 |
| 预期 | 1. 弹窗关闭，列表中快照仍存在<br>2. 重新获取 SQL，内容已更新 |

### TC-SNAPSHOT-05 编辑快照（重命名）

| 项 | 内容 |
|---|---|
| 优先级 | P1 |
| 步骤 | 1. 点击快照的「编辑」<br>2. 将名称改为 `uat_customers_snapshot_v2`<br>3. 点击「保存」 |
| 预期 | 1. 列表中名称变为 `uat_customers_snapshot_v2`<br>2. 文件路径变为 `snapshots/uat_customers_snapshot_v2.sql` |

### TC-SNAPSHOT-06 运行单个快照

| 项 | 内容 |
|---|---|
| 优先级 | P0 |
| 步骤 | 1. 点击 `uat_customers_snapshot_v2` 的「运行」按钮<br>2. 等待运行完成 |
| 预期 | 1. 运行对话框弹出，run_type 自动为 `snapshot`<br>2. 日志正常输出，运行成功（status = success）<br>3. 列表中该快照的运行状态变为 `success`<br>4. 运行历史中新增一条 snapshot 类型记录 |

### TC-SNAPSHOT-07 全量快照运行（RunDialog）

| 项 | 内容 |
|---|---|
| 优先级 | P1 |
| 步骤 | 1. 打开运行对话框（任意入口）<br>2. 运行类型选择 `snapshot`<br>3. selection 留空<br>4. 点击「开始」 |
| 预期 | 1. 运行成功<br>2. 运行历史中 run_type 为 `snapshot`，selection 为空 |

### TC-SNAPSHOT-08 Models 列表不包含 snapshot

| 项 | 内容 |
|---|---|
| 优先级 | P0 |
| 步骤 | 1. 切换到 Models 标签页 |
| 预期 | 1. Models 列表中不出现 `uat_customers_snapshot_v2`<br>2. snapshot 仅出现在 Snapshots 标签页 |

### TC-SNAPSHOT-09 DAG 中显示 snapshot 节点

| 项 | 内容 |
|---|---|
| 优先级 | P1 |
| 步骤 | 1. 切换到 DAG 标签页<br>2. 搜索 snapshot 名称 |
| 预期 | 1. DAG 图中存在 snapshot 节点<br>2. 节点类型为 snapshot，有对应的颜色/样式 |

### TC-SNAPSHOT-10 删除快照

| 项 | 内容 |
|---|---|
| 优先级 | P0 |
| 步骤 | 1. 点击 `uat_customers_snapshot_v2` 的「删除」<br>2. 在确认弹窗中点击「确定」 |
| 预期 | 1. 列表中该快照消失<br>2. DAG 中对应节点消失<br>3. 磁盘上 `snapshots/uat_customers_snapshot_v2.sql` 文件被删除 |

### TC-SNAPSHOT-11 新建快照（check 策略）

| 项 | 内容 |
|---|---|
| 优先级 | P1 |
| 步骤 | 1. 点击「新建快照」<br>2. 名称填 `uat_orders_check_snapshot`<br>3. SQL 使用 check 策略（`strategy='check'`，`check_cols='all'`）<br>4. 点击「创建」 |
| 预期 | 1. 列表中新增快照<br>2. 策略列显示 `check`（橙色 tag）<br>3. 目标 Schema 列显示对应值 |

### TC-SNAPSHOT-12 快照名称重复校验

| 项 | 内容 |
|---|---|
| 优先级 | P1 |
| 步骤 | 1. 新建一个名为 `uat_dup_snapshot` 的快照<br>2. 再次新建同名快照 |
| 预期 | 1. 第二次创建返回 409 错误，提示「快照已存在」<br>2. 列表中只有一个该名称的快照 |

### TC-SNAPSHOT-13 快照名称非法字符校验

| 项 | 内容 |
|---|---|
| 优先级 | P2 |
| 步骤 | 1. 新建快照，名称填 `my snapshot`（含空格）或 `my-snapshot`（含横杠） |
| 预期 | 1. 后端返回 422 校验错误<br>2. 快照未创建 |

---

## 二、前端 E2E 测试用例（Playwright）

### E2E-SNAP-01 Snapshots 标签页空状态

| 项 | 内容 |
|---|---|
| 优先级 | P0 |
| 步骤 | 1. 进入项目详情页<br>2. 点击「Snapshots」标签 |
| 预期 | 1. 标签切换成功，页面无报错<br>2. 显示「新建快照」按钮<br>3. 显示「暂无快照」空状态提示 |
| 自动化 | `test_e2e_snapshots_tab_empty` |

### E2E-SNAP-02 新建快照（完整交互）

| 项 | 内容 |
|---|---|
| 优先级 | P0 |
| 步骤 | 1. 点击「新建快照」按钮<br>2. 弹窗中填写名称 `e2e_customers_snapshot`<br>3. 在 SQL 编辑器中输入完整的 snapshot SQL<br>4. 点击「创建」 |
| 预期 | 1. 弹窗关闭<br>2. 列表中新增快照，名称正确<br>3. 策略列显示 `timestamp` 标签<br>4. 目标 Schema 列显示 `snapshots` |
| 自动化 | `test_e2e_create_snapshot` |

### E2E-SNAP-03 Models 列表隔离

| 项 | 内容 |
|---|---|
| 优先级 | P0 |
| 步骤 | 1. 切换到 Models 标签页 |
| 预期 | 1. Models 列表中不出现 snapshot 名称 |
| 自动化 | `test_e2e_snapshot_not_in_models` |

### E2E-SNAP-04 编辑快照

| 项 | 内容 |
|---|---|
| 优先级 | P0 |
| 步骤 | 1. 点击快照行的「编辑」按钮<br>2. 弹窗标题显示「编辑快照：xxx」<br>3. 修改 SQL 内容<br>4. 点击「保存」 |
| 预期 | 1. 弹窗关闭<br>2. 列表中快照仍然存在<br>3. 重新打开编辑，SQL 已更新 |
| 自动化 | `test_e2e_edit_snapshot` |

### E2E-SNAP-05 运行单个快照

| 项 | 内容 |
|---|---|
| 优先级 | P0 |
| 步骤 | 1. 点击快照行的「运行」按钮<br>2. 运行对话框弹出，运行类型自动为 `snapshot`<br>3. 点击「开始」<br>4. 等待运行完成 |
| 预期 | 1. 日志实时输出<br>2. 运行成功（状态 success）<br>3. 列表中运行状态列显示对应状态标签 |
| 自动化 | `test_e2e_run_snapshot` |

### E2E-SNAP-06 运行对话框 snapshot 选项

| 项 | 内容 |
|---|---|
| 优先级 | P1 |
| 步骤 | 1. 打开运行对话框<br>2. 展开运行类型下拉 |
| 预期 | 1. 下拉列表中有 `snapshot` 选项 |
| 自动化 | `test_e2e_run_dialog_has_snapshot_option` |

### E2E-SNAP-07 删除快照

| 项 | 内容 |
|---|---|
| 优先级 | P0 |
| 步骤 | 1. 点击快照行的「删除」按钮<br>2. 确认弹窗中点击「确定」 |
| 预期 | 1. 确认弹窗关闭<br>2. 列表中该快照消失<br>3. 显示空状态提示 |
| 自动化 | `test_e2e_delete_snapshot` |

---

## 三、视觉回归测试

| 用例 | 截图文件 | 说明 |
|------|---------|------|
| Snapshots 标签页（空） | `detail-snapshots.png` | 空列表状态下的标签页视觉 |
| 新建快照弹窗 | `dialog-new-snapshot.png` | 新建快照弹窗默认状态视觉 |
