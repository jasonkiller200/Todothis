import sqlite3

db_path = 'C:/app/Todothis/instance/todo_system.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute('SELECT id, title, description, status, todo_type, user_id, assigned_by_user_id, created_at, updated_at FROM todo;')
rows = cursor.fetchall()

for row in rows:
    print(f"ID: {row[0]}, Title: {row[1]}, Type: {row[4]}, Created At: {row[7]}")

conn.close()
