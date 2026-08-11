# dbt+SQLServer构建数据仓库(9)：用Vibe Coding创建一个DBT UI

> 本文以一个完整的销售数据仓库项目为例，演示如何通过我自己用Vibe Coding写的一个 DBT UI 可视化工具，配合底层 dbt 引擎，在 SQL Server 上快速搭建一套 stage → core → mart 三层分库的数据仓库。

## 一、为什么需要可视化的 dbt？

dbt（data build tool）是数据领域最流行的转换层工具之一，它让数据分析师和工程师可以用「写 SQL + 版本控制」的方式构建数据仓库。但 dbt 本质上是命令行工具，对不熟悉 CLI 的同学有一定门槛，而且项目配置、模型管理、血缘查看等操作散落在各个 YAML 和 SQL 文件中。

**DBT UI** 正是为了解决这个问题而生——它把 dbt 的核心能力封装成了一个 Web 界面：

- 项目创建、分层配置、Source 管理全部可视化
- 模型 SQL 在线编辑，保存即解析
- 一键运行，实时日志推送
- DAG 血缘图直观展示数据流向
- 运行历史和日志随时回溯

这个工具是我用Vibe Coding写的，火山引擎此时在打折所以体验了下，为了生图方便，环境我又选择回了Trae CN + Doubao-Seed-2.1-Turbo。并没有继续用VSCode+ClaudeCode+DeepSeek V4 Flash，主要还是想看下这半年字节的进化速度，同时也是想使用多模态模型做UAT相关的操作和验证。

这个项目的github地址：<https://github.com/microsoftbi/DBTUI。当然我也建议你可以自己用Vibe> Coding做一个，以此熟悉Vibe Coding的环境以及dbt的操作。

下面我们用一个销售数据仓库的完整案例，看看它是怎么工作的。

## 二、整体架构：三层物理分库

我们采用经典的 **三层分库架构**，每一层对应 SQL Server 上一个独立的物理数据库：

```
sales_db（源系统） → stage_db（贴源层） → core_db（核心层） → mart_db（应用层）
```

| 层级     | 数据库       | 物化方式  | 职责             |
| ------ | --------- | ----- | -------------- |
| Source | sales\_db | —     | 业务系统原始数据       |
| Stage  | stage\_db | table | 1:1 贴源加载，字段规范化 |
| Core   | core\_db  | table | 维度建模，维度表 + 事实表 |
| Mart   | mart\_db  | table | 面向业务的宽表，供报表使用  |

SQL Server 原生支持跨库查询（`database.schema.table`），dbt 通过 `{{ source() }}` 和 `{{ ref() }}` 自动处理跨库引用，开发者完全不用关心物理位置。

## 三、第一步：创建项目

打开 DBT UI，首页是项目列表。点击右上角「新建项目」。

