# Printing ERP — Backup & Restore System Guide

**For:** Non-technical ERP owner / Office admin  
**Last updated:** 16-09-2026

---

## 1. Quick Start (5-minute setup)

### Step 1: Run the ONE-TIME setup
On the ERP server computer (the Windows 10 Pro PC):

1. Open the folder `D:\PrintingERP\print_ERP\`
2. **Double-click** `setup_backup_system.bat`
3. If Windows asks "Do you want to allow this app to make changes?" → click **Yes** (it only needs access to your D: drive folders)
4. Let it run — it will:
   - Create backup directories
   - Copy easy-to-find shortcuts to `D:\PrintingERP\`
   - Register the Windows Task Scheduler morning backup
   - Run a **test manual backup** at the end so you know it works

### Step 2: That's it — you're protected
Every time Windows starts:
- 10 minutes after login (to let the ERP start first)
- It checks if **today's** backup already exists
- If not → creates one verified backup
- If yes → skips. **No duplicates, ever.**

---

## 2. One-Backup-Per-Day Rule

This is the single most important behavior:

> *No matter how many times Windows restarts in a single day, you get **at most one automatic backup**.*

### Example:
| Computer started at | Action |
|---------------------|--------|
| 8:30 AM             | ✅ Creates today's backup |
| 10:00 AM (restart)  | ⏭️ Skips — today's already exists |
| 2:15 PM (restart)   | ⏭️ Skips — today's already exists |
| 9:00 AM next day    | ✅ Creates **new** (new date) |

You can always run **manual backups** as many times as you want (they don't count toward the limit).

---

## 3. Backup Location & Structure

### Backup files are stored here:
```
D:\PrintingERP\backups\
├── daily\            # Last 30 daily backups
├── weekly\           # Last 12 weekly (every Monday)
├── monthly\          # Last 12 monthly (every 1st of month)
├── pre_restore\      # Safety copies BEFORE any restore operation
└── logs\
    ├── backup.log              # Full backup history
    └── latest_backup_status.txt  # 1-file quick summary
```

### Inside each .zip backup file:
```
ERP_Backup_2026-09-16_08-42-15.zip
├── database\
│   └── db.sqlite3         # 100% of ERP data (clients, jobs, users...)
├── media\                 # Uploaded files (if you use any)
│   └── ...
└── metadata\
    └── metadata.json      # Timestamp, Django version, status, etc.
```

### What is backed up:
✅ **Entire database** — Clients, Employees, Attendance, Advances, Production jobs, Job costing, Delivery challans, Users/permissions, Pricing rules, Billing/invoices, Reports, and every other table  
✅ **Media / uploaded files** — Images, PDFs, documents (if you add any)  
✅ **Metadata** — Date/time, backup type, Django version, PC name, verification status

### What is NOT backed up (safe to ignore):
❌ `venv/` (virtual environment — reinstallable from requirements.txt)  
❌ `__pycache__/`, `*.pyc`, `.git/`, cache, temp files  
❌ `staticfiles/` (can be regenerated)  
❌ Windows / installed programs

---

## 4. How to Make a Manual Backup (Anytime)

**Method A — Easy desktop shortcut**
Double-click:
```
D:\PrintingERP\backup_now.bat
```
Wait for it to finish. At the end it will say **BACKUP COMPLETED SUCCESSFULLY** and show the filename + size.

**Method B — From Django (Admin only)**
1. Log in as **admin**
2. Click the new **⟳ Backups** link in the top navbar
3. You'll see the live status page

---

## 5. How to Check If Your Latest Backup Worked

### Option 1 — Quick status file (1 second)
Open:
```
D:\PrintingERP\backups\logs\latest_backup_status.txt
```
It will look like:
```
Last backup:
16-09-2026 08:42:15

Status:
SUCCESS

Backup:
ERP_Backup_2026-09-16_08-42-15.zip

