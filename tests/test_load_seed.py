import importlib.util
from contextlib import closing
import shutil
import sqlite3
from pathlib import Path

import pytest

import load_seed
from load_seed import SEED_DIR, load

ROOT = Path(__file__).resolve().parent.parent


def dump(db_path: Path) -> dict[str, list[tuple]]:
    with closing(sqlite3.connect(db_path)) as conn:
        return {
            "tickets": conn.execute("SELECT * FROM tickets ORDER BY ticket_id").fetchall(),
            "customers": conn.execute("SELECT * FROM customers ORDER BY customer_id").fetchall(),
        }


def columns(db_path: Path, table: str) -> list[tuple[str, str]]:
    with closing(sqlite3.connect(db_path)) as conn:
        return [(row[1], row[2]) for row in conn.execute(f"PRAGMA table_info({table})")]


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "app.db"
    load(path)
    return path


def test_loads_row_counts(tmp_path):
    counts = load(tmp_path / "app.db")
    assert counts == {"tickets": 24, "customers": 20}
    data = dump(tmp_path / "app.db")
    assert len(data["tickets"]) == 24
    assert len(data["customers"]) == 20


def test_columns_match_mcp_server(db):
    assert columns(db, "tickets") == [
        ("ticket_id", "TEXT"),
        ("customer_id", "TEXT"),
        ("created_at", "TEXT"),
        ("text", "TEXT"),
    ]
    assert columns(db, "customers") == [
        ("customer_id", "TEXT"),
        ("name", "TEXT"),
        ("plan", "TEXT"),
        ("open_tickets", "INTEGER"),
    ]


def test_open_tickets_is_integer_and_compares_numerically(db):
    with closing(sqlite3.connect(db)) as conn:
        types = {row[0] for row in conn.execute("SELECT typeof(open_tickets) FROM customers")}
        busy = conn.execute("SELECT COUNT(*) FROM customers WHERE open_tickets >= 3").fetchone()[0]
    assert types == {"integer"}
    assert busy == 4


def test_ticket_text_with_commas_kept_whole(db):
    with closing(sqlite3.connect(db)) as conn:
        text = conn.execute("SELECT text FROM tickets WHERE ticket_id = 'T-1047'").fetchone()[0]
    assert text == "Refund the duplicate charge, please."


def test_rerun_gives_identical_tables(db):
    before = dump(db)
    assert load(db) == {"tickets": 24, "customers": 20}
    assert dump(db) == before


def test_seed_files_untouched(tmp_path):
    before = {p.name: p.read_bytes() for p in SEED_DIR.iterdir()}
    load(tmp_path / "app.db")
    assert {p.name: p.read_bytes() for p in SEED_DIR.iterdir()} == before


def bad_seed(tmp_path, customers_csv: str | None = None, tickets_csv: str | None = None) -> Path:
    seed = tmp_path / "seed"
    shutil.copytree(SEED_DIR, seed)
    if customers_csv is not None:
        (seed / "customers.csv").write_text(customers_csv, encoding="utf-8")
    if tickets_csv is not None:
        (seed / "tickets.csv").write_text(tickets_csv, encoding="utf-8")
    return seed


CUSTOMERS_HEADER = "customer_id,name,plan,open_tickets\n"
TICKETS_HEADER = "ticket_id,customer_id,created_at,text\n"


@pytest.mark.parametrize(
    ("seed_files", "message"),
    [
        ({"customers_csv": CUSTOMERS_HEADER + "C-77,Initech,Enterprise,three\n"}, "open_tickets must be an integer"),
        ({"customers_csv": "customer_id,name,plan\nC-77,Initech,Enterprise\n"}, "expected columns"),
        ({"customers_csv": CUSTOMERS_HEADER + "C-77,Initech,Enterprise\n"}, "customers.csv line 2: expected 4 fields"),
        ({"customers_csv": CUSTOMERS_HEADER + "C-77,Initech,Enterprise,2,extra\n"}, "customers.csv line 2: expected 4 fields"),
        ({"tickets_csv": TICKETS_HEADER + "T-1,C-77,2026-09-01T09:14:00\n"}, "tickets.csv line 2: expected 4 fields"),
        ({"tickets_csv": TICKETS_HEADER + "T-1,C-77,2026-09-01T09:14:00,Refund me, please\n"}, "tickets.csv line 2: expected 4 fields"),
    ],
)
def test_bad_seed_fails_before_write_and_keeps_old_data(db, tmp_path, seed_files, message):
    before = dump(db)
    with pytest.raises(ValueError, match=message):
        load(db, bad_seed(tmp_path, **seed_files))
    assert dump(db) == before


def test_duplicate_id_fails_mid_write_and_rolls_back(db, tmp_path):
    before = dump(db)
    duplicate = "customer_id,name,plan,open_tickets\nC-77,Northwind,Enterprise,2\nC-77,Northwind,Enterprise,2\n"
    with pytest.raises(sqlite3.IntegrityError):
        load(db, bad_seed(tmp_path, customers_csv=duplicate))
    assert dump(db) == before


def import_triage_server():
    spec = importlib.util.spec_from_file_location("triage_server", ROOT / "mcp" / "triage_server.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_default_db_path_is_the_one_mcp_server_reads():
    assert load.__defaults__[0] == load_seed.DB_PATH == import_triage_server().DB_PATH


@pytest.fixture
def triage_server(db, monkeypatch):
    module = import_triage_server()
    monkeypatch.setattr(module, "DB_PATH", db)
    return module


def test_mcp_get_ticket(triage_server):
    assert triage_server.get_ticket("T-1042") == {
        "ticket_id": "T-1042",
        "customer_id": "C-77",
        "created_at": "2026-09-01T09:14:00",
        "text": "I was charged twice this month and nobody answers.",
    }


def test_mcp_get_customer_history(triage_server):
    customer = triage_server.get_customer_history("C-77")
    assert (customer["name"], customer["plan"], customer["open_tickets"]) == ("Northwind", "Enterprise", 2)
    assert "T-1042" in customer["ticket_ids"]
