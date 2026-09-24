# M.Video ERP 跟进报告（2026-09-24 09:12 CST）

## 后续更新：报告归并规则修正（2026-09-24）

- 用户澄清：只维护一份 M.Video ERP 累计跟进报告，不再按每个对话或每次变更新建报告文件。
- `AGENTS.md` 已改为固定累计更新本文件；该项目报告不得与 Ozon ERP 合并。

## 后续更新：GitHub 初始化与全量留档（2026-09-24）

- 用户指定远端 `git@github.com:leeqiang974-alt/mvideo.git`；已在 `E:\mvideo\MvideoERP` 初始化 Git，并保持 `.env`、数据库、日志等由 `.gitignore` 排除。
- 初始完整快照提交：`3b40e0f`（`chore: initial Mvideo ERP snapshot`）。远端已有仅含 README 的初始化提交，已合并并以本项目完整 README 解决冲突，合并提交为 `1922e79`。
- 已成功推送 `main` 到 GitHub，且本地 `main` 已跟踪 `origin/main`。

## 跟进目标

- 处理前期审计发现的高优先级可用性问题：基础 `/health` 被外部 OMNI 网络探测阻塞。
- 让基础健康检查只反映本地服务和数据库，把外部 OMNI 探测拆为显式诊断接口。
- 在项目中固化独立跟进报告要求。

## 变更前状态

- 笔记本 `C:\MvideoERP` 服务由计划任务 `MvideoERP-Boot` 启动，监听 `127.0.0.1:8077`。
- 原 `/health` 每次同步调用 OMNI `check_connection()`；外部 API 延迟或超时时，本地健康检查也会超时。
- 工作站完整测试基线为 85 项通过。
- 项目没有 Git 仓库，不能依赖提交历史回滚。

## 实际修改

- 修改 `backend/app/main.py`：
  - `/health` 只读取本地数据库、表清单和最新批次，不再访问外部 OMNI。
  - 表清单改为从当前数据库实际 schema 读取，不再把代码声明的表误报为已存在。
  - 保留兼容字段 `omni_ok=null`，新增 `omni_status=not_checked`。
  - 新增 `/health/integrations/omni`，仅在明确调用时进行外部 OMNI 连通性探测。
- 新增 `tests/test_health_routes.py`，验证基础健康检查不会触发外部集成探测语义。
- 新增项目 `AGENTS.md`，固化 M.Video 独立跟进报告要求。
- 同步上述运行代码和测试到笔记本 `C:\MvideoERP`，按原计划任务停止并重新运行 `MvideoERP-Boot`。
- 将项目规则和本报告同步到笔记本项目，供后续对话直接引用。
- 未修改 SQLite 数据库、批量队列、价格、库存或 OMNI 写入逻辑。

## 安全备份与一致性

- 修改前 `main.py` 已重建并备份到：`C:\MvideoERP-backups\20260924-090908\backend\app\main.py`。
- 修改前备份 SHA-256：`1ec19fac1983c9c438870957d814ad909bb72cd4f9f2a3effc4a070b9b4ad8c1`，本地重建文件与远端备份一致。
- 修改后 `main.py` 本地和笔记本 SHA-256 均为：`99d898f94350d7b2d80a654a5d53d0130dae2f9d75a7b4f652a1d0a5b1990f0f`。

## 验证证据

- 工作站完整测试：`89 passed`；新增测试覆盖基础健康检查的“外部配置调用即失败”哨兵，以及 OMNI 未配置、连通、不可用和客户端关闭行为。
- 笔记本现有虚拟环境未安装 pytest，因此远端无法重复跑 pytest；已使用远端虚拟环境执行 `py_compile`，`main.py` 和新测试文件均通过语法编译。
- 重启 `MvideoERP-Boot` 后，笔记本本机请求 `http://127.0.0.1:8077/health` 返回 HTTP 200。
- 返回内容包含：`ok=true`、数据库实际 `table_count=7`、`omni_ok=null`、`omni_status=not_checked`，最新批次仍为 ID 7、状态 `done`。包含 SSH 往返的实测约 0.9 秒。
- 笔记本显式请求 `/health/integrations/omni` 成功返回结构化结果 `omni_ok=false/status=unavailable`，证明新路由可用，同时说明当时 OMNI 外部连通性不可用；基础 `/health` 未受其影响。

## 结果与影响

- 基础存活探针不再受 OMNI 外部网络延迟影响，服务监控可以区分“本地 API/数据库存活”和“OMNI 不可用”。
- 外部连通性仍可通过 `/health/integrations/omni` 显式检查，不丢失诊断能力。
- 本次重启没有恢复或触发批量外发任务。

