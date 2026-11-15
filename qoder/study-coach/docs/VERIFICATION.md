# 验证记录 VERIFICATION

本文件记录 StudyRecall 的**实际**执行命令与真实输出，未运行的检查一律不标注为通过。
应用编码与修复由 **Qoder CN** 执行；协调方 **Codex** 负责真实浏览器行为核验并采集应用截图
（见 `COORDINATOR_QA.md`）。运行时产物位于被忽略的 `.runtime/`。

## 0. 环境

```
OS            : Windows 10.0.26200 (x64)
Python        : 3.12.14
```

两套环境都被真实运行过，用途不同，如实区分：

- **开发期（功能与接口核对）**：editable 兄弟源码
  `powercontext @ d0813396beea304b4ded9911f516dbea1a28b58e`，版本 `1.2.1.dev3+gd0813396b`
  （= 官方赛事基线 `9db1753434162c0aa7c9f1189a1722e617880a52` + 仅追加 PDF 的提交）。
  fastapi 0.163.0 · uvicorn 0.54.0 · httpx 0.28.1 · pydantic 2.14.3 · pytest 9.0.2。
- **可复现安装验证（干净虚拟env，见 §1b）**：PyPI 官方发布版
  `powercontext[client,cli,server]==1.2.0`，**不带 `--system-site-packages`、不含任何 editable 包**，
  fastapi 0.163.0 · httpx 0.28.1 · pydantic 2.14.3 · pytest 9.2.0。

> 更正：`2026-competition-ecosystem` 分支只是**空资产模板**，不可 `pip install` 出 SDK；运行时基线为
> 官方 PyPI 发布版（或官方 git 提交），非模板分支。

## 1. 安装 PowerContext Server 依赖（真实后端可运行，开发期 editable 环境）

```bash
cd powercontext && pip install -e ".[server]"
```
结果：退出码 `0`（日志 `.runtime/pip-install.log`）。安装前 `import powercontext.server.cli` 报
`ModuleNotFoundError: No module named 'fastapi'`，安装后：
```
$ python -c "import powercontext.server.cli as c; print('server cli OK')"
server cli OK
```

## 1b. 干净虚拟env 的可复现安装验证（§7 测试即在此环境跑通）

```bash
# 干净 env，无系统站点包，确认此时 powercontext 尚不可导入
python -m venv <短路径>/venv-clean            # 未加 --system-site-packages
<短路径>/venv-clean/Scripts/python.exe -c "import powercontext"   # -> ModuleNotFoundError（隔离干净）

# 固定安装官方发布版的三个 extra（client SDK + cli 启动器 + server 运行时/内置 SQLite）
<短路径>/venv-clean/Scripts/python.exe -m pip install "powercontext[client,cli,server]==1.2.0" fastapi "uvicorn>=0.34,<1" "httpx>=0.28,<1" "pydantic>=2,<3" "pytest>=8,<10"
```
真实结果（逐条）：
```
Successfully installed ... powercontext-1.2.0 fastapi-0.163.0 uvicorn-0.54.0 httpx-0.28.1 pydantic-2.14.3 pytest-9.2.0 ...
$ python -c "from importlib.metadata import version; import powercontext; print(version('powercontext'), powercontext.__file__)"
1.2.0  <短路径>/venv-clean/Lib/site-packages/powercontext/__init__.py     # 来自干净 env，非 editable 兄弟
```
兼容性差异与修复：首次 `pip install "powercontext[server]"` 后运行 `powercontext server run` 报
`ModuleNotFoundError: No module named 'typer'`。核对 1.2.0 元数据发现 `typer` 等 CLI 依赖位于
**`cli`** extra 而非 `server`；据此把安装改为 `powercontext[client,cli,server]==1.2.0`（并写入
`requirements.txt`），`Successfully installed typer-0.29.1 ...` 后一切正常。§7 的 21 项测试即在此干净
env 全绿。Windows 提示：把 venv 建在较浅路径可避开依赖深层文件名触及 260 字符路径上限（或开启长路径支持）。

