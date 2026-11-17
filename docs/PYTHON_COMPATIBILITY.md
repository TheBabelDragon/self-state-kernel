# Python Compatibility

Preserved: SELF.GET/SET/SNAPSHOT, QUERY, RUN, IF, CMD4, TRACE, INTEGRITY, register_*, strict_bool, passthrough, create_kernel, self_test.

Changed: defensive `kernel.state`; no `bool(KernelResult)`; path conflicts; registry safety; integrity scopes; CMD4 structured status; presence includes `type_conflict` / `null_traversal`.

## Shared vectors

Python and Rust agree on `vectors/state_vectors.json`:

- Lookup classifications
- Write success/failure and error labels
- Final version and final path values
- Failed-write atomicity

Do not edit `generated_vectors.rs` by hand; regenerate from the JSON fixture.
