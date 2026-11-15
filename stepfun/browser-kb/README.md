# EdgeKB：浏览器端向量化与 seekdb 混合检索

对应赛事「阶跃星辰」题目。完整源码、固定依赖、合成语料、实测原始记录均在 `stepfun/browser-kb/`。
一页说明见 [TECHNICAL_NOTE.md](TECHNICAL_NOTE.md)，完整实测见 [docs/evidence/browser-benchmark.json](docs/evidence/browser-benchmark.json)。

## 安装与启动（Windows 11 已实测）

需要 Node.js 22+（实测 24.22.1）、Python 3.11+、Chrome / Edge 现代版本、至少约 3 GB 可用内存。
本项目通过官方 `@oceanbase/seekdb-node` 启动独立本地 seekdb 进程，再以 **seekdb-js 的 server 模式**连接。
不需要 Docker、WSL、API Key 或云端推理服务。原生运行库随 npm 的平台可选依赖安装，请勿禁用 optional dependencies。

在仓库根目录执行：

```powershell
cd stepfun/browser-kb
npm ci --ignore-scripts
python -m pip install -r requirements-models.txt
npm run models
npm run build
npm start
```

打开 <http://127.0.0.1:8027>。`npm ci --ignore-scripts` 避免下载本应用完全不用的 Node 端 ONNX 推理组件；
浏览器 Worker 构建使用已随平台可选依赖提供的 esbuild 二进制。推理不在 Node 中运行。
`npm start` 的 prestart 会重新构建 Worker，也可以显式运行 `npm run build`。

模型首次下载约 157 MB，首次 npm 安装还会取得当前系统的 seekdb 原生运行库。
网络需要镜像时，可在模型下载前设置 `$env:HF_ENDPOINT='https://hf-mirror.com'`；仍固定同一模型提交版本。
下载后所有模型、运行时脚本和 WASM 均由本机服务提供，浏览器不再依赖模型站点。
Linux/macOS 未做本机运行库验证；若自动本地运行库未返回 TCP 端点，请配置已有本地 seekdb server 的环境变量。
示例在 `config.example.env`，运行前在终端设置变量；本应用不自动加载 `.env` 文件。

## 一次完整验证

1. 选择「自动」，点击「加载本地模型」；界面显示实际 WebGPU/FP16 或降级后的 WASM/INT8。
2. 当前知识库保持 `notes`，点击「导入内置英文样例」，等待提示共 16 条且索引刷新完成。
3. 查询 `How do indexes accelerate SQL queries?`，混合检索首条应为 `Database indexes`，结果附原文、ID 和排序分值。
4. 粘贴新段落后导入，刷新完成后查询其中关键词，验证增量写入；重复导入同一资料使用 upsert，稳定 ID 不重复新增。
5. 输入另一个知识库名，例如 `other`，旧结果立即清除；导入不同资料，再从「已有知识库」切回 `notes` 验证隔离。
6. 改变模型精度后重新加载、重新导入；不同精度/模型版本的向量使用不同集合，查询不会混用旧向量。
7. 关闭服务后重新 `npm start`，知识库保留在 `.runtime/seekdb/`。

支持 `.txt`、`.md` 和 JSON 文件；JSON 是 `{id,title,text}` 数组，或 `{documents:[...]}`，见 `data/sample.json`。
纯文本按空行分段，长段落按 120 词分块。每次最多 500 块，每文件最多 1 MB。
all-MiniLM-L6-v2 以英文为主，基准与样例使用英文，不宣称已验证中文检索质量。

## 数据流与数据库责任

`src/embedding-worker.mjs` 在浏览器 Worker 中执行 Transformers.js / ONNX Runtime Web。
FP32、FP16 与 INT8 的文档向量和查询向量均由浏览器计算，维数 384，mean pooling + L2 normalize。
`public/core.mjs` 在 GPU 初始化或实际试运行失败时终止失败 Worker，建立全新的 WASM Worker；界面使用实际返回的后端和精度。
WASM 默认最多 4 线程，COOP/COEP 隔离由本地 Web 服务设置。

