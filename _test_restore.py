import sys, shutil, sqlite3, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "backup_system"))
import restore as r
import config as cfg

print("=== TEST 9: NON-DESTRUCTIVE restore functions using TEMP DB ===")
zip_path = sorted(Path(cfg.DAILY_DIR).glob("ERP_Backup_*.zip"))[0]
print(f"Using: {zip_path.name}")

td = r.extract_zip_to_temp(zip_path)
assert td is not None, "extract failed"
print(f"Extract OK -> {td}")

orig_db = cfg.DB_PATH
orig_media = cfg.MEDIA_ROOT
test_dir = Path(tempfile.mkdtemp(prefix="erp_restoretst_", dir=str(cfg.BACKUP_ROOT.parent)))
cfg.DB_PATH = test_dir / "db.sqlite3"
cfg.MEDIA_ROOT = test_dir / "media"
try:
    src_db = td / cfg.ZIP_DB_DIR / cfg.ZIP_DB_NAME
    src_media = td / cfg.ZIP_MEDIA_DIR
    ok1 = r.restore_database_from(src_db)
    print(f"restore_database_from: {ok1}")
    ok2 = r.restore_media_from(src_media)
    print(f"restore_media_from: {ok2}")
    assert ok1 and ok2, "restore operations failed"
    conn = sqlite3.connect(f"file:{cfg.DB_PATH}?mode=ro", uri=True)
    tables = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
    conn.close()
    print(f"Restored DB has {tables} tables (expecting ~34)")
    assert tables >= 30, f"too few tables: {tables}"
    # Ensure we have the accounts_user table with data
    conn2 = sqlite3.connect(f"file:{cfg.DB_PATH}?mode=ro", uri=True)
    users = conn2.execute("SELECT COUNT(*) FROM accounts_user").fetchone()[0]
    jobs = conn2.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='jobs'").fetchone()[0]
    clients = conn2.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='clients_client'").fetchone()[0]
    conn2.close()
    print(f"  Accounts users count: {users}")
    print(f"  Jobs table exists: {bool(jobs)}")
    print(f"  Clients table exists: {bool(clients)}")
    assert users >= 1, "no users in restored db"
    print("\nTEST 9 PASSED: Database and media restore functions work correctly.")
finally:
    cfg.DB_PATH = orig_db
    cfg.MEDIA_ROOT = orig_media
    shutil.rmtree(td, ignore_errors=True)
    shutil.rmtree(test_dir, ignore_errors=True)
    print("Temp dirs cleaned.")
