# Stage 1112 — SELF-State Kernel

Independent, UI-free kernel for the MetaField / field-computing stack.

## Core model

```
SELF.GET(...)
SELF.SET(...)
QUERY(...)
RUN(...)
IF(...)
CMD4(...)
TRACE
INTEGRITY
explicit passthrough
```

## Design principles

- Kernel is independent of UI.
- Modules are separate from the kernel and attach cleanly.
- Boolean control decisions are **strict** and **fail-closed** (`strict_bool` rejects Python truthiness).
- Errors never masquerade as successful control values.
- Results retain provenance through trace records.
- State integrity is hashable (`integrity()` → SHA-256) and inspectable.
- Modules can later provide thermal, geometry, CAN, compiler-provenance, or external-compute functionality.

## Quick start

```bash
python self_state_kernel.py
```

Runs `self_test()` then `demo()`.

## Key pieces

| Piece | Role |
|-------|------|
| `Kernel` | Core: state, command registry, modules, trace, integrity |
| `SelfContext` / `SELF` | Public GET / SET / SNAPSHOT interface |
| `KernelResult` | Envelope with explicit `.passthrough()` |
| `AngelicCipherModule` | Example attachable module (gematria encode/decode/verify/checksum) |
| `CMD4` | Higher-order state resolver (special-case → INSPECT / NORMAL / FAIL_SAFE) |
| `evaluate_special_case` | Thermal + geometry thickness variance check |

## Hardware context note

Related real-time boundary work lives in [`arty-realtime`](https://github.com/TheBabelDragon/arty-realtime).

- Repo name is historical.
- **Current target platform: Digilent Eclypse Z7** (Zynq-7000 XC7Z020 + Zmod ports).
- See ADR-001 / ADR-002 in that repo for the decision from earlier Arty-centric framing to Eclypse Z7 + Ethernet (FT601 deferred).
- Genesys ZU is the higher-end sibling in the same Digilent SYZYGY/Zmod family; not the active target of the current ADRs.

## Status

- Reference implementation, Stage 1112.
- `DEFAULT_GEMATRIA` / `DEFAULT_ANGELIC_PAIRS` are minimal placeholders sufficient for the included self-test; replace with full tables as needed.
- Ready for modules (thermal, geometry, Field Bus, etc.) to attach.