Size:
42.18 MB
```

### Option 2 — Django admin page
Admin → **⟳ Backups** → Shows full dashboard with counts, size, and last 50 log lines.

### Option 3 — Full log file
Open with Notepad:
```
D:\PrintingERP\backups\logs\backup.log
```

---

## 6. How to Restore the ERP from a Backup

### ⚠️ WARNING
Restoring **replaces your current data**. A safety backup is ALWAYS made first.

### Step-by-step restore:

1. **On the ERP server computer**, close the running ERP server window if open.

2. Double-click:
   ```
   D:\PrintingERP\restore_erp.bat
   ```
   A menu appears listing **every verified backup** (daily + weekly + monthly), newest first:
   ```
   #        DATE        SIZE      BUCKET   FILE
   1  16-09-2026 08:42  42.18 MB   daily   ERP_Backup_2026-09-16_08-42-15.zip
   2  15-09-2026 08:31  41.90 MB   daily   ERP_Backup_2026-09-15_08-31-03.zip
   ...
   ```

3. **Enter the backup number** you want (e.g. `2`), press Enter.

4. **The system verifies it first** (tests CRC, SQLite integrity check, metadata).
   - If verification fails → ABORTED automatically (no damage). Pick another backup.

5. **TWO confirmations are required** (to prevent accidents):
   - Type **`Y`**  →  first confirmation
   - Type the word **`CONFIRM`** exactly (case-sensitive) → final go-ahead

6. **5 restore steps run automatically** in order:
   1. ✅ Create **PRE-RESTORE SAFETY BACKUP** of your CURRENT data → saved to `D:\PrintingERP\backups\pre_restore\pre_restore_YYYY-MM-DD_HH-MM-SS\`
   2. ✅ Stop any running ERP server (process listening on port 8000 only)
   3. ✅ Restore the database (with automatic rollback if integrity fails)
   4. ✅ Restore media / uploaded files
   5. ✅ Verify restored database integrity

7. **You'll see RESTORE SUCCESS** banner with:
   - Restored from: `<filename>`
   - Safety backup location: `<path>` (keep this, delete only when you're 100% sure)

8. **Manually restart the ERP server** when ready:
   ```
   D:\PrintingERP\start_lan_server.bat
   ```

---

## 7. How Pre-Restore Protection Works

Before **any** restore touches your live database or files, the system first saves:
```
D:\PrintingERP\backups\pre_restore\pre_restore_2026-09-16_14-30-00\
    ├── db.sqlite3      # Snapshot of current live DB (safe SQLite backup)
    ├── media\          # Copy of current uploaded files
    └── README.txt      # Timestamp and recovery instructions
```

If you restore the WRONG backup by accident:
1. Don't panic — your old data is 100% intact in that `pre_restore_*` folder.
2. Copy the `db.sqlite3` file inside it back to `D:\PrintingERP\print_ERP\db.sqlite3` (overwrite the bad one).
3. Copy the media folder back if needed.
4. Or use `restore_erp.bat` again and select the pre-restore safety snapshot's date if you've also zipped it manually.

---

## 8. How to Recreate the Windows Task Scheduler Task

If the task gets deleted or you move the ERP to another folder, just re-run:
```
D:\PrintingERP\print_ERP\setup_backup_system.bat
```

It will re-create everything (idempotent — safe to run multiple times).

### Manual Task Scheduler steps (if you prefer clicking):
1. Open **Task Scheduler** → `Create Task` (NOT Basic Task — Basic doesn't support all options)
2. **General tab:**
   - Name: `Printing ERP - Morning Backup`
   - Description: `One verified ERP backup per day after system startup`
   - Check: "Run only when user is logged on" (simplest) or "Run whether user is logged on or not"
   - Configure for: Windows 10
3. **Triggers tab → New:**
   - Begin the task: `At startup`
   - ✔️ Delay task for: `10 minutes`
   - ✔️ Enabled
4. **Actions tab → New:**
   - Action: `Start a program`
   - Program/script: `D:\PrintingERP\print_ERP\backup_system\morning_backup.bat`
   - Start in: `D:\PrintingERP\print_ERP`
5. **Settings tab:**
   - ✔️ Allow task to be run on demand
   - ✔️ Run task as soon as possible after a scheduled start is missed
   - ✔️ If the task fails, restart every: `5 minutes` → Attempt up to: `1`
   - ✔️ If the task is already running, apply rule: `Do not start a new instance`
6. OK → enter Windows password if prompted.

### Test the scheduled task now (don't wait 10 min):
Task Scheduler → Right-click task → **Run**

---

## 9. How to Test Restoration (Without Risking Live Data)

**Do this once a month** so you know it works when you need it:

1. Run a manual backup first → `D:\PrintingERP\backup_now.bat`
2. Go into Django as admin → **Create one temporary test client** named "ZZZ RESTORE TEST".
3. Now run `restore_erp.bat` → pick the backup you made in step #1.
4. Confirm restore (type `Y`, then `CONFIRM`).
5. After restore finishes → start ERP server.
6. Log in → Clients → Search for "ZZZ RESTORE TEST". **It should be GONE** (because the test was created *after* the backup).
7. To undo the test restore, go to `D:\PrintingERP\backups\pre_restore\pre_restore_<timestamp>\` and restore that safety backup (or use restore_erp again and pick a backup that contains the test client).

✅ If steps 4–6 work → your backup system is **fully operational**.

---

## 10. Troubleshooting

### Problem 1 — Morning backup didn't run
Check the log: `D:\PrintingERP\backups\logs\backup.log`
- If log is **empty** → Scheduled task didn't start. Re-run `setup_backup_system.bat`.
- If log shows "Today's backup already exists" → ✅ That's expected (one-per-day rule).
- If log shows error about lock file → delete `D:\PrintingERP\backups\logs\.backup_in_progress.lock` (only if no backup is running!).

### Problem 2 — Error: Insufficient free disk space
- The system requires at least 2 GB free before creating any backup.
- Delete ONLY from `daily/` (oldest manually), NEVER from `pre_restore/` or the latest successful backup.
- Retention auto-cleans: daily keeps 30, weekly 12, monthly 12. When these thresholds are exceeded, old backups are deleted *after* a new one is verified.

### Problem 3 — Restore says "Could not stop ERP server"
- Close the ERP server command window manually (Ctrl+C or X).
- Or restart the computer → ERP will be stopped.
- Then re-run restore_erp.bat.

### Problem 4 — Restore took wrong backup
DO NOT RESTART THE ERP SERVER YET. Your current data is safe at:
```
D:\PrintingERP\backups\pre_restore\pre_restore_<most recent date>\db.sqlite3
```
Copy that file over:
```
D:\PrintingERP\print_ERP\db.sqlite3
```
And the `media\` folder from pre_restore if you need it.

### Problem 5 — Backup size seems large
SQLite databases don't shrink on their own. If you delete many old records, compact the DB:
```
D:\PrintingERP\print_ERP\venv\Scripts\python.exe -c "import sqlite3;conn=sqlite3.connect(r'D:\PrintingERP\print_ERP\db.sqlite3');conn.execute('VACUUM');conn.close()"
```
(Close the ERP server first, then run).

### Problem 6 — Mobile / tablet LAN access not working after setup
This backup system does **NOT** touch your LAN, Wi-Fi, firewall, or Django settings at all. If Wi-Fi access broke, check the same troubleshooting steps you used before (server running? same Wi-Fi? network Private?).

---

## 11. Security & Confidentiality

- Backups live **locally on D: drive only**. They are never:
  - ❌ Uploaded to the internet
  - ❌ Exposed through Django URLs (no `http://192.168.1.2:8000/backups/` exists)
  - ❌ Downloadable by Employees or Managers (⟳ Backups page requires `admin` role)
  - ❌ Included in Git (`.gitignore` protects backups, db, media, zips, env)
