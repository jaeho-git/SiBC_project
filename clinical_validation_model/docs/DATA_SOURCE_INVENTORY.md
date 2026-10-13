# Data source inventory

| Source | Mode | Safe use | Limitation |
|---|---|---|---|
| Medical latest actual artifact | artifact/read-only | checksum, schema, row count, pseudonymized measured evidence adapter research | date-only exam time; units/source record metadata incomplete |
| Medical temporal cohort artifact | artifact/read-only | temporal availability research | not a clinical reference standard |
| Medical wearable summary artifact | artifact/read-only | measured summary adapter research | non-wear/device/sync/app/algorithm/timezone/manual/duplicate metadata unavailable |
| Synthetic Clinical Layer fixtures | fixture | branch, gate, conflict, leakage, CDEI and contract testing | not clinical truth or real-world performance |
| Survey | unavailable | interface only | `BLOCKED_BY_SURVEY_SOURCE` |
| DB | scaffold | explicitly selected, read-only repeatable-read managed query only | snapshot extraction not approved; no connection attempted by baseline |

Medical `pred_*` and `risk_*` fields are never eligible clinical evidence.

