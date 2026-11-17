# State Model

## Presence / traversal outcomes

| Outcome | Meaning |
|---------|---------|
| `absent` | A path component does not exist |
| `null` | Leaf path exists and holds null |
| `value` | Leaf path exists with a concrete value |
| `type_conflict` | Intermediate is a non-container (e.g. integer); cannot descend |
| `null_traversal` | Intermediate is explicit null; cannot descend |

`GET(path, default)` returns `default` only when the leaf is **absent**.

## Mutation atomicity

Validate → apply on copy → swap on success → increment version. Failures leave state and version unchanged.

## Shared fixture contract

`vectors/state_vectors.json` is the **single source of truth**.

- Format: `self-state-kernel-vectors/0.1.2`
- Python: `tests/test_parity_vectors.py` runs the JSON directly
- Rust: `scripts/generate_rust_vectors.py` emits `generated_vectors.rs`
- CI fails if generated output is stale

Each case includes ops, expected presence/error labels, `final_version`, and `final_paths`.