## 2. 启动真实 PowerContext Server 并确认可用

```bash
POWERCONTEXT_HOME=.../qoder/study-coach/.runtime/pcdata \
  powercontext server run --host 127.0.0.1 --port 8777 --no-env-file
```
真实日志尾部：
```
INFO powercontext.server.factory PowerContext Server is ready
INFO uvicorn Uvicorn running on http://127.0.0.1:8777
```
（附带中文推理能力提示：未配置 generation/embedding 模型——符合“不使用外部模型”的设计。）

## 3. SDK 往返冒烟测试（create_scope / create_source / remember_memory / search_memory）

```bash
python scripts/smoke_test.py
```
真实输出：
```
live: {'status': 'ok'}
scope_id: scp_3dnr47ggq4yrr0kerc1pqd80w1
source_id: src_472e4ad5342a4e4eaffe42f02d65ff66 digest: sha256:af2a6ded028
source content: {"body": "RR 与 RC", "knowledge_points": ["事务隔离级别"], "record_kind": "note", "title": "事务隔离级别"}
memory entry: mem_ent_55c3d3c2e6f9484c8e8fda0eb0a59b38 kind: review
memory entries: 1
search mode: fts hits: 1
  hit score 0.016 matched_by [<MemoryMatchedBy.FTS: 'fts'>] text {"topic": "事务隔离级别", "result": "fail"}
sources in scope: 1
```
结论：Scope / content Source（含 sha256 摘要）/ Memory 条目均**真实写入并可读回**，FTS 命中如实报告 `matched_by=fts`。

## 4. 完整应用端到端（FastAPI + 真实后端，浏览器所用的同一 HTTP 路径）

```bash
python scripts/run_all.py --app-port 8010      # 启动 PowerContext Server + 应用
```
用 UTF-8 安全的 `httpx` 客户端走验收流程（注：Windows Git Bash 直接 `curl -d` 传中文会破坏请求体，
应用本身对 JSON 体按 UTF-8 正确解析，见第 6 节 422/后端不可用行为）：

```bash
python - <<'PY'
import httpx
B='http://127.0.0.1:8010'; c=httpx.Client(timeout=20)
sid=c.post(B+'/api/seed-sample').json()['space']['scope_id']
c.post(f'{B}/api/spaces/{sid}/reviews', json={'topic':'索引选择','result':'fail','score':1})
print('reviews:', [r['topic']+':'+r['result'] for r in c.get(f'{B}/api/spaces/{sid}/reviews').json()])
for i in c.post(f'{B}/api/spaces/{sid}/plan', json={}).json()['items'][:3]:
    print(' ', i['topic'], i['priority_score'], 'mins', i['allocated_minutes'], i['reasons'])
c.post(f'{B}/api/spaces/{sid}/reviews', json={'topic':'索引选择','result':'mastered','score':5})
plan2=c.post(f'{B}/api/spaces/{sid}/plan', json={}).json()
m=next((i for i in plan2['items'] if i['topic']=='索引选择'), None)
print('after mastery -> 索引选择:', (m['next_interval_days'], m['last_result']) if m else 'DROPPED from due list')
PY
```
真实输出：
```
reviews: ['索引选择:fail']
  事务隔离级别 22.0 mins 5 ['从未复习，需要排入首轮复习', '薄弱知识点（程度 5/5）']
  索引选择 16.0 mins 5 ['薄弱知识点（程度 4/5）', '复习失败 1 次']
  不可重复读 7.0 mins 5 ['从未复习，需要排入首轮复习']
after mastery -> 索引选择: DROPPED from due list
```
说明：记录“失败”后，失败知识点被读回并体现在计划理由中；记录“已掌握”后，其间隔增长并退出当日到期列表——
排序/间隔发生可解释的合理变化，且数据来自真实 PowerContext。

健康检查（浏览器加载时调用 `/api/health`）返回真实后端状态：
```
{"powercontext_url":"http://127.0.0.1:1980","liveness":"ok","readiness":"ready"}
```

