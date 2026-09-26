---
title: 'Seed loader'
type: 'feature'
created: '2026-09-26'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context: ['{project-root}/_bmad-output/specs/spec-epic-1/SPEC.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `mcp/triage_server.py` reads `app.db`, but nothing creates it, so the agent's MCP tools have no data (SPEC CAP-2, CAP-3).

**Approach:** Add `load_seed.py` at the repo root. It reads `seed/tickets.csv` (24 rows) and `seed/customers.csv` (20 rows) and replaces the `tickets` and `customers` tables in the repo-root `app.db`, using the exact column names the MCP server queries. `open_tickets` is stored as an INTEGER, so the Enterprise rule's "3 or more" compares numerically. Re-running it gives identical tables with no duplicates. It runs offline, only reads `seed/`, and adds no dependencies. Offline tests load into a temporary database and check the row counts, the integer type, idempotency, and that `get_ticket("T-1042")` and `get_customer_history("C-77")` answer from the loaded data.

</frozen-after-approval>

## Implementation Notes

- Added `load_seed.py` (repo root) and `tests/test_load_seed.py`. No new dependencies; `pyproject.toml` untouched.
- `load(db_path, seed_dir)` defaults to the repo-root `app.db` and `seed/` via `__file__`, not the CWD, matching `mcp/triage_server.py`'s `DB_PATH`. Tests pass a temp path, so they never touch the real `app.db`.
- Both CSVs are read and checked (exact header, integer `open_tickets`) before the database is opened. The drop/create/insert runs in one transaction via `sqlite3.connect(..., autocommit=False)` + `with conn` (Python 3.12+), which keeps DDL inside the transaction too. A bad seed raises `ValueError` before any write; a failure mid-write (e.g. duplicate ID) rolls back. Either way the old data is kept.
- `ticket_id` and `customer_id` are primary keys, so a duplicate ID in the seed fails the load loudly instead of creating duplicate rows.
- Tests load `mcp/triage_server.py` by file path with `importlib`, because the local `mcp/` folder shares its name with the installed `mcp` package. They also monkeypatch its `DB_PATH` to the temp database.
- Surprise: only one seed ticket (`T-1047`) contains a comma; it's used to check that quoted CSV fields load whole.


## Review Triage Log

Pass 1 (blind-hunter):

- Extra/short CSV rows silently truncated or raise a raw `IntegrityError`: low, rejected. The seed is read-only and verified clean (24/20 rows, 4 fields each). A per-row guard adds a branch for a state the fixed seed can't reach.
- `plan` and other fields not validated (casing, negatives, empty, ISO dates): low, rejected. Every seed value is valid (plans are only Enterprise/Team/Starter) and the seed is read-only. Validating them would add policy logic to the loader.
- No foreign key from `tickets.customer_id` to `customers`: low, rejected. Every ticket's customer exists in the read-only seed.
- `ROLLBACK` when no transaction is active masks the real error: low, patched. Replaced manual `BEGIN`/`COMMIT`/`ROLLBACK` with `autocommit=False` + `with conn`.
- CLI path untested: low, rejected. Checked by hand: `uv run python load_seed.py` run twice prints 24/20, and run from `/tmp` it writes the repo-root `app.db`. A subprocess test would write the real `app.db`.
- Mid-write rollback and duplicate IDs untested; `tickets` column types unchecked: low, patched. Added `test_duplicate_id_fails_mid_write_and_rolls_back` (it fails with `autocommit=True`) and exact `tickets` column types.
- A UTF-8 BOM gives a confusing header error: false. The seed files have no BOM (first bytes `cus`) and are read-only.
- `SCHEMA.split(";")` is fragile: low, patched. `SCHEMA` is now a tuple of separate statements.