![项目列表页](https://images.cnblogs.com/cnblogs_com/aspnetx/65269/o_260810173141_01_project_list.png)

填写项目信息，选择 `sqlserver` 适配器：

![新建项目](https://images.cnblogs.com/cnblogs_com/aspnetx/65269/o_260810173141_03_fill_project_info.png))

点击确定后，系统会自动完成：

1. 创建 dbt 项目脚手架（models/staging、models/core、models/marts 等目录）
2. 生成 SQL Server 连接配置（profiles.yml）
3. 配置三层分库（dbt\_project.yml 中按目录分配 database）
4. 执行首次 `dbt parse` 解析

> **dbt parse 是做什么的？**
>
> `dbt parse` 会扫描整个项目的 SQL 和 YAML 文件，解析 `{{ ref() }}`、`{{ source() }}`、`{{ config() }}` 等 Jinja 表达式，构建模型间的依赖关系（DAG），最终生成一份 `manifest.json` 项目清单。它**不连接数据库、不执行 SQL**，只做"编译"和语法校验。
>
> DBT UI 上展示的模型列表、DAG 图、测试列表、Source 列表等所有信息，都来自这份 manifest。所以每次新建/修改模型、Source 或分层配置后，系统都会自动重新 parse，把最新状态同步到界面上。

几秒钟后，项目就出现在列表中了。

## 四、分层配置：可视化管理 dbt\_project.yml

项目创建时已经默认配好了三层，但你随时可以通过「分层配置」按钮来调整：

![分层配置列表](https://images.cnblogs.com/cnblogs_com/aspnetx/65269/o_260810173141_07c_layer_config_list.png)

每一行对应 `dbt_project.yml` 中 `models` 下的一个目录配置，可以设置目标数据库、Schema、物化策略等。修改保存后系统会自动重新解析，完全不用手动编辑 YAML。

## 五、配置源系统（Sources）

源数据在 `sales_db` 数据库中，包含 customer、product、salesorder 三张表。我们需要告诉 dbt 这些源表的位置。

切换到「Sources」标签页，点击「新建 Source」：

![Sources 标签页](https://images.cnblogs.com/cnblogs_com/aspnetx/65269/o_260810172226_08_sources_tab.png)

填写 Source 名称、数据库、Schema 等信息：

![新建 Source](https://images.cnblogs.com/cnblogs_com/aspnetx/65269/o_260810172226_08a_new_source_dialog.png))

创建后，在 Source 详情页添加三张源表：

![Source 表列表](https://images.cnblogs.com/cnblogs_com/aspnetx/65269/o_260810172226_08d_source_table_list.png))

这样，在模型 SQL 中就可以用 `{{ source('sales_db', 'customer') }}` 来引用源表了。

## 六、Stage 层：贴源加载

Stage 层是数据仓库的入口，负责从源系统 1:1 加载数据，做字段命名规范化，默认以表形式物化到 `stage_db`。

点击「新建模型」，选择「Stage 层」，编写 SQL：

![新建 Stage 模型](https://images.cnblogs.com/cnblogs_com/aspnetx/65269/o_260810171946_10_fill_stg_customer.png))

```sql
SELECT
    customer_id,
    customer_name,
    gender,
    age,
    city,
    create_date
FROM {{ source('sales_db', 'customer') }}
```

用同样的方式创建 `stg_product` 和 `stg_salesorder`。完成后 Stage 层模型列表如下：

![Stage 层模型列表](https://images.cnblogs.com/cnblogs_com/aspnetx/65269/o_260810171947_11_stage_model_list.png))

点击「运行」按钮，选择运行类型和表达式，即可执行 dbt run：

![运行 stg\_customer](https://images.cnblogs.com/cnblogs_com/aspnetx/65269/o_260810172127_12_run_stg_customer.png))

运行过程中日志实时推送：

![Stage 运行中](https://images.cnblogs.com/cnblogs_com/aspnetx/65269/o_260810171946_13_stage_running.png))

运行成功后，`stage_db` 中就创建好了对应的视图。

## 七、Core 层：维度建模

Core 层采用维度建模，将数据组织为维度表和事实表，写入 `core_db`，以表形式物化。

我们创建三个模型：

| 模型            | 类型  | 上游依赖            |
| ------------- | --- | --------------- |
| dim\_customer | 维度表 | stg\_customer   |
| dim\_product  | 维度表 | stg\_product    |
| fact\_sales   | 事实表 | stg\_salesorder |

以 `fact_sales` 为例，只取已完成的订单作为销售事实：

```sql
SELECT
    s.order_id,
    s.order_date,
    s.customer_id,
    s.product_id,
    s.quantity,
    s.unit_price,
    s.amount,
    s.status
FROM {{ ref('stg_salesorder') }} s
WHERE s.status = 'completed'
```

![编辑 fact\_sales](https://images.cnblogs.com/cnblogs_com/aspnetx/65269/o_260810171113_16_edit_fact_sales.png))

注意这里用的是 `{{ ref('stg_salesorder') }}` 而不是 `source()`。dbt 会自动识别 `stg_salesorder` 在 `stage_db`，`fact_sales` 在 `core_db`，并生成正确的跨库 SQL。

## 八、Mart 层：应用宽表

Mart 层面向具体业务场景，通常构建大宽表直接供报表使用。我们创建一张 `sales_wide` 宽表，关联事实表和所有维度：

```sql
SELECT
    f.order_id,
    f.order_date,
    f.customer_id,
    c.customer_name,
    c.gender,
    c.age,
    c.city,
    f.product_id,
    p.product_name,
    p.category,
    p.price,
    f.quantity,
    f.unit_price,
    f.amount,
    f.status
FROM {{ ref('fact_sales') }} f
LEFT JOIN {{ ref('dim_customer') }} c ON f.customer_id = c.customer_id
LEFT JOIN {{ ref('dim_product') }} p ON f.product_id = p.product_id
```

这个模型会被物化到 `mart_db` 中。

## 九、DAG 血缘图：一眼看清数据流向

切换到 DAG 标签页，完整的数据流向一目了然：

![DAG 全景图](https://images.cnblogs.com/cnblogs_com/aspnetx/65269/o_260810171113_25_dag_overview.png))

- 🔵 蓝色节点：model（模型）
- 🟢 绿色节点：source（源表）
- 🟡 橙色节点：test（测试）

点击任意节点，可以高亮它的完整血缘链路。比如 `sales_wide` 的血缘：

![DAG sales\_wide 血缘](https://images.cnblogs.com/cnblogs_com/aspnetx/65269/o_260810171629_27_dag_sales_wide_lineage.png))

从图中可以清晰看到数据从 `sales_db` 源表 → `stage_db` 贴源 → `core_db` 维度建模 → `mart_db` 宽表的完整路径。

## 十、数据测试：保障数据质量

dbt 不仅能构建模型，还能做数据质量测试。切换到 Tests 标签页，可以创建和管理测试：

![Tests 标签页](https://images.cnblogs.com/cnblogs_com/aspnetx/65269/o_260810171805_21_tests_tab.png))

比如我们创建一个测试，验证销售金额必须为正数：

```sql
SELECT *
FROM {{ ref('sales_wide') }}
WHERE amount <= 0
```

测试的逻辑很简单：如果 SQL 返回任何行，说明存在异常数据，测试失败。运行测试后就能知道数据是否符合预期。

## 十一、运行历史：随时回溯

所有运行记录都保存在「运行历史」标签页中，包括运行类型、选择表达式、状态、开始时间等：

![运行历史列表](https://images.cnblogs.com/cnblogs_com/aspnetx/65269/o_260810171805_28_run_history_list.png)

点击「查看日志」可以查看完整的运行日志，方便排查问题。

## 十二、总结

通过 DBT UI，我们用纯可视化的方式完成了一个完整的数据仓库项目：

1. **项目创建** — 一键生成脚手架和三层分库配置
2. **Source 管理** — 可视化定义源系统表
3. **三层建模** — Stage 贴源、Core 维度建模、Mart 宽表，每层独立数据库
4. **DAG 血缘** — 直观展示跨库数据流向
5. **数据测试** — 保障数据质量
6. **运行历史** — 完整的执行记录和日志

底层由 dbt 驱动，保证了工程化能力（版本控制、增量构建、测试框架等）；上层由 DBT UI 提供可视化操作，降低了使用门槛，也提升了日常开发效率。

如果你正在使用 SQL Server 并考虑引入 dbt，不妨试试 DBT UI，让数据仓库构建变得更简单。
