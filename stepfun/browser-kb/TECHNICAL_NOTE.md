# EdgeKB 一页技术说明

**环境与口径。** 2026-11-16，Windows 11 / 13th Gen Intel(R) Core(TM) i9-13900HX，32 逻辑核，
Chrome 157.0.8103.52；seekdb 1.4.0，内存预算 2 GB，随机本地 TCP。
固定 16 篇合成英文文档、6 条查询、二值相关性标注；每配置 3 次导入、18 次查询，耗时取中位数。
质量为 Recall@3 / nDCG@3，全部排名来自真实 seekdb；小样本结果不外推。

**模型与量化。** Xenova/all-MiniLM-L6-v2，提交 `751bff37182d3f1213fa05d7196b954e230abad9`，Apache-2.0。
采用作者公开预量化 ONNX：FP32、FP16、INT8（`model_quantized.onnx`），384 维、mean pooling、归一化。
下载脚本固定版本并记录实际 SHA256；体积口径为相同 tokenizer/config 加各自 ONNX，不含共用 WASM。
INT8 压缩比 **3.85×**，FP16 **1.98×**。

| 精度 / 后端 / 批大小 | 模型 MiB | 文档/秒 | DB 检索 ms | 查询端到端 ms | Recall / nDCG |
|---|---:|---:|---:|---:|---|
| FP32 / wasm / 1 | 86.88 | 50.70 | 7.62 | 30.39 | 1.000 / 1.000 |
| Q8 / wasm / 1 | 22.59 | 72.36 | 6.53 | 23.99 | 1.000 / 1.000 |
| Q8 / wasm / 8 | 22.59 | 55.33 | 9.42 | 37.37 | 1.000 / 0.987 |
| FP16 / webgpu / 8 | 43.88 | 155.98 | 6.99 | 32.74 | 1.000 / 1.000 |

**端侧与状态。** Transformers.js 4.3.2 / ONNX Runtime Web 在浏览器 Worker 推理；
优先 WebGPU FP16 并做真实试运行，失败则重建 WASM Worker（INT8），UI 显示实际后端。
Chrome 157 实际跑通 GPU；Chromium 141 GPU 初始化失败后实际降级成功。浏览器请求被限定至本机，外部请求为 0。
集合键包含知识库、精度与模型版本，切换清除旧结果，请求固定目标；不同向量空间不混用。

**数据库与优化。** seekdb-js 的 Schema 创建 cosine HNSW、全文索引，存 ID、原文、向量、元数据；
`embeddingFunction:null`。`hybridSearch` 交由 `DBMS_HYBRID_SEARCH.GET_SQL` 进行库内 RRF（常数 60）。
完整 DB 操作排队，避免连接级搜索变量串扰；upsert 增量写入，整次导入结束统一 refresh。
同一批浏览器真实向量，逐文档写入/刷新与批量统一刷新各重复 3 次：中位数
**10584.12 → 657.75 ms（16.09×）**，相关性指标一致；该对照排除 embedding 耗时。
WASM 批 8 在本机较批 1 慢，故默认批 1；WebGPU 批 8 提升导入吞吐，短查询延迟未优于 INT8/WASM。
首次观察的文件加载/会话初始化、图预热和后续请求分别记录；缓存口径及逐次数据见附录 JSON。

**复现。** README 安装后 `npm start`；`npm test`（5 项通过）、`npm run benchmark`。
附录：`docs/evidence/browser-benchmark.json`、`model-manifest.json`、`ui-smoke.json`；截图见 `docs/images/`。
