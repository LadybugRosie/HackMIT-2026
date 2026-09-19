"""Post-submit analyses run in the background so submit never waits on the network.
Stage 5 adds fact-check, Stage 6 adds similarity; until then pending checks are marked skipped."""
from __future__ import annotations

import logging

from .db import Db

logger = logging.getLogger(__name__)


def run_post_submit(db: Db, store, submission_id: str) -> None:
    row = db.one("SELECT factcheck_status, similarity_status FROM submissions WHERE submission_id = ?", (submission_id,))
    if row is None:
        return
    updates = {}
    if row["factcheck_status"] == "pending":
        updates["factcheck_status"] = "skipped"
    if row["similarity_status"] == "pending":
        updates["similarity_status"] = "skipped"
    if updates:
        sets = ", ".join(f"{k} = ?" for k in updates)
        db.exec(f"UPDATE submissions SET {sets} WHERE submission_id = ?", [*updates.values(), submission_id])