## 剩余风险与建议优先级

1. 高：项目尚无 Git 版本基线；应先排除 `.env`、数据库、日志、work 产物和密钥，再建立代码版本管理。
2. 高：此前重传状态文件出现 `todo=0`、`pending_push=374`、末尾批次失败的状态不一致；恢复任何批量写入前应先做只读对账，禁止直接续跑。
3. 中：笔记本测试环境缺少 pytest，部署后只能做语法和接口验收；建议安装与 requirements 锁定一致的开发测试依赖，但不要污染生产运行依赖。
4. 中：`/health/integrations/omni` 仍按当前 OMNI 超时设置同步等待，这是显式诊断接口的预期行为；监控系统不应把它当高频存活探针。

## 恢复/回滚

1. 停止计划任务 `MvideoERP-Boot`。
2. 将备份 `C:\MvideoERP-backups\20260924-090908\backend\app\main.py` 复制回 `C:\MvideoERP\backend\app\main.py`。
3. 删除新增测试文件（可选，不影响运行）。
4. 重新运行 `MvideoERP-Boot`，并验证 `127.0.0.1:8077/health`。

## 可复制到其他对话的摘要

2026-09-24 已修复 M.Video ERP 健康检查被 OMNI 外部请求阻塞的问题：基础 `/health` 现在只检查本地服务和数据库实际 schema，OMNI 探测拆到 `/health/integrations/omni`。本地完整测试 89 passed，笔记本远端语法检查通过，计划任务重启后 `/health` 返回 HTTP 200、`omni_status=not_checked`；显式 OMNI 探测接口可用，但当时返回 unavailable。未修改数据库、批量队列、价格或库存。修改前源码已备份到 `C:\MvideoERP-backups\20260924-090908`。

## 后续更新：单 SKU Ozon → M.Video 后端 dry-run（2026-09-24 15:02 CST）

### 跟进目标

- 按用户确认的“先后端逻辑、后做界面”顺序，建立单 SKU 从 Ozon 来源到 M.Video Excel 模板行的独立 dry-run 流程。
- 严格隔离现有批量迁移状态机；本阶段只生成待人工核对的 Excel workbook，不执行真实上传。

### 变更前状态

- 项目已有类目映射、批量迁移和模板能力，但没有独立的单 SKU 任务表和状态机。
- 完整自动化基线为 89 项通过。
- Ozon 来源 RUB 零售价、CNY 采购价、mm/g 与 M.Video cm/kg 的边界需要在后端固化，避免误把零售价当采购成本或单位填错。

### 实际操作

- 新增独立单 SKU ORM：
  - `backend/app/models.py` 新增 `SingleSkuStatus` 与 `SingleSkuJob`。
  - 字段覆盖来源证据、Ozon 类目、M.Video group/infomodel、CNY 采购成本、mm/g 包装、库存、确认标记、RUB 定价、净化标题描述、dry-run 结果和上传审计字段。
- 更新数据库初始化：
  - `backend/app/database.py` 在建表后执行单 SKU 表的兼容列检查；新增列允许为空，不重写历史数据。
- 新增 `backend/app/single_sku/`：
  - `pricing.py`：复用/承载 RUB 定价计算，输入人工确认的 CNY 成本及规格数据。
  - `brand_sanitizer.py`：品牌固定为 `Нет бренда`，净化标题和描述中的品牌内容，保留型号。
  - `workflow.py`：独立创建任务、校验 confirmed 类目映射、校验采购价/库存/材质/证书/TN VED、执行单位换算、计算售价、构造切带机模板第 5 行并输出 dry-run workbook。
  - `__init__.py`：包初始化文件。
- 新增 `tests/test_single_sku_workflow.py`，覆盖单位换算、RUB 不得作为 CNY 成本、定价、Excel 行列位、无上传状态、类目/库存/合规阻断和旧表补列。
- 更新 `AGENTS.md`，把单 SKU 独立模型、dry-run 边界、固定切带机映射、单位换算和品牌规则固化为项目长期规则。
- 更新 `.gitignore`，忽略测试和 dry-run 生成目录 `/work/single_sku/`。
- 新增 `pytest.ini`，将默认测试路径限定为 `tests`，避免误收集 `work/_make_test.py` 这类手动 HTTP 脚本。

### 涉及文件、服务、数据

