"""SQLite repository; no frames are stored. One lock guards short transactions."""
import json
import sqlite3
import threading
import time
from pathlib import Path

class History:
    def __init__(self, path: Path | str):
        self.lock = threading.RLock()
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        with self.lock:
            self.db.executescript('''
            PRAGMA journal_mode=WAL;
            PRAGMA foreign_keys=ON;
            CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, source TEXT, started REAL, ended REAL, summary TEXT);
            CREATE TABLE IF NOT EXISTS tracks(session TEXT, id INTEGER, class_id INTEGER, class_name TEXT, first_seen REAL, last_seen REAL, confidence REAL, PRIMARY KEY(session,id));
            CREATE TABLE IF NOT EXISTS detections(id INTEGER PRIMARY KEY, session TEXT, timestamp REAL, source_time REAL, track_id INTEGER, class TEXT, confidence REAL, x REAL, y REAL, x1 REAL, y1 REAL, x2 REAL, y2 REAL);
            CREATE INDEX IF NOT EXISTS idx_det_session ON detections(session,id);
            CREATE TABLE IF NOT EXISTS count_events(id INTEGER PRIMARY KEY, session TEXT, timestamp REAL, track_id INTEGER, event TEXT, region TEXT);
            CREATE TABLE IF NOT EXISTS analytics(id INTEGER PRIMARY KEY, session TEXT, timestamp REAL, payload TEXT);
            CREATE TABLE IF NOT EXISTS uploaded_models(name TEXT PRIMARY KEY, created REAL, classes TEXT);
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
            ''')
            self.db.commit()
    def execute(self, sql: str, params=()):
        with self.lock, self.db:
            return self.db.execute(sql, params)
    def rows(self, sql: str, params=()):
        with self.lock:
            return [dict(r) for r in self.db.execute(sql, params).fetchall()]
    def get(self, key, default=None):
        rows=self.rows('SELECT value FROM settings WHERE key=?',(key,))
        return json.loads(rows[0]['value']) if rows else default
    def set(self,key,value):
        self.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',(key,json.dumps(value)))
    def start(self,sid,source):
        self.execute('INSERT INTO sessions VALUES(?,?,?,?,?)',(sid,source,time.time(),None,None))
    def finish(self,sid,summary):
        self.execute('UPDATE sessions SET ended=?,summary=? WHERE id=?',(time.time(),json.dumps(summary),sid))
    def sessions(self):
        rows=self.rows('SELECT * FROM sessions ORDER BY started DESC LIMIT 100')
        for r in rows:
            r['summary']=json.loads(r['summary']) if r['summary'] else None
        return rows
    def iter_detections(self,sid):
        last=0
        while True:
            rows=self.rows('SELECT * FROM detections WHERE session=? AND id>? ORDER BY id LIMIT 500',(sid,last))
            if not rows: return
            for row in rows: yield row
            last=rows[-1]['id']
