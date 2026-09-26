"""Load seed/tickets.csv and seed/customers.csv into app.db for mcp/triage_server.py.

Re-running replaces both tables, so the database is the same every time.

    uv run python load_seed.py
"""

import csv
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "app.db"
SEED_DIR = ROOT / "seed"

TICKET_COLUMNS = ["ticket_id", "customer_id", "created_at", "text"]
CUSTOMER_COLUMNS = ["customer_id", "name", "plan", "open_tickets"]

SCHEMA = (
    "DROP TABLE IF EXISTS tickets",
    "DROP TABLE IF EXISTS customers",
    """CREATE TABLE customers (
        customer_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        plan TEXT NOT NULL,
        open_tickets INTEGER NOT NULL
    )""",
    """CREATE TABLE tickets (
        ticket_id TEXT PRIMARY KEY,
        customer_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        text TEXT NOT NULL
    )""",
)


def read_csv(path: Path, columns: list[str]) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != columns:
            raise ValueError(f"{path.name}: expected columns {columns}, found {reader.fieldnames}")
        rows = []
        for row in reader:
            # DictReader puts extra fields under None and fills missing ones with None.
            if None in row or None in row.values():
                raise ValueError(f"{path.name} line {reader.line_num}: expected {len(columns)} fields")
            rows.append(row)
        return rows


def read_customers(path: Path) -> list[tuple]:
    rows = []
    for line, row in enumerate(read_csv(path, CUSTOMER_COLUMNS), start=2):
        try:
            open_tickets = int(row["open_tickets"])
        except ValueError:
            raise ValueError(
                f"{path.name} line {line}: open_tickets must be an integer, got {row['open_tickets']!r}"
            ) from None
        rows.append((row["customer_id"], row["name"], row["plan"], open_tickets))
    return rows


def load(db_path: Path = DB_PATH, seed_dir: Path = SEED_DIR) -> dict[str, int]:
    """Replace the tickets and customers tables in db_path with the seed data.

    Both CSVs are read and checked before the database is touched, and the
    replace runs in one transaction, so a bad seed leaves the old data intact.
    """
    customers = read_customers(seed_dir / "customers.csv")
    tickets = [tuple(row[c] for c in TICKET_COLUMNS) for row in read_csv(seed_dir / "tickets.csv", TICKET_COLUMNS)]

    # autocommit=False keeps the DROP and CREATE statements inside the
    # transaction too; `with conn` commits on success and rolls back on error.
    conn = sqlite3.connect(db_path, autocommit=False)
    try:
        with conn:
            for statement in SCHEMA:
                conn.execute(statement)
            conn.executemany("INSERT INTO customers VALUES (?, ?, ?, ?)", customers)
            conn.executemany("INSERT INTO tickets VALUES (?, ?, ?, ?)", tickets)
    finally:
        conn.close()
    return {"tickets": len(tickets), "customers": len(customers)}


if __name__ == "__main__":
    counts = load()
    print(f"Loaded {counts['tickets']} tickets and {counts['customers']} customers into {DB_PATH}")
