"""
seed_admin.py
-------------
Gumagawa ng admin account para sa admin panel.
Patakbuhin:  python seed_admin.py
Ang password ay hina-hash (hindi naka-plaintext sa database).
"""

import getpass

import database as db
from security import hash_password


def main():
    db.init_schema()
    with db.DBSession() as conn:
        if conn is None:
            print("Hindi makakonekta sa MySQL. Siguraduhing tumatakbo ang XAMPP MySQL.")
            return

        username = input("Admin username: ").strip()
        if not username:
            print("Kailangan ng username.")
            return

        existing = db.fetch_one(conn, "SELECT id FROM admins WHERE username=%s", (username,))
        password = getpass.getpass("Admin password: ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Hindi tugma ang password.")
            return
        if len(password) < 8:
            print("Dapat at least 8 characters ang password.")
            return

        pw_hash = hash_password(password)
        if existing:
            db.execute_query(conn, "UPDATE admins SET password_hash=%s WHERE id=%s",
                             (pw_hash, existing["id"]))
            print(f"Na-update ang password ng admin '{username}'.")
        else:
            db.execute_query(conn, "INSERT INTO admins (username, password_hash) VALUES (%s, %s)",
                             (username, pw_hash))
            print(f"Nagawa ang admin '{username}'.")


if __name__ == "__main__":
    main()
