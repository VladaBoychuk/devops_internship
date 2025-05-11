import os
import re
import psycopg2
from datetime import datetime, timezone
from zoneinfo import ZoneInfo 

DB_HOST = os.getenv('DB_HOST', 'db')
DB_NAME = os.getenv('DB_NAME', 'sftp_activity_db')
DB_USER = os.getenv('DB_USER', 'sftp_reporter_user')
DB_PASS = os.getenv('DB_PASS', 'Password_123') 
DB_PORT = os.getenv('DB_PORT', '5432')

UTC_TZ = ZoneInfo("UTC") 

HOST_IPS = {
    'sftp1': '192.168.56.101',
    'sftp2': '192.168.56.102',
    'sftp3': '192.168.56.103'
}

SFTP_LOG_ROOT_DIR = '/collected_sftp_files'

FILENAME_REGEX = re.compile(r'^(sftp[1-3])_(\d{8})_(\d{6})\.txt$')

def get_postgresql_connection():
    conn = psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        port=DB_PORT
    )
    return conn

def init_db_schema():
    conn = None
    try:
        conn = get_postgresql_connection()
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS sftp_log_entries (
            id SERIAL PRIMARY KEY,
            filename TEXT UNIQUE NOT NULL,
            source_host TEXT NOT NULL,
            receiving_host TEXT NOT NULL,
            file_timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            processed_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """)
        conn.commit()
        print("Database schema initialized (table 'sftp_log_entries' checked/created for PostgreSQL).")
    except psycopg2.Error as e:
        print(f"Error initializing PostgreSQL database schema: {e}")
    finally:
        if conn:
            cursor.close()
            conn.close()

def parse_filename(filename):
    match = FILENAME_REGEX.match(filename)
    if match:
        source_host = match.group(1)
        date_str = match.group(2)
        time_str = match.group(3)
        
        try:
            year = int(date_str[0:4])
            month = int(date_str[4:6])
            day = int(date_str[6:8])
            hour = int(time_str[0:2])
            minute = int(time_str[2:4])
            second = int(time_str[4:6])
            
            file_datetime_utc = datetime(year, month, day, hour, minute, second)
            return source_host, file_datetime_utc
        except ValueError:
            return None, None
    return None, None

def scan_and_update_db():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting scan of {SFTP_LOG_ROOT_DIR} for PostgreSQL update...")
    conn = None
    try:
        conn = get_postgresql_connection()
        cursor = conn.cursor()
        files_processed_in_this_run = 0

        for receiving_host_dir in os.listdir(SFTP_LOG_ROOT_DIR):
            receiving_host_path = os.path.join(SFTP_LOG_ROOT_DIR, receiving_host_dir)
            if os.path.isdir(receiving_host_path):
                # We expect the folder name to be the name of the receiving host + "_uploads"
                # For example, "sftp1_uploads" -> "sftp1"
                receiving_host_match = re.match(r'^(sftp[1-3])(?:_uploads)?$', receiving_host_dir)
                if not receiving_host_match:
                    print(f"Skipping directory with unexpected name: {receiving_host_dir}")
                    continue
                
                receiving_host = receiving_host_match.group(1)
                
                print(f"Scanning sub-directory for {receiving_host}: {receiving_host_path}")
                for filename in os.listdir(receiving_host_path):
                    if filename.endswith('.txt'):
                        source_host, file_datetime_utc = parse_filename(filename)
                        if source_host and file_datetime_utc:
                            if source_host == receiving_host:
                                continue

                            processed_at_datetime_utc = datetime.now(UTC_TZ).replace(tzinfo=None)


                            try:
                                cursor.execute(
                                    """
                                    INSERT INTO sftp_log_entries 
                                        (filename, source_host, receiving_host, file_timestamp, processed_at) 
                                    VALUES (%s, %s, %s, %s, %s)
                                    ON CONFLICT (filename) DO NOTHING
                                    """,
                                    (filename, source_host, receiving_host, file_datetime_utc, processed_at_datetime_utc)
                                )
                                if cursor.rowcount > 0:
                                    files_processed_in_this_run += 1
                                    print(f"Added to DB (PG): {filename} (Source: {source_host}, Receiver: {receiving_host})")
                            except psycopg2.Error as e:
                                print(f"Error inserting {filename} into PostgreSQL: {e}")
                                conn.rollback() 
                            else:
                                conn.commit() 
                        else:
                            print(f"Could not parse filename: {filename} in {receiving_host_dir}")
            
        print(f"Scan finished. {files_processed_in_this_run} new files added to PostgreSQL DB in this run.")

    except psycopg2.Error as e:
        print(f"Database connection or operation error in scan_and_update_db (PG): {e}")
    except Exception as e:
        print(f"An unexpected error occurred in scan_and_update_db (PG): {e}")
    finally:
        if conn:
            cursor.close()
            conn.close()

if __name__ == '__main__':
    print("Running parser_and_db.py directly (for PostgreSQL). Initializing schema...")
    init_db_schema()
    print("\nScanning for initial data...")
    scan_and_update_db()
    print("\nManual run finished.")