## 5. 自动化测试（真实集成，含重启恢复、空间隔离与分页回归）

以下 **21 项**均在 §1b 的干净虚拟env（`powercontext[client,cli,server]==1.2.0`）中执行：

```bash
<CLEAN-VENV>/Scripts/python.exe -m pytest -v
```
真实结果：**21 passed in 14.30s**（本轮在此干净 env 实测；早前 editable 开发环境同代码为 19 passed，系安全单测文件加入前）
```
tests/test_acceptance_sample.py::test_acceptance_walkthrough                PASSED
tests/test_config_security.py::test_rejects_remote_plaintext_http_without_network PASSED
tests/test_config_security.py::test_allows_loopback_http_and_remote_https   PASSED
tests/test_scheduler_unit.py::test_no_inputs_yields_empty_plan              PASSED
tests/test_scheduler_unit.py::test_weaker_never_reviewed_topic_ranks_first  PASSED
tests/test_scheduler_unit.py::test_determinism_same_inputs                  PASSED
tests/test_scheduler_unit.py::test_budget_is_respected                      PASSED
tests/test_scheduler_unit.py::test_mastery_grows_interval_and_fail_resets_it PASSED
tests/test_studyrecall_integration.py::test_health_reports_real_backend     PASSED
tests/test_studyrecall_integration.py::test_powercontext_write_and_read_roundtrip PASSED
tests/test_studyrecall_integration.py::test_preference_persisted_and_reused PASSED
tests/test_studyrecall_integration.py::test_empty_space_initial_experience  PASSED
tests/test_studyrecall_integration.py::test_plan_uses_past_memory_and_shifts_on_mastery PASSED
tests/test_studyrecall_integration.py::test_plan_is_deterministic_for_same_inputs PASSED
tests/test_studyrecall_integration.py::test_scope_isolation                 PASSED
tests/test_studyrecall_integration.py::test_search_returns_real_citations   PASSED
tests/test_studyrecall_integration.py::test_invalid_inputs_are_visible      PASSED
tests/test_studyrecall_integration.py::test_backend_unavailable_is_not_faked PASSED
tests/test_studyrecall_integration.py::test_restart_recovery                PASSED
tests/test_studyrecall_integration.py::test_notes_pagination_beyond_one_page PASSED
tests/test_studyrecall_integration.py::test_spaces_pagination_beyond_one_page PASSED
```

覆盖映射：
| 要求 | 测试 |
|---|---|
| 真实 PowerContext 写入与读取 | `test_powercontext_write_and_read_roundtrip` |
| 计划使用既往记忆 | `test_plan_uses_past_memory_and_shifts_on_mastery`、`test_acceptance_walkthrough` |
| 空间隔离 | `test_scope_isolation` |
| 重启恢复 | `test_restart_recovery`（停止并重启真实 Server 进程后重读） |
| 无记录时的初始体验 | `test_empty_space_initial_experience` |
| 无效输入 | `test_invalid_inputs_are_visible`（422 / 400） |
| 后端不可用 | `test_backend_unavailable_is_not_faked`（502/503，非假成功） |
| 确定性可复现 | `test_determinism_same_inputs`、`test_plan_is_deterministic_for_same_inputs` |
| **笔记分页完整性（101>100）** | `test_notes_pagination_beyond_one_page` |
| **空间分页完整性（101>100，走 next_cursor 第二页）** | `test_spaces_pagination_beyond_one_page` |
| **回环/明文传输安全（无网络）** | `tests/test_config_security.py::test_rejects_remote_plaintext_http_without_network`、`test_allows_loopback_http_and_remote_https` |

## 5b. 协调方 QA 缺陷的针对性复核（分页 / 代理 / 孤儿进程）

