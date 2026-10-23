"""
Admin-only backup status view.

This module:
  * Reads backups status from D:\PrintingERP\backups\ via
    backup_system (imported with sys.path adjustment).
  * Provides a URL /backup-status/ accessible ONLY to user.role == 'admin'.
  * Exposes NO backup files for download (security).
  * Shows: last backup time/status/size, count, last error, list of recent backups.
"""

from __future__ import annotations

import json
import os
import sys
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpRequest, HttpResponseForbidden
from django.shortcuts import render

# Import backup_system config & helpers
BACKUP_PKG_ROOT = Path(__file__).resolve().parent.parent / 'backup_system'
if str(BACKUP_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKUP_PKG_ROOT))

try:
    import config as cfg  # type: ignore
    _CFG_OK = True
except Exception:
    _CFG_OK = False


def _human_bytes(n: int) -> str:
    step = 1024.0
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if n < step:
            return f"{n:.2f} {unit}"
        n /= step
    return f"{n:.2f} PB"


def _list_backups(bucket: Path) -> List[Dict[str, Any]]:
    if not bucket or not bucket.exists():
        return []
    items: List[Dict[str, Any]] = []
    for fp in bucket.glob("ERP_Backup_*.zip"):
        try:
            if not fp.is_file():
                continue
            st = fp.stat()
            items.append({
                'name': fp.name,
                'size': st.st_size,
                'size_h': _human_bytes(st.st_size),
                'mtime': time.strftime("%d-%m-%Y %H:%M:%S", time.localtime(st.st_mtime)),
                'bucket': bucket.name,
            })
        except Exception:
            pass
    items.sort(key=lambda x: x['name'], reverse=True)
    return items


@login_required
def backup_status_view(request: HttpRequest):
    # Role check: admin only
    user = request.user
    if not getattr(user, 'role', None) == 'admin':
        return HttpResponseForbidden(
            "Forbidden: Only admin users can view backup status.")

    ctx: Dict[str, Any] = {
        'cfg_ok': _CFG_OK,
    }
    if not _CFG_OK:
        ctx['error'] = 'Backup configuration module could not be loaded.'
        return render(request, 'admin/backup_status.html', ctx)

    # --- Latest status file ---
    latest = {'exists': False, 'text': ''}
    if cfg.LATEST_STATUS_FILE.exists():
        latest['exists'] = True
        try:
            latest['text'] = cfg.LATEST_STATUS_FILE.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            latest['text'] = '(Could not read)'
    ctx['latest'] = latest

    # --- Log tail (last 50 lines) ---
    log_tail: List[str] = []
    if cfg.LOG_FILE.exists():
        try:
            with open(cfg.LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
                all_lines = f.read().splitlines()
                log_tail = all_lines[-50:]
        except Exception:
            log_tail = ['(Could not read log file)']
    ctx['log_tail'] = log_tail

    # --- Count backups ---
    daily = _list_backups(cfg.DAILY_DIR)
    weekly = _list_backups(cfg.WEEKLY_DIR)
    monthly = _list_backups(cfg.MONTHLY_DIR)
    pre_restore = _list_backups(cfg.PRE_RESTORE_DIR)

    all_backups = daily + weekly + monthly
    ctx['count_daily'] = len(daily)
    ctx['count_weekly'] = len(weekly)
    ctx['count_monthly'] = len(monthly)
    ctx['count_total'] = len(all_backups)
    ctx['count_pre_restore'] = len(pre_restore)

    # --- Total size used ---
    total_size = 0
    for bucket in (cfg.DAILY_DIR, cfg.WEEKLY_DIR, cfg.MONTHLY_DIR, cfg.PRE_RESTORE_DIR):
        if bucket.exists():
            for p in bucket.rglob('*'):
                try:
                    if p.is_file():
                        total_size += p.stat().st_size
                except Exception:
                    pass
    ctx['total_size_h'] = _human_bytes(total_size)

    # --- Most recent backups table ---
    all_sorted = sorted(all_backups, key=lambda x: x['name'], reverse=True)[:20]
    ctx['recent_backups'] = all_sorted

    # --- Configurable values to display ---
    ctx['retention'] = {
        'daily': cfg.RETENTION_DAILY,
        'weekly': cfg.RETENTION_WEEKLY,
        'monthly': cfg.RETENTION_MONTHLY,
        'startup_delay_min': cfg.BACKUP_STARTUP_DELAY_MINUTES,
        'min_free_gb': cfg.MIN_FREE_SPACE_GB,
    }
    ctx['backup_root'] = str(cfg.BACKUP_ROOT)
    ctx['log_file'] = str(cfg.LOG_FILE)
    ctx['db_engine'] = cfg.DB_ENGINE
    ctx['media_root'] = str(cfg.MEDIA_ROOT)

    return render(request, 'admin/backup_status.html', ctx)
