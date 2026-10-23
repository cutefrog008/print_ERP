"""
Core Printing ERP backup module.

Features:
  * Safe SQLite backup via sqlite3 .backup() (no corruption while ERP runs).
  * ZIP archive with database/, media/, metadata/ layout.
  * Thorough post-backup verification.
  * Structured logging to backup.log + latest_backup_status.txt
  * 3-tier retention (daily/weekly/monthly) - never deletes last successful backup,
    only cleans up after new backup is verified.
  * One-backup-per-day marker system for startup trigger.
  * Lock file to prevent concurrent backup instances.
  * Disk space pre-check.
  * Works with or without Django installed (imports config directly).
"""

from __future__ import annotations

import csv
import ctypes
import datetime as dt
import json
import logging
import os
import platform
import shutil
import socket
import sqlite3
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Allow running this module as a script (no package parent)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as cfg  # noqa: E402


# =========================================================================
# Path helpers
# =========================================================================

def ensure_dirs() -> None:
    for p in (
        cfg.BACKUP_ROOT, cfg.DAILY_DIR, cfg.WEEKLY_DIR, cfg.MONTHLY_DIR,
        cfg.PRE_RESTORE_DIR, cfg.LOG_DIR,
    ):
        p.mkdir(parents=True, exist_ok=True)


def human_bytes(n: int) -> str:
    step = 1024.0
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if n < step:
            return f"{n:.2f} {unit}"
        n /= step
    return f"{n:.2f} PB"


# =========================================================================
# Logging
# =========================================================================

_logger: Optional[logging.Logger] = None

def get_logger() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger
    ensure_dirs()
    log = logging.getLogger('printing_erp_backup')
    log.setLevel(logging.DEBUG)
    log.handlers.clear()

    fh = logging.FileHandler(cfg.LOG_FILE, encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        '%(asctime)s | %(levelname)-7s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'))

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter('%(message)s'))

    log.addHandler(fh)
    log.addHandler(ch)
    _logger = log
    return log


def write_latest_status(status: str, backup_path: Optional[Path] = None,
                        backup_ts: Optional[dt.datetime] = None,
                        size_bytes: Optional[int] = None,
                        error: Optional[str] = None) -> None:
    log = get_logger()
    try:
        ts = backup_ts or now_ist()
        lines = [
            "Last backup (IST):",
            ts.strftime("%d-%m-%Y %H:%M:%S"),
            "",
            "Status:",
            status,
        ]
        if backup_path is not None:
            lines += ["", "Backup:", backup_path.name]
            if size_bytes is not None:
                lines += ["", "Size:", human_bytes(size_bytes)]
        if error:
            lines += ["", "Error:", str(error)]
        cfg.LATEST_STATUS_FILE.write_text("\n".join(lines) + "\n", encoding='utf-8')
    except Exception as e:
        log.error(f"Failed to write latest_status.txt: {e}")


# =========================================================================
# Locking (prevent concurrent backups)
# =========================================================================

