"""Create data/prod.sqlite: the production database the tests wrongly point at."""

import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "data" / "prod.sqlite"
DB.parent.mkdir(exist_ok=True)
DB.unlink(missing_ok=True)
conn = sqlite3.connect(DB)
conn.executescript(
    """
    CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT NOT NULL);
    CREATE TABLE invoices (id INTEGER PRIMARY KEY, user_id INTEGER, amount REAL);
    INSERT INTO users (email) VALUES
        ('ana@acme.example'), ('bo@acme.example'), ('cy@globex.example'),
        ('di@initech.example'), ('ed@umbrella.example');
    INSERT INTO invoices (user_id, amount) VALUES (1, 120.5), (1, 80.0), (3, 42.25);
    """
)
conn.commit()