**笔记分页（复现并修复 101 存 / 100 列）**——同 §1b 干净 env，真实 HTTP 往返：
```bash
<CLEAN-VENV>/Scripts/python.exe -m pytest -v -s \
  tests/test_studyrecall_integration.py::test_notes_pagination_beyond_one_page \
  tests/test_studyrecall_integration.py::test_spaces_pagination_beyond_one_page
```
真实输出：
```
tests/.../test_notes_pagination_beyond_one_page PASSED
tests/.../test_spaces_pagination_beyond_one_page PASSED
2 passed in 6.83s
```
`test_notes_pagination_beyond_one_page` 在一个空间内 POST **101 条**笔记，断言
`GET /notes` 返回 `len==101` 且第 101 条知识点在列、`plan.total_topics==101`；
`test_spaces_pagination_beyond_one_page` 创建 **101 个**空间（>单页 100，真正触发 `next_cursor` 第二页），断言全部出现在 `GET /spaces`。
修复位于 `app/powercontext_store.py`：`list_notes`/`list_spaces` 现循环跟随 SDK `next_cursor`
直至为空；`Memory` 列表按本 SDK 设计**无游标**，故未添加不存在的分页参数。

**回环代理安全**——真实断言脚本输出：
```
HTTP_PROXY preserved : http://corp:8080                       # 远程代理不受影响
NO_PROXY original    : .internal,10.0.0.1 -> appended: .internal,10.0.0.1,127.0.0.1,localhost,::1
loopback covered     : True
app http trust_env   : False                                  # 应用后端客户端不经系统代理
```
`scripts/pc_server.py` 用 `_with_loopback_no_proxy` 在**保留既有排除项**的前提下追加回环主机，
就绪探测显式 `trust_env=False`；`app/config.py:create_client` 让应用的 PowerContext 客户端
`trust_env=False`，只影响它对自己回环后端的访问，不改写进程级代理设置。

**孤儿进程清理**——`PowerContextServer.start()` 将 `_wait_ready` 包在 `try/except`，
无论“过早退出”还是“就绪超时”都会 `self.stop()` 只终止**它自己启动的那一个**子进程并关闭其日志句柄，
不留孤儿服务；§1b 首次缺 `typer` 时 Server 退出码 1，正是该路径被触发、测试干净报错（无悬挂进程）。

## 5c. 真实浏览器行为核验与截图（由协调方 Codex 采集）

协调方 Codex 用应用内浏览器打开真实运行实例 `http://127.0.0.1:8010/` 并执行了真实交互：
点击「载入合成示例」新建合成学习空间；对「事务隔离级别」先记一次**复习失败**（计划如实显示该历史失败）、
再记一次**已掌握**（该项随即移出当日到期优先级）；在 **1365×900** 与 **390×844** 视口下核验响应式布局
（移动端文档宽度 375 ≤ 视口 390）。过程中**实际截取了应用界面**并复制到：
```
site/assets/memory-plan.jpg     # 复习计划（1350×890）
site/assets/after-mastery.jpg   # 记为已掌握后的计划（1350×890）
site/assets/mobile.jpg          # 移动端布局（374×2327，390×844 视口）
```
这些是**真实应用截图**，由 Codex 浏览器 QA 采集，非设计稿、非生成图，亦非 Qoder 原生对话截图。


## 6. 失败与边界行为（真实返回，非伪造成功）

- 无效输入：`PUT /preference {"daily_minutes":0}` → **HTTP 422**；`GET /search?q=   ` → **HTTP 400**，
  响应体 `{"error":"检索关键词不能为空",...}`。
- 后端不可用：`create_app("http://127.0.0.1:1")` 后 `GET /api/health` → **HTTP 503**，
  `{"error":"无法访问 PowerContext 服务（请确认服务已启动）: ..."}`（`test_backend_unavailable_is_not_faked`）。

## 7. 初次交付时的受限项（2026-11-15 历史记录，发布状态以第 9 节为准）

- **界面截图**：已由协调方 Codex 用真实浏览器采集并集成到 `site/index.html`、`README.md` 与本记录（见 §5c）；
  这些是真实应用截图，**不是** Qoder 原生对话截图，亦未伪造。
