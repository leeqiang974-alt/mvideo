"""Application configuration. Secrets come from env / .env, never hard-coded.

Mirrors the Ozon ERP config pattern: process env is authoritative, .env is a
fallback. Defaults to a zero-infrastructure SQLite DB so the app runs with no
Postgres install; point DATABASE_URL at Postgres in production.
"""

from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv

_ENV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"
)
load_dotenv(_ENV_PATH, override=False)


class Settings:
    def __init__(self) -> None:
        self.app_env = os.getenv("APP_ENV", "development")
        self.database_url = os.getenv("DATABASE_URL", "sqlite:///./mvideo_erp.db")

        # --- M.Video traditional API ---
        self.mvideo_api_base_url = os.getenv(
            "MVIDEO_API_BASE_URL", "https://api.sellers.mvideo.ru"
        ).rstrip("/")
        # API key is created once in ЛК -> меню учётной записи -> «Доступ к API».
        # NEVER hard-code here; read from env / .env.
        self.mvideo_api_key = os.getenv("MVIDEO_API_KEY", "")
        # Supplier ID (vendorId). Used for EAN13 -> EAN18 conversion (last 5 digits).
        self.mvideo_vendor_id = os.getenv("MVIDEO_VENDOR_ID", "")
        self.mvideo_timeout_seconds = float(os.getenv("MVIDEO_TIMEOUT_SECONDS", "30"))

        # --- Ozon Seller API (read-only source of migrated products) ---
        self.ozon_api_base_url = os.getenv(
            "OZON_API_BASE_URL", "https://api-seller.ozon.ru"
        ).rstrip("/")
        self.ozon_client_id = os.getenv("OZON_CLIENT_ID", "")
        self.ozon_api_key = os.getenv("OZON_API_KEY", "")
        self.ozon_timeout_seconds = float(os.getenv("OZON_TIMEOUT_SECONDS", "30"))

        # --- Rate limit policy (M.Video traditional API; conservative defaults) ---
        # Documented OmniNet budget: 300 writes / 3 hours, ban 5 min on exceed.
        # Traditional API numbers are not published -> we self-throttle below it.
        self.rl_window_seconds = int(os.getenv("RL_WINDOW_SECONDS", "10800"))  # 3h
        self.rl_max_requests = int(os.getenv("RL_MAX_REQUESTS", "300"))
        self.rl_ban_seconds = int(os.getenv("RL_BAN_SECONDS", "300"))  # 5 min
        self.rl_safety_headroom = float(os.getenv("RL_SAFETY_HEADROOM", "0.9"))

        # --- Migration behaviour ---
        self.mv_supply_scheme = os.getenv("MV_SUPPLY_SCHEME", "FBS")
        self.mv_tax_system = os.getenv("MV_NDS", "USN")  # ОСН | USN -> 0/5/7/22
        self.mv_warehouse_code = os.getenv("MV_WAREHOUSE_CODE", "")  # R-объект for stock
        self.poll_interval_seconds = int(os.getenv("POLL_INTERVAL_SECONDS", "120"))
        self.poll_batch_size = int(os.getenv("POLL_BATCH_SIZE", "20"))
        self.default_price_rub = float(os.getenv("DEFAULT_PRICE_RUB", "0"))
        self.default_stock = int(os.getenv("DEFAULT_STOCK", "0"))

        # --- OMNI API (omni-net) — v0.3 primary write channel ---
        # Empirically: traditional API MaterialV2/PriceV2/StockV2 returns
        # API_KEY_INTERNAL_NOT_CONTAINS_KEY_TYPE for this account; OMNI price/stock
        # are authorized. Auth header is `api-key` with the DEDICATED Omniom key
        # (created in ЛК -> «Доступ к API» with «Omniom: ...» permissions).
        self.omni_api_base_url = os.getenv(
            "OMNI_API_BASE_URL", "https://omni-net.sellers.mvideo.ru"
        ).rstrip("/")
        # v0.3.1: OMNI uses its own key (Omniom perms), NOT the traditional
        # MVIDEO_API_KEY (which returns 401 «Ошибка авторизации» on omni-net).
        self.omni_api_key = os.getenv("OMNI_API_KEY", "")
        self.omni_timeout_seconds = float(os.getenv("OMNI_TIMEOUT_SECONDS", "30"))

        # --- Currency: Ozon prices are CNY, M.Video price update accepts RUB only ---
        # CNY -> RUB multiplier. Override via env; tune with the current rate.
        self.mv_rub_rate = float(os.getenv("MV_RUB_RATE", "12.0"))

        # --- Alibaba Cloud OSS (public image URLs for the Excel import template) ---
        self.oss_endpoint = os.getenv("OSS_ENDPOINT", "")
        self.oss_bucket = os.getenv("OSS_BUCKET", "")
        self.oss_access_key_id = os.getenv("OSS_ACCESS_KEY_ID", "")
        self.oss_access_key_secret = os.getenv("OSS_ACCESS_KEY_SECRET", "")
        self.oss_public_base = os.getenv("OSS_PUBLIC_BASE", "")
        # Shared Aliyun key file fallback (lines[1]=AKID, lines[3]=SK).
        self.oss_credential_file = os.getenv("ALIYUN_OSS_CREDENTIAL_FILE", "")


@lru_cache
def get_settings() -> Settings:
    return Settings()
