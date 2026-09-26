import json
from typing import get_args

import pytest
from pydantic import ValidationError

from triage_schema import (
    ROUTE_FOR_CATEGORY,
    Category,
    Route,
    TriageDecision,
    validate_decision,
)

VALID = {
    "category": "billing",
    "priority": "P2",
    "route": "billing-team",
    "rationale": "Double charge puts money at stake, so P2.",
}


def with_(**changes):
    return {**VALID, **changes}


def error_locs(exc: ValidationError) -> set[str]:
    return {str(part) for err in exc.errors() for part in err["loc"]}


def test_valid_decision():
    decision = validate_decision(VALID)
    assert decision.category == "billing"
    assert decision.priority == "P2"
    assert decision.route == "billing-team"
    assert decision.rationale == VALID["rationale"]


def test_valid_json_string():
    assert validate_decision(json.dumps(VALID)) == validate_decision(VALID)


def test_bad_category():
    with pytest.raises(ValidationError) as exc:
        validate_decision(with_(category="urgent"))
    assert error_locs(exc.value) == {"category"}


def test_bad_category_case_matters():
    with pytest.raises(ValidationError) as exc:
        validate_decision(with_(category="Billing"))
    assert error_locs(exc.value) == {"category"}


@pytest.mark.parametrize("priority", ["P0", "p2", 2])
def test_bad_priority(priority):
    with pytest.raises(ValidationError) as exc:
        validate_decision(with_(priority=priority))
    assert error_locs(exc.value) == {"priority"}


def test_bad_route():
    with pytest.raises(ValidationError) as exc:
        validate_decision(with_(route="sales-team"))
    assert error_locs(exc.value) == {"route"}


def test_route_category_mismatch():
    with pytest.raises(ValidationError) as exc:
        validate_decision(with_(route="bug-team"))
    assert error_locs(exc.value) == {"route"}
    assert "expected 'billing-team'" in exc.value.errors()[0]["msg"]


PAIRS = [
    ("billing", "billing-team"),
    ("bug", "bug-team"),
    ("access", "access-team"),
    ("performance", "performance-team"),
    ("how-to", "how-to-team"),
]


@pytest.mark.parametrize("category,route", PAIRS)
@pytest.mark.parametrize("priority", ["P1", "P2", "P3", "P4"])
def test_valid_decision_all_pairs_and_priorities(category, route, priority):
    decision = validate_decision(with_(category=category, route=route, priority=priority))
    assert (decision.category, decision.route, decision.priority) == (category, route, priority)


@pytest.mark.parametrize(
    "data,field",
    [
        (with_(priority=2), "priority"),
        (with_(route="bug-team"), "route"),
        (with_(escalated=True), "escalated"),
    ],
)
def test_rejections_via_json_string(data, field):
    with pytest.raises(ValidationError) as exc:
        validate_decision(json.dumps(data))
    assert error_locs(exc.value) == {field}


def test_no_type_coercion_bytes_rationale():
    with pytest.raises(ValidationError) as exc:
        validate_decision(with_(rationale=b"Money at stake."))
    assert error_locs(exc.value) == {"rationale"}


@pytest.mark.parametrize(
    "changes,field",
    [({"category": None}, "category"), ({"rationale": 123}, "rationale")],
)
def test_null_and_wrong_type(changes, field):
    with pytest.raises(ValidationError) as exc:
        validate_decision(with_(**changes))
    assert error_locs(exc.value) == {field}


def test_missing_field():
    data = dict(VALID)
    del data["rationale"]
    with pytest.raises(ValidationError) as exc:
        validate_decision(data)
    assert error_locs(exc.value) == {"rationale"}


def test_extra_field():
    with pytest.raises(ValidationError) as exc:
        validate_decision(with_(escalated=True))
    assert error_locs(exc.value) == {"escalated"}


def test_empty_rationale():
    with pytest.raises(ValidationError) as exc:
        validate_decision(with_(rationale="   "))
    assert error_locs(exc.value) == {"rationale"}


def test_rationale_with_abbreviations_passes():
    validate_decision(with_(rationale="Refund vs. credit, e.g. a double charge, so P2."))


@pytest.mark.parametrize("payload", ["[]", '"text"', "{not json", ""])
def test_not_an_object(payload):
    with pytest.raises(ValidationError):
        validate_decision(payload)


def test_route_for_category_covers_all_categories():
    assert set(ROUTE_FOR_CATEGORY) == set(get_args(Category))
    assert set(ROUTE_FOR_CATEGORY.values()) == set(get_args(Route))
    assert len(ROUTE_FOR_CATEGORY) == 5


def test_model_dump_is_json_serialisable_with_four_fields():
    dumped = validate_decision(VALID).model_dump()
    assert type(dumped) is dict
    assert json.loads(json.dumps(dumped)) == VALID


def test_json_schema_lists_required_fields_with_enums():
    schema = TriageDecision.model_json_schema()
    assert set(schema["required"]) == {"category", "priority", "route", "rationale"}
    props = schema["properties"]
    assert set(props["category"]["enum"]) == set(get_args(Category))
    assert set(props["priority"]["enum"]) == {"P1", "P2", "P3", "P4"}
    assert set(props["route"]["enum"]) == set(get_args(Route))
    assert props["rationale"]["type"] == "string"
