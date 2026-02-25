from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


def make_log_path(output_dir: Path) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    return output_dir / f"outreach_log_{timestamp}.csv"


def write_logs(log_path: Path, rows: Iterable[dict]) -> None:
    rows = list(rows)
    if not rows:
        return

    fieldnames = list(rows[0].keys())
    with log_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
