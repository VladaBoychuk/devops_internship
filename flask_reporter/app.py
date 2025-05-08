import sqlite3
from flask import Flask, render_template, g, current_app
from parser_and_db import (
    init_db            as initialize_database_schema,
    scan_and_update_db as update_database_from_files,
    DATABASE_FILE      as DB_PATH,
    HOST_IPS
)
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
app.config['DATABASE'] = DB_PATH

# Кольори для кожного джерела
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
    print("APScheduler: Running scheduled job to update database from files...")
    with app.app_context():
        update_database_from_files()
    print("APScheduler: Scheduled DB update finished.")

@app.route('/')
def report():
    conn = get_db()
    cursor = conn.cursor()
    # Зчитуємо реальні записи
    cursor.execute("""
        SELECT 
            receiving_host,
            source_host,
            COUNT(id) AS files_count
        FROM 
            sftp_log_entries
        GROUP BY 
            receiving_host, source_host
    """)
    rows = cursor.fetchall()

    # Всі хости (sftp1, sftp2, sftp3)
    hosts = sorted(HOST_IPS.keys())

    # Створимо словник для швидкого lookup
    counts = {
        (r['receiving_host'], r['source_host']): r['files_count']
        for r in rows
    }

    # Побудова списку для таблиці: всі пари receiving != source
    stats = []
    for recv in hosts:
        for src in hosts:
            if recv == src:
                continue
            stats.append({
                'receiving_host': recv,
                'source_host':    src,
                'files_count':    counts.get((recv, src), 0)
            })

    # Дані для stacked-діаграми
    chart_labels   = hosts
    chart_datasets = []
    for src in hosts:
        data = [ counts.get((recv, src), 0) for recv in hosts ]
        chart_datasets.append({
            'label':           f'from {src}',
            'data':            data,
            'backgroundColor': SOURCE_COLORS[src]
        })

    return render_template(
        'report.html',
         stats=          stats,
         chart_labels=   chart_labels,
         chart_datasets= chart_datasets
    )

if __name__ == '__main__':
    with app.app_context():
        initialize_database_schema()
        update_database_from_files()
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(scheduled_update_db_job, 'interval', minutes=1, id='update_db_job')
    scheduler.start()
    app.run(debug=True, host='0.0.0.0', port=5001, use_reloader=False)
