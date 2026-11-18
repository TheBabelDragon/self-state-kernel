# Angelic Cipher Calculation Authority (v0.2)

## Status

Implemented as an independently testable calculation module. The current
A–Z character mapping and AB/CD pair defaults are an **experimental legacy
profile**. They are **not** presented as historically authoritative angelic
cipher rules. Missing mappings are not invented.

## Identifiers

| Field | Value |
|-------|--------|
| Authority | `angelic-cipher` |
| Authority version | `0.2.0` |
| Result contract version | `1.0.0` |
| Default profile id | `legacy-experimental` |
| Default profile version | `1.0.0` |
| Mapping id | `legacy-az-hebrewish-v1` |
| Normalization profile | `legacy-upper-ascii` |
| Case policy | upper |

## Commands (kernel-facing)

Preserved names:

- `ANGELIC.ENCODE`
- `ANGELIC.DECODE`
- `ANGELIC.VERIFY`
- `ANGELIC.CHECKSUM`

### Compatibility

When `legacy_compat=True` (default), return shapes match pre-v0.2 callers:

- `encode` → `{input, codes, checksum, _cipher_result}`
- `decode` → `str`
- `verify` → `{ok, original, decoded, codes, _cipher_result}`
- `checksum` → `int`

The full versioned contract is always available under `_cipher_result` or via
the independent `AngelicCipher` API.

## Result contract

Every calculation identifies:

- `authority`, `authority_version`
- `profile_id`, `profile_version`, `mapping_id`
- `input`, `normalization_profile`
- `encoded_sequence`, `total` / `checksum` where applicable
- `operation`, `status`, `ok`
- `provenance`, `warnings`, `errors`
- `result_contract_version`

Status values:

- `valid`
- `unmapped_input`
- `ambiguous_mapping`
- `non_invertible`
- `normalization_mismatch`
- `unsupported_operation`
- `invalid_input`
- `collision`

Zero is never used as a substitute for missing or invalid values.

## Legacy character-sum algorithm

For each character after `legacy-upper-ascii` normalization:

- Space → code `0`
- Mapped A–Z → table value
- Anything else → `unmapped_input` (strict mode raises)

The pairs table is **not** consulted by this algorithm.

## Pair processing

`AngelicCipher.encode_with_pairs` is a **separately declared** experimental
rule profile:

- Longest-match greedy left-to-right over the pairs table
- Fallback to character mapping
- Tokens may be strings (pair expansions) or integers (character codes)
- `encoded_sequence` is left null; see `provenance.tokens`

Do not treat pair processing as part of the legacy encode path.

## Independent use

```python
from angelic_cipher import AngelicCipher

c = AngelicCipher()
r = c.encode("AB")
assert r.ok and r.total == 3
print(r.to_json())
```

## What remains undefined

- Historically authoritative angelic mappings (if any)
- Additional profiles beyond `legacy-experimental`
- Full BabelCodec normalization integration
- Ambiguous multi-character decoding strategies beyond inverse single-code lookup
- Formal pair-overlap conflict policy beyond longest-match greedy

## Test vectors

See `tests/test_angelic_cipher.py`. State parity vectors in `vectors/` remain
focused on kernel state semantics and are not mixed with cipher vectors.
