import sqlite3
from flask import Flask, render_template, g, current_app
from parser_and_db import init_db as initialize_database_schema, \
                          scan_and_update_db as update_database_from_files, \
                          DATABASE_FILE as DB_PATH, \
                          HOST_IPS
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
app.config['DATABASE'] = DB_PATH

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
    print(f"APScheduler: Running scheduled job to update database from files...")
    with app.app_context():
        update_database_from_files()
    print(f"APScheduler: Scheduled DB update finished.")

@app.route('/')
def report():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            source_host, 
            source_ip, 
            COUNT(id) as files_sent_count
        FROM 
            sftp_log_entries
        GROUP BY 
            source_host, source_ip
        ORDER BY 
            source_host
    """)
    sftp_stats = cursor.fetchall()

    chart_labels = []
    chart_data = []
    for stat_row in sftp_stats:
        chart_labels.append(stat_row['source_host'])
        chart_data.append(stat_row['files_sent_count'])

    return render_template('report.html', 
                           stats=sftp_stats, 
                           chart_labels=chart_labels, 
                           chart_data=chart_data,
                           host_ips_dict=HOST_IPS)

if __name__ == '__main__':
    with app.app_context():
        initialize_database_schema()
        print("Initial data population...")
        update_database_from_files() 
    
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(scheduled_update_db_job, 'interval', minutes=1, id='update_db_job')
    scheduler.start()
    print("APScheduler started, will update DB every 1 minute.")
    
    app.run(debug=True, host='0.0.0.0', port=5001, use_reloader=False)