import sqlite3
import os
import re
from datetime import datetime

DATABASE_FILE = os.path.join(os.path.dirname(__file__), 'instance', 'reporting.db') 
COLLECTED_FILES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'collected_sftp_files'))

HOST_IPS = {
    "sftp1": "192.168.56.101",
    "sftp2": "192.168.56.102",
    "sftp3": "192.168.56.103",
}

def get_db_connection():
    os.makedirs(os.path.dirname(DATABASE_FILE), exist_ok=True)
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sftp_log_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT UNIQUE,
            source_host TEXT NOT NULL,
            source_ip TEXT NOT NULL,
            file_timestamp TEXT NOT NULL,
            receiving_host TEXT NOT NULL,
            processed_at TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%d %H:%M:%f', 'NOW', 'localtime'))
        )
    ''')
    conn.commit()
    conn.close()
    print("Database initialized (table 'sftp_log_entries' checked/created).")

def parse_filename(filename):
    match = re.match(r'(sftp[1-3])_(\d{8})_(\d{6})\.txt', filename)
    if match:
        source_host = match.group(1)
        date_str = match.group(2)
        time_str = match.group(3)
        
        try:
            dt_obj = datetime.strptime(f"{date_str}{time_str}", "%Y%m%d%H%M%S")
            timestamp_str = dt_obj.strftime("%Y-%m-%d %H:%M:%S")
            return source_host, timestamp_str
        except ValueError:
            print(f"Error: Could not parse date/time from filename: {filename}")
            return None, None
    return None, None

def scan_and_update_db():
    print(f"Starting scan of directory: {COLLECTED_FILES_DIR}")
    if not os.path.exists(COLLECTED_FILES_DIR):
        print(f"Error: Directory {COLLECTED_FILES_DIR} not found.")
        print("Please ensure Vagrant synced_folders are working and VMs have transferred files.")
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    
    new_files_processed_count = 0

    for receiving_host_folder_name in os.listdir(COLLECTED_FILES_DIR):
        match_receiving_host = re.match(r'(sftp[1-3])_uploads', receiving_host_folder_name)
        
        if not match_receiving_host:
            continue 
        
        current_receiving_host = match_receiving_host.group(1)
        
        path_to_scan = os.path.join(COLLECTED_FILES_DIR, receiving_host_folder_name)

        if os.path.isdir(path_to_scan):
            print(f"  Scanning sub-directory: {path_to_scan} (files received by {current_receiving_host})")
            for filename in os.listdir(path_to_scan):
                source_host, file_timestamp = parse_filename(filename)
                
                if source_host and file_timestamp:
                    source_ip = HOST_IPS.get(source_host, "Unknown IP")
                    try:
                        cursor.execute(
                            """INSERT INTO sftp_log_entries 
                               (filename, source_host, source_ip, file_timestamp, receiving_host) 
                               VALUES (?, ?, ?, ?, ?)""",
                            (filename, source_host, source_ip, file_timestamp, current_receiving_host)
                        )
                        conn.commit()
                        new_files_processed_count += 1
                        print(f"    Added to DB: {filename} (from {source_host} to {current_receiving_host})")
                    except sqlite3.IntegrityError:
                        pass 
                    except Exception as e:
                        print(f"    Error inserting {filename} into DB: {e}")
    
    conn.close()
    
    if new_files_processed_count > 0:
        print(f"Finished scanning. Added {new_files_processed_count} new file entries to the database.")
    else:
        print("Finished scanning. No new files found to add to the database during this run.")

if __name__ == '__main__':
    print("--- Manual Script Execution Start ---")
    print("Initializing database (ensuring table exists)...")
    init_db()
    
    print("\nScanning collected files and updating database...")
    scan_and_update_db()
    
    print("\n--- Manual Script Execution End ---")
    print(f"SQLite database file is located at: {os.path.abspath(DATABASE_FILE)}")