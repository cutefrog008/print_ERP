"""
Configuration for Printing ERP backup and restore system.
All values here can be adjusted by the user.
"""

from pathlib import Path
import os

# ---------- Paths ----------
PROJECT_ROOT = Path(__file__).resolve().parent.parent  # D:\PrintingERP\print_ERP
PARENT_DIR = PROJECT_ROOT.parent                      # D:\PrintingERP

BACKUP_ROOT = Path(os.environ.get('ERP_BACKUP_ROOT', str(PARENT_DIR / 'backups')))

DAILY_DIR = BACKUP_ROOT / 'daily'
WEEKLY_DIR = BACKUP_ROOT / 'weekly'
MONTHLY_DIR = BACKUP_ROOT / 'monthly'
PRE_RESTORE_DIR = BACKUP_ROOT / 'pre_restore'
LOG_DIR = BACKUP_ROOT / 'logs'
LOG_FILE = LOG_DIR / 'backup.log'
LATEST_STATUS_FILE = LOG_DIR / 'latest_backup_status.txt'

# ---------- Delay (Morning startup) ----------
BACKUP_STARTUP_DELAY_MINUTES = int(os.environ.get('ERP_BACKUP_DELAY', 10))

# ---------- Retention ----------
RETENTION_DAILY = int(os.environ.get('ERP_RETENTION_DAILY', 30))
RETENTION_WEEKLY = int(os.environ.get('ERP_RETENTION_WEEKLY', 12))
RETENTION_MONTHLY = int(os.environ.get('ERP_RETENTION_MONTHLY', 12))

# ---------- Disk space ----------
MIN_FREE_SPACE_GB = float(os.environ.get('ERP_MIN_FREE_GB', 2.0))

# ---------- Database ----------
DB_PATH = PROJECT_ROOT / 'db.sqlite3'
DB_ENGINE = 'sqlite3'

# ---------- Media ----------
MEDIA_ROOT = PROJECT_ROOT / 'media'

# ---------- Filename ----------
BACKUP_PREFIX = 'ERP_Backup_'
BACKUP_DATE_FORMAT = '%Y-%m-%d_%H-%M-%S'
BACKUP_EXT = '.zip'

# ---------- One-per-day marker ----------
# Marker files live inside daily dir named  .marker-YYYY-MM-DD
MARKER_PREFIX = '.marker-'

# ---------- Lock file ----------
LOCK_FILE = LOG_DIR / '.backup_in_progress.lock'

# ---------- Zip internal layout ----------
ZIP_DB_DIR = 'database'
ZIP_MEDIA_DIR = 'media'
ZIP_META_DIR = 'metadata'
ZIP_META_FILE = 'metadata.json'
ZIP_DB_NAME = 'db.sqlite3'

# ---------- Task Scheduler ----------
TASK_NAME = 'Printing ERP - Morning Backup'
TASK_DESC = 'Runs Printing ERP morning backup once per day after system startup with configurable delay.'
