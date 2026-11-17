# Architecture — SELF-State Kernel

Authoritative **application/system state** for TheBabelDragon.

| Owns | Does not own |
|------|----------------|
| State values, paths, presence/null | Platform boot (ActionOS) |
| Deterministic transitions & sequence | Execution authz/journal (BabelForge) |
| Invariant evaluation interfaces | Unicode codec engine (BabelCodec) |
| Integrity scopes (state/registry/trace/config) | Hardware drivers |