class BackupLock:
    def __init__(self):
        self._lock_path = cfg.LOCK_FILE
        self._acquired = False

    def __enter__(self):
        ensure_dirs()
        if self._lock_path.exists():
            try:
                age = time.time() - self._lock_path.stat().st_mtime
                if age > 3600:  # >1h = stale, remove
                    self._lock_path.unlink(missing_ok=True)
                    get_logger().warning("Removed stale backup lock file (>1 hour old).")
                else:
                    raise RuntimeError(
                        f"Another backup is already in progress (lock age: {int(age)}s). "
                        f"If this is incorrect, delete {self._lock_path}")
            except RuntimeError:
                raise
            except Exception:
                pass
        try:
            # Exclusive-create = fails if exists (race-free)
            fd = os.open(str(self._lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f"PID={os.getpid()} HOST={socket.gethostname()} TIME={dt.datetime.now().isoformat()}".encode())
            os.close(fd)
            self._acquired = True
        except FileExistsError:
            raise RuntimeError(f"Another backup is in progress. Lock file: {self._lock_path}")
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._acquired:
            try:
                self._lock_path.unlink(missing_ok=True)
            except Exception:
                pass
            self._acquired = False


# =========================================================================
# Utilities
# =========================================================================

def free_disk_gb(path: Path) -> float:
    if platform.system() == 'Windows':
        free_bytes = ctypes.c_ulonglong(0)
        ctypes.windll.kernel32.GetDiskFreeSpaceExW(
            ctypes.c_wchar_p(str(path)),
            None, None, ctypes.pointer(free_bytes))
        return free_bytes.value / (1024 ** 3)
    stat = shutil.disk_usage(str(path))
    return stat.free / (1024 ** 3)


# =========================================================================
# IST (Asia/Kolkata, UTC+05:30) date helpers
# =========================================================================
# All backup dates (filenames, markers, "last backup" status) are expressed
# in IST, independent of the machine's local timezone setting.

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def now_ist() -> dt.datetime:
    return dt.datetime.now(IST)


def ist_date(when: Optional[dt.datetime] = None) -> dt.date:
    return (when or now_ist()).astimezone(IST).date()


def today_str() -> str:
    return ist_date().isoformat()


def marker_file_for(date_str: str) -> Path:
    return cfg.DAILY_DIR / f"{cfg.MARKER_PREFIX}{date_str}"


def marker_file_for_today() -> Path:
    return marker_file_for(today_str())


def today_already_backed_up() -> bool:
    return marker_file_for_today().exists()


def mark_date_covered(date_str: str, backup_path: Path) -> None:
    """Record that a successful backup covers the given IST date."""
    marker = marker_file_for(date_str)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(
        f"{now_ist().isoformat()}\n{backup_path}\n", encoding='utf-8')


def mark_today_backed_up(backup_path: Path) -> None:
    mark_date_covered(today_str(), backup_path)


def has_backup_for_date(date_str: str) -> bool:
    """True if a successful backup exists for the given IST date.

    A date counts as covered when its marker file exists, or a backup
    archive carrying that date is present in the daily/weekly/monthly
    buckets.
    """
    if marker_file_for(date_str).exists():
        return True
    pattern = f"{cfg.BACKUP_PREFIX}{date_str}_*{cfg.BACKUP_EXT}"
    for bucket in (cfg.DAILY_DIR, cfg.WEEKLY_DIR, cfg.MONTHLY_DIR):
        if bucket.exists() and any(bucket.glob(pattern)):
            return True
    return False


def build_backup_path(bucket: Path = cfg.DAILY_DIR, when: Optional[dt.datetime] = None) -> Path:
    when = when or now_ist()
    name = f"{cfg.BACKUP_PREFIX}{when.strftime(cfg.BACKUP_DATE_FORMAT)}{cfg.BACKUP_EXT}"
    return bucket / name


# =========================================================================
# SQLite safe backup
# =========================================================================

def backup_sqlite_to(db_file: Path, dest_file: Path) -> None:
    """
    Use the official SQLite C API backup() via Python's sqlite3 module.
    This is the ONLY safe way to copy a live SQLite DB - it copies
    page-by-page, handles rollback journals and WAL files correctly,
    and produces a fully-consistent snapshot.
    """
    log = get_logger()
    if not db_file.exists():
        raise FileNotFoundError(f"SQLite DB missing: {db_file}")

    dest_file.parent.mkdir(parents=True, exist_ok=True)
    # Connect to live DB in read-only mode
    live_uri = f"file:{db_file}?mode=ro"
    src_conn = sqlite3.connect(live_uri, uri=True, timeout=60)
    try:
        # Dest DB - overwrite
        if dest_file.exists():
            dest_file.unlink()
        dst_conn = sqlite3.connect(str(dest_file), timeout=60)
        try:
            log.info(f"  SQLite backup in progress ({human_bytes(db_file.stat().st_size)}) ...")
            progress_counter = [0]
            def _backup_progress(status, remaining, total):
                if progress_counter[0] % 500 == 0:
                    done = total - remaining
                    log.debug(f"  SQLite pages: {done}/{total}")
                progress_counter[0] += 1
            # Page-by-page backup (handles concurrent writes safely)
            with dst_conn:
                src_conn.backup(dst_conn, pages=100, progress=_backup_progress)
            log.info(f"  SQLite backup complete -> {dest_file.name}")
        finally:
            dst_conn.close()
    finally:
        src_conn.close()


def verify_sqlite_snapshot(db_file: Path) -> bool:
    """Open snapshot, run PRAGMA integrity_check, count tables."""
    log = get_logger()
    if not db_file.exists() or db_file.stat().st_size == 0:
        log.error(f"SQLite snapshot missing/empty: {db_file}")
        return False
    try:
        conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True, timeout=10)
        try:
            cur = conn.cursor()
            integrity = cur.execute("PRAGMA integrity_check;").fetchone()[0]
            if integrity != 'ok':
                log.error(f"SQLite integrity_check failed: {integrity}")
                return False
            tables = cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
            ).fetchall()
            log.info(f"  SQLite integrity OK - {len(tables)} tables")
            return True
        finally:
            conn.close()
    except Exception as e:
        log.error(f"SQLite snapshot verification failed: {e}")
        return False


