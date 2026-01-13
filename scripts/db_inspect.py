import sqlite3
con=sqlite3.connect('/mlflow/mlflow.db')
cur=con.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
print('tables:', cur.fetchall())
try:
    cur.execute('SELECT count(*) FROM runs')
    print('runs_count', cur.fetchone())
except Exception as e:
    print('runs_count error', e)
try:
    cur.execute("SELECT run_uuid, run_name, experiment_id, artifact_uri FROM runs")
    rows = cur.fetchall()
    print('runs:')
    for r in rows:
        print(r)
except Exception as e:
    print('runs query error', e)
try:
    cur.execute("PRAGMA table_info('runs')")
    print('runs columns:', cur.fetchall())
    cur.execute('SELECT * FROM runs LIMIT 10')
    for r in cur.fetchall():
        print('run row:', r)
except Exception as e:
    print('runs inspect error', e)
try:
    cur.execute('SELECT experiment_id, name FROM experiments')
    for r in cur.fetchall():
        print('experiment:', r)
except Exception as e:
    print('experiments error', e)
con.close()
