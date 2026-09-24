# M.Video ERP 项目规则

## 项目累计跟进报告规则（2026-09-24）

- 对 M.Video ERP 的代码修改、配置调整、服务启停、批量任务启动/暂停/重试、部署或数据修复，统一累计更新唯一中文报告；只读检查不更新报告。
- 报告固定累计更新 `docs/followups/MVIDEO_FOLLOWUP_2026-09-24_0912.zh-CN.md`，不得按日期或单次任务新建额外报告，也不得与 Ozon ERP 报告合并。
- 每次更新至少追加：跟进目标、变更前状态、实际操作、涉及文件/服务/数据、验证证据、剩余风险、恢复或回滚方式，以及可直接复制到其他对话的摘要。
- 用户要求在其他对话跟进时，优先引用本项目唯一累计报告，不得仅依赖当前聊天上下文。

## 单 SKU Ozon → M.Video 后端规则（2026-09-24）

- 单 SKU 流程使用独立 `single_sku_jobs` / `SingleSkuJob` 模型和独立状态，禁止接入或复用 `MigrationBatch`、`MigrationItem` 的批量迁移状态机。
- 当前阶段只允许 dry-run：构造 Excel 模板行和本地 workbook，不设置 `upload_ref`、不设置 `uploaded_at`、不调用真实上传。
- Ozon 的 RUB 零售价只作为来源证据，绝不能自动写入 CNY 采购成本；定价只接受人工确认、有限且大于 0 的 CNY 采购价。M.Video 的 RUB 售价和正整数库存也必须发布前确认。
- Ozon 来源包装单位为 mm/g；定价函数尺寸使用 cm、重量使用 g，Excel 重量使用 kg。换算必须精确执行：`mm ÷ 10`、`g ÷ 1000`。
- 切带机固定映射：Ozon 类目 `17029021` → M.Video group `604171101`、infomodel `INF-307590`；模板为 `work/template_dispenser.xlsx`，工作表 `Шаблон для загрузки товаров`，数据从第 5 行开始。禁止再使用 `605085601` 或 `INF-303899`。
- 类目映射必须存在且状态为 `confirmed`；未知类目、缺失材质、类目要求的证书、TN VED 或品牌授权不满足时必须阻断。
- 所有上传商品品牌固定写 `Нет бренда`；标题和描述必须净化品牌内容但允许保留型号。

## Python 包加载与集成接口测试规则（2026-09-24）

- `backend/app` 包内部必须使用相对导入：包顶层模块使用 `from .module`，`integrations`、`pipeline` 等子包使用 `from ..module`；禁止在包内写 `from app...`，避免测试同时加入仓库根和 `backend` 后加载出 `backend.app` 与 `app` 两套模块和配置缓存。
- 使用 FastAPI `TestClient` 调用内存 SQLite 时，测试引擎必须同时设置 `check_same_thread=False` 与 `poolclass=StaticPool`，因为请求在独立线程执行；默认内存连接池会让建表连接和请求连接不是同一个内存数据库。
- 外部系统 intake 接口必须校验 `X-Integration-Key`：服务端未配置密钥返回 503，缺失或错误密钥返回 401；密钥不得出现在响应、日志、测试快照或提交文件中。
- 版本化 intake 请求必须保留 `schema_version` 与 `idempotency_key`；同一幂等键绑定不同货源时返回 409，重复货源应幂等返回同一任务。
- `SingleSkuJob` 必须由数据库强制 `(source_platform, source_product_id, source_sku_id)` 自然键唯一，约束/索引名固定为 `uq_single_sku_jobs_source`；不能只依赖应用层查询，避免并发 intake 创建重复任务。
- FastAPI startup 必须先执行 `init_db()`；旧库补建 `ix_single_sku_jobs_idempotency_key` 或 `uq_single_sku_jobs_source` 前，若发现重复幂等键、重复自然键或不完整来源身份，必须抛出错误并要求先备份和人工对账，禁止静默合并。