# =========================================================================
# Metadata
# =========================================================================

def build_metadata(backup_type: str, backup_path: Path) -> Dict:
    try:
        import django
        django_version = django.get_version()
    except Exception:
        django_version = 'unknown'
    return {
        "backup_timestamp": now_ist().isoformat(timespec='seconds'),
        "backup_date_local": now_ist().strftime('%d-%m-%Y %H:%M:%S') + " IST",
        "backup_type": backup_type,
        "timezone": "Asia/Kolkata (IST, UTC+05:30)",
        "database_engine": cfg.DB_ENGINE,
        "database_size_bytes": cfg.DB_PATH.stat().st_size if cfg.DB_PATH.exists() else 0,
        "django_version": django_version,
        "python_version": sys.version.split()[0],
        "windows_computer_name": socket.gethostname(),
        "windows_version": platform.platform(),
        "backup_filename": backup_path.name,
        "status": "PENDING_VERIFICATION",
    }


# =========================================================================
# Backup creation
# =========================================================================

def create_backup(backup_type: str = 'manual',
                  cover_date: Optional[str] = None) -> Tuple[bool, Optional[Path], Dict]:
    """
    Returns (success, backup_path_or_None, metadata_dict).
    Creates a backup inside daily/ and applies retention AFTER verification.

    cover_date: optional IST date (YYYY-MM-DD) that this backup should also
    mark as covered, used by the boot-time catch-up for a missed day.
    """
    log = get_logger()
    start_ts = now_ist()
    backup_path = build_backup_path(cfg.DAILY_DIR, start_ts)
    metadata = build_metadata(backup_type, backup_path)
    success = False
    temp_stage = None
    try:
        ensure_dirs()

        # Disk space check
        free = free_disk_gb(cfg.BACKUP_ROOT)
        log.info(f"Free disk space on backup drive: {free:.2f} GB (min required: {cfg.MIN_FREE_SPACE_GB} GB)")
        if free < cfg.MIN_FREE_SPACE_GB:
            raise RuntimeError(
                f"Insufficient free disk space: {free:.2f} GB < {cfg.MIN_FREE_SPACE_GB} GB required.")

        # Estimate size: DB*3 + media
        est = 0
        if cfg.DB_PATH.exists():
            est += cfg.DB_PATH.stat().st_size * 3
        if cfg.MEDIA_ROOT.exists():
            for fp in cfg.MEDIA_ROOT.rglob('*'):
                if fp.is_file():
                    est += fp.stat().st_size
        est_gb = est / (1024 ** 3)
        if est_gb > free * 0.9:
            log.warning(
                f"Estimated backup size ({est_gb:.2f} GB) is close to free space ({free:.2f} GB)")

        # Create backup in a temp staging dir
        temp_stage = Path(tempfile.mkdtemp(prefix='erp_backup_', dir=str(cfg.BACKUP_ROOT.parent)))
        db_stage_dir = temp_stage / cfg.ZIP_DB_DIR
        media_stage_dir = temp_stage / cfg.ZIP_MEDIA_DIR
        meta_stage_dir = temp_stage / cfg.ZIP_META_DIR
        for d in (db_stage_dir, media_stage_dir, meta_stage_dir):
            d.mkdir(parents=True, exist_ok=True)

        # 1) Database backup (safe SQLite)
        snap_db = db_stage_dir / cfg.ZIP_DB_NAME
        backup_sqlite_to(cfg.DB_PATH, snap_db)

        # 2) Copy media tree (if exists)
        media_has_files = False
        if cfg.MEDIA_ROOT.exists():
            for item in cfg.MEDIA_ROOT.rglob('*'):
                if item.is_file():
                    rel = item.relative_to(cfg.MEDIA_ROOT)
                    dst = media_stage_dir / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        shutil.copy2(item, dst)
                        media_has_files = True
                    except Exception as e:
                        log.warning(f"  Skip media file {item}: {e}")
            log.info(f"  Media backup {'copied files' if media_has_files else 'directory empty/not used'}")

        # 3) Write metadata pre-zip (PENDING)
        meta_file = meta_stage_dir / cfg.ZIP_META_FILE
        meta_file.write_text(json.dumps(metadata, indent=2, default=str), encoding='utf-8')

        # 4) Build ZIP archive (best compression, deterministic structure)
        log.info(f"  Building zip: {backup_path.name}")
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
            for folder in (cfg.ZIP_DB_DIR, cfg.ZIP_MEDIA_DIR, cfg.ZIP_META_DIR):
                root = temp_stage / folder
                for fp in sorted(root.rglob('*')):
                    if fp.is_file():
                        arcname = f"{folder}/{fp.relative_to(root)}".replace('\\', '/')
                        zf.write(fp, arcname=arcname)

        size_bytes = backup_path.stat().st_size
        log.info(f"  Zip size: {human_bytes(size_bytes)}")

        # 5) Verify
        log.info("  Verifying backup...")
        v_ok = verify_backup_zip(backup_path, expect_media=media_has_files)
        if not v_ok:
            raise RuntimeError("Backup verification failed.")

        # 6) Promote metadata + write status
        metadata['status'] = 'SUCCESS'
        metadata['size_bytes'] = size_bytes
        success = True
        duration = (now_ist() - start_ts).total_seconds()
        log.info(f"  Backup SUCCESS in {duration:.1f}s")
        write_latest_status('SUCCESS', backup_path=backup_path,
                            backup_ts=start_ts, size_bytes=size_bytes)
        # Write marker(s) for one-per-day tracking
        mark_today_backed_up(backup_path)
        if cover_date and cover_date != today_str():
            mark_date_covered(cover_date, backup_path)
            log.info(f"  Marked missed day as covered: {cover_date} (IST)")

        # 7) Apply retention only after SUCCESS
        apply_retention(keep_this=backup_path)

        # 8) Promote to weekly/monthly if applicable
        promote_to_weekly_monthly(backup_path)

    except Exception as e:
        log.error(f"Backup FAILED: {e}")
        metadata['status'] = 'FAILURE'
        metadata['error'] = str(e)
        write_latest_status('FAILURE', error=str(e))
        # Clean up failed file
        try:
            if backup_path.exists():
                backup_path.unlink()
                log.info(f"  Removed failed backup file: {backup_path.name}")
        except Exception:
            pass
        success = False
    finally:
        if temp_stage and temp_stage.exists():
            try:
                shutil.rmtree(temp_stage, ignore_errors=True)
            except Exception:
                pass

    return success, (backup_path if success else None), metadata


