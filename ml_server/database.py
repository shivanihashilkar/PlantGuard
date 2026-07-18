"""
MySQL database helpers for LeafScan â€” leafscan database.

Tables:
  users       â€” user_id, first_name, last_name, email, password
  plants      â€” plant_id, user_id, image_path, upload_date
  predictions â€” prediction_id, plant_id, disease_name, confidence, result_date
"""

import mysql.connector

SERVER_CONFIG = {
    "host":     "127.0.0.1",
    "user":     "root",
    "password": "",           # XAMPP default - no password
}

DB_CONFIG = {
    "host":     "127.0.0.1",
    "user":     "root",
    "password": "",           # XAMPP default - no password
    "database": "leafscan",
}

GUEST_EMAIL = "guest@leafscan.local"


def get_connection():
    return mysql.connector.connect(**DB_CONFIG)


def init_database():
    """Create the leafscan database and required tables if they do not exist."""
    server_conn = mysql.connector.connect(**SERVER_CONFIG)
    server_cur = server_conn.cursor()
    server_cur.execute("CREATE DATABASE IF NOT EXISTS leafscan")
    server_cur.close()
    server_conn.close()

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id      INT AUTO_INCREMENT PRIMARY KEY,
            first_name   VARCHAR(100) NOT NULL,
            last_name    VARCHAR(100) NOT NULL,
            email        VARCHAR(150) UNIQUE NOT NULL,
            password     VARCHAR(255) NOT NULL,
            created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS plants (
            plant_id      INT AUTO_INCREMENT PRIMARY KEY,
            user_id       INT NOT NULL,
            image_path    VARCHAR(255) NOT NULL,
            upload_date   DATETIME DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_plants_user
                FOREIGN KEY (user_id) REFERENCES users(user_id)
                ON DELETE CASCADE
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            prediction_id  INT AUTO_INCREMENT PRIMARY KEY,
            plant_id       INT NOT NULL,
            disease_name   VARCHAR(150) NOT NULL,
            confidence     FLOAT NOT NULL,
            result_date    DATETIME DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_predictions_plant
                FOREIGN KEY (plant_id) REFERENCES plants(plant_id)
                ON DELETE CASCADE
        )
    """)
    conn.commit()
    cur.close()
    conn.close()


def get_or_create_guest_user():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT user_id FROM users WHERE email = %s", (GUEST_EMAIL,))
    user = cur.fetchone()
    if user:
        user_id = user["user_id"]
    else:
        cur.execute(
            "INSERT INTO users (first_name, last_name, email, password) VALUES (%s,%s,%s,%s)",
            ("Guest", "User", GUEST_EMAIL, "")
        )
        conn.commit()
        user_id = cur.lastrowid
    cur.close()
    conn.close()
    return user_id


def resolve_scan_user_id(user_id):
    if user_id:
        try:
            scan_user_id = int(user_id)
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT user_id FROM users WHERE user_id = %s", (scan_user_id,))
            exists = cur.fetchone()
            cur.close()
            conn.close()
            if exists:
                return scan_user_id
        except (TypeError, ValueError, mysql.connector.Error):
            pass
    return get_or_create_guest_user()


# â”€â”€ Users â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def register_user(first_name, last_name, email, password_hash):
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (first_name, last_name, email, password) VALUES (%s,%s,%s,%s)",
            (first_name, last_name, email, password_hash)
        )
        conn.commit()
        return {"success": True, "user_id": cur.lastrowid}
    except mysql.connector.IntegrityError:
        return {"success": False, "error": "Email already registered"}
    finally:
        cur.close(); conn.close()


def login_user(email, password_hash):
    conn = get_connection()
    cur  = conn.cursor(dictionary=True)
    cur.execute(
        "SELECT user_id, first_name, last_name, email FROM users WHERE email=%s AND password=%s",
        (email, password_hash)
    )
    user = cur.fetchone()
    cur.close(); conn.close()
    return user   # None if not found


# â”€â”€ Plants + Predictions â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def save_scan(user_id, image_path, disease_name, confidence):
    """
    Insert a row into plants then predictions.
    Returns the prediction_id.
    """
    user_id = resolve_scan_user_id(user_id)
    conn = get_connection()
    cur  = conn.cursor()

    # 1. Save plant/image record
    cur.execute(
        "INSERT INTO plants (user_id, image_path) VALUES (%s, %s)",
        (user_id, image_path)
    )
    plant_id = cur.lastrowid

    # 2. Save prediction result
    cur.execute(
        "INSERT INTO predictions (plant_id, disease_name, confidence) VALUES (%s, %s, %s)",
        (plant_id, disease_name, confidence)
    )
    prediction_id = cur.lastrowid

    conn.commit()
    cur.close(); conn.close()
    return prediction_id


def get_user_history(user_id):
    """Get all scans for a user with their predictions."""
    conn = get_connection()
    cur  = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT
            pl.plant_id,
            pl.image_path,
            pl.upload_date,
            pr.prediction_id,
            pr.disease_name,
            pr.confidence,
            pr.result_date
        FROM plants pl
        JOIN predictions pr ON pl.plant_id = pr.plant_id
        WHERE pl.user_id = %s
        ORDER BY pl.upload_date DESC
    """, (user_id,))
    rows = cur.fetchall()
    cur.close(); conn.close()
    return rows


def get_user_stats(user_id):
    """Dashboard stats for a user."""
    conn = get_connection()
    cur  = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT
            COUNT(*)                              AS total_scans,
            SUM(pr.disease_name != 'Healthy')     AS diseases_found,
            ROUND(AVG(pr.confidence), 1)          AS avg_confidence
        FROM plants pl
        JOIN predictions pr ON pl.plant_id = pr.plant_id
        WHERE pl.user_id = %s
    """, (user_id,))
    stats = cur.fetchone()
    cur.close(); conn.close()
    return stats

