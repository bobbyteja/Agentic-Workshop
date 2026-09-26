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
- Both CSVs are read and checked (exact header, exactly four fields per row, integer `open_tickets`) before the database is opened. The drop/create/insert runs in one transaction via `sqlite3.connect(..., autocommit=False)` + `with conn` (Python 3.12+), which keeps DDL inside the transaction too. A bad seed raises `ValueError` before any write; a failure mid-write (e.g. duplicate ID) rolls back. Either way the old data is kept.
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

## Review Findings

Code review 2026-09-26 (blind-hunter, edge-case-hunter, verification-gap, acceptance-auditor), diff `main...story/ravivutukuri-1.2` (`3a0ce59`).

- [x] [Review][Decision] Malformed CSV rows are not rejected before the write — a short row gives `None` fields (TypeError for customers, NOT NULL `IntegrityError` mid-write for tickets); extra fields land under key `None` and are dropped silently. Implementation Notes claim "a bad seed raises `ValueError` before any write", which only holds for the header and `open_tickets`. Options: add a per-row field-count check in `read_csv` (makes the claim true), or narrow the note (seed is read-only and clean today). **Resolved (Ravi): add the per-row check**; `read_csv` now raises `ValueError` naming the file and line, before any write.
- [x] [Review][Patch] Test that `load_seed.DB_PATH` (the `load()` default) equals the MCP server's un-patched `DB_PATH` [tests/test_load_seed.py:113]
- [x] [Review][Patch] Close SQLite connections in the test helpers (`with conn` commits but doesn't close; Python 3.13 warns) [tests/test_load_seed.py:13]
- [x] [Review][Patch] CLI message prints only `app.db`; print the resolved path, since it writes the repo root whatever the CWD [load_seed.py:81]

Rejected:
- `int()` accepts `" 3 "`, `"+3"`, `"1_0"`, `"-1"` (edge, blind): low. Every seed value is a plain digit, 0–4, and the seed is read-only.
- Missing parent directory for `db_path` raises `OperationalError` (edge): false. It fails loudly, and the default parent is the repo root, which always exists.
- `test_seed_files_untouched` breaks if `seed/` gains a subdirectory (edge): false. `seed/` is read-only and holds two files.
- `status: 'done'` set while review is running (auditor): rejected because the fix would edit the spec. This review sets the final status.
- No subprocess test of the CLI (auditor): low. The default-path patch covers the risky part, and running it twice was checked by hand.
- Loader doesn't enforce 24/20 rows (auditor): false. The tests assert the counts against the fixed seed.
- "Compares numerically" test can't fail as text (blind): false. Text `>= 3` does give the same 4 rows, but `typeof == 'integer'` fails if the column is TEXT, so a regression is caught.
- Duplicate ticket ID / bad `tickets.csv` untested (blind): false for the transaction claim. The duplicate-customer test already fails after both DROPs and CREATEs; with `autocommit=True` it fails.
- `ticket_ids` only checks membership (blind): false. Row counts plus primary keys plus the full-dump rerun test catch dropped or duplicated tickets.
- `review_loop_iteration: 0` vs Pass 1 log (blind): rejected because the fix would edit the spec.
