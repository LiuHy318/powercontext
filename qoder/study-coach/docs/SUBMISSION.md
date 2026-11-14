# 提交材料清单 SUBMISSION

## 已交付（位于 `qoder/study-coach/`）

- [x] 源码：`app/`（后端）、`static/`（前端）、`scripts/`（启动与冒烟）
- [x] 依赖文件：`requirements.txt`（固定官方 PyPI `powercontext[client,cli,server]==1.2.0`；
      并注明 `2026-competition-ecosystem` 是空资产模板、不可安装 SDK，运行时不依赖本地绝对路径）
- [x] 配置示例：`config.example.env`（仅占位值，无凭据）
- [x] 忽略规则：`.gitignore`（`.runtime/`、venv、缓存、*.db 等运行产物不入库）
- [x] 测试：`tests/`（真实集成 + 调度单测 + 验收样例，**19 项全绿**，含 101 笔记 / 55 空间分页回归）
- [x] 干净虚拟env 安装验证：隔离 venv（无 `--system-site-packages`）安装官方 1.2.0 后全量测试通过（见 VERIFICATION §1b）
- [x] 协调方 QA 缺陷修复：分页游标、回环代理、就绪失败仅清理自有子进程（见 VERIFICATION §5b、DEVLOG 第 10 条）
- [x] 合成验证样例：`app/sample_data.py` + `POST /api/seed-sample`
- [x] 验证结果与逐条命令输出：`docs/VERIFICATION.md`
- [x] 真实开发记录：`docs/DEVLOG.md`（分工如实：Qoder CN 编码/修复，Codex 需求梳理 + 浏览器核验 + 采集截图）
- [x] 真实应用截图：`site/assets/memory-plan.jpg`、`after-mastery.jpg`、`mobile.jpg`（Codex 浏览器采集，已集成到站点/文档）
- [x] Qoder Sites 静态展示产物：`site/index.html`（合成演示 + 真实截图，明确标注未连接数据库）
- [x] 完整运行说明：`README.md`
- [x] 代码仓库链接：`https://github.com/LiuHy318/powercontext/tree/feature/qoder-study-coach/qoder/study-coach`

## 需求覆盖对照

| 规格条目 | 实现证据 |
|---|---|
| 1 学习空间 + 明确隔离 | PowerContext Scope；`test_scope_isolation` |
| 2 导入笔记（标题/原文/来源/知识点） | content Source；`test_powercontext_write_and_read_roundtrip` |
| 3 偏好/薄弱点/复习记录 | Memory 条目；`test_preference_persisted_and_reused` |
| 4 有解释的复习计划 | `app/scheduler.py`；计划项 `reasons`/`factors` |
| 5 检索记忆 + 真实来源引用，计划反映变化 | `search_memory(fts)` + Source；`test_acceptance_walkthrough` |
| 6 重启后仍可读取 | SQLite 持久化；`test_restart_recovery` |
| 7 演示与真实区分、失败可见 | 后端状态徽标/错误横幅；`test_invalid_inputs_are_visible`、`test_backend_unavailable_is_not_faked` |
| 真实 PowerContext 存储/检索，非伪记忆库/浏览器假存储 | 仅经 `PowerContextClient` 读写；见架构映射表 |
| 无外部收费模型 | 无 generation/embedding；确定性算法 |
| 不谎称语义检索 | 仅报告 `mode=fts` |
| 协调方 QA：分页完整性（101 笔记 / 55 空间） | `list_notes`/`list_spaces` 跟随 `next_cursor`；`test_notes_pagination_beyond_one_page`、`test_spaces_pagination_beyond_one_page` |
| 协调方 QA：可复现干净安装 | 隔离 venv 安装 `powercontext[client,cli,server]==1.2.0`，19 项全绿；VERIFICATION §1b |
| 协调方 QA：回环代理与孤儿清理 | `NO_PROXY` 追加回环 + 客户端 `trust_env=False`；就绪失败仅 `stop()` 自有子进程；VERIFICATION §5b |

## 发布前待办（需授权 / 需外部动作，尚未执行）

- [ ] **参赛账号 UID**：由作者在官方账号页面确认后填写到 `README.md` / `site/index.html`——当前显式留空，绝不臆造。
- [x] **真实界面截图**：已由协调方 Codex 用浏览器采集（`site/assets/*.jpg`）并集成到站点/文档（真实应用截图，非 Qoder 原生对话截图）。
- [x] **代码仓库链接**：`https://github.com/LiuHy318/powercontext/tree/feature/qoder-study-coach/qoder/study-coach`。
- [ ] **Qoder Sites 发布**：按任务要求，本次**未发布/未推送**；发布需既有用户授权并确认公开可未登录访问。
- [ ] **源码提交/推送**：由协调方基于官方生态基线在 `feature/qoder-study-coach` 分支处理；本会话未改动 git 远端、未推送。

## 运行入口速查

```bash
pip install "powercontext[client,cli,server]==1.2.0"   # 官方 PyPI 发布版（非空模板分支）
pip install -r requirements.txt                         # 应用依赖（requirements.txt 也固定同一版本）
python scripts/run_all.py                               # 起真实后端 + 应用 → http://127.0.0.1:8010
python -m pytest -q                                     # 真实集成测试（自启隔离 PowerContext Server，19 项）
```
