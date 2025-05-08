import sqlite3
from flask import Flask, render_template, g, current_app
from parser_and_db import (
    init_db          as initialize_database_schema,
    scan_and_update_db as update_database_from_files,
    DATABASE_FILE      as DB_PATH,
    HOST_IPS
)
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

app = Flask(__name__)
app.config['DATABASE'] = DB_PATH
app.config['STALENESS_THRESHOLD_MINUTES'] = 15

UTC_TZ = ZoneInfo("UTC")
last_successful_db_update_by_scheduler = "N/A"

SOURCE_COLORS = {
    'sftp1': 'rgba(255,  99, 132, 0.7)',
    'sftp2': 'rgba(54,  162, 235, 0.7)',
    'sftp3': 'rgba(255, 206,  86, 0.7)',
}

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

@app.cli.command('init-db')
def init_db_command():
    initialize_database_schema()
    print('Initialized the database.')

@app.cli.command('update-db')
def update_db_command():
    print('CLI: Scanning files and updating database...')
    with app.app_context():
        update_database_from_files()
    print('CLI: Database update process finished.')

def scheduled_update_db_job():
    global last_successful_db_update_by_scheduler
    print("APScheduler: Running scheduled job to update database from files...")
    with app.app_context():
        update_database_from_files()
    last_successful_db_update_by_scheduler = datetime.now(UTC_TZ).strftime("%Y-%m-%d %H:%M:%S")
    print(f"APScheduler: Scheduled DB update finished at {last_successful_db_update_by_scheduler} UTC.")

@app.route('/')
def report():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT receiving_host, source_host, COUNT(id) AS files_count
        FROM sftp_log_entries
        GROUP BY receiving_host, source_host
    """)
    rows = cursor.fetchall()

    hosts = sorted(HOST_IPS.keys())
    counts = {(r['receiving_host'], r['source_host']): r['files_count'] for r in rows}

    stats_detailed_table = []
    for recv in hosts:
        for src in hosts:
            if recv == src:
                continue
            stats_detailed_table.append({
                'receiving_host': recv,
                'source_host':    src,
                'files_count':    counts.get((recv, src), 0)
            })

    chart_labels = hosts
    chart_datasets = []
    for src_host_chart in hosts:
        data = [counts.get((recv_host_chart, src_host_chart), 0) for recv_host_chart in hosts]
        chart_datasets.append({
            'label':           f'From {src_host_chart}',
            'data':            data,
            'backgroundColor': SOURCE_COLORS[src_host_chart]
        })

    cursor.execute("SELECT source_host, COUNT(id) AS total_sent FROM sftp_log_entries GROUP BY source_host")
    total_sent_map = {r['source_host']: r['total_sent'] for r in cursor.fetchall()}

    cursor.execute("SELECT source_host, MIN(file_timestamp) AS first_sent_ts FROM sftp_log_entries GROUP BY source_host")
    first_sent_map = {r['source_host']: r['first_sent_ts'] for r in cursor.fetchall()}

    cursor.execute("""
        SELECT source_host, MAX(processed_at) AS last_processed_utc_str
        FROM sftp_log_entries
        GROUP BY source_host
    """)
    last_processed_map = {r['source_host']: r['last_processed_utc_str'] for r in cursor.fetchall()}

    host_sending_activity = []
    threshold_minutes = current_app.config['STALENESS_THRESHOLD_MINUTES']
    now_aware_utc = datetime.now(UTC_TZ)

    for host_name in hosts:
        last_processed_utc_str_from_db = last_processed_map.get(host_name)
        
        status_display = "No activity"
        status_class_display = "status-no-activity"
        last_processed_display_str = "No activity"

        if last_processed_utc_str_from_db:
            try:
                dt_processed_naive_utc = datetime.fromisoformat(last_processed_utc_str_from_db)
                dt_processed_aware_utc = dt_processed_naive_utc.replace(tzinfo=UTC_TZ)
                
                delta = now_aware_utc - dt_processed_aware_utc

                last_processed_display_str = dt_processed_aware_utc.strftime("%Y-%m-%d %H:%M:%S")
                if delta > timedelta(minutes=threshold_minutes):
                    status_display = "Stale!"
                    status_class_display = "status-stale"
                else:
                    status_display = "Active"
                    status_class_display = "status-active"
            except ValueError as e:
                print(f"Error parsing processed_at timestamp for {host_name}: '{last_processed_utc_str_from_db}'. Error: {e}")
                last_processed_display_str = "Parse error"
                status_display = "Error"
                status_class_display = "status-error"
        
        first_file_sent_str = first_sent_map.get(host_name, "N/A")
        if first_file_sent_str != "N/A":
             first_file_sent_str += " UTC"

        host_sending_activity.append({
            'source_host':      host_name,
            'ip_address':       HOST_IPS.get(host_name, 'N/A'),
            'total_files_sent': total_sent_map.get(host_name, 0),
            'first_file_sent':  first_file_sent_str,
            'last_file_sent':   f"{last_processed_display_str} UTC" if last_processed_display_str not in ["No activity", "Parse error"] else last_processed_display_str,
            'status':           status_display,
            'status_class':     status_class_display
        })

    page_load_time_str = datetime.now(UTC_TZ).strftime("%Y-%m-%d %H:%M:%S") + " UTC"
    last_db_update_str = last_successful_db_update_by_scheduler
    if last_db_update_str != "N/A":
        last_db_update_str += " UTC"

    return render_template('report.html',
        stats_detailed_table=stats_detailed_table,
        host_sending_activity=host_sending_activity,
        chart_labels=chart_labels,
        chart_datasets=chart_datasets,
        last_db_update=last_db_update_str,
        page_load_time=page_load_time_str,
        staleness_threshold_minutes=threshold_minutes
    )

if __name__ == '__main__':
    with app.app_context():
        initialize_database_schema()
        update_database_from_files() 
        last_successful_db_update_by_scheduler = datetime.now(UTC_TZ).strftime("%Y-%m-%d %H:%M:%S")

    scheduler = BackgroundScheduler(daemon=True, timezone=UTC_TZ)
    scheduler.add_job(scheduled_update_db_job, 'interval', minutes=1, id='update_db_job')
    scheduler.start()
    print(f"APScheduler started (timezone: UTC). Last initial DB update: {last_successful_db_update_by_scheduler} UTC.")

    app.run(debug=True, host='0.0.0.0', port=5001, use_reloader=False)