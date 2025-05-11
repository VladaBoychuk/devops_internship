import os
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, g, current_app, request
from parser_and_db import (
    init_db_schema     as initialize_database_schema,
    scan_and_update_db as update_database_from_files,
    HOST_IPS
)
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo

app = Flask(__name__)
app.config['STALENESS_THRESHOLD_MINUTES'] = 15

DB_HOST = os.getenv('DB_HOST', 'db')
DB_NAME = os.getenv('DB_NAME', 'sftp_activity_db')
DB_USER = os.getenv('DB_USER', 'sftp_reporter_user')
DB_PASS = os.getenv('DB_PASS', 'your_strong_password')
DB_PORT = os.getenv('DB_PORT', '5432')

UTC_TZ = ZoneInfo("UTC")
last_successful_db_update_by_scheduler = "N/A"

SOURCE_COLORS = {
    'sftp1': 'rgba(255,  99, 132, 1)',
    'sftp2': 'rgba(54,  162, 235, 1)',
    'sftp3': 'rgba(153, 102, 255, 1)',
}

def get_db():
    if 'db' not in g:
        try:
            g.db = psycopg2.connect(
                host=DB_HOST,
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASS,
                port=DB_PORT
            )
        except psycopg2.Error as e:
            print(f"Error connecting to PostgreSQL database: {e}")
            raise
    return g.db

@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop('db', None)
    if db is not None:
        if not db.closed:
            db.close()

@app.cli.command('init-db')
def init_db_command():
    initialize_database_schema()

@app.cli.command('update-db')
def update_db_command():
    print('CLI: Scanning files and updating database (PostgreSQL)...')
    with app.app_context():
        update_database_from_files()
    print('CLI: Database update process finished (PostgreSQL).')

def scheduled_update_db_job():
    global last_successful_db_update_by_scheduler
    print("APScheduler: Running scheduled job to update database from files (PostgreSQL)...")
    with app.app_context():
        update_database_from_files()
    last_successful_db_update_by_scheduler = datetime.now(UTC_TZ).strftime("%Y-%m-%d %H:%M:%S")
    print(f"APScheduler: Scheduled DB update finished at {last_successful_db_update_by_scheduler} UTC (PostgreSQL).")

