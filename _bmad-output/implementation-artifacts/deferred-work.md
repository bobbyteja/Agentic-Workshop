# Deferred work

## Deferred from: code review of 1-triage-decision-schema.md (2026-09-26)

- Structured-output compatibility of `TriageDecision` is unverified. `extra="forbid"` puts `additionalProperties: false` in the JSON schema, and nothing yet shows that `ChatGoogleGenerativeAI(...).with_structured_output(TriageDecision)` or `ChatGroq` accepts it. Status: maybe-false, would be medium if true. Settle it in Epic 2 CAP-4 by running structured output against both providers.
