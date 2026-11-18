# Architecture — SELF-State Kernel

Authoritative **application/system state** for TheBabelDragon.

| Owns | Does not own |
|------|----------------|
| State values, paths, presence/null | Platform boot (ActionOS) |
| Deterministic transitions & sequence | Execution authz/journal (BabelForge) |
| Invariant evaluation interfaces | Unicode codec engine (BabelCodec) |
| Integrity scopes (state/registry/trace/config) | Hardware drivers |
| Module registration and command dispatch | Sigilspace geometry / rendering |

## Module boundary (v0.2)

### SELF-State Kernel

- State values and paths
- Presence/null semantics
- Deterministic transitions and logical sequencing
- State, registry, trace, and configuration integrity
- Module registration and command dispatch
- Kernel-level invariant interfaces

### Angelic Cipher module (`angelic_cipher.py`)

- Explicitly versioned mapping profile
- Character and sequence encoding
- Pair/sequence processing when formally specified
- Calculation results and calculation provenance
- Cipher-specific validation and test vectors

The kernel does **not** become a Unicode normalization engine, general gematria
replacement, Sigilspace geometry engine, rendering system, or BabelForge
execution/authorization replacement.

Unicode inspection and normalization remain behind a declared
BabelCodec-compatible boundary. The legacy profile uses only `.upper()` and
does not claim NFC/NFD behavior.
