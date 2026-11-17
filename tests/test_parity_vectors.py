"""Shared vector parity: Python must accept the same cases as Rust."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from self_state_kernel import Kernel, LogicalClock, Presence


def run_vectors(path: Path) -> None:
    doc = json.loads(path.read_text())
    for idx, case in enumerate(doc["cases"]):
        k = Kernel(clock=LogicalClock())
        for op in case["ops"]:
            kind = op["op"]
            if kind == "set":
                r = k.SET(op["path"], op.get("value"))
                expect = op.get("ok", True)
                if r.ok != expect:
                    raise AssertionError(
                        f"case {idx} set {op['path']}: ok={r.ok} expected {expect}"
                    )
            elif kind == "lookup":
                lr = k.LOOKUP(op["path"])
                got = lr.presence.value
                if got != op["presence"]:
                    raise AssertionError(
                        f"case {idx} lookup {op['path']}: {got} != {op['presence']}"
                    )
            elif kind == "version":
                if k._state.version != op["eq"]:
                    raise AssertionError(
                        f"case {idx} version: {k._state.version} != {op['eq']}"
                    )


def test_parity():
    run_vectors(ROOT / "vectors" / "state_vectors.json")


if __name__ == "__main__":
    test_parity()
    print("parity OK")
