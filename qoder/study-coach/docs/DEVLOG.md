# 开发记录 DEVLOG

> 分工如实：**Qoder CN** 完成本作品的主要编码、调试、测试编写与缺陷修复（含本轮协调方 QA 全部修复）；
> 协调方 **Codex** 负责需求梳理与复核，并用真实浏览器核验应用行为、采集界面截图（见 `COORDINATOR_QA.md`）。
> 除上述外未使用其他工具代写代码。以下按时间线如实记录。

## 元信息

- 主开发：Qoder CN CLI
- 协调/浏览器核验/截图采集：Codex
- 会话日期：2026-11-15（本地 +09:00）
- 环境：Windows 10.0.26200 / Python 3.12.14
- 运行时后端：PyPI 官方 `powercontext[client,cli,server]==1.2.0`（干净虚拟env 验证）；
  开发接口核对期使用 editable 兄弟源码 `d0813396beea304b4ded9911f516dbea1a28b58e`（`1.2.1.dev3+gd0813396b`）
- 代码仓库分支：`LiuHy318/powercontext @ feature/qoder-study-coach`，路径 `qoder/study-coach`
- 需求规格：`PROJECT_BRIEF.md`
- 只读参考源码：`../all-solutions/src/powercontext`（API 核对用，未修改）
- 交付目录：`qoder/study-coach/`

## 时间线（任务 → 实际产出）

1. **读规格与探查环境**
   - 读 `PROJECT_BRIEF.md`；确认赛事约束、验收样例、PowerContext 必须承载核心状态。
   - 确认 `powercontext` 已 editable 安装、`powercontext` CLI 可用；发现 `server` 子命令缺失
     （`ModuleNotFoundError: fastapi`）。

2. **核对 PowerContext 真实接口（只读源码，不臆造 API）**
   - 读 `client/client.py`、`http/_generated/models.py`、`server/cli.py`、`server/settings.py`、`paths.py`。
   - 选定集成面：`PowerContextClient` 的 `create_scope/list_scopes/get_scope`、
     `create_source/get_source/list_sources`、`remember_memory/revise_memory_entry/list_memory_entries`、
     `search_memory(mode=fts)`；确认内置 SQLite 持久化与 `POWERCONTEXT_HOME` 数据目录，
     `SourceType=content`、`MemorySearchMode.FTS` 等取值均来自源码而非杜撰。

3. **安装真实后端依赖**
   - `pip install -e ".[server]"`（退出 0）。随后 `import powercontext.server.cli` 成功。

4. **最小可行性冒烟测试（先证明“真连得上、写得进、读得回”）**
   - `scripts/smoke_test.py`：创建 Scope、写 content Source、写 Memory、`list_memory_entries`、
     `search_memory` FTS 命中并回读，全部成功（输出见 `docs/VERIFICATION.md` §3）。
   - 发现 `MemoryEntry` 身份在 `.citation.entry_id`（非 `.entry_id`），据此修正。

5. **实现后端 `app/`**
   - `config.py`（仅指向 Server，无本地状态）、`domain.py`（API 模型 + 编解码 + 常量）、
     `powercontext_store.py`（把业务对象映射到 Scope/Source/Memory，统一错误翻译为
     `PowerContextBackendError`，绝不伪造成功）、`scheduler.py`（确定性可解释计划算法）、
     `sample_data.py`（合成学习者资料）、`main.py`（FastAPI 编排 + 静态托管）。
   - 迭代修正：`_source_id` 误用改为显式 `note_source_map`；预算分配越界修复；
     `weak-point` 去重避免构造非法空 topic；时间戳改为微秒以稳定乱序。

6. **实现前端 `static/`**
   - 原生 HTML/CSS/JS 响应式中文 UI：空间、偏好、笔记、薄弱点、复习记录、计划、检索；
     后端状态徽标、错误横幅、422/后端不可用可见提示；输出转义防 XSS；`localStorage` 仅存选中空间 id。

7. **编写并跑通真实测试 `tests/`**
   - `scripts/pc_server.py` 以隔离 HOME 启动真实 Server（`python -c` 调 `main()`，修正 `-m` 空退出）。
   - 集成测试 + 调度单测 + 验收样例共 17 项：`python -m pytest` 全绿（见 §5 记录）。后续协调方 QA 轮次
     新增 2 项分页回归，合计 **19 项**全绿（见下方第 10 条）。

8. **端到端实机验证**
   - `scripts/run_all.py` 同时起后端与应用，`httpx` 走完整验收流程，确认失败优先/掌握后间隔变化、
     来源引用、重启恢复均真实生效。

9. **站点与文档**
   - `site/index.html` 静态展示页（合成演示，明确标注未连数据库）。
   - `README.md`、`docs/VERIFICATION.md`、本 `DEVLOG.md`、`docs/SUBMISSION.md`、
     `requirements.txt`、`config.example.env`、`.gitignore`。

10. **协调方 QA 复核后的缺陷修复（本轮，Qoder CN 编码 / Codex 浏览器核验）**
    - **分页丢失（101 存 / 100 列）**：`powercontext_store.list_notes` 原先只取
      `ListSourcesRequest(limit=100)` 的单页；`list_spaces` 只取默认 50 条单页。改为循环跟随
      SDK `next_cursor` 直至为空（`_PAGE_LIMIT=100`）；`Memory` 列表在本 SDK 无游标，未臆造分页参数。
      新增真实回归 `test_notes_pagination_beyond_one_page`（101 条笔记全部列出且进入计划）与
      `test_spaces_pagination_beyond_one_page`（55 个空间全部列出）。
    - **安装基线纠正**：`requirements.txt`/README/VERIFICATION 更正为官方 PyPI 发布版
      `powercontext[client,cli,server]==1.2.0`；注明 `2026-competition-ecosystem` 分支是空资产模板、
      不可安装 SDK。在**干净虚拟env**（无 `--system-site-packages`、无 editable 泄漏）实测：先发现
      `[server]` 未带入 CLI 所需的 `typer`（Server 启动退出码 1），核对元数据后补 `cli` extra 修复，
      19 项测试全绿。运行时不依赖任何本地绝对路径。
    - **Windows 回环代理**：`scripts/pc_server.py` 追加回环 `NO_PROXY`（保留既有排除、不改远程代理），
      就绪探测 `trust_env=False`；`app/config.py:create_client` 让应用后端客户端 `trust_env=False`，
      可靠直达自己的回环 Server。
    - **孤儿进程**：`PowerContextServer.start()` 将就绪等待包进 `try/except`，过早退出或超时时
      只 `stop()` 自己启动的那一个子进程并关闭日志句柄，不留悬挂服务。
    - **界面截图与仓库链接**：集成 Codex 采集的真实应用截图到站点与文档；仓库链接统一指向
      `https://github.com/LiuHy318/powercontext/tree/feature/qoder-study-coach/qoder/study-coach`。

## 诚实声明

- 界面截图均为协调方 Codex 用真实浏览器对本地运行实例的实际采集（`site/assets/*.jpg`），Qoder CN
  未生成或伪造任何截图，也未编造用户量、提效数据、参赛 UID 或发布链接；Qoder 原生对话截图本会话未产生、不虚构。
- 未读取或打印凭据/环境密钥；未联系任何人；未改动 `../all-solutions` 等参考仓库；未改动 git 远端、
  未发布/推送源码。提交/发布由协调方基于官方生态基线在 `feature/qoder-study-coach` 分支处理。
- PowerContext 为唯一事实存储，核心状态均经真实 SDK/HTTP 读写；集成测试自启真实 Server。
