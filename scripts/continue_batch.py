"""Continue a migration batch after the operator has manually uploaded the
filled Excel template to the M.Video web ЛК (v0.4.0).

Usage:
    .venv\\Scripts\\python.exe scripts\\continue_batch.py --batch-id N
    .venv\\Scripts\\python.exe scripts\\continue_batch.py --batch-id N --apply-writes
    .venv\\Scripts\\python.exe scripts\\continue_batch.py --batch-id N --apply-writes --max-items 50

What it does (in order):
  1. poll_mappings   — read OMNI /v1/product/mapping/list; any offer_id that
                       now has a product_id advances mapping_pending ->
                       product_matched.
  2. apply_price_stock — DRY-RUN by default: prints how many rows WOULD be
                       pushed to OMNI price/stock. With --apply-writes it
                       actually calls price_update / stock_update and advances
                       product_matched -> priced -> stocked.
  3. readback_verify  — for rows that already have mv_product_id, read
                       price/info + stock/info back and compare to local
                       expectations (kopeck alignment, 1 RUB tolerance).
  4. batch_report     — print the aggregate status / needs_review detail.

Safety:
  * Without --apply-writes NOTHING on the OMNI side is modified. The script
    only reads (mapping/list, price/info, stock/info).
  * --max-items limits how many PRODUCT_MATCHED rows get price/stock writes
    when --apply-writes is on (default 50). Start small.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.normpath(os.path.join(_HERE, "..", "backend"))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from sqlalchemy import select  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.database import SessionLocal, init_db  # noqa: E402
from app.integrations.omni_client import OmniClient  # noqa: E402
from app.models import ItemStatus, MigrationItem  # noqa: E402
from app.ratelimit import RequestBudgeter  # noqa: E402
from app.pipeline.migrate_service import (  # noqa: E402
    apply_price_stock,
    poll_mappings,
)
from app.pipeline.report_service import batch_report, readback_verify  # noqa: E402


def _print_report(rep: dict) -> None:
    print(f"  batch_id:           {rep.get('batch_id')}")
    print(f"  batch_ref:          {rep.get('batch_ref')}")
    print(f"  status:             {rep.get('status')}")
    print(f"  total:              {rep.get('total_count')}")
    print(f"  mapped_product_id:  {rep.get('mapped_product_id')}")
    print(f"  priced:             {rep.get('priced')}")
    print(f"  stocked:            {rep.get('stocked')}")
    print(f"  needs_review:       {rep.get('needs_review_count')}")
    print("  by_status:")
    for st_name, cnt in (rep.get("by_status") or {}).items():
        print(f"    - {st_name}: {cnt}")
    items = rep.get("needs_review") or []
    if items:
        print("  needs_review detail:")
        for it in items[:20]:
            print(f"    - [{it.get('offer_id')}] {it.get('name')}: {it.get('last_error')}")


def _print_readback(v: dict) -> None:
    print(f"  readback checked: {v.get('checked')}")
    print(f"    matched:  {len(v.get('matched') or [])}")
    print(f"    mismatch: {len(v.get('mismatch') or [])}")
    print(f"    missing:  {len(v.get('missing') or [])}")
    for m in (v.get("mismatch") or [])[:10]:
        print(f"      ! {m.get('offer_id')} ({m.get('product_id')}) "
              f"field={m.get('field')} expected={m.get('expected_kopecks', m.get('expected_count'))} "
              f"actual={m.get('actual_kopecks', m.get('actual_count'))}")
    for m in (v.get("missing") or [])[:10]:
        print(f"      ? {m.get('offer_id')} ({m.get('product_id')}) {m.get('reason')}")


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    ap = argparse.ArgumentParser(description="Continue a migration batch after manual Excel upload")
    ap.add_argument("--batch-id", type=int, required=True, help="MigrationBatch.id to continue")
    ap.add_argument("--apply-writes", action="store_true", default=False,
                    help="Actually push price/stock to OMNI (default: dry-run)")
    ap.add_argument("--max-items", type=int, default=50,
                    help="Cap PRODUCT_MATCHED rows that get written when --apply-writes is on")
    args = ap.parse_args()

    st = get_settings()
    if not (st.omni_api_key or st.mvideo_api_key):
        print("ERROR: OMNI_API_KEY missing in .env")
        return 1

    init_db()
    session = SessionLocal()
    budgeter = RequestBudgeter(session)
    omni = OmniClient(
        api_key=st.omni_api_key or st.mvideo_api_key,
        base_url=st.omni_api_base_url,
        timeout_seconds=st.omni_timeout_seconds,
        budgeter=budgeter,
    )

    try:
        print(f"=== continue batch {args.batch_id} "
              f"({'APPLY-WRITES' if args.apply_writes else 'DRY-RUN'}) ===")

        # 1) poll mappings (read-only)
        print("\n[1/4] poll_mappings ...")
        mp = poll_mappings(session, omni, batch_id=args.batch_id)
        print(f"  product_matched={mp.get('product_matched')} mapping_pending={mp.get('mapping_pending')}")

        # 2) apply price/stock (dry-run unless --apply-writes)
        print("\n[2/4] apply_price_stock ...")
        if args.apply_writes:
            # Cap: temporarily push rows beyond --max-items back to
            # MAPPING_PENDING so apply_price_stock skips them; restore after.
            all_matched = session.execute(
                select(MigrationItem)
                .where(MigrationItem.batch_id == args.batch_id)
                .where(MigrationItem.status == ItemStatus.PRODUCT_MATCHED)
                .order_by(MigrationItem.id)
            ).scalars().all()
            excess = list(all_matched[args.max_items:])
            for it in excess:
                it.status = ItemStatus.MAPPING_PENDING
            session.commit()
            print(f"  (apply-writes ON; writing {min(len(all_matched), args.max_items)} rows, "
                  f"holding back {len(excess)})")
            try:
                ps = apply_price_stock(
                    session, omni, batch_id=args.batch_id, dry_run=False,
                )
            finally:
                for it in excess:
                    it.status = ItemStatus.PRODUCT_MATCHED
                session.commit()
        else:
            ps = apply_price_stock(
                session, omni, batch_id=args.batch_id, dry_run=True,
            )
        print(f"  would_price={ps.get('would_price')} would_stock={ps.get('would_stock')} "
              f"priced={ps.get('priced')} stocked={ps.get('stocked')} failed={ps.get('failed')}")

        # 3) readback verify (read-only)
        print("\n[3/4] readback_verify ...")
        items_to_check = session.execute(
            select(MigrationItem)
            .where(MigrationItem.batch_id == args.batch_id)
            .where(MigrationItem.mv_product_id != "")
        ).scalars().all()
        rb = readback_verify(omni, items_to_check)
        _print_readback(rb)

        # 4) batch report
        print("\n[4/4] batch_report ...")
        rep = batch_report(session, args.batch_id)
        _print_report(rep)

    finally:
        omni.close()
        session.close()

    if not args.apply_writes:
        print("\nNote: DRY-RUN — no price/stock was changed. "
              "Re-run with --apply-writes to push.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
