"""Regression and correction tests for SELF-State Kernel."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from self_state_kernel import (
    AngelicCipherModule,
    DecisionStatus,
    Kernel,
    KernelRegistryError,
    KernelResult,
    LogicalClock,
    Presence,
    create_kernel,
    self_test,
    strict_bool,
    KernelConditionError,
)


def test_self_test_passes():
    assert self_test() is True


def test_missing_vs_null():
    k = create_kernel()
    assert k.LOOKUP("x.y").presence is Presence.ABSENT
    assert k.GET("x.y", default="D") == "D"
    r = k.SET("x.y", None)
    assert r.ok
    assert k.LOOKUP("x.y").presence is Presence.NULL
    assert k.GET("x.y", default="D") is None
    assert k.CONTAINS("x.y") is True
    assert k.CONTAINS("x.z") is False


def test_nested_path_conflict_atomic():
    k = create_kernel()
    assert k.SET("machine", 42).ok
    bad = k.SET("machine.temperature", 80)
    assert bad.ok is False
    assert k.GET("machine") == 42


def test_defensive_state_property():
    k = create_kernel()
    k.SET("a.b", 1)
    snap = k.state
    snap["a"]["b"] = 999
    assert k.GET("a.b") == 1


def test_duplicate_command_rejected():
    k = Kernel(clock=LogicalClock())
    k.register_command("FOO", lambda: 1)
    try:
        k.register_command("FOO", lambda: 2)
        assert False
    except KernelRegistryError:
        pass


def test_failed_module_attachment_rollback():
    k = Kernel(clock=LogicalClock())

    class BadMod:
        def attach(self, kernel):
            kernel.register_command("BAD.CMD", lambda: None)
            raise RuntimeError("boom")

    try:
        k.register_module("bad", BadMod())
        assert False
    except KernelRegistryError:
        pass
    assert "BAD.CMD" not in k._commands
    assert "bad" not in k._modules


def test_kernel_result_no_truthiness():
    r = KernelResult(ok=True, operation="X", value=1)
    try:
        bool(r)
        assert False
    except TypeError:
        pass


def test_nan_inf_rejected():
    k = create_kernel()
    assert k.SET("n", float("nan")).ok is False
    assert k.SET("i", float("inf")).ok is False
    assert k.SET("ni", float("-inf")).ok is False


def test_cycle_rejected():
    k = create_kernel()
    a: dict = {}
    a["self"] = a
    assert k.SET("cycle", a).ok is False


def test_deterministic_clock_sequence():
    clock = LogicalClock()
    k = create_kernel(clock=clock)
    s1 = k.SET("a", 1).trace_sequence
    s2 = k.SET("b", 2).trace_sequence
    assert s1 is not None and s2 is not None
    assert s2 == s1 + 1
    assert clock.wall_time() is None


def test_state_integrity_changes():
    k = create_kernel()
    h1 = k.state_integrity()
    k.SET("z", 1)
    h2 = k.state_integrity()
    assert h1 != h2


def test_registry_identity_changes():
    k = Kernel(clock=LogicalClock())
    h1 = k.registry_identity()
    k.register_command("X", lambda: None)
    h2 = k.registry_identity()
    assert h1 != h2


def test_cmd4_missing_fail_safe():
    k = Kernel(clock=LogicalClock())
    k.register_command("CMD4", k.CMD4)
    r = k.CMD4()
    assert r.ok
    assert r.value["status"] == DecisionStatus.FAIL_SAFE.value
    assert r.value["special_case"] is None


def test_cmd4_inspect():
    k = create_kernel()
    k.SET("thermal.temperature", 100.0)
    k.SET("geometry.thickness", 10.0)
    k.SET("geometry.target_thickness", 8.0)
    k.SET("geometry.allowed_variance", 0.5)
    r = k.CMD4()
    assert r.value["status"] == DecisionStatus.INSPECT_STATE.value
    assert r.value["special_case"] is True


def test_cmd4_normal():
    k = create_kernel()
    k.SET("thermal.temperature", 100.0)
    k.SET("geometry.thickness", 8.1)
    k.SET("geometry.target_thickness", 8.0)
    k.SET("geometry.allowed_variance", 0.5)
    r = k.CMD4()
    assert r.value["status"] == DecisionStatus.NORMAL_STATE.value
    assert r.value["special_case"] is False


def test_angelic_roundtrip():
    m = AngelicCipherModule()
    ver = m.verify("HELLO")
    assert ver["ok"] is True


def test_angelic_collision_detection():
    try:
        AngelicCipherModule(gematria={"A": 1, "B": 1})
        assert False
    except Exception:
        pass


def test_empty_path_rejected():
    k = create_kernel()
    assert k.SET("", 1).ok is False
    assert k.SET("a..b", 1).ok is False


if __name__ == "__main__":
    failed = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"OK {name}")
            except Exception as e:
                failed += 1
                print(f"FAIL {name}: {e}")
    if failed:
        raise SystemExit(1)
    print("ALL PASSED")