- 代码与测试：
  - `backend/app/models.py`
  - `backend/app/database.py`
  - `backend/app/single_sku/__init__.py`
  - `backend/app/single_sku/pricing.py`
  - `backend/app/single_sku/brand_sanitizer.py`
  - `backend/app/single_sku/workflow.py`
  - `tests/test_single_sku_workflow.py`
- 规则与配置：
  - `AGENTS.md`
  - `.gitignore`
  - `pytest.ini`
  - `docs/followups/MVIDEO_FOLLOWUP_2026-09-24_0912.zh-CN.md`
- 未重启笔记本或本机后端服务，未执行真实 M.Video 上传，未修改生产数据库、价格、库存、批量队列或密钥。
- dry-run Excel 仅输出到本地 `work/single_sku/`，该目录已被 Git 忽略。

### 关键业务规则落地

- Ozon 的 RUB 零售价只保存为来源证据，绝不自动作为 CNY 采购成本。
- CNY 采购价必须由人工确认，并且为有限、大于 0 的数值。
- M.Video 库存必须为大于 0 的正整数，RUB 售价由定价模型输出并在发布前确认。
- 精确换算：`mm ÷ 10 -> cm`，`g ÷ 1000 -> kg`；定价函数尺寸使用 cm，Excel 重量使用 kg。
- 切带机固定使用 Ozon 类目 `17029021`、M.Video group `604171101`、infomodel `INF-307590`；模板为 `work/template_dispenser.xlsx`，数据行为第 5 行。
- 类目映射必须为 `confirmed`；证书、TN VED、材质等类目要求不满足时阻断。
- 品牌统一写 `Нет бренда`；标题和描述去除品牌内容，型号允许保留。

### 验证证据

- 语法编译通过：

```powershell
python -m py_compile backend/app/models.py backend/app/database.py backend/app/single_sku/__init__.py backend/app/single_sku/pricing.py backend/app/single_sku/brand_sanitizer.py backend/app/single_sku/workflow.py
```

- 验证过程中先发现并修正两个实现问题：
  - `workflow.py` 缺少 `SingleSkuJob` 导入，已补充。
  - Python 3.14 当前环境的 `Decimal` 不支持 `is_integer()`，库存整数判断已改为余数判断。
- 新增单测单独运行结果：`7 passed`。
- 最终按项目标准命令运行：

```powershell
python -m pytest -q
```

- 最终结果：`96 passed, 167 warnings in 22.90s`。
- 测试已断言 dry-run 结果中 `upload_ref == ""`、`uploaded_at is None`，确认本阶段没有真实上传。

### 剩余风险

1. 当前只完成后端 dry-run 能力，尚无人工核对界面或 API 路由，运营暂时不能从页面操作。
2. 当前发布规则只落地切带机类目；其他类目必须先补齐 confirmed 映射、95 列模板、group/infomodel、证书、TN VED、材质和品牌授权规则。
3. 自动测试覆盖关键字段和阻断条件，但尚未进行业务人员对整份 95 列模板的逐列人工复核。
4. 本次变更尚未部署到笔记本生产环境；当前仅在工作站完成验证和 Git 留档。
5. 输出中的 deprecation warnings 来自既有 FastAPI/SQLAlchemy 用法和新增时间戳写法，当前不影响功能，后续可单独治理。

### 恢复/回滚方式

1. 本次提交尚未部署前，可直接回退该提交，恢复到上一个 Git 版本。
2. 如果某环境已经初始化过新表且确认没有需要保留的单 SKU 任务，可在回退代码后手动删除 `single_sku_jobs` 表；删除前必须先备份数据库。
3. 本地生成的 dry-run workbook 位于忽略目录 `work/single_sku/`，可按需删除，不影响源码。
4. 回滚后重新运行 `python -m pytest -q`，确认恢复到回滚版本的测试状态。

### 可复制到其他对话的摘要

2026-09-24 已完成 M.Video 单 SKU Ozon → M.Video 后端 dry-run：新增独立 `SingleSkuJob` / `single_sku_jobs`，没有混入批量迁移状态机；支持人工确认正 CNY 采购价和正整数库存，精确执行 `mm ÷ 10`、`g ÷ 1000`，调用定价模型生成 RUB 售价，品牌固定为 `Нет бренда` 并净化标题描述，最终生成切带机 95 列模板第 5 行。Ozon RUB 价格仅保留为证据，不会作为 CNY 成本；当前不设置上传引用、不上传。新增 7 个单测，最终完整测试 `96 passed`。dry-run 文件输出到已忽略的 `work/single_sku/`，尚未部署到笔记本生产环境。
## 后续更新：单 SKU intake API 与包加载修复（2026-09-24 15:42 CST）

