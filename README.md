# SELF-State Kernel

Authoritative **state semantics** for the TheBabelDragon ecosystem.

Not an OS kernel, not BabelForge, not ActionOS.

## Quick start

```bash
python3 self_state_kernel.py
python3 tests/test_kernel_corrections.py
python3 tests/test_parity_vectors.py
cargo test --workspace
```

## Layout

| Path | Role |
|------|------|
| `self_state_kernel.py` | Public entry (re-exports) |
| `_kernel_impl.py` | Full Python reference implementation |
| `crates/self-state-core` | `no_std` state store + value model |
| `crates/self-state-host` | Host tests + shared vector runner |
| `vectors/` | Cross-implementation test vectors |
| `docs/` | Architecture and contracts |

## Status (v0.1.1)

Corrections:

- Presence: `absent` / `null` / `value` / **`type_conflict`** / **`null_traversal`**
- Nested path conflicts and null intermediates rejected atomically
- Injectable logical clock; explicit `KernelResult` (no truthiness)
- Registry safety; integrity scopes; CMD4 FAIL_SAFE semantics
- Rust foundation + shared parity vectors

## License

MIT
