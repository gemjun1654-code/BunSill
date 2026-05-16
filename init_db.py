import sqlite3

def init_db():
    conn = sqlite3.connect("lost_items.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        location TEXT NOT NULL,
        lost_date TEXT,
        description TEXT,
        category TEXT DEFAULT '기타',
        image_filename TEXT,
        found INTEGER DEFAULT 0
        )
        """)

    conn.commit()
    conn.close()

    print("✓ 데이터베이스 초기화 완료")

if __name__ == "__main__":
    init_db()