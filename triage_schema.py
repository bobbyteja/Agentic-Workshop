"""The triage decision schema: the single source of truth for a valid decision.

Allowed values come from TRIAGE_POLICY.md. Epic 2's agent returns a
`TriageDecision` as structured output; Epic 3's `valid_schema` scorer
validates against it with `validate_decision`.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

Category = Literal["billing", "bug", "access", "performance", "how-to"]
Priority = Literal["P1", "P2", "P3", "P4"]
Route = Literal["billing-team", "bug-team", "access-team", "performance-team", "how-to-team"]

ROUTE_FOR_CATEGORY: dict[Category, Route] = {
    "billing": "billing-team",
    "bug": "bug-team",
    "access": "access-team",
    "performance": "performance-team",
    "how-to": "how-to-team",
}


class TriageDecision(BaseModel):
    """One triage decision: category, priority, route and a one-sentence rationale."""

    model_config = ConfigDict(extra="forbid", strict=True)

    category: Category
    priority: Priority
    route: Route = Field(
        description="Must be the team for the category: "
        + ", ".join(f"{c}->{r}" for c, r in ROUTE_FOR_CATEGORY.items())
        + "."
    )
    rationale: str

    @field_validator("route")
    @classmethod
    def route_matches_category(cls, route: str, info: ValidationInfo) -> str:
        # If category itself failed validation it is absent here, so only
        # the category error is reported, not a spurious mismatch.
        category = info.data.get("category")
        if category is not None:
            expected = ROUTE_FOR_CATEGORY[category]
            if route != expected:
                raise ValueError(
                    f"route {route!r} does not match category {category!r}; expected {expected!r}"
                )
        return route

    @field_validator("rationale")
    @classmethod
    def rationale_not_blank(cls, rationale: str) -> str:
        if not rationale.strip():
            raise ValueError("rationale must not be empty")
        return rationale


def validate_decision(data: dict | str) -> TriageDecision:
    """Validate a decision given as a dict or a JSON string.

    Raises pydantic.ValidationError, whose errors name the offending field.
    """
    if isinstance(data, str):
        return TriageDecision.model_validate_json(data)
    return TriageDecision.model_validate(data)
