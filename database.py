"""
database.py
-----------
MySQL/MariaDB connection helper para sa XAMPP (Python).
Hango sa pattern na itinuro ni sir, dinagdagan ng portfolio schema.

Awtomatikong gumagawa ng database at tables kung wala pa.

Gamitin:
    import database as db
    with db.DBSession() as conn:
        rows = db.fetch_all(conn, "SELECT * FROM projects")
"""

import mysql.connector
from mysql.connector import Error

from config import Config


def get_config(**overrides):
    """Kopya ng DB config na may overrides (e.g. password=...)."""
    cfg = Config.db_config()
    cfg.update(overrides)
    return cfg


def create_database(db_name):
    """Gumawa ng bagong database kung wala pa."""
    cfg = get_config()
    cfg.pop("database", None)
    conn = None
    try:
        conn = mysql.connector.connect(**cfg)
        cursor = conn.cursor()
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
            f"DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        conn.commit()
        cursor.close()
        print(f"[DB] Database '{db_name}' handa na.")
    except Error as e:
        print(f"[DB ERROR] Hindi makagawa ng database: {e}")
    finally:
        if conn is not None and conn.is_connected():
            conn.close()


def get_connection(database=None, **overrides):
    """Magbalik ng MySQL connection, o None kung hindi makakonekta."""
    cfg = get_config(**overrides)
    cfg.setdefault("connection_timeout", 10)   # huwag mag-hang sa connect
    if database is not None:
        cfg["database"] = database
    try:
        conn = mysql.connector.connect(**cfg)
        if conn.is_connected():
            # Huwag mag-antay nang walang hanggan sa row/table locks
            cur = conn.cursor()
            cur.execute("SET SESSION innodb_lock_wait_timeout=10")
            cur.close()
            return conn
    except Error as e:
        if "Unknown database" in str(e):
            create_database(cfg.get("database"))
            return get_connection(database=cfg.get("database"), **overrides)
        print(f"[DB ERROR] Hindi makonekta: {e}")
        return None
    return None


# Schema ng portfolio. Idempotent (safe patakbuhin paulit-ulit).
SCHEMA = {
    "admins": """
        CREATE TABLE IF NOT EXISTS admins (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    "projects": """
        CREATE TABLE IF NOT EXISTS projects (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(150) NOT NULL,
            slug VARCHAR(170) NOT NULL UNIQUE,
            summary VARCHAR(300),
            description TEXT,
            tech_stack VARCHAR(255),
            image_url VARCHAR(500),
            live_url VARCHAR(500),
            repo_url VARCHAR(500),
            category VARCHAR(20) NOT NULL DEFAULT 'webdev',
            is_visible TINYINT(1) NOT NULL DEFAULT 1,
            sort_order INT NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    "messages": """
        CREATE TABLE IF NOT EXISTS messages (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(150) NOT NULL,
            subject VARCHAR(200),
            body TEXT NOT NULL,
            is_read TINYINT(1) NOT NULL DEFAULT 0,
            ip_address VARCHAR(45),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    "templates": """
        CREATE TABLE IF NOT EXISTS templates (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(150) NOT NULL,
            slug VARCHAR(170) NOT NULL UNIQUE,
            summary VARCHAR(300),
            description TEXT,
            tech_stack VARCHAR(255),
            price VARCHAR(50),
            image_url VARCHAR(500),
            demo_url VARCHAR(500),
            buy_url VARCHAR(500),
            is_visible TINYINT(1) NOT NULL DEFAULT 1,
            sort_order INT NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
}


def create_tables(conn):
    """Gumawa ng lahat ng tables ng portfolio kung wala pa."""
    cursor = conn.cursor()
    for name, ddl in SCHEMA.items():
        cursor.execute(ddl)
    conn.commit()
    cursor.close()


def _column_exists(conn, table, column):
    """Suriin kung existing ang column (via information_schema)."""
    row = fetch_one(
        conn,
        "SELECT COUNT(*) AS c FROM information_schema.columns "
        "WHERE table_schema=%s AND table_name=%s AND column_name=%s",
        (Config.DB_NAME, table, column),
    )
    return bool(row and row["c"] > 0)


def migrate(conn):
    """Idempotent na migration para sa lumang DB (hal. bagong column)."""
    migrations = [
        ("projects", "category",
         "ALTER TABLE projects ADD COLUMN "
         "category VARCHAR(20) NOT NULL DEFAULT 'webdev'"),
    ]
    cursor = conn.cursor()
    for table, column, ddl in migrations:
        if not _column_exists(conn, table, column):
            cursor.execute(ddl)
    conn.commit()
    cursor.close()


def init_schema():
    """Gumawa ng database + lahat ng tables. Tawagin ISANG BESES sa startup.
    Hindi na ito tinatawag sa bawat request (para iwas lock contention)."""
    create_database(Config.DB_NAME)
    conn = get_connection()
    if conn is None:
        return False
    try:
        create_tables(conn)
        migrate(conn)
        return True
    finally:
        conn.close()


# ===================== CRUD HELPERS =====================

def execute_query(conn, query, params=None):
    """INSERT/UPDATE/DELETE. Magbalik ng lastrowid (o rowcount)."""
    cursor = conn.cursor()
    try:
        cursor.execute(query, params or ())
        conn.commit()
        return cursor.lastrowid
    except Error as e:
        conn.rollback()
        print(f"[DB ERROR] {e}")
        return None
    finally:
        cursor.close()


def fetch_all(conn, query, params=None):
    """Magbalik ng list ng dict (rows)."""
    cursor = conn.cursor(dictionary=True)
    cursor.execute(query, params or ())
    rows = cursor.fetchall()
    cursor.close()
    return rows


def fetch_one(conn, query, params=None):
    """Magbalik ng isang dict row o None."""
    rows = fetch_all(conn, query, params)
    return rows[0] if rows else None


# ===================== CONTEXT MANAGER =====================

class DBSession:
    """Gamitin: with DBSession() as conn: ..."""
    def __init__(self, **overrides):
        self.conn = None
        self.overrides = overrides

    def __enter__(self):
        self.conn = get_connection(**self.overrides)
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn is not None and getattr(self.conn, "is_connected", lambda: False)():
            if exc_type is not None:
                # I-rollback ang anumang hindi pa na-commit na changes
                try:
                    self.conn.rollback()
                except Error as e:
                    print(f"[DB ERROR] Rollback failed: {e}")
            self.conn.close()
        return False


if __name__ == "__main__":
    if init_schema():
        print("[DB] Lahat ng tables handa na.")
    else:
        print("Hindi makakonekta. Siguraduhing tumatakbo ang MySQL sa XAMPP.")
