import sqlite3


def emails(conn: sqlite3.Connection) -> list[str]:
    return [row[0] for row in conn.execute("SELECT email FROM users ORDER BY id")]


def invoice_total(conn: sqlite3.Connection, user_id: int) -> float:
    row = conn.execute(
        "SELECT coalesce(sum(amount), 0) FROM invoices WHERE user_id = ?", (user_id,)
    ).fetchone()
    return round(row[0], 2)
