import os
import re
import psycopg2
from datetime import datetime
from zoneinfo import ZoneInfo

# Paths
BASE_DIR = os.path.dirname(__file__)
DATABASE_FILE = os.path.join(BASE_DIR, 'instance', 'reporting.db')
COLLECTED_FILES_DIR = os.path.abspath(
    os.path.join(BASE_DIR, '..', 'collected_sftp_files')
)

# Database connection settings
DB_HOST = os.getenv('DB_HOST', 'db')
DB_NAME = os.getenv('DB_NAME', 'sftp_activity_db')
DB_USER = os.getenv('DB_USER', 'sftp_reporter_user')
DB_PASS = os.getenv('DB_PASS', 'Password_123')
DB_PORT = os.getenv('DB_PORT', '5432')

# Timezone for UTC
UTC_TZ = ZoneInfo("UTC")

# Mapping of SFTP hostnames to their IP addresses
HOST_IPS = {
    "sftp1": "192.168.56.101",
    "sftp2": "192.168.56.102",
    "sftp3": "192.168.56.103",
}

# Root directory for collected SFTP files
SFTP_LOG_ROOT_DIR = COLLECTED_FILES_DIR

# Regex to match filenames like sftp1_YYYYMMDD_HHMMSS.txt
FILENAME_REGEX = re.compile(r'^(sftp[1-3])_(\d{8})_(\d{6})\.txt$')

def get_postgresql_connection():
    """Return a new PostgreSQL connection."""
    return psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        port=DB_PORT
    )

def init_db_schema():
    """
    Create the sftp_log_entries table with a UNIQUE constraint
    to prevent duplicate records.
    """
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS sftp_log_entries (
        id SERIAL PRIMARY KEY,
        filename TEXT NOT NULL,
        source_host TEXT NOT NULL,
        receiving_host TEXT NOT NULL,
        file_timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL,
        processed_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (filename, source_host, receiving_host)
    );
    """
    conn = None
    try:
        conn = get_postgresql_connection()
        with conn.cursor() as cur:
            cur.execute(create_table_sql)
        conn.commit()
        print("Database schema initialized: table with unique constraint ready.")
    except psycopg2.Error as e:
        print(f"Error initializing database schema: {e}")
    finally:
        if conn:
            conn.close()

def parse_filename(filename):
    """
    Parse the filename into source_host and a datetime object.
    Returns (source_host, file_datetime) or (None, None) on failure.
    """
    match = FILENAME_REGEX.match(filename)
    if not match:
        return None, None
    source_host, date_str, time_str = match.groups()
    try:
        dt = datetime(
            int(date_str[0:4]), int(date_str[4:6]), int(date_str[6:8]),
            int(time_str[0:2]), int(time_str[2:4]), int(time_str[4:6])
        )
        return source_host, dt
    except ValueError:
        return None, None

def scan_and_update_db():
    """
    Scan SFTP upload directories and insert new log entries into the database.
    Duplicate entries are automatically skipped via ON CONFLICT DO NOTHING.
    """
    now_utc = datetime.now(UTC_TZ).replace(tzinfo=None)
    print(f"[{now_utc:%Y-%m-%d %H:%M:%S}] Starting scan of {SFTP_LOG_ROOT_DIR}...")

    insert_sql = """
    INSERT INTO sftp_log_entries
        (filename, source_host, receiving_host, file_timestamp, processed_at)
    VALUES (%s, %s, %s, %s, %s)
    ON CONFLICT (filename, source_host, receiving_host) DO NOTHING;
    """

    conn = None
    files_added = 0
    try:
        conn = get_postgresql_connection()
        with conn.cursor() as cur:
            for dirname in os.listdir(SFTP_LOG_ROOT_DIR):
                dir_path = os.path.join(SFTP_LOG_ROOT_DIR, dirname)
                match = re.match(r'^(sftp[1-3])(?:_uploads)?$', dirname)
                if not (os.path.isdir(dir_path) and match):
                    continue

                receiving_host = match.group(1)
                print(f"  Scanning {receiving_host} in {dir_path}...")

                for fname in os.listdir(dir_path):
                    if not fname.endswith('.txt'):
                        continue

                    source_host, file_dt = parse_filename(fname)
                    if not source_host or source_host == receiving_host:
                        continue

                    cur.execute(
                        insert_sql,
                        (fname, source_host, receiving_host, file_dt, now_utc)
                    )
                    if cur.rowcount == 1:
                        files_added += 1
                        print(f"    + Added: {fname} ({source_host} → {receiving_host})")

            conn.commit()

        print(f"Scan complete. New files added: {files_added}")
    except Exception as e:
        print(f"Unexpected error during scan: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    print("Initializing database schema...")
    init_db_schema()
    print("\nPerforming initial scan...")
    scan_and_update_db()
    print("\nDone.")
