---
title: 'Triage decision schema'
type: 'feature'
created: '2026-09-26'
status: 'done'
baseline_commit: 'b3b8661a9eb32d9ea4ac37e91f8f18c6083472f6'
route: 'dispatch'
review_loop_iteration: 0
context: ['{project-root}/_bmad-output/specs/spec-epic-1/SPEC.md', '{project-root}/TRIAGE_POLICY.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Nothing defines what a valid triage decision is, so Epic 2's agent has no structured-output target and Epic 3's `valid_schema` scorer has nothing to validate against (SPEC CAP-1).

**Approach:** Add one importable Pydantic model, the single source of truth for a decision: `category`, `priority`, `route`, `rationale`, each restricted to `TRIAGE_POLICY.md`'s allowed values, route tied to category, and anything else rejected with an error naming the field.

## Boundaries & Constraints

**Always:** Categories and routes are exactly those in `TRIAGE_POLICY.md` — five of each, mapped one-to-one (`billing`→`billing-team`, `bug`→`bug-team`, `access`→`access-team`, `performance`→`performance-team`, `how-to`→`how-to-team`). Priority is one of `P1`, `P2`, `P3`, `P4`. All four fields are required strings; extra fields are rejected. Validation accepts both a Python dict and a JSON string. Errors name the offending field. Runs offline with no API keys. Decision (human, 2026-09-26): "one-sentence rationale" is enforced as non-empty only — any non-blank string passes; no sentence-count check, so rationales containing "e.g." or "vs." are never rejected.

**Never:** No agent, MCP, loader or eval code. No edits to `seed/`, `TRIAGE_POLICY.md`, `mcp/triage_server.py` or `run_agent.py`. No new dependencies (Pydantic is already a direct dependency). No type coercion (e.g. `2` is not `P2`; case matters — `Billing` is rejected).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Valid decision | `{"category":"billing","priority":"P2","route":"billing-team","rationale":"Double charge puts money at stake, so P2."}` | Validates; fields readable as attributes | N/A |
| Valid JSON string | Same decision as a JSON string | Validates identically | N/A |
| Bad category | `category: "urgent"` | Rejected | Error names `category` |
| Bad priority | `priority: "P0"` or `"p2"` | Rejected | Error names `priority` |
| Bad route | `route: "sales-team"` | Rejected | Error names `route` |
| Route/category mismatch | `billing` + `bug-team` | Rejected | Error names `route` and the expected `billing-team` |
| Missing field | no `rationale` | Rejected | Error names `rationale` |
| Extra field | adds `"escalated": true` | Rejected | Error names `escalated` |
| Empty rationale | `rationale: "   "` | Rejected | Error names `rationale` |
| Not an object | JSON `[]`, `"text"`, or malformed JSON | Rejected | Clear validation error, no crash |

</frozen-after-approval>

## Code Map

- `TRIAGE_POLICY.md` -- source of the five category/route pairs and P1–P4; read-only.
- `_bmad-output/specs/spec-epic-1/SPEC.md` -- CAP-1 contract; constraint that the schema is importable as the single source of truth.
- `_bmad-output/specs/spec-epic-2/SPEC.md` (CAP-4) -- consumer: agent returns this model as structured output and retries once on validation failure.
- `_bmad-output/specs/spec-epic-3/SPEC.md` (CAP-1) -- consumer: `valid_schema` scores 1/0 by validating output against this model.
- `run_agent.py` -- prints the decision with `json.dumps`, so the agent must hand back a plain dict (`model_dump()`); do not edit.
- `pyproject.toml` -- `pydantic>=2.8` already present; pytest's `testpaths = ["tests"]`, and `tests/` does not exist yet.

## Tasks & Acceptance

**Execution:**
- [x] `triage_schema.py` -- create at repo root: `Category`, `Priority`, `Route` literal types; a `ROUTE_FOR_CATEGORY` mapping; `TriageDecision` Pydantic model (strict, extra fields forbidden, route-matches-category validator, rationale validator); `validate_decision(data: dict | str) -> TriageDecision` wrapper -- one importable source of truth for Epics 2 and 3, root-level like `run_agent.py`'s `agent` import.
- [x] `tests/test_triage_schema.py` -- create: one test per I/O matrix row, plus a check that `ROUTE_FOR_CATEGORY` covers all five categories -- proves CAP-1 offline.

**Acceptance Criteria:**
- Given a fresh checkout with no `.env`, when `uv run pytest` runs, then all schema tests pass with no network access.
- Given any valid decision, when it is validated and then `model_dump()`-ed, then the result is a plain dict that `json.dumps` serialises with exactly the four fields.
- Given `TriageDecision.model_json_schema()`, when inspected, then it lists the four required fields with their allowed values as enums.

### Review Findings

Code review 2026-09-26 (blind-hunter, edge-case-hunter, verification-gap, acceptance-auditor), diff `b3b8661..7accafd`.

- [x] [Review][Patch] Build the `route` field description from `ROUTE_FOR_CATEGORY` instead of a hand-written copy of the pairing, and test that it names every pair [triage_schema.py:33]
- [x] [Review][Patch] Pin the "clear validation error" for non-object input by asserting the error type (`json_invalid` / `model_type`), not only `ValidationError` [tests/test_triage_schema.py:146]
- [x] [Review][Defer] The schema is not yet shown to work as structured output with `ChatGoogleGenerativeAI` / `ChatGroq` (`additionalProperties: false` from `extra="forbid"`) [triage_schema.py:29] — deferred: maybe-false, would be medium if true. Settle it in Epic 2 CAP-4 by calling `with_structured_output(TriageDecision)` on both providers.

Rejected:
- Zero-width-only rationale passes (edge): low. A model is unlikely to produce it, and the fix needs a custom character list.
- Duplicate JSON keys, last one wins (edge): low. LLM structured output doesn't produce this, and the fix needs a custom JSON hook.
- `model_construct` instance returned without re-validation (edge): low. Outside the `dict | str` contract; same as #9 in Pass 1.
- `pyproject.toml` edited outside the Code Map (auditor): false. The Code Map lists it and Implementation Notes record why `pythonpath` is needed.
- Rationale doesn't have to name the rule (auditor): rejected because the fix would edit the spec. The frozen human decision is non-empty only. SPEC.md's open question should be closed through `/bmad-spec`.
- `review_loop_iteration: 0` contradicts the Pass 1 log (auditor, blind): rejected because the fix would edit the spec under review.
- Route check depends on field order (blind): false. Reordering fails `test_route_category_mismatch`, and Implementation Notes document the choice.
- Allowed values not tested against `TRIAGE_POLICY.md` (blind): low. The policy is read-only and the auditor confirmed the values match. Parsing markdown in a test adds complexity.
- `validate_decision` rejects `bytes` (blind): false. It fails loudly with a `ValidationError` and bytes are outside the `dict | str` contract.
- Empty `""` rationale not in the test (blind): false. It takes the same `.strip()` branch that the `"   "` test pins.
- Docstring says "one-sentence rationale" (blind): false. It describes the intended content, which matches the policy. It doesn't claim the validator enforces it.
- `ROUTE_FOR_CATEGORY` is a mutable dict (blind): low. No caller mutates it; decided in Pass 1 #7.

## Implementation Notes

- Added `pythonpath = ["."]` to `[tool.pytest.ini_options]` in `pyproject.toml`: pytest's default import mode puts `tests/` rather than the repo root on `sys.path`, so without it `from triage_schema import ...` fails to import. Config only, no new dependency.
- The route/category mismatch is a `field_validator` on `route` (not a model validator), so the error's `loc` is `route`. It is skipped when `category` has already failed, so a bad category reports only `category`.

## Spec Change Log

## Review Triage Log

Pass 1 (blind-hunter, edge-case-hunter, verification-gap):

| # | Layer | Finding | Verdict | Evidence | Route |
|---|---|---|---|---|---|
| 1 | verification-gap | `strict=True` unprotected by any test | low | Pre-verified: removing `strict=True` leaves all 20 tests green; `b"..."` rationale is coerced in lax mode | patch |
| 2 | blind | Only billing/P2 tested as valid; values only checked against own Literals | low | Probe: all 5 pairs × P1/P3/P4 validate today, but a typo in both mapping and Literal would pass every test | patch |
| 3 | blind | Rejections tested only via dict, not JSON-string path | low | Probe: priority 2, mismatch, extra field all reject with the same loc via JSON; path untested | patch |
| 4 | blind | Null / wrong-type values untested | low | Probe: `category=None`, `rationale=123` reject correctly; no test pins it | patch |
| 5 | blind | `test_bad_category_case_matters` uses `in`, siblings use `==` | low | Would miss a spurious extra route error | patch |
| 6 | blind | Mismatch test's `"billing-team" in str(exc)` also matches echoed input | low | Pydantic's message echoes `input_value`, so the check can pass without the expected-route hint | patch |
| 7 | blind | `ROUTE_FOR_CATEGORY` typed `dict[str, str]`, mutable, duplicates `Route` | low | Annotation defeats type checking of the pairing; runtime mutation and duplication have no named caller that would do it | patch (annotation only) |
| 8 | blind | JSON schema doesn't express route↔category pairing | low | LLM targeting the schema sees route as free choice; mismatch costs Epic 2's one retry. `TRIAGE_POLICY.md` also gives the pairing, so impact is small | patch |
| 9 | edge | `validate_decision` returns an existing `TriageDecision` instance unrevalidated | low | Probe: a `model_construct` instance passes through. Outside the `dict \| str` contract, no caller builds one; fix adds a guard | rejected |
| 10 | blind | Docstring/type hint silent on `bytes` and instances | low | `bytes` already rejected; instance case as #9 | rejected |
| 11 | edge | Rationale not checked for one sentence / naming a rule | false | Frozen human decision: non-empty only | rejected |
| 12 | edge | Rationale not stripped, breaking exact-match downstream | false | No consumer exact-matches rationale: Epic 3 compares category/priority and judges rationale by LLM | rejected |

## Design Notes

Pydantic's `ValidationError` already reports the field path (`loc`), so errors name the field without a custom exception type; `validate_decision` only picks dict vs. JSON-string parsing. The route/category check runs after field validation, so a bad category reports `category`, not a mismatch. Use `ConfigDict(extra="forbid", strict=True)`.

## Verification

**Commands:**
- `uv run pytest tests/test_triage_schema.py -v` -- expected: all tests pass.
- `uv run python -c "from triage_schema import validate_decision; print(validate_decision({'category':'billing','priority':'P2','route':'billing-team','rationale':'Money at stake.'}).model_dump())"` -- expected: prints the dict.
