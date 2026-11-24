import json
import sqlite3
import time


CACHE_SECONDS = 20 * 24 * 60 * 60


class ArtworkCache:
    def __init__(self, path):
        self.connection = sqlite3.connect(path, timeout = 5)
        try:
            with self.connection:
                self.connection.execute('BEGIN IMMEDIATE')
                self.connection.execute(
                    'CREATE TABLE IF NOT EXISTS artwork_cache '
                    '(key TEXT PRIMARY KEY, expires REAL NOT NULL, value TEXT NOT NULL)')
                version = self.connection.execute('PRAGMA user_version').fetchone()[0]
                if version == 0:
                    self.connection.execute('UPDATE artwork_cache SET expires = expires + ?', (5 * 24 * 60 * 60,))
                    self.connection.execute('PRAGMA user_version = 1')
                self.connection.execute('DELETE FROM artwork_cache WHERE expires <= ?', (time.time(),))
        except sqlite3.Error:
            self.connection.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def close(self):
        self.connection.close()

    def get(self, key):
        key = json.dumps(key, ensure_ascii = False)
        row = self.connection.execute(
            'SELECT value FROM artwork_cache WHERE key = ? AND expires > ?', (key, time.time())).fetchone()
        return (True, json.loads(row[0])) if row is not None else (False, None)

    def put(self, key, value):
        key = json.dumps(key, ensure_ascii = False)
        value = json.dumps(value, ensure_ascii = False)
        with self.connection:
            self.connection.execute(
                'INSERT OR REPLACE INTO artwork_cache (key, expires, value) VALUES (?, ?, ?)',
                (key, time.time() + CACHE_SECONDS, value))
