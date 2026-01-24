import sqlite3

db_path = 'f:/Antigravity/exam-record/exam_record.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print(f"Checking {db_path}...")
cursor.execute("DROP TABLE IF EXISTS votes")
print("Dropped votes table.")
cursor.execute("DROP TABLE IF EXISTS _alembic_tmp_reports")
print("Dropped _alembic_tmp_reports table.")

# Find duplicates
query = """
SELECT event_id, work_id, COUNT(*)
FROM reports
GROUP BY event_id, work_id
HAVING COUNT(*) > 1
"""
cursor.execute(query)
duplicates = cursor.fetchall()

print(f"Found {len(duplicates)} duplicate groups")

for event_id, work_id, count in duplicates:
    print(f"Processing duplicate: event {event_id}, work {work_id}")
    # Get all ids for this group
    cursor.execute("SELECT id FROM reports WHERE event_id=? AND work_id=? ORDER BY id ASC", (event_id, work_id))
    ids = [row[0] for row in cursor.fetchall()]
    
    # Keep the first one, delete rest
    ids_to_delete = ids[1:]
    if ids_to_delete:
        print(f"Deleting duplicates: {ids_to_delete}")
        # Use comma separated string for IN clause
        placeholders = ','.join('?' * len(ids_to_delete))
        cursor.execute(f"DELETE FROM reports WHERE id IN ({placeholders})", ids_to_delete)

conn.commit()
print("Cleanup complete")
conn.close()
