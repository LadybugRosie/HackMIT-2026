"""Post-submit analyses run in the background so submit never waits on the network.
Stage 6 adds similarity; until then a pending similarity check is marked skipped."""
from __future__ import annotations

import json
import logging

from .db import Db
from .factcheck import run_factcheck

logger = logging.getLogger(__name__)


def run_post_submit(db: Db, store, submission_id: str, resolver=None) -> None:
    row = db.one("SELECT content, factcheck_status, similarity_status FROM submissions WHERE submission_id = ?", (submission_id,))
    if row is None:
        return
    if row["factcheck_status"] == "pending":
        if resolver is None:
            db.exec("UPDATE submissions SET factcheck_status = 'skipped' WHERE submission_id = ?", (submission_id,))
        else:
            try:
                result = run_factcheck(row["content"], resolver)
                db.exec("UPDATE submissions SET factcheck_status = 'done', factcheck_json = ? WHERE submission_id = ?",
                        (json.dumps(result), submission_id))
            except Exception:  # never leave a submission stuck on pending
                logger.exception("factcheck failed for %s", submission_id)
                db.exec("UPDATE submissions SET factcheck_status = 'error' WHERE submission_id = ?", (submission_id,))
    if row["similarity_status"] == "pending":
        db.exec("UPDATE submissions SET similarity_status = 'skipped' WHERE submission_id = ?", (submission_id,))
