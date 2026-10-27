"""
Boot-time orchestrator for the Printing ERP.

Invoked by start_erp.bat (which Windows Task Scheduler runs at logon).
All dates are IST (Asia/Kolkata, UTC+05:30).

What it does:
  1. Works out "yesterday" in IST.
  2. Checks whether a backup was taken AFTER that IST day ended, i.e.
     one that really contains the whole day's work. A backup made
     during the day itself does not count.
  3. If not, creates a verified catch-up backup now and marks the day
     as covered.
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

    if bk.day_fully_backed_up(prev):
        newest = bk.latest_backup_time()
        log.info(f"[OK] {prev} is covered by a backup taken after that day "
                 f"({newest.strftime('%d-%m-%Y %H:%M:%S')} IST) - nothing to create.")
        return 0

    log.warning(f"[MISSING] No backup of {prev} (IST) was taken after that day "
                f"ended. Creating a catch-up backup now...")
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
