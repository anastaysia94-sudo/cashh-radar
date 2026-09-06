from pathlib import Path
import sqlite3, json, os, datetime
src=Path(os.getenv('CASHH_DB_PATH','data/cashh_radar.db'))
out=Path(os.getenv('CASHH_EXPORT_PATH','cashh_radar_export.json'))
conn=sqlite3.connect(src);conn.row_factory=sqlite3.Row
payload={'exported_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'tables':{}}
for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
    name=row['name'];payload['tables'][name]=[dict(r) for r in conn.execute(f'SELECT * FROM "{name}"')]
out.write_text(json.dumps(payload,indent=2,default=str));print(out)