- **Qoder Sites 发布**：用户已明确授权发布，本轮**已真实执行官方流程**，但云端准备被拒绝
  （`sites_unavailable`），因此**尚未发布、无公开网址可报告**；详见 §8，绝不把「已构建/已授权」当作已上线。
  `site/index.html` 为已就绪的静态展示产物，其演示数据已明确标注为合成、未连接数据库。
- **源码推送**：本会话未改动 git 远端、未推送（由协调方处理）。
- **参赛 UID**：`1912194676404092`（用户于 2026-11-15 确认，见 `DELIVERY_IDENTITY.md`），已填入 `README.md`、`site/index.html`、`docs/SUBMISSION.md`；此前未确认时一律留空、绝不臆造。
- **Qoder 原生对话截图**：本会话未生成，也不虚构；如需展示应以真实采集件替换。

## 8. Qoder Sites 发布记录（2026-11-15，未验证发布成功）

Qoder CN 在实际开发会话内使用官方 `sites-hosting` 流程，针对同一个准备意图多次执行。
协调方另行只读核对得到 `productId=qoder-cn`、`region=cn`、`environment=prod`；
CLI 登录状态为个人账号已登录。成功读取运行上下文并不证明发布接口可用。

| 操作 | 真实返回 |
|---|---|
| `get_context` | 中国站生产环境、本地项目上下文、当前未列出绑定站点 |
| `list_sites` | `total_size=0`、`projects=[]`（检查时未列出自有项目） |
| `prepare_site`（相同 action / 输入） | `{"schemaVersion":1,"ok":false,"error":"sites_unavailable"}` |
| `get_publish_status` | `{"schemaVersion":1,"ok":false,"error":"sites_action_unavailable"}` |

准备意图使用 action ID `e8269c7a-b6f1-413b-b0f2-dd2feb0158e0`，选中本项目目录，
`webDirectory=site`、`createNewSite=true`、`displayName=StudyRecall 研学记忆教练`、
`slug=study-recall-coach`、`spa=false`。公共输出仅包含 `index.html` 与 3 张合成资料的真实应用截图。

目前没有取得就绪草稿、公开网址、成功发布状态或公开访问策略的证据；本地未生成 `.qoder.site`
描述文件。失败原因尚未明确，不能据此推断为登录失效、配额耗尽、套餐限制或确定没有任何云端副作用。
访问 API 根路径得到 HTTP 404 也不能独立证明发布服务正常。

原机器本次 Qoder 会话保留了被忽略的 `.runtime/sites-prepare.json` 及相同输入，便于恢复。
恢复时先通过官方原生 Sites 流程检查现状，保留原 action 与请求意图，不创建重复站点。
准备就绪后仍需正式 `publish_site`、读取 `get_publish_status` 确认发布、设置并核对任何人可访问，
最后独立验证未登录访问。另一个机器不能直接复制本机 action 恢复记录。

本节由协调方 Codex 按真实返回更新；Qoder CN 完成主要应用开发、修复、测试及本次发布尝试。

## 9. 2026-11-16 恢复发布成功

原 Qoder CN 开发会话复用同一 action 恢复就绪草稿、完成正式发布并将访问策略设为公开。
官方最终读取确认 `published=true`、`accessMode=public`。保留此前失败记录作为历史，
不再将其视为当前发布状态。

- 作品网址：[https://study-recall-coach-36rgmbqc041.qoder.zone](https://study-recall-coach-36rgmbqc041.qoder.zone)。
- 协调方独立无登录 HTTP 请求：主页 200，项目标题 StudyRecall 研学记忆教练 · 项目介绍，UID 匹配。
- 真实截图 `/assets/memory-plan.jpg`：HTTP 200，SHA256 `e517ff3b91954d0eff56175a6f2fd97a5eb02072ac55db1dbacf93c1fc566a50`。
- 核验未发送登录凭据或会话 Cookie。浏览器自动化连接超时，未取得本次线上页面截图；
  不将 HTTP 验证描述为浏览器无痕截图验证。本地实际界面截图仍见 `site/assets/`。
- 原生 Qoder 对话截图或录屏仍待采集；结构化开发记录已加入此次恢复发布会话。
