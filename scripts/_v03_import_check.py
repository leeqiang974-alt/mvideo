# -*- coding: utf-8 -*-
"""One-off import verification for v0.3 modules (not a test file)."""
import sys
sys.path.insert(0, "backend")
from app.currency import cny_to_rub, build_price_item, build_stock_item  # noqa
from app.oss_uploader import OssUploader  # noqa
from app.pipeline.image_pipeline import (  # noqa
    process_local_images,
    upload_processed_to_oss,
)
from app.pipeline.template_builder import (  # noqa
    build_template_rows,
    write_template_xlsx,
)
print("cny 100@12 =", cny_to_rub(100.0, "12.0"))
print("TPL_IMPORT_OK")
