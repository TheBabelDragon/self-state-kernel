# Python Compatibility

Preserved: SELF.GET/SET/SNAPSHOT, QUERY, RUN, IF, CMD4, TRACE, INTEGRITY, register_*, strict_bool, passthrough, create_kernel, self_test.

Changed: kernel.state is snapshot; KernelResult refuses bool(); nested non-map writes fail; duplicate registration rejected; transactional module attach; integrity scopes split; CMD4 structured status.