- **If you want OFFSITE protection** (hard drive failure):
  1. Periodically copy the latest zip from `D:\PrintingERP\backups\daily\` to an external USB drive **or**
  2. Copy to another network computer in the office (not the ERP server).

---

## Appendix — Configurable Settings (Advanced)

All defaults are in `D:\PrintingERP\print_ERP\backup_system\config.py`. To change a value permanently, set a **Windows environment variable**:

Open a command prompt as this user and type (for example, 5-minute delay):
```cmd
setx ERP_BACKUP_DELAY 5
```
(Log off and back on for environment variable to take effect.)

| Setting | Environment Variable | Default | What it does |
|---------|----------------------|---------|--------------|
| Startup delay minutes | `ERP_BACKUP_DELAY` | 10 | Minutes to wait after Windows starts before backup |
| Daily retention | `ERP_RETENTION_DAILY` | 30 | How many daily backups to keep |
| Weekly retention | `ERP_RETENTION_WEEKLY` | 12 | How many weekly backups to keep |
| Monthly retention | `ERP_RETENTION_MONTHLY` | 12 | How many monthly backups to keep |
| Min free disk space (GB) | `ERP_MIN_FREE_GB` | 2.0 | Refuse to run if D: has less free space |
| Backup root path | `ERP_BACKUP_ROOT` | `D:\PrintingERP\backups` | Where to store all backups |

---

## Appendix — Files Quick Reference

| Path | Purpose |
|------|---------|
| `D:\PrintingERP\backup_now.bat` | **Manual backup** (double-click) |
| `D:\PrintingERP\restore_erp.bat` | **Restore** (interactive menu) |
| `D:\PrintingERP\setup_backup_system.bat` | **Re-run setup** (one-click) |
| `D:\PrintingERP\start_lan_server.bat` | Start ERP web server on LAN |
| `D:\PrintingERP\BACKUP_RESTORE.md` | This file |
| `D:\PrintingERP\print_ERP\backup_system\backup.py` | Backup engine (safe SQLite copy) |
| `D:\PrintingERP\print_ERP\backup_system\restore.py` | Restore engine |
| `D:\PrintingERP\print_ERP\backup_system\config.py` | All tunable defaults |
| `D:\PrintingERP\backups\daily\` | Last 30 daily verified .zip backups |
| `D:\PrintingERP\backups\weekly\` | Last 12 weekly verified .zip backups |
| `D:\PrintingERP\backups\monthly\` | Last 12 monthly verified .zip backups |
| `D:\PrintingERP\backups\pre_restore\` | Safety snapshots before each restore |
| `D:\PrintingERP\backups\logs\backup.log` | Complete chronological history |
| `D:\PrintingERP\backups\logs\latest_backup_status.txt` | One-file summary |
| Django URL `/backup-status/` | Admin-only dashboard |

---

**Last line:** If you're ever in doubt about whether backups are working, run `backup_now.bat` → if it ends with **BACKUP COMPLETED SUCCESSFULLY**, you're protected. ✅
