# Reasoning options validation — 1.0.4

The chart publishes `reasoning_effort` options `none` and `high`, with default
`none`. It retains the existing engine arguments and all resource settings.

## Local checks

- Olares CLI `chart lint`: passed, including both owner installation scenarios.
- Manifest and Chart versions match; both reasoning environment declarations
  are non-editable and do not apply changes independently.
- Helm render with new-install defaults: passed.
- Helm render with the new environment values absent from installation values:
  passed; template defaults still supply `none,high` and `none`.
- Semantic comparison against the parent commit: all other manifest environment
  declarations and rendered workload fields are unchanged.
- Existing Model Console source tests for reasoning-rule seeding, validation and
  reconciliation of persisted cards: passed (`go test ./internal/config -run
  'ReasoningEffort|OverlayReasoning' -count=1`). This is a source-level check,
  not a runtime check of the pinned container image.

## Runtime checks pending deployment

This change was not uploaded, installed or deployed. The following checks are
not executed against this chart revision:

- Router catalog publication after a new install and after upgrading an existing
  model card. Verify options `none`/`high` and default `none`.
- Real requests with omitted effort, `none` and `high`. Check engine-default
  behavior, successful complete replies, and no reasoning output for `none`.

| Interface | Build / viewport | Status | Remaining check |
| --- | --- | --- | --- |
| Official dsh PC | Not measured | Blocked: chart not deployed | Options, selection persistence, request effort |
| Vue mobile: chat and settings | Not measured | Blocked: chart not deployed | Options, selection persistence, request effort |
| Vue desktop: chat and settings | Not measured | Blocked: chart not deployed | Options, selection persistence, request effort |

UI checks must use the real Host and Router, select `none`, save and reload, then
confirm the actual request carries `reasoning_effort: "none"`. Do not substitute
a mocked catalog or a successful source test for runtime acceptance.
