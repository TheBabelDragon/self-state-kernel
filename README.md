# SELF-State Kernel

Authoritative **state semantics** for the TheBabelDragon ecosystem.

Not an OS kernel, not BabelForge, not ActionOS.

## Quick start

```bash
python3 self_state_kernel.py
python3 tests/test_kernel_corrections.py
python3 tests/test_parity_vectors.py
python3 tests/test_angelic_cipher.py
cargo test --workspace
```

## Layout

| Path | Role |
|------|------|
| `self_state_kernel.py` | Public entry (re-exports) |
| `_kernel_impl.py` | Full Python reference implementation |
| `angelic_cipher.py` | **v0.2** Angelic Cipher calculation authority (independently usable) |
| `crates/self-state-core` | `no_std` state store + value model |
| `crates/self-state-host` | Host tests + shared vector runner |
| `vectors/` | Cross-implementation **state** test vectors (not cipher vectors) |
| `docs/` | Architecture and contracts |

## Status (v0.2.0)

### Angelic Cipher Authority

- Explicit profile identity: `legacy-experimental` / `1.0.0`
- Mapping id: `legacy-az-hebrewish-v1`
- Versioned JSON-serializable result contract (`result_contract_version` 1.0.0)
- Independent calculator (`AngelicCipher`) — no Kernel required
- Kernel adapter preserves `ANGELIC.ENCODE|DECODE|VERIFY|CHECKSUM`
- Legacy return shapes retained via compatibility adapter (`_cipher_result` extension)
- Pair processing is a **separate** experimental rule profile (not used by legacy encode)
- Unmapped / collision / non-invertible inputs are never silently accepted
- Current A–Z mappings are **experimental legacy**, not historical authority

### Kernel

- Schema: `self-state-kernel/0.2.0`
- Presence: `absent` / `null` / `value` / `type_conflict` / `null_traversal`
- Nested path conflicts and null intermediates rejected atomically
- Injectable logical clock; explicit `KernelResult` (no truthiness)
- Registry safety with module attachment rollback
- Integrity scopes; CMD4 FAIL_SAFE semantics
- Rust foundation + shared **state** parity vectors

## License

MIT
