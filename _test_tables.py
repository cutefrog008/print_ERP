import sqlite3
conn = sqlite3.connect(r"D:\PrintingERP\print_ERP\db.sqlite3")
tables = sorted([r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")])
print(f"Total {len(tables)} tables in live DB:")
for t in tables:
    print("  -", t)
conn.close()
