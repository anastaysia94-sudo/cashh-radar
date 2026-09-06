from pathlib import Path
import sqlite3, os, datetime
src=Path(os.getenv('CASHH_DB_PATH','data/cashh_radar.db'))
outdir=Path(os.getenv('CASHH_BACKUP_DIR','backups'));outdir.mkdir(parents=True,exist_ok=True)
ts=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
out=outdir/f'cashh_radar_{ts}.db'
with sqlite3.connect(src) as s, sqlite3.connect(out) as d: s.backup(d)
print(out)
