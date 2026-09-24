# MvideoERP (v0.1)

一个可独立运行的 M.Video 卖家 ERP，核心能力是把 **Ozon 店铺商品迁移到 M.Video**（自建 API 管线，非网页操作）。架构骨架沿用 Ozon ERP（FastAPI + SQLAlchemy + 滑动窗口限流 + 后台轮询），但**上架状态机按 M.Video 规则重写**，不照搬 Ozon。

## 状态机（M.Video 语义）

成功 = 审核通过（«Готов к продаже»）**且**已设价 **且** 已设库存。

```
queued ──质量门──> prepared ──MaterialV2创建──> on_moderation(На модерации)
                                                      │ 轮询
              ┌────────────────────────────────────────┤
              ▼                                       ▼
        ready_to_sell ──PriceV2──> priced ──StockV2──> stocked(成功)
        （«С ошибками» 退回 -> needs_review，改卡后重送审）
```

写后即对账：每阶段结束 `sum(各状态) == total_count`。

## 目录结构

```
MvideoERP/
├── backend/app/
│   ├── config.py            # 配置（密钥只从 env/.env 读）
│   ├── database.py          # SQLAlchemy 引擎/会话（SQLite 默认）
│   ├── models.py            # 7 张表 + 状态枚举
│   ├── endpoints.py         # M.Video 传统 API 路径注册表（标 VERIFY）
│   ├── barcode.py           # EAN13/UPC -> EAN18
│   ├── ratelimit.py         # 滑动窗口请求预算器（300次/3h 自节流）
│   ├── quality_gate.py      # 上架前质量门
│   ├── scheduler.py         # 后台审核轮询线程
│   ├── main.py              # FastAPI 入口
│   ├── integrations/
│   │   ├── mvideo_client.py # M.Video 写侧客户端
│   │   └── ozon_client.py   # Ozon 读侧客户端
│   └── pipeline/
│       ├── mapping.py        # Ozon 商品 -> M.Video payload
│       ├── migrate_service.py # 五阶段编排
│       └── reconcile.py      # 对账
├── scripts/
│   ├── init_db.py           # 建表
│   ├── check_env.py         # 检查 .env 必填项（不打印真实值）
│   └── run_migration.py      # CLI 一键迁移（支持 --limit N 冒烟）
├── serve.py                 # uvicorn 启动（127.0.0.1:8077）
├── requirements.txt
└── .env.example
```

## 快速开始

### 1. 装依赖（venv 已建好）
```
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 2. 配置 .env
```
copy .env.example .env
```
填这四项（**绝不提交真实 .env**）：

| 变量 | 说明 |
|---|---|
| `MVIDEO_API_KEY` | M.Video API-ключ，后台路径：**ЛК -> меню учётной записи（账户菜单）-> «Доступ к API» -> создать ключ**。每账号最多 10 个，仅创建时可见一次。 |
| `MVIDEO_VENDOR_ID` | 供应商 ID（5 位数字），用于 EAN13->EAN18 转换。 |
| `OZON_CLIENT_ID` | 复用 Ozon ERP 的 Client-Id。 |
| `OZON_API_KEY` | 复用 Ozon ERP 的 Api-Key。 |

### 3. 建表
```
.venv\Scripts\python.exe scripts\init_db.py
```
默认 SQLite `mvideo_erp.db`。要换 Postgres 就把 `DATABASE_URL` 改成 `postgresql+psycopg://user:pass@127.0.0.1:5432/mvideo_erp`。

### 4. 检查环境（不打印真实密钥）
```
.venv\Scripts\python.exe scripts\check_env.py
```

### 5. 冒烟：只迁 1 个商品
```
.venv\Scripts\python.exe scripts\run_migration.py --limit 1
```
这会：从 Ozon 拉 1 个商品 -> 质量门 -> MaterialV2 提交创建 -> 轮询审核 -> 设价设库存 -> 对账。

### 6. 启动 API 服务
```
.venv\Scripts\python.exe serve.py
```
- `GET  /health`
- `GET  /api/batches`
- `POST /api/batches`            body: `{"limit": 1, "note": "smoke"}`
- `GET  /api/batches/{id}`
- `POST /api/batches/{id}/run`  继续该批次（prepare/submit/poll/price）

## 重要说明

- **`endpoints.py` 里所有路径标了 `# VERIFY`**：M.Video 传统 API 的精确 HTTP 路径与 JSON schema 在登录 ЛК 后的分群 OpenAPI 里。拿到真实 OpenAPI 后只改这一个文件，其余代码不动。
- **类目映射**：Ozon 类目首次出现会在 `category_mappings` 表建 `draft` 行；需人工把 `mv_group_id` / `mv_infomodel_id` 填好（标 `ready`），否则质量门会把该商品挡在 `needs_review`。
- **ТНВЭД**：ФЗ-289（2026-10-01 生效）要求质量文档；`certificates` 表已预留，PDF 上传后续版本接。
- **限流**：自节流 300 写/3h（90% 安全余量），429 自动退避 5 分钟；价格/库存批量每批 ≤500。
- **安全**：所有密钥只从 `.env`/环境变量读，代码、日志、API 响应均不出现。
