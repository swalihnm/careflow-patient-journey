# Claims pre-check agent -- synthetic eval report

Demonstration only (SPEC 10): detection of *deliberately injected* problems in synthetic claims, not real-world denial prediction -- no public labelled claims-denial dataset exists to calibrate against real outcomes.

## Detection rate per problem type

| Problem type | Detected | Rate |
| --- | --- | --- |
| wrong_code | 10/10 | 100% |
| uncovered_service | 10/10 | 100% |
| missing_preauth | 10/10 | 100% |
| waiting_period_violation | 10/10 | 100% |

## False-flag rate (on 40 clean claims)

0/40 clean claims raised at least one flag (0% false-flag rate).
