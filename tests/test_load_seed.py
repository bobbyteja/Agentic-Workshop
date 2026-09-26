import importlib.util
import shutil
import sqlite3
from pathlib import Path

import pytest

from load_seed import SEED_DIR, load

ROOT = Path(__file__).resolve().parent.parent


def dump(db_path: Path) -> dict[str, list[tuple]]:
    with sqlite3.connect(db_path) as conn:
        return {
            "tickets": conn.execute("SELECT * FROM tickets ORDER BY ticket_id").fetchall(),
            "customers": conn.execute("SELECT * FROM customers ORDER BY customer_id").fetchall(),
        }


def columns(db_path: Path, table: str) -> list[tuple[str, str]]:
    with sqlite3.connect(db_path) as conn:
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
    with sqlite3.connect(db) as conn:
        types = {row[0] for row in conn.execute("SELECT typeof(open_tickets) FROM customers")}
        busy = conn.execute("SELECT COUNT(*) FROM customers WHERE open_tickets >= 3").fetchone()[0]
    assert types == {"integer"}
    assert busy == 4


def test_ticket_text_with_commas_kept_whole(db):
    with sqlite3.connect(db) as conn:
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


def bad_seed(tmp_path, customers_csv: str) -> Path:
    seed = tmp_path / "seed"
    seed.mkdir()
    shutil.copy(SEED_DIR / "tickets.csv", seed / "tickets.csv")
    (seed / "customers.csv").write_text(customers_csv, encoding="utf-8")
    return seed


@pytest.mark.parametrize(
    ("customers_csv", "message"),
    [
        ("customer_id,name,plan,open_tickets\nC-77,Initech,Enterprise,three\n", "open_tickets must be an integer"),
        ("customer_id,name,plan\nC-77,Initech,Enterprise\n", "expected columns"),
    ],
)
def test_bad_seed_fails_and_keeps_old_data(db, tmp_path, customers_csv, message):
    before = dump(db)
    with pytest.raises(ValueError, match=message):
        load(db, bad_seed(tmp_path, customers_csv))
    assert dump(db) == before


def test_duplicate_id_fails_mid_write_and_rolls_back(db, tmp_path):
    before = dump(db)
    duplicate = "customer_id,name,plan,open_tickets\nC-77,Northwind,Enterprise,2\nC-77,Northwind,Enterprise,2\n"
    with pytest.raises(sqlite3.IntegrityError):
        load(db, bad_seed(tmp_path, duplicate))
    assert dump(db) == before


@pytest.fixture
def triage_server(db, monkeypatch):
    spec = importlib.util.spec_from_file_location("triage_server", ROOT / "mcp" / "triage_server.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
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