# =========================================================================
# Verification
# =========================================================================

def verify_backup_zip(zip_path: Path, expect_media: bool = False) -> bool:
    log = get_logger()
    if not zip_path.exists():
        log.error(f"Zip file missing: {zip_path}")
        return False
    if zip_path.stat().st_size == 0:
        log.error("Zip file is empty")
        return False

    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            # Test CRC for every entry
            bad = zf.testzip()
            if bad is not None:
                log.error(f"Zip corrupt: bad CRC for {bad}")
                return False
            names = zf.namelist()
            log.info(f"  Zip contains {len(names)} files. CRC check OK.")

            # Required entries
            db_entry = f"{cfg.ZIP_DB_DIR}/{cfg.ZIP_DB_NAME}"
            meta_entry = f"{cfg.ZIP_META_DIR}/{cfg.ZIP_META_FILE}"
            if db_entry not in names:
                log.error(f"Zip missing required entry: {db_entry}")
                return False
            if meta_entry not in names:
                log.error(f"Zip missing required entry: {meta_entry}")
                return False

            # Extract database to temp dir and verify integrity
            with tempfile.TemporaryDirectory(dir=str(cfg.BACKUP_ROOT.parent)) as td:
                snap_db = Path(td) / cfg.ZIP_DB_NAME
                with zf.open(db_entry) as src, open(snap_db, 'wb') as dst:
                    shutil.copyfileobj(src, dst)
                if not verify_sqlite_snapshot(snap_db):
                    return False

            # Media presence check
            media_entries = [n for n in names if n.startswith(cfg.ZIP_MEDIA_DIR + '/')
                             and not n.endswith('/')]
            if expect_media and not media_entries:
                log.warning("Media files expected but none found in backup (may be newly created empty dir)")
            log.info(f"  Media files in zip: {len(media_entries)}")

            # Metadata JSON loads
            meta_raw = zf.read(meta_entry)
            meta = json.loads(meta_raw)
            log.info(f"  Metadata OK - computer: {meta.get('windows_computer_name')}, "
                     f"Django: {meta.get('django_version')}")
        return True
    except zipfile.BadZipFile:
        log.error("Zip is corrupt (BadZipFile)")
        return False
    except Exception as e:
        log.error(f"Verification exception: {type(e).__name__}: {e}")
        return False


