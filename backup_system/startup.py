"""
Boot-time orchestrator for the Printing ERP.

Invoked by start_erp.bat (which Windows Task Scheduler runs at logon).
All dates are IST (Asia/Kolkata, UTC+05:30).

What it does:
  1. Works out "yesterday" in IST.
  2. Checks whether a successful backup exists for that IST day
     (marker file or matching archive in daily/weekly/monthly).
  3. If it is missing, creates a verified catch-up backup now and marks
     the missed day as covered.
  4. Reports back via exit code whether the platform may start.

Exit codes:
  0 -> previous day already backed up, OR catch-up backup created and verified
  1 -> catch-up backup was needed but could not be produced
  2 -> usage error
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import backup as bk    # noqa: E402
import config as cfg   # noqa: E402


def previous_ist_date_str() -> str:
    return (bk.ist_date() - dt.timedelta(days=1)).isoformat()


def check_and_ensure_previous_day() -> int:
    log = bk.get_logger()
    bk.ensure_dirs()

    prev = previous_ist_date_str()
    log.info("=" * 60)
    log.info("PRINTING ERP STARTUP - PREVIOUS-DAY BACKUP CHECK")
    log.info("=" * 60)
    log.info(f"IST now      : {bk.now_ist().strftime('%d-%m-%Y %H:%M:%S')}")
    log.info(f"Previous day : {prev} (IST)")

    if bk.has_backup_for_date(prev):
        log.info(f"[OK] Backup for {prev} already exists - nothing to create.")
        return 0

    log.warning(f"[MISSING] No backup for {prev} (IST). Creating a catch-up backup now...")
    try:
        with bk.BackupLock():
            success, path, _meta = bk.create_backup(
                backup_type='startup_catchup', cover_date=prev)
    except RuntimeError as e:
        log.error(f"Catch-up backup skipped (lock held): {e}")
        return 1
    except Exception as e:
        log.error(f"Catch-up backup failed: {type(e).__name__}: {e}")
        return 1

    if success and path:
        log.info(f"[OK] Catch-up backup created and verified: {path.name}")
        return 0

    log.error(f"[FAIL] Could not produce a backup for {prev}. Log: {cfg.LOG_FILE}")
    return 1


def main(argv) -> int:
    action = argv[1].lower() if len(argv) > 1 else 'check'
    if action == 'check':
        return check_and_ensure_previous_day()
    print("Usage: startup.py check")
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv))
