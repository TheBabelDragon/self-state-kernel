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
| `self_state_kernel.py` | Corrected Python reference |
| `crates/self-state-core` | `no_std` state store + value model |
| `crates/self-state-host` | Host tests + shared vector runner |
| `vectors/` | Cross-implementation test vectors |
| `docs/` | Architecture and contracts |

## Status

v0.1 corrections: presence vs null, atomic nested paths, injectable clock, explicit results, registry safety, integrity scopes, CMD4 FAIL_SAFE semantics, Rust foundation + parity vectors.