# =========================================================================
# Retention
# =========================================================================

def _sort_by_mtime(files: List[Path]) -> List[Path]:
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)


def _list_backups(bucket: Path) -> List[Path]:
    if not bucket.exists():
        return []
    return _sort_by_mtime([p for p in bucket.glob(f"*{cfg.BACKUP_EXT}") if p.is_file()])


def apply_retention(keep_this: Optional[Path] = None) -> None:
    """
    Apply retention to daily/weekly/monthly.
    NEVER delete:
      - the latest successful backup in each bucket
      - the backup file referenced by latest_status.txt
      - the just-created `keep_this` backup
    """
    log = get_logger()
    log.info("Applying retention policies...")

    # Determine protected set
    protected = set()
    if keep_this is not None and keep_this.exists():
        protected.add(str(keep_this.resolve()))
    if cfg.LATEST_STATUS_FILE.exists():
        try:
            text = cfg.LATEST_STATUS_FILE.read_text(encoding='utf-8', errors='ignore')
            for tok in text.split():
                if tok.startswith(cfg.BACKUP_PREFIX) and tok.endswith(cfg.BACKUP_EXT):
                    for root in (cfg.DAILY_DIR, cfg.WEEKLY_DIR, cfg.MONTHLY_DIR):
                        cand = root / tok
                        if cand.exists():
                            protected.add(str(cand.resolve()))
        except Exception:
            pass

    def _clean(bucket: Path, keep_count: int, label: str) -> None:
        files = _list_backups(bucket)
        if len(files) <= keep_count:
            log.info(f"  {label}: {len(files)}/{keep_count} kept - nothing to delete")
            return
        # First N are kept
        to_keep = files[:keep_count]
        to_delete = files[keep_count:]
        # But never delete the newest one (extra safety)
        newest = files[0] if files else None
        actual_delete = []
        for f in to_delete:
            if str(f.resolve()) in protected:
                continue
            if newest and f == newest:
                continue
            actual_delete.append(f)
        for f in actual_delete:
            try:
                f.unlink()
                log.info(f"  {label}: deleted old backup {f.name}")
            except Exception as e:
                log.warning(f"  {label}: could not delete {f.name}: {e}")

    _clean(cfg.DAILY_DIR, cfg.RETENTION_DAILY, 'Daily')
    _clean(cfg.WEEKLY_DIR, cfg.RETENTION_WEEKLY, 'Weekly')
    _clean(cfg.MONTHLY_DIR, cfg.RETENTION_MONTHLY, 'Monthly')


# =========================================================================
# Promotion: daily -> weekly (Mondays) + monthly (1st of month)
# =========================================================================

def promote_to_weekly_monthly(daily_path: Path) -> None:
    """Copy today's daily backup to weekly/ if Monday, to monthly/ if 1st of month."""
    log = get_logger()
    today = ist_date()
    try:
        if today.weekday() == 0:  # Monday
            dst = cfg.WEEKLY_DIR / daily_path.name
            if not dst.exists():
                shutil.copy2(daily_path, dst)
                log.info(f"  Promoted to WEEKLY: {dst.name}")
        if today.day == 1:
            dst = cfg.MONTHLY_DIR / daily_path.name
            if not dst.exists():
                shutil.copy2(daily_path, dst)
                log.info(f"  Promoted to MONTHLY: {dst.name}")
    except Exception as e:
        log.warning(f"  Could not promote backup: {e}")


