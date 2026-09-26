---
id: SPEC-epic-1
companions: [../../../TRIAGE_POLICY.md, ../../../mcp/triage_server.py]
sources: [../../../INTENT.md]
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate. Source documents listed in frontmatter are for traceability — consult them only if you need narrative rationale or prose color this contract intentionally omits.

# Epic 1: triage data and schema

## Why

The workshop's triage agent needs two foundations before it can exist: a fixed shape for what a triage decision is, and the seed data in a database its MCP tools can query. `mcp/triage_server.py` already reads `app.db`, but nothing creates it, and nothing defines a valid decision for Epic 2's agent to return or Epic 3's eval to check. Epic 1 lays both down, offline, so every later epic builds on the same contract.

## Capabilities

- **CAP-1**
  - **intent:** Any part of the project can check whether a triage decision is valid: a JSON object with a category, a priority, a route and a one-sentence rationale, drawn only from the allowed values.
  - **success:** A decision with category in `billing`/`bug`/`access`/`performance`/`how-to`, priority in `P1`–`P4`, route in `billing-team`/`bug-team`/`access-team`/`performance-team`/`how-to-team` and a rationale passes. A bad category, priority or route, a route that doesn't match its category per `TRIAGE_POLICY.md` (e.g. `billing` + `bug-team`), a missing field, or an extra field each fails with an error naming the offending field.

- **CAP-2**
  - **intent:** One command loads the seed data into the local database the MCP server reads.
  - **success:** `uv run python load_seed.py` creates `app.db` with table `tickets` (24 rows: `ticket_id`, `customer_id`, `created_at`, `text`) and table `customers` (20 rows: `customer_id`, `name`, `plan`, `open_tickets` stored as an integer so the Enterprise rule's "3 or more" compares numerically), and `get_ticket("T-1042")` and `get_customer_history("C-77")` from `mcp/triage_server.py` return rows from it.

- **CAP-3**
  - **intent:** Re-running the loader is safe and gives the same database.
  - **success:** Running `uv run python load_seed.py` a second time exits cleanly and leaves both tables with identical row counts and contents — no duplicates.

## Constraints

- Python 3.12 or newer, managed with uv; packages added with `uv add`.
- `seed/` is read-only; the loader only reads it.
- No network calls and no API keys: schema and loader run fully offline.
- `mcp/triage_server.py`'s table and column names (`tickets`: `ticket_id`, `customer_id`, `created_at`, `text`; `customers`: `customer_id`, `name`, `plan`, `open_tickets`) must keep working unchanged.
- Allowed categories and routes are exactly those in `TRIAGE_POLICY.md`'s table — none invented, none dropped.
- The schema is the single source of truth, importable from Python: Epic 2's agent returns it as structured output and Epic 3's `valid_schema` scorer validates against it.
- `app.db` is git-ignored and never committed.

## Non-goals

- The agent and its MCP tools (Epic 2).
- Evals (Epic 3).
- Any user interface.

## Success signal

On a fresh clone, `uv run python load_seed.py` run twice leaves one `app.db` that `mcp/triage_server.py` answers `get_ticket("T-1042")` from, and the schema accepts `billing` / `P2` / `billing-team` with a rationale while rejecting `urgent` / `P0` / `sales-team` with field-named errors — no network, no keys.

## Assumptions

- "Same database" on reload means same tables, columns and rows (replace, not append); a byte-identical file is not required.
- Extra fields in a decision count as "anything else" and are rejected.
- Where the schema lives (module name) is the build story's call; Epic 2 imports it from there.

## Open Questions

- How strictly is "one-sentence rationale" enforced: non-empty only, or also a single-sentence check?
