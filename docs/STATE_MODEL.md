# State Model

## Presence / traversal outcomes

| Outcome | Meaning |
|---------|---------|
| `absent` | A path component does not exist |
| `null` | Leaf path exists and holds null |
| `value` | Leaf path exists with a concrete value |
| `type_conflict` | Intermediate is a non-container (e.g. integer); cannot descend |
| `null_traversal` | Intermediate is explicit null; cannot descend |

`GET(path, default)` returns `default` only when the leaf is **absent**. Explicit null is returned as `None`. Traversal conflicts are not “missing”.

## Mutation atomicity

1. Validate value and path.
2. Apply on a deep copy of the store.
3. On success: swap root and increment version by 1.
4. On failure: leave root and version **unchanged**. No partial containers.

Failed writes caused by scalar or null intermediates do not create nested maps.

## Version

Version increments **only** after a successful mutation. Failed validation or traversal leaves version identical.