### 跟进目标

- 为独立的“Ozon → M.Video 单 SKU”流程补齐窄口径版本化 intake API，让外部 Ozon ERP/插件可以通过安全边界创建待人工核对任务。
- 修复测试中 `backend.app` 与 `app` 双模块加载导致的配置缓存分裂，避免接口读取不到调用方设置的集成密钥。
- 保持单 SKU 模型独立于现有批量迁移状态机，并继续严格限制当前阶段只创建任务、不触发定价外发或真实上传。

### 变更前状态

- 上一 Git 基线：`dae0a9c feat: add single-SKU M.Video dry-run workflow`。
- 新增 intake 测试初次运行结果为 `12 failed, 1 passed`；认证失败的主要表现是接口返回 503，原因是测试清了 `backend.app.config.get_settings` 缓存，路由却加载了另一套 `app.config.get_settings`。
- 相对导入修复后，认证问题消失，但 `TestClient` 请求线程拿不到主线程创建的内存 SQLite 表，仍有 5 个 `no such table: single_sku_jobs` 失败。
- 当前没有真实 M.Video 上传，也没有启动或恢复批量任务。

### 实际修改

- 新增 `backend/app/single_sku/api.py`：
  - 路由前缀 `/api/v1/integrations/ozon`，提供 `POST /single-sku-jobs` 和 `GET /single-sku-jobs/{job_ref}`。
  - 仅接受契约版本 `ozon.single-sku.v1`，校验 HTTPS 货源 URL、正包装数值、1–15 张 HTTPS 图片、货源产品/SKU ID。
  - 使用 `X-Integration-Key` 做机器间认证；服务端未配置密钥返回 503，密钥缺失或错误返回 401。
  - 支持自然键幂等和 `idempotency_key`；同一幂等键绑定不同货源返回 409，重复货源返回同一任务和 HTTP 200。
  - 新任务状态为 `awaiting_input`，只保存来源证据，不自动把 Ozon RUB 写成 CNY 采购成本，也不触发自动发布。
- 修改 `backend/app/single_sku/workflow.py`，创建任务时持久化 `schema_version` 与 `idempotency_key`。
- 修改 `backend/app/models.py`，为 `single_sku_jobs` 补充 `schema_version`、`idempotency_key` 字段，并增加数据库级自然键唯一约束 `uq_single_sku_jobs_source`，防止并发 intake 仅靠应用层查询而插入重复货源。
- 修改 `backend/app/database.py`：`init_db()` 在补列后执行 `ensure_single_sku_jobs_indexes()`；旧库补建唯一索引前先检查重复幂等键、不完整来源身份和重复自然键，发现历史脏数据时抛出 `RuntimeError`，要求备份和人工对账，禁止静默合并。
- 修改 `.env.example` 与 `backend/app/config.py`，新增空值模板配置 `INTEGRATION_API_KEY`；没有写入真实密钥。
- 修改 `backend/app/main.py`，注册单 SKU intake router；startup 中先执行 `init_db()` 再启动 poller，同时把包内绝对导入改为相对导入。
- 将 `backend/app` 内部所有包级 `from app...` 改为相对导入：顶层模块使用 `.`，`integrations`、`pipeline` 子包使用 `..`。
- 修改 `tests/conftest.py`：内存 SQLite 增加 `poolclass=StaticPool`，保证 FastAPI `TestClient` 的请求线程与建表线程共享同一个内存数据库。
- 新增 `tests/test_single_sku_intake_api.py`，覆盖认证、未配置密钥、创建任务、重复货源、幂等键冲突、载荷校验、任务查询、数据库自然键强制、旧库索引补建，以及重复幂等键/空白来源身份/重复自然键三类不安全历史数据阻断。
- 更新 `AGENTS.md`，固化相对导入、跨线程内存 SQLite、集成密钥和幂等规则。

### 涉及文件、服务、数据

- 运行代码：`backend/app/main.py`、`backend/app/config.py`、`backend/app/currency.py`、`backend/app/database.py`、`backend/app/models.py`、`backend/app/oss_uploader.py`、`backend/app/scheduler.py`、`backend/app/single_sku/api.py`、`backend/app/single_sku/workflow.py`。
- 集成与流水线：`backend/app/integrations/mvideo_client.py`、`backend/app/integrations/omni_client.py`、`backend/app/pipeline/mapping.py`、`backend/app/pipeline/migrate_service.py`、`backend/app/pipeline/reconcile.py`、`backend/app/pipeline/report_service.py`。
- 测试与规则：`tests/test_single_sku_intake_api.py`、`tests/conftest.py`、`.env.example`、`AGENTS.md`、本累计报告。
- 未重启本机或笔记本服务，未修改生产数据库、价格、库存、批量队列或密钥文件。
- 未调用真实 M.Video 商品创建、价格、库存或上传接口；测试中的 Excel 生成本质仍为 dry-run。
- `work/downloads/_test_oss.xlsx` 在测试后保持二进制脏状态，未查明业务来源，本次不纳入提交，避免把测试产物误作为业务变更。

