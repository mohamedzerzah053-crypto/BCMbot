import sqlite3

DB_NAME = "bot_data.db"

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(owner_id: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # جدول الأزرار
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS buttons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id INTEGER,
                title TEXT NOT NULL,
                type TEXT NOT NULL CHECK (type IN ('menu', 'content')),
                FOREIGN KEY (parent_id) REFERENCES buttons (id) ON DELETE CASCADE
            )
        ''')
        
        # جدول المحتوى
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS contents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                button_id INTEGER NOT NULL,
                from_chat_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                FOREIGN KEY (button_id) REFERENCES buttons (id) ON DELETE CASCADE
            )
        ''')
        
        # جدول المشرفين
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY,
                role TEXT NOT NULL CHECK (role IN ('owner', 'admin'))
            )
        ''')
        
        cursor.execute('INSERT OR IGNORE INTO admins (user_id, role) VALUES (?, "owner")', (owner_id,))
        conn.commit()

def is_admin(user_id: int) -> bool:
    with get_connection() as conn:
        res = conn.execute('SELECT 1 FROM admins WHERE user_id = ?', (user_id,)).fetchone()
        return res is not None

def is_owner(user_id: int) -> bool:
    with get_connection() as conn:
        res = conn.execute('SELECT 1 FROM admins WHERE user_id = ? AND role = "owner"', (user_id,)).fetchone()
        return res is not None

def add_admin(user_id: int):
    with get_connection() as conn:
        conn.execute('INSERT OR REPLACE INTO admins (user_id, role) VALUES (?, "admin")', (user_id,))
        conn.commit()

def remove_admin(user_id: int):
    with get_connection() as conn:
        conn.execute('DELETE FROM admins WHERE user_id = ? AND role = "admin"', (user_id,))
        conn.commit()

def get_button(button_id: int):
    with get_connection() as conn:
        return conn.execute('SELECT * FROM buttons WHERE id = ?', (button_id,)).fetchone()

def get_child_buttons(parent_id: int = None):
    with get_connection() as conn:
        if parent_id is None:
            return conn.execute('SELECT * FROM buttons WHERE parent_id IS NULL').fetchall()
        return conn.execute('SELECT * FROM buttons WHERE parent_id = ?', (parent_id,)).fetchall()

def add_button(title: str, button_type: str, parent_id: int = None) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO buttons (parent_id, title, type) VALUES (?, ?, ?)', 
                       (parent_id, title, button_type))
        conn.commit()
        return cursor.lastrowid

def update_button_title(button_id: int, new_title: str):
    with get_connection() as conn:
        conn.execute('UPDATE buttons SET title = ? WHERE id = ?', (new_title, button_id))
        conn.commit()

def delete_button(button_id: int):
    with get_connection() as conn:
        conn.execute('PRAGMA foreign_keys = ON')
        conn.execute('DELETE FROM buttons WHERE id = ?', (button_id,))
        conn.commit()

def add_content(button_id: int, from_chat_id: int, message_id: int):
    with get_connection() as conn:
        conn.execute('INSERT INTO contents (button_id, from_chat_id, message_id) VALUES (?, ?, ?)',
                     (button_id, from_chat_id, message_id))
        conn.commit()

def get_button_contents(button_id: int):
    with get_connection() as conn:
        return conn.execute('SELECT * FROM contents WHERE button_id = ? ORDER BY id ASC', (button_id,)).fetchall()

def clear_button_contents(button_id: int):
    with get_connection() as conn:
        conn.execute('DELETE FROM contents WHERE button_id = ?', (button_id,))
        conn.commit()
      
