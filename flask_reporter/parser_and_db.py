#!/usr/bin/env python3
"""
Parser and DB update module with fixed schema and recursive scanning.
"""
import sqlite3
import os
import re
from datetime import datetime

# Paths
BASE_DIR = os.path.dirname(__file__)
DATABASE_FILE = os.path.join(BASE_DIR, 'instance', 'reporting.db')
COLLECTED_FILES_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', 'collected_sftp_files'))

HOST_IPS = {
    "sftp1": "192.168.56.101",
    "sftp2": "192.168.56.102",
    "sftp3": "192.168.56.103",
}

def get_db_connection():
    """Ensure DB directory exists and return a SQLite connection."""
    os.makedirs(os.path.dirname(DATABASE_FILE), exist_ok=True)
    conn = sqlite3.connect(DATABASE_FILE, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Create the sftp_log_entries table with composite unique key."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sftp_log_entries (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            filename       TEXT    NOT NULL,
            source_host    TEXT    NOT NULL,
            source_ip      TEXT    NOT NULL,
            file_timestamp TEXT    NOT NULL,
            receiving_host TEXT    NOT NULL,
            processed_at   TEXT    NOT NULL DEFAULT (STRFTIME('%Y-%m-%d %H:%M:%f', 'NOW', 'localtime')),
            UNIQUE(filename, receiving_host)
        )
    ''')
    conn.commit()
    conn.close()
    print("Database initialized (table 'sftp_log_entries' checked/created).")


def parse_filename(filename):
    """Extract source_host and timestamp from filename pattern."""
    match = re.match(r'(sftp[1-3])_(\d{8})_(\d{6})\.txt', filename)
    if not match:
        return None, None
    source_host, date_str, time_str = match.groups()
    try:
        dt = datetime.strptime(f"{date_str}{time_str}", "%Y%m%d%H%M%S")
        timestamp_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        return source_host, timestamp_str
    except ValueError:
        print(f"Error: could not parse datetime from filename '{filename}'")
        return None, None


def scan_and_update_db():
    """
    Walk through collected_sftp_files/*_uploads recursively,
    parse each file, and insert new entries into the DB.
    """
    print(f"Starting scan of directory: {COLLECTED_FILES_DIR}")
    if not os.path.exists(COLLECTED_FILES_DIR):
        print(f"Error: Directory {COLLECTED_FILES_DIR} not found.")
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    new_count = 0

    for folder_name in os.listdir(COLLECTED_FILES_DIR):
        m = re.match(r'(sftp[1-3])_uploads', folder_name)
        if not m:
            continue
        receiving_host = m.group(1)
        root_dir = os.path.join(COLLECTED_FILES_DIR, folder_name)
        if not os.path.isdir(root_dir):
            continue
        print(f"  Scanning sub-directory: {root_dir} (receiving_host={receiving_host})")

        # recursive walk
        for dirpath, dirnames, filenames in os.walk(root_dir):
            for fname in filenames:
                src_host, ts = parse_filename(fname)
                if not src_host:
                    print(f"    Skipping non-matching file: {fname}")
                    continue
                src_ip = HOST_IPS.get(src_host, "Unknown")
                try:
                    cursor.execute(
                        '''INSERT INTO sftp_log_entries
                           (filename, source_host, source_ip, file_timestamp, receiving_host)
                           VALUES (?, ?, ?, ?, ?)''',
                        (fname, src_host, src_ip, ts, receiving_host)
                    )
                    conn.commit()
                    new_count += 1
                    print(f"    Added: {fname} from {src_host} to {receiving_host}")
                except sqlite3.IntegrityError:
                    # already seen this (filename, receiving_host)
                    pass
                except Exception as e:
                    print(f"    Error inserting {fname}: {e}")

    conn.close()
    if new_count:
        print(f"Finished scanning. {new_count} new entries added.")
    else:
        print("Finished scanning. No new files added.")


if __name__ == '__main__':
    print("--- Manual Script Execution Start ---")
    init_db()
    print("\nScanning and updating database...\n")
    scan_and_update_db()
    print("\n--- Manual Script Execution End ---")
    print(f"DB location: {DATABASE_FILE}")
