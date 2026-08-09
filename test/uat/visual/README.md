# 视觉回归测试

使用 **Playwright** 对 DBT UI 前端关键页面与组件做像素级视觉回归测试。

## 覆盖范围

| 用例文件 | 覆盖内容 |
|---|---|
| `test_01_project_list.py` | 项目列表页（空状态） |
| `test_02_detail_tabs.py` | 项目详情页四个标签：Models / Tests / DAG / 运行历史 |
| `test_03_dialogs.py` | 弹窗：新建项目 / 运行 / 连接配置 |

## 前置条件

- 后端运行在 `http://localhost:8000`
- 前端运行在 `http://localhost:5173`
- 已安装 Playwright 与 Chromium 浏览器

## 安装

```bash
pip install playwright
python -m playwright install chromium --with-deps
```

## 运行

```bash
cd test/uat/visual

# 首次运行：生成基线截图
pytest --update-snapshots

# 日常回归：对比基线
pytest

# 只跑某个文件
pytest test_02_detail_tabs.py -v

# 自定义地址
DBT_UI_BASE_URL=http://localhost:5173 DBT_API_BASE_URL=http://localhost:8000 pytest
```

## 基线管理

- 基线截图保存在 `snapshots/` 目录（与测试文件同名的子目录）
- UI 有**预期内**的视觉变更时，用 `--update-snapshots` 重新生成基线并提交
- 建议基线截图纳入版本控制

## 注意事项

- 测试使用固定视口（1440×900, DPR=1），避免不同环境分辨率差异
- 动态内容（如运行时间、项目 ID）不做全页对比，或通过 mask 排除
- DAG 布局由算法生成，只要节点/边/颜色一致即可，位置允许微小差异
