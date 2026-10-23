"""
Restore system for Printing ERP backups.

Safe workflow:
  1. List available verified backups.
  2. Let user select one.
  3. WARNING + explicit confirmation (twice: Y then type CONFIRM).
  4. Make PRE-RESTORE safety backup of CURRENT DB + media -> pre_restore/.
  5. STOP running ERP server (kill python.exe using port 8000 only - safe check).
  6. Restore DB + media from selected backup.
  7. Verify restored DB integrity.
  8. Report SUCCESS/FAILURE, user can restart ERP manually.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import signal
import shutil
import socket
import sqlite3
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as cfg
from backup import (
    BackupLock, ensure_dirs, free_disk_gb, get_logger, human_bytes,
    verify_backup_zip, verify_sqlite_snapshot, write_latest_status,
)


def list_all_backups() -> List[Tuple[Path, os.stat_result]]:
    """Return list of (Path, stat_result) for all backups across daily/weekly/monthly, newest first."""
    all_files: List[Tuple[Path, os.stat_result]] = []
    for bucket in (cfg.DAILY_DIR, cfg.WEEKLY_DIR, cfg.MONTHLY_DIR):
        if bucket.exists():
            for f in bucket.glob(f"*{cfg.BACKUP_EXT}"):
                if f.is_file():
                    try:
                        all_files.append((f, f.stat()))
                    except Exception:
                        pass
    all_files.sort(key=lambda x: x[1].st_mtime, reverse=True)
    return all_files


def show_table(backups: List[Tuple[Path, os.stat_result]]) -> None:
    hdr = f"{'#':>3}  {'DATE':>19}  {'SIZE':>10}  {'BUCKET':>8}  FILE"
    print("")
    print(hdr)
    print("-" * (len(hdr) + 20))
    for i, (p, s) in enumerate(backups, 1):
        bucket = p.parent.name
        when = time.strftime("%d-%m-%Y %H:%M:%S", time.localtime(s.st_mtime))
        print(f"{i:>3}  {when:>19}  {human_bytes(s.st_size):>10}  {bucket:>8}  {p.name}")
    print("")


def prompt_choice(backups: List[Tuple[Path, os.stat_result]]) -> Optional[Path]:
    while True:
        raw = input("Enter backup number to restore, or 0 to cancel: ").strip()
        if raw == '0':
            return None
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(backups):
                return backups[idx - 1][0]
        print(f"Invalid input. Please enter a number between 1 and {len(backups)} (or 0 to cancel).")


def prompt_confirm(backup_path: Path) -> bool:
    print("")
    print("=" * 72)
    print("                         !! WARNING !!")
    print("=" * 72)
    print("")
    print("You are about to RESTORE the ERP from backup:")
    print(f"    {backup_path.name}")
    print("")
    print("This operation WILL REPLACE the current database and media files.")
    print("A safety backup of your CURRENT data will be created in:")
    print(f"    {cfg.PRE_RESTORE_DIR}")
    print("before any destructive action.")
    print("")
    print("The running ERP server (if any) will be STOPPED.")
    print("")
    ans1 = input("Type Y to continue, N to cancel: ").strip().lower()
    if ans1 != 'y':
        print("Restore cancelled.")
        return False
    print("")
    print("To confirm, please type the word:   CONFIRM   (case-sensitive)")
    ans2 = input("  > ").strip()
    if ans2 != 'CONFIRM':
        print("Restore cancelled (confirmation text did not match).")
        return False
    print("")
    return True


# ====================================================================
# Pre-restore safety backup (lightweight copy, not zipped for speed)
# ====================================================================

def make_pre_restore_safety_backup() -> Optional[Path]:
    """Create a timestamped folder in pre_restore/ with current DB + media.
    Returns the folder path or None on failure."""
    log = get_logger()
    ensure_dirs()
    ts = dt.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    safety_root = cfg.PRE_RESTORE_DIR / f"pre_restore_{ts}"
    try:
        safety_root.mkdir(parents=True, exist_ok=False)
    except Exception as e:
        log.error(f"Could not create pre-restore folder: {e}")
        return None

    log.info(f"Creating PRE-RESTORE safety backup at: {safety_root}")

    # 1) Safe SQLite backup of current live DB (same method used in normal backup)
    try:
        from backup import backup_sqlite_to
        backup_sqlite_to(cfg.DB_PATH, safety_root / cfg.ZIP_DB_NAME)
        log.info("  Live SQLite DB snapshot copied.")
    except Exception as e:
        log.error(f"  Failed to snapshot live DB: {e}")
        return None

    # 2) Copy media tree (if exists)
    if cfg.MEDIA_ROOT.exists():
        try:
            dst_media = safety_root / 'media'
            dst_media.mkdir(parents=True, exist_ok=True)
            for item in cfg.MEDIA_ROOT.rglob('*'):
                if item.is_file():
                    rel = item.relative_to(cfg.MEDIA_ROOT)
                    dst = dst_media / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, dst)
            log.info("  Media tree copied.")
        except Exception as e:
            log.warning(f"  Media copy had issues (non-fatal): {e}")

    # 3) Marker
    (safety_root / "README.txt").write_text(
        "Pre-restore safety backup.\n"
        f"Created: {dt.datetime.now().isoformat(timespec='seconds')}\n"
        "If restore fails, you can copy db.sqlite3 back to your ERP project folder\n"
        "and restore the media/ folder manually.\n",
        encoding='utf-8')

    log.info(f"Pre-restore safety backup complete -> {safety_root}")
    return safety_root


# ====================================================================
# Stop ERP server (safely)
# ====================================================================

def stop_erp_server() -> bool:
    """
    Try to stop the running Django dev server.
    Strategy 1 - Graceful: find python.exe listening on TCP 8000, send CTRL_C_EVENT.
    Strategy 2 - Harder: if still running after 15s, terminate only the process on 8000.
    Never kills unrelated Python processes.
    """
    log = get_logger()
    def pid_on_port_8000() -> Optional[int]:
        try:
            # PowerShell via subprocess would be ideal, but to avoid external tools
            # we parse netstat -ano output.
            import subprocess
            out = subprocess.check_output(
                ['netstat', '-ano'], stderr=subprocess.DEVNULL).decode('mbcs', errors='ignore')
            for line in out.splitlines():
                parts = line.split()
                if len(parts) < 5:
                    continue
                if parts[0].upper() == 'TCP' and ':8000' in parts[1] and parts[3] == 'LISTENING':
                    try:
                        return int(parts[4])
                    except Exception:
                        continue
        except Exception:
            pass
        return None

    pid = pid_on_port_8000()
    if pid is None:
        log.info("No ERP server process detected listening on port 8000.")
        return True

    log.info(f"Detected ERP server running (PID {pid}). Attempting graceful stop...")
    try:
        # Windows: send Ctrl+C to console process
        os.kill(pid, signal.CTRL_C_EVENT)  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        try:
            os.kill(pid, signal.SIGTERM)
        except Exception as e:
            log.warning(f"  Graceful signal failed: {e}")

    # Wait up to 15s
    for _ in range(15):
        time.sleep(1)
        if pid_on_port_8000() != pid:
            log.info("  ERP server stopped gracefully.")
            return True

    # Fallback: terminate
    try:
        os.kill(pid, signal.SIGTERM)
    except Exception:
        pass
    for _ in range(5):
        time.sleep(1)
        if pid_on_port_8000() != pid:
            log.info("  ERP server terminated.")
            return True
    log.warning(f"  Could not stop ERP PID {pid}. Restore may fail due to file lock.")
    return False


# ====================================================================
# Restore operations
# ====================================================================

def extract_zip_to_temp(zip_path: Path) -> Optional[Path]:
    log = get_logger()
    if not zip_path.exists():
        log.error(f"Backup zip missing: {zip_path}")
        return None
    td = Path(tempfile.mkdtemp(prefix='erp_restore_', dir=str(cfg.BACKUP_ROOT.parent)))
    log.info(f"Extracting backup to temp: {td}")
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(td)
    except Exception as e:
        log.error(f"Zip extract failed: {e}")
        shutil.rmtree(td, ignore_errors=True)
        return None
    return td


def restore_database_from(src_db: Path) -> bool:
    """Overwrite cfg.DB_PATH with src_db using SQLite backup API (safe even if locked)."""
    log = get_logger()
    if not src_db.exists():
        log.error(f"Source DB missing from backup: {src_db}")
        return False

    # Close any open handles - ensure destination parent exists
    cfg.DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Strategy:
    # 1) Rename live -> .old (safe rollback point)
    # 2) Copy src -> destination
    # 3) Verify integrity of new live DB
    # 4) Delete .old if OK, else restore .old
    old_db = cfg.DB_PATH.with_suffix('.sqlite3.restore_old')
    rollback_needed = True
    try:
        if cfg.DB_PATH.exists():
            cfg.DB_PATH.replace(old_db)  # atomic-ish on Windows
            log.info(f"  Renamed live DB to: {old_db.name}")

        # Use SQLite backup API for copy (src read-only, dst = new live)
        src_conn = sqlite3.connect(f"file:{src_db}?mode=ro", uri=True, timeout=30)
        try:
            if cfg.DB_PATH.exists():
                cfg.DB_PATH.unlink()
            dst_conn = sqlite3.connect(str(cfg.DB_PATH), timeout=30)
            try:
                with dst_conn:
                    src_conn.backup(dst_conn, pages=100)
            finally:
                dst_conn.close()
        finally:
            src_conn.close()
        log.info("  Database restored to live path.")

        # Verify new DB integrity
        if not verify_sqlite_snapshot(cfg.DB_PATH):
            raise RuntimeError("Restored DB integrity check FAILED.")
        log.info("  Restored DB integrity: OK.")

        rollback_needed = False
    except Exception as e:
        log.error(f"DB restore error: {e}")
        # Rollback
        try:
            if rollback_needed and old_db.exists():
                log.warning(f"  Rolling back: restoring {old_db.name}")
                if cfg.DB_PATH.exists():
                    cfg.DB_PATH.unlink(missing_ok=True)
                old_db.replace(cfg.DB_PATH)
        except Exception as rb:
            log.error(f"    ROLLBACK FAILED: {rb}")
        return False
    finally:
        # Clean up rollback file only if we rolled forward successfully
        if not rollback_needed and old_db.exists():
            try:
                old_db.unlink()
            except Exception:
                pass
    return True


def restore_media_from(src_media: Path) -> bool:
    log = get_logger()
    # If media didn't exist in backup (no files), we must NOT wipe out an existing media dir.
    if not src_media.exists():
        log.info("  No media directory in backup - skipping media restore.")
        return True
    has_files = any(src_media.rglob('*'))
    if not has_files:
        log.info("  Media directory in backup is empty - skipping media restore.")
        return True

    # Rename current media (if exists) to .old for rollback
    old_media = cfg.PROJECT_ROOT / 'media.restore_old'
    rollback_needed = True
    try:
        if cfg.MEDIA_ROOT.exists() and any(cfg.MEDIA_ROOT.rglob('*')):
            cfg.MEDIA_ROOT.replace(old_media)
            log.info(f"  Renamed live media/ to media.restore_old/")

        cfg.MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
        for item in src_media.rglob('*'):
            if item.is_file():
                rel = item.relative_to(src_media)
                dst = cfg.MEDIA_ROOT / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dst)
        log.info("  Media tree restored.")
        rollback_needed = False
    except Exception as e:
        log.error(f"Media restore error: {e}")
        try:
            if rollback_needed and old_media.exists():
                log.warning("  Rolling back media...")
                if cfg.MEDIA_ROOT.exists():
                    shutil.rmtree(cfg.MEDIA_ROOT, ignore_errors=True)
                old_media.replace(cfg.MEDIA_ROOT)
        except Exception as rb:
            log.error(f"    ROLLBACK FAILED: {rb}")
        return False
    finally:
        if not rollback_needed and old_media.exists():
            shutil.rmtree(old_media, ignore_errors=True)
    return True


# ====================================================================
# Main restore flow
# ====================================================================

def run_restore_interactive() -> int:
    log = get_logger()
    log.info("=" * 60)
    log.info("PRINTING ERP RESTORE - INTERACTIVE")
    log.info("=" * 60)
    ensure_dirs()

    backups = list_all_backups()
    if not backups:
        print("")
        print("ERROR: No backups found in:")
        print(f"  {cfg.DAILY_DIR}")
        print(f"  {cfg.WEEKLY_DIR}")
        print(f"  {cfg.MONTHLY_DIR}")
        print("")
        return 2
    show_table(backups)

    chosen = prompt_choice(backups)
    if chosen is None:
        print("Cancelled by user.")
        return 0

    print(f"\nSelected backup: {chosen.name}")
    # Pre-verify
    print("Verifying selected backup integrity...")
    v_ok = verify_backup_zip(chosen)
    if not v_ok:
        print("ERROR: Selected backup failed verification. Restore ABORTED.")
        print("Please choose a different backup file.")
        return 3

    if not prompt_confirm(chosen):
        return 0

    # ---- Destructive phase ----
    try:
        with BackupLock():
            # 1) Pre-restore safety backup of current data
            print("Step 1/5: Creating pre-restore safety backup of current data...")
            safety = make_pre_restore_safety_backup()
            if safety is None:
                print("FATAL: Could not create pre-restore safety backup. Aborted.")
                return 4
            print(f"   Safety backup saved to: {safety}")

            # 2) Stop ERP server
            print("Step 2/5: Stopping ERP server (if running)...")
            stop_erp_server()

            # 3) Extract selected backup to temp
            print("Step 3/5: Extracting backup archive...")
            temp = extract_zip_to_temp(chosen)
            if temp is None:
                print("FATAL: Could not extract backup archive.")
                print(f"  Your current data is still safe in: {safety}")
                return 5
            try:
                src_db = temp / cfg.ZIP_DB_DIR / cfg.ZIP_DB_NAME
                src_media = temp / cfg.ZIP_MEDIA_DIR

                # 4) Restore DB (with rollback)
                print("Step 4/5: Restoring database...")
                if not restore_database_from(src_db):
                    print("FATAL: Database restore failed.")
                    print(f"  PRE-RESTORE safety backup is here: {safety}")
                    return 6

                # 5) Restore media (with rollback)
                print("Step 5/5: Restoring media/files...")
                if not restore_media_from(src_media):
                    print("FATAL: Media restore failed.")
                    print(f"  PRE-RESTORE safety backup is here: {safety}")
                    return 7
            finally:
                shutil.rmtree(temp, ignore_errors=True)

    except RuntimeError as e:
        log.error(f"Lock error: {e}")
        return 8

    # Final summary
    print("")
    print("=" * 72)
    print("                        RESTORE SUCCESS")
    print("=" * 72)
    print(f"  Restored from : {chosen.name}")
    print(f"  Safety backup : {safety}")
    print(f"  Time finished : {dt.datetime.now().strftime('%d-%m-%Y %H:%M:%S')}")
    print("")
    print("NEXT STEPS:")
    print("  1. Verify the restored data by starting the ERP server:")
    print(f"       {cfg.PROJECT_ROOT / 'start_lan_server.bat'}")
    print("  2. Log in and confirm your data is correct.")
    print("  3. If anything is wrong, restore from pre-restore safety backup.")
    print("")
    write_latest_status('RESTORED', backup_path=chosen,
                        backup_ts=dt.datetime.now())
    return 0


def main(argv):
    ensure_dirs()
    if len(argv) > 1 and argv[1].lower() == '--non-interactive':
        print("--non-interactive restore not supported; restore needs human confirmation.")
        return 9
    try:
        return run_restore_interactive()
    except KeyboardInterrupt:
        print("\nRestore cancelled by user (Ctrl+C).")
        return 130


if __name__ == '__main__':
    sys.exit(main(sys.argv))