后端只接收已计算的向量，不提供 embedding endpoint。`lib/store.mjs` 使用 seekdb-js：

- `Schema`：384 维 cosine HNSW + `space` 全文索引，`embeddingFunction:null`，禁用服务端默认向量化。
- 业务字段：SDK 集合中的 ID、document、embedding、metadata（标题、模型版本、精度、`embeddingLocation=browser`）。
- `hybridSearch`：全文 query + KNN + RRF（rankConstant=60）；实际调用 seekdb 的 `DBMS_HYBRID_SEARCH.GET_SQL` 并执行生成的 SQL。
- 应用不在 JavaScript 中拉取两路候选再自行融合，也不在客户端实现检索替代数据库。
- 导入分批 upsert，**整次导入结束只 refresh_index 一次**；成功响应须等刷新完成。稳定 ID 支持增量和幂等重传。
- 服务端序列化完整数据库操作，保护 SDK hybridSearch 使用的连接内 `@search_parm`，避免并发会话覆盖搜索参数。

## 复现测试与性能报告

```powershell
npm test
npx playwright install chromium
npm run build
npm run benchmark
```

基准默认使用本机 Chrome（Playwright `channel=chrome`）；没有 Chrome 时可设置 `$env:BROWSER_CHANNEL='chromium'`。
基准在独立浏览器上下文中运行，使用同一页面、同一 Worker 和真实本地 seekdb。
每组使用固定 16 文档 / 6 查询，重复 3 次，保留逐查询记录、三次导入记录和中位数。
测试浏览器禁止访问非 localhost 主机；实测没有云端请求。
「运行完整对照」按钮也执行相同浏览器基准，并可下载原始 JSON。
输出位于 `.runtime/browser-benchmark.json`，表格与实验边界见一页技术说明。

`scripts/refresh-benchmark.mjs` 可单独补跑刷新策略对照；`scripts/ui-smoke.mjs` 验证自动后端、导入、查询、切换和手机宽度。
`scripts/browser-inference.mjs` 是独立组件测试，不宣称完成数据库检索。
数据库集成测试用人工基向量只检查存取/隔离；**质量与性能报告全部使用真实浏览器模型向量**。

## 模型与开源来源

模型：[`Xenova/all-MiniLM-L6-v2`](https://huggingface.co/Xenova/all-MiniLM-L6-v2)，
提交 `751bff37182d3f1213fa05d7196b954e230abad9`，Apache-2.0；来源为 sentence-transformers/all-MiniLM-L6-v2。
本项目采用模型作者公开提供的预转换 FP32、FP16、INT8 ONNX 权重：分别为 `model.onnx`、`model_fp16.onnx`、
`model_quantized.onnx`。**没有声称自行训练或重新量化模型**。获取过程为固定 revision 下载这些文件，并记录实际体积与 SHA256；
详见 `scripts/download_models.py`、`model-config.json`、`docs/evidence/model-manifest.json`。

依赖使用官方 [seekdb-js](https://github.com/oceanbase/seekdb-js)、
[seekdb-bindings](https://github.com/oceanbase/seekdb-bindings)、
[Transformers.js](https://github.com/huggingface/transformers.js)，版本固定在 package-lock.json。
应用业务代码、测试、合成语料与评测流程在本题中新增，没有复制其他参赛者方案。

## 验证边界

实测浏览器版本和设备写入原始 JSON。Chrome 157 已测通实际 WebGPU FP16 和 WASM；旧 Chromium 141 的 GPU 模型初始化失败时，
已实际验证重建 WASM Worker 降级。没有假称该旧环境的 GPU 路径成功。
Edge 未单独执行本机性能对比。固定小样本的高 Recall 不代表通用检索质量或赛事得分。
首次浏览器模型文件加载/会话初始化与图预热、后续查询计时分开记录；模型缓存可能被复用，原始报告明确说明缓存口径。

运行界面实拍见 `docs/images/desktop.png`、`docs/images/mobile.png`。
