"""Write-then-reconcile for a migration batch (v0.3 OMNI pipeline).

v0.1 (2026-09-17) | v0.3 (2026-09-18): state set updated to the
Excel-template + OMNI channel (queued/prepared/images_processed/template_built/
template_uploaded/mapping_pending/product_matched/priced/stocked/...).

Borrowed from the Ozon ERP "write then immediately reconcile" invariant:
after every batch of state transitions, recompute the per-status counters and
assert that the sum of items still equals ``total_count`` (nothing is lost or
duplicated). Returns a small summary dict for logs / API responses.
"""

from __future__ import annotations

import logging
from collections import Counter

from sqlalchemy import select

from ..models import MigrationBatch, MigrationItem, ItemStatus

log = logging.getLogger("mvideo.reconcile")

# every item status that exists -> must be accounted for
_ALL_STATES = {
    ItemStatus.QUEUED,
    ItemStatus.PREPARED,
    ItemStatus.IMAGES_PROCESSED,
    ItemStatus.TEMPLATE_BUILT,
    ItemStatus.TEMPLATE_UPLOADED,
    ItemStatus.MAPPING_PENDING,
    ItemStatus.PRODUCT_MATCHED,
    ItemStatus.PRICED,
    ItemStatus.STOCKED,
    ItemStatus.NEEDS_REVIEW,
    ItemStatus.FAILED,
    ItemStatus.SKIPPED,
    ItemStatus.WAITING_QUOTA,
}


def reconcile_batch(session, batch: MigrationBatch) -> dict:
    """Recompute counters, verify sum == total_count, return summary."""
    session.refresh(batch)
    batch.reconcile_counts()

    rows = session.execute(
        select(MigrationItem.status).where(MigrationItem.batch_id == batch.id)
    ).scalars().all()
    counts = Counter(rows)
    accounted = sum(counts.values())

    summary = {
        "batch_id": batch.id,
        "batch_ref": batch.batch_ref,
        "total_count": batch.total_count,
        "actual_rows": accounted,
        "sum_counters": batch.submitted_count
        + batch.on_moderation_count
        + batch.ready_count
        + batch.priced_count
        + batch.stocked_count
        + batch.errored_count
        + batch.failed_count
        + batch.skipped_count,
        "by_status": dict(counts),
        "queued": counts.get(ItemStatus.QUEUED, 0),
        "prepared": counts.get(ItemStatus.PREPARED, 0),
        "images_processed": counts.get(ItemStatus.IMAGES_PROCESSED, 0),
        "template_built": counts.get(ItemStatus.TEMPLATE_BUILT, 0),
        "template_uploaded": counts.get(ItemStatus.TEMPLATE_UPLOADED, 0),
        "mapping_pending": counts.get(ItemStatus.MAPPING_PENDING, 0),
        "product_matched": counts.get(ItemStatus.PRODUCT_MATCHED, 0),
        "submitted": batch.submitted_count,
        "on_moderation": batch.on_moderation_count,
        "ready_to_sell": batch.ready_count,
        "priced": batch.priced_count,
        "stocked": batch.stocked_count,
        "needs_review": batch.errored_count,
        "failed": batch.failed_count,
        "skipped": batch.skipped_count,
        "consistent": accounted == batch.total_count,
    }
    session.commit()

    if not summary["consistent"]:
        log.error(
            "reconcile mismatch batch=%s total=%s actual=%s",
            batch.batch_ref, batch.total_count, accounted,
        )
    else:
        log.info(
            "reconcile ok batch=%s total=%s stocked=%s needs_review=%s",
            batch.batch_ref, accounted, batch.stocked_count, batch.errored_count,
        )
    return summary
