import sqlite3

conn = sqlite3.connect("data/eonet.db")
cur = conn.cursor()

print("TABLES:")
for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table';"):
    print("-", row[0])

print("\nCOUNTS:")
for table in ["events", "categories", "sources", "event_geometries", "import_log"]:
    count = cur.execute(f"SELECT COUNT(*) FROM {table};").fetchone()[0]
    print(f"{table}: {count}")

print("\nLAST IMPORT:")
row = cur.execute("SELECT * FROM import_log ORDER BY id DESC LIMIT 1;").fetchone()
print(row)

conn.close()