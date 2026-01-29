import sqlite3

class ScanDatabase:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:") 
        self.cursor = self.conn.cursor()
        self.init_db()

    def init_db(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS urls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE,
                source TEXT
            )
        ''')
        self.conn.commit()

    def bulk_insert_urls(self, url_generator, source="unknown"):
        sql = "INSERT OR IGNORE INTO urls (url, source) VALUES (?, ?)"
        batch = []
        for url in url_generator:
            if url:
                batch.append((url, source))
                if len(batch) >= 1000:
                    self.cursor.executemany(sql, batch)
                    batch = []
        if batch: self.cursor.executemany(sql, batch)
        self.conn.commit()

    def get_unique_urls(self):
        self.cursor.execute("SELECT url FROM urls")
        while True:
            row = self.cursor.fetchone()
            if row is None: break
            yield row[0]

    def close(self):
        self.conn.close()