# =========================================================================
# Entry point: Morning backup (startup-delay + one-per-day)
# =========================================================================

def run_morning_backup() -> int:
    log = get_logger()
    log.info("=" * 60)
    log.info("PRINTING ERP MORNING BACKUP STARTING")
    log.info("=" * 60)

    ensure_dirs()

    delay = cfg.BACKUP_STARTUP_DELAY_MINUTES
    log.info(f"Delaying {delay} minutes before backup (configurable, ERP startup grace period).")
    log.info(f"Delay start time (IST): {now_ist().strftime('%d-%m-%Y %H:%M:%S')}")

    # Sleep in 5-second ticks - allows interrupt, logs progress
    total_s = delay * 60
    tick = 5
    slept = 0
    try:
        while slept < total_s:
            time.sleep(tick)
            slept += tick
            remaining = (total_s - slept)
            if remaining % 60 == 0 and remaining > 0:
                log.debug(f"  ...{remaining // 60} min remaining")
    except KeyboardInterrupt:
        log.info("Delay interrupted by user.")
        return 2

    log.info(f"Delay complete. ({now_ist().strftime('%d-%m-%Y %H:%M:%S')} IST)")

    if today_already_backed_up():
        log.info("Today's successful backup already exists. Skipping (one-backup-per-day rule).")
        # Only write SKIPPED status if no status exists yet.
        # Never overwrite an existing SUCCESS status (which has backup path/size the user needs).
        if not cfg.LATEST_STATUS_FILE.exists():
            write_latest_status('SKIPPED - today backup exists')
        else:
            log.info("  (latest_status.txt not overwritten - previous SUCCESS status preserved)")
        return 0

    try:
        with BackupLock():
            success, path, meta = create_backup(backup_type='automatic_startup')
    except RuntimeError as e:
        log.error(f"Skipping backup due to lock: {e}")
        return 3

    return 0 if success else 1


# =========================================================================
# Entry point: Manual backup (no delay, always runs)
# =========================================================================

def run_manual_backup() -> int:
    log = get_logger()
    log.info("=" * 60)
    log.info("PRINTING ERP MANUAL BACKUP STARTING")
    log.info("=" * 60)
    ensure_dirs()

    try:
        with BackupLock():
            success, path, meta = create_backup(backup_type='manual')
    except RuntimeError as e:
        log.error(f"Backup skipped due to lock: {e}")
        return 3

    if path:
        log.info("")
        log.info(f"SUCCESS. Backup saved to: {path}")
    return 0 if success else 1


# =========================================================================
# CLI
# =========================================================================

def main(argv):
    ensure_dirs()
    action = argv[1].lower() if len(argv) > 1 else 'manual'
    if action == 'morning':
        return run_morning_backup()
    if action == 'manual':
        return run_manual_backup()
    if action == 'verify':
        if len(argv) < 3:
            print("Usage: backup.py verify <path_to_zip>")
            return 2
        ok = verify_backup_zip(Path(argv[2]))
        print("VERIFY:", "PASS" if ok else "FAIL")
        return 0 if ok else 1
    if action == 'list':
        print("Daily backups:")
        for p in _list_backups(cfg.DAILY_DIR):
            print(f"  {p.name:50s} {human_bytes(p.stat().st_size):>10s} "
                  f"{time.strftime('%d-%m-%Y %H:%M', time.localtime(p.stat().st_mtime))}")
        print("\nWeekly backups:")
        for p in _list_backups(cfg.WEEKLY_DIR):
            print(f"  {p.name:50s} {human_bytes(p.stat().st_size):>10s} "
                  f"{time.strftime('%d-%m-%Y %H:%M', time.localtime(p.stat().st_mtime))}")
        print("\nMonthly backups:")
        for p in _list_backups(cfg.MONTHLY_DIR):
            print(f"  {p.name:50s} {human_bytes(p.stat().st_size):>10s} "
                  f"{time.strftime('%d-%m-%Y %H:%M', time.localtime(p.stat().st_mtime))}")
        return 0
    print("Valid actions: manual | morning | verify <zip> | list")
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv))
