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