### 验证证据

- Python 编译验证通过：

```powershell
.\.venv\Scripts\python.exe -m compileall -q backend\app
```

- intake API 专项测试最终结果：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_single_sku_intake_api.py -q
```

```text
19 passed, 18 warnings in 1.61s
```

- M.Video 全量测试最终结果：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

```text
115 passed, 185 warnings in 12.31s
```

- 响应体不包含 `INTEGRATION_API_KEY`；认证测试确认错误密钥和未配置密钥分别返回 401/503。
- 新任务断言 `purchase_cost_cny is None`、`stock is None`、`cost_confirmed is False`、`stock_confirmed is False`、`dry_run_result_json == {}`、`upload_ref == ""`、`uploaded_at is None`，证明未越过人工核对和 dry-run 边界。
- 旧库升级测试确认干净历史数据可重复执行补建并保持幂等；不安全历史数据会在创建索引前抛出 `RuntimeError`，且数据库级自然键约束会直接拒绝重复货源。
- 独立代码审查尝试受平台错误 `MissingParameter: partial` 阻断，未能形成外部审查结论；已完成本地暂存差异审计，覆盖密钥、RUB→CNY 误用、真实上传边界和不安全历史数据迁移。

### 剩余风险

1. 当前仅完成后端 intake 边界和独立任务创建，人工核对采购价、尺寸、售价、库存、合规材料的界面尚未完成。
2. 真实部署时必须由环境变量或密钥管理服务提供长随机 `INTEGRATION_API_KEY`，不得把真实共享密钥写入 `.env.example`、Git 或截图。
3. 旧数据库需要执行补列和唯一索引补建；上线前必须备份数据库并完成历史数据对账，若迁移硬阻断，不得手工跳过或静默合并重复任务。
4. 目前只确认切带机类目的模板与映射；其他类目仍需先完成 confirmed 映射、95 列模板、证书、TN VED、品牌授权等预检。
5. `work/downloads/_test_oss.xlsx` 的测试后二进制差异尚未解释，后续应只读追踪生成路径，确认是否应恢复跟踪文件或调整测试夹具。
6. 本次工作站验证尚未部署到笔记本生产环境。

### 恢复/回滚方式

1. 若尚未部署，只需要回滚本次 intake API 提交，代码恢复到 `dae0a9c`。
2. 若环境已经执行补列或索引补建，回滚代码前先备份数据库；如确认没有需要保留的单 SKU 任务，可删除 `single_sku_jobs.schema_version`、`single_sku_jobs.idempotency_key` 并按数据库类型重建相关唯一索引。若仍需保留任务，已创建的唯一索引可以保留，待人工对账后再重新启动。
3. 清空部署环境中的 `INTEGRATION_API_KEY` 会让 intake 接口返回 503，但不会影响既有批量流水线运行。
4. 回滚后重新运行 `.\.venv\Scripts\python.exe -m pytest -q`，确认恢复到基线测试状态。

### GitHub 推送状态

- 截至本次功能代码提交，推送尚未发生；实际推送结果将在推送后追加到本报告，并形成后续 docs 提交。

### 可复制到其他对话的摘要

2026-09-24 已完成 M.Video 单 SKU Ozon → M.Video 的版本化 intake API：外部系统通过 `/api/v1/integrations/ozon/single-sku-jobs` 提交 `ozon.single-sku.v1` 载荷，并使用 `X-Integration-Key` 认证。接口支持自然键和 `idempotency_key` 幂等，重复货源返回同一任务，幂等键冲突返回 409；数据库级自然键唯一约束防止并发重复创建，旧库存在重复幂等键、空白来源身份或重复自然键时会硬阻断并要求人工对账。新任务停留在 `awaiting_input`，不会把 Ozon RUB 当 CNY 成本，也不会触发上传。已修复包内绝对导入造成的双配置缓存问题，并使用 `StaticPool` 修复 TestClient 跨线程内存 SQLite。最终专项测试 `19 passed`，全量测试 `115 passed`；当前未部署、未真实上传。
