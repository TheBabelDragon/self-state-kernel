# Python compatibility notes

## v0.1.1 → v0.2.0

### Angelic Cipher

- `AngelicCipherModule` still registers the same four commands.
- Default constructor arguments (`gematria=`, `pairs=`) still work.
- Return values of `encode` / `verify` gain an extra `_cipher_result` key;
  existing keys (`input`, `codes`, `checksum`, `ok`, `original`, `decoded`)
  retain prior meaning and types.
- `decode` still returns a `str`.
- `checksum` still returns an `int`.
- Collision / unmapped errors still surface as `KernelValueError` when invoked
  through the kernel.

### New public symbols

Importable from `self_state_kernel` and `angelic_cipher`:

- `AngelicCipher`, `CipherResult`, `CalculationStatus`, `AngelicCipherError`
- `PROFILE_LEGACY_EXPERIMENTAL`, `MAPPING_ID_LEGACY_AZ`, etc.

### Kernel schema

`Kernel.SCHEMA_VERSION` is now `self-state-kernel/0.2.0`. Registry identity
hashes therefore change; state parity vectors are unaffected in semantics.
