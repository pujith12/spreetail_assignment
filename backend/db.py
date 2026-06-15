import sqlite3
import os

DATABASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'splitright.db')

def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    # Enable foreign key support in SQLite
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'schema.sql')
    with get_db_connection() as conn:
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
        conn.executescript(schema_sql)
        
        # Seed default exchange rates (default is 84.5 for USD as per requirements)
        conn.execute("""
            INSERT INTO exchange_rates (currency, rate)
            VALUES ('USD', 84.5)
            ON CONFLICT(currency) DO UPDATE SET rate = excluded.rate;
        """)
        conn.commit()

if __name__ == '__main__':
    init_db()
    print(f"Database initialized successfully at {DATABASE_PATH}")
