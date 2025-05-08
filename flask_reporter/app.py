import sqlite3
from flask import Flask, render_template, g, current_app
from parser_and_db import (
    init_db             as initialize_database_schema,
    scan_and_update_db  as update_database_from_files,
    DATABASE_FILE       as DB_PATH,
    HOST_IPS
)
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['DATABASE'] = DB_PATH
app.config['STALENESS_THRESHOLD_MINUTES'] = 15

# Tracks last time the scheduler successfully updated the DB
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
    last_successful_db_update_by_scheduler = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"APScheduler: Scheduled DB update finished at {last_successful_db_update_by_scheduler}.")

@app.route('/')
def report():
    conn = get_db()
    cursor = conn.cursor()

    # Detailed transfers table
    cursor.execute("""
        SELECT receiving_host, source_host, COUNT(id) AS files_count
        FROM sftp_log_entries
        GROUP BY receiving_host, source_host
    """)
    rows = cursor.fetchall()

    hosts = sorted(HOST_IPS.keys())
    counts = {
        (r['receiving_host'], r['source_host']): r['files_count']
        for r in rows
    }

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

    # Stacked chart datasets
    chart_labels = hosts
    chart_datasets = []
    for src in hosts:
        data = [counts.get((recv, src), 0) for recv in hosts]
        chart_datasets.append({
            'label':           f'From {src}',
            'data':            data,
            'backgroundColor': SOURCE_COLORS[src]
        })

    # Sending activity aggregates
    cursor.execute("SELECT source_host, COUNT(id) AS total_sent FROM sftp_log_entries GROUP BY source_host")
    total_sent_map = {r['source_host']: r['total_sent'] for r in cursor.fetchall()}

    cursor.execute("SELECT source_host, MIN(file_timestamp) AS first_sent_ts FROM sftp_log_entries GROUP BY source_host")
    first_sent_map = {r['source_host']: r['first_sent_ts'] for r in cursor.fetchall()}

    # Use processed_at for freshness checking
    cursor.execute("""
        SELECT source_host, MAX(processed_at) AS last_processed
        FROM sftp_log_entries
        GROUP BY source_host
    """)
    last_proc_map = {r['source_host']: r['last_processed'] for r in cursor.fetchall()}

    # Build host sending activity with staleness logic
    host_sending_activity = []
    threshold = current_app.config['STALENESS_THRESHOLD_MINUTES']
    for host_name in hosts:
        last_proc_str = last_proc_map.get(host_name)
        if last_proc_str:
            try:
                last_proc_dt = datetime.fromisoformat(last_proc_str)
                delta = datetime.now() - last_proc_dt
                if delta > timedelta(minutes=threshold):
                    status = "Stale!"
                    status_class = "status-stale"
                else:
                    status = "Active"
                    status_class = "status-active"
            except ValueError:
                status = "Error"
                status_class = "status-error"
        else:
            last_proc_str = "No activity"
            status = "No activity"
            status_class = "status-no-activity"

        host_sending_activity.append({
            'source_host':      host_name,
            'ip_address':       HOST_IPS.get(host_name, 'N/A'),
            'total_files_sent': total_sent_map.get(host_name, 0),
            'first_file_sent':  first_sent_map.get(host_name, 'N/A'),
            'last_file_sent':   last_proc_str,
            'status':           status,
            'status_class':     status_class
        })

    page_load_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return render_template('report.html',
        stats_detailed_table=stats_detailed_table,
        host_sending_activity=host_sending_activity,
        chart_labels=chart_labels,
        chart_datasets=chart_datasets,
        last_db_update=last_successful_db_update_by_scheduler,
        page_load_time=page_load_time,
        staleness_threshold_minutes=threshold
    )

if __name__ == '__main__':
    with app.app_context():
        initialize_database_schema()
        update_database_from_files()
        # Initialize scheduler timestamp
        last_successful_db_update_by_scheduler = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(scheduled_update_db_job, 'interval', minutes=1, id='update_db_job')
    scheduler.start()
    print(f"APScheduler started. Last initial DB update: {last_successful_db_update_by_scheduler}")

    app.run(debug=True, host='0.0.0.0', port=5001, use_reloader=False)
