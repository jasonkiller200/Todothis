import sqlite3
import json
from datetime import datetime

DB_PATH = 'instance/todo_system.db'
BACKUP_FILE = 'backup_data.json'

def backup_data():
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row # 讓查詢結果可以像字典一樣存取

        cursor = conn.cursor()

        # 備份 User 資料
        cursor.execute("SELECT id, user_key, name, role, department, level, avatar, email, password_hash, is_active, last_login, failed_login_attempts, account_locked_until, created_at FROM user")
        users_data = []
        user_id_to_user_key = {} # 用於待辦事項的 user_id 到 user_key 映射

        for row in cursor.fetchall():
            user = dict(row)
            user_id_to_user_key[user['id']] = user['user_key']
            # 將 datetime 物件轉換為字串
            for k in ['last_login', 'account_locked_until', 'created_at']:
                if user[k]:
                    user[k] = datetime.fromisoformat(user[k]).isoformat()
            del user['id'] # 備份時不需要舊的 id
            users_data.append(user)

        # 備份 Todo 資料
        cursor.execute("SELECT id, title, description, status, todo_type, user_id, assigned_by_user_id, uncompleted_reason, created_at, updated_at FROM todo")
        todos_data = []
        for row in cursor.fetchall():
            todo = dict(row)
            # 將 user_id 和 assigned_by_user_id 轉換為 user_key
            todo['user_key'] = user_id_to_user_key.get(todo['user_id'])
            todo['assigned_by_user_key'] = user_id_to_user_key.get(todo['assigned_by_user_id'])
            
            # 將 datetime 物件轉換為字串
            for k in ['created_at', 'updated_at']:
                if todo[k]:
                    todo[k] = datetime.fromisoformat(todo[k]).isoformat()
            
            del todo['id'] # 備份時不需要舊的 id
            del todo['user_id']
            del todo['assigned_by_user_id']
            todos_data.append(todo)

        backup_content = {
            'users': users_data,
            'todos': todos_data
        }

        with open(BACKUP_FILE, 'w', encoding='utf-8') as f:
            json.dump(backup_content, f, ensure_ascii=False, indent=4)

        print(f"資料已成功備份到 {BACKUP_FILE}")

    except sqlite3.Error as e:
        print(f"資料庫操作錯誤: {e}")
    except Exception as e:
        print(f"備份過程中發生錯誤: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    backup_data()