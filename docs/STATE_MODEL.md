# State Model

## Presence

| Presence | Meaning |
|----------|---------|
| absent | Path does not exist |
| null | Path exists and holds null |
| value | Path exists with a concrete value |

`GET(path, default)` returns `default` only when **absent**.

## Mutation

Validate → apply on copy → swap → increment version. Failures leave prior state intact.