@app.route('/')
def report():
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor) 

    selected_date_str = request.args.get('selected_date')
    start_hour_str = request.args.get('start_hour', '00')
    end_hour_str = request.args.get('end_hour', '23')
    
    today_utc_date = datetime.now(UTC_TZ).date()

    if selected_date_str:
        try:
            selected_date_dt = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
        except ValueError:
            selected_date_dt = today_utc_date
    else:
        selected_date_dt = today_utc_date
    selected_date_for_query = selected_date_dt

    try:
        selected_start_hour_int = int(start_hour_str)
        selected_end_hour_int = int(end_hour_str)
        if not (0 <= selected_start_hour_int <= 23 and \
                0 <= selected_end_hour_int <= 23 and \
                selected_start_hour_int <= selected_end_hour_int):
            raise ValueError("Invalid hour range")
    except ValueError:
        selected_start_hour_int = 0
        selected_end_hour_int = 23
    
    cursor.execute("""
        SELECT receiving_host, source_host, COUNT(id) AS files_count
        FROM sftp_log_entries GROUP BY receiving_host, source_host
    """)
    rows = cursor.fetchall()
    hosts = sorted(HOST_IPS.keys())
    counts = {(r['receiving_host'], r['source_host']): r['files_count'] for r in rows}
    stats_detailed_table = []
    for recv in hosts:
        for src in hosts:
            if recv == src: continue
            stats_detailed_table.append({
                'receiving_host': recv, 'source_host': src,
                'files_count': counts.get((recv, src), 0)
            })
    chart_labels_overall = hosts
    chart_datasets_overall = []
    for src_host_chart in hosts:
        data_values = [counts.get((recv_host_chart, src_host_chart), 0) for recv_host_chart in hosts]
        chart_datasets_overall.append({
            'label': f'From {src_host_chart}', 'data': data_values,
            'backgroundColor': SOURCE_COLORS[src_host_chart].replace('1)', '0.7)')
        })

    cursor.execute("SELECT source_host, COUNT(id) AS total_sent FROM sftp_log_entries GROUP BY source_host")
    total_sent_map = {r['source_host']: r['total_sent'] for r in cursor.fetchall()}
    
    cursor.execute("SELECT source_host, MIN(file_timestamp) AS first_sent_ts FROM sftp_log_entries GROUP BY source_host")
    first_sent_rows = cursor.fetchall()
    first_sent_map = {}
    for row in first_sent_rows:
        dt_obj = row['first_sent_ts']
        if dt_obj:
            first_sent_map[row['source_host']] = dt_obj.strftime('%Y-%m-%d %H:%M:%S')
        else:
            first_sent_map[row['source_host']] = "N/A"

    cursor.execute("SELECT source_host, MAX(processed_at) AS last_processed_utc_dt FROM sftp_log_entries GROUP BY source_host")
    last_processed_rows = cursor.fetchall()
    last_processed_map = {row['source_host']: row['last_processed_utc_dt'] for row in last_processed_rows}

    host_sending_activity = []
    threshold_minutes = current_app.config['STALENESS_THRESHOLD_MINUTES']
    now_aware_utc = datetime.now(UTC_TZ)
    for host_name in hosts:
        last_processed_dt_from_db = last_processed_map.get(host_name)
        status_display, status_class_display, last_processed_display_str = "No activity", "status-no-activity", "No activity"
        if last_processed_dt_from_db:
            try:
                dt_processed_aware_utc = last_processed_dt_from_db.replace(tzinfo=UTC_TZ)
                delta = now_aware_utc - dt_processed_aware_utc
                last_processed_display_str = dt_processed_aware_utc.strftime("%Y-%m-%d %H:%M:%S")
                if delta > timedelta(minutes=threshold_minutes):
                    status_display, status_class_display = "Stale!", "status-stale"
                else:
                    status_display, status_class_display = "Active", "status-active"
            except Exception as e:
                print(f"Error processing last_processed_dt for {host_name}: {last_processed_dt_from_db}. Error: {e}")
                last_processed_display_str, status_display, status_class_display = "Error processing date", "Error", "status-error"
        
        first_file_sent_str_display = first_sent_map.get(host_name, "N/A")
        if first_file_sent_str_display != "N/A": first_file_sent_str_display += " UTC"
        
        last_file_sent_str_display = last_processed_display_str
        if last_file_sent_str_display not in ["No activity", "Error processing date"]:
             last_file_sent_str_display += " UTC"

        host_sending_activity.append({
            'source_host': host_name, 'ip_address': HOST_IPS.get(host_name, 'N/A'),
            'total_files_sent': total_sent_map.get(host_name, 0),
            'first_file_sent': first_file_sent_str_display,
            'last_file_sent': last_file_sent_str_display,
            'status': status_display, 'status_class': status_class_display
        })
    
    cursor.execute("""
        SELECT EXTRACT(HOUR FROM file_timestamp) AS hour_of_day, source_host, COUNT(id) AS files_count
        FROM sftp_log_entries
        WHERE file_timestamp::date = %s AND EXTRACT(HOUR FROM file_timestamp) BETWEEN %s AND %s
        GROUP BY source_host, hour_of_day
        ORDER BY source_host ASC, hour_of_day ASC
    """, (selected_date_for_query, selected_start_hour_int, selected_end_hour_int))
    hourly_data_per_source_rows = cursor.fetchall()

    num_hours_in_range = selected_end_hour_int - selected_start_hour_int + 1
    hourly_chart_labels = [f"{h:02d}:00" for h in range(selected_start_hour_int, selected_end_hour_int + 1)]
    hourly_source_data = {host: [0] * num_hours_in_range for host in hosts} 

    for row in hourly_data_per_source_rows:
        try:
            hour_of_day_int = int(row['hour_of_day']) 
            source = row['source_host']
            if source in hourly_source_data and selected_start_hour_int <= hour_of_day_int <= selected_end_hour_int:
                relative_hour_index = hour_of_day_int - selected_start_hour_int
                hourly_source_data[source][relative_hour_index] = row['files_count']
        except (ValueError, TypeError, KeyError) as e:
            print(f"Warning: Could not process hourly data row for filtered range: {dict(row)}. Error: {e}")

    hourly_per_source_datasets = [] 
    for source_host_name in hosts:
        bar_color = SOURCE_COLORS.get(source_host_name, 'rgba(128,128,128,1)')
        hourly_per_source_datasets.append({
            'label': f'From {source_host_name}',
            'data': hourly_source_data[source_host_name],
            'backgroundColor': bar_color,
            'borderColor': bar_color, 
            'borderWidth': 1
        })

    page_load_time_str = datetime.now(UTC_TZ).strftime("%Y-%m-%d %H:%M:%S") + " UTC"
    last_db_update_str = last_successful_db_update_by_scheduler
    if last_db_update_str != "N/A": last_db_update_str += " UTC"

    if not cursor.closed:
        cursor.close()

    return render_template('report.html',
        stats_detailed_table=stats_detailed_table,
        host_sending_activity=host_sending_activity,
        chart_labels_overall=chart_labels_overall,
        chart_datasets_overall=chart_datasets_overall,
        last_db_update=last_db_update_str,
        page_load_time=page_load_time_str,
        staleness_threshold_minutes=threshold_minutes,
        selected_date_for_display=selected_date_dt.strftime('%Y-%m-%d'),
        selected_start_hour_for_display=selected_start_hour_int,
        selected_end_hour_for_display=selected_end_hour_int,
        hourly_chart_labels=hourly_chart_labels,
        hourly_chart_datasets=hourly_per_source_datasets
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