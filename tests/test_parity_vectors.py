"""Shared vector parity: Python executes vectors/state_vectors.json as contract."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from self_state_kernel import Kernel, LogicalClock, Presence

PRESENCE_MAP = {
    "absent": Presence.ABSENT,
    "null": Presence.NULL,
    "value": Presence.VALUE,
    "type_conflict": Presence.TYPE_CONFLICT,
    "null_traversal": Presence.NULL_TRAVERSAL,
}


def materialize(value):
    if isinstance(value, dict) and value.get("__special__") == "nan":
        return float("nan")
    return value


def run_vectors(path: Path) -> None:
    doc = json.loads(path.read_text())
    for case in doc["cases"]:
        k = Kernel(clock=LogicalClock())
        name = case.get("name", "?")
        for op in case["ops"]:
            kind = op["op"]
            if kind == "set":
                before_v = k._state.version
                r = k.SET(op["path"], materialize(op.get("value")))
                expect_ok = op.get("ok", True)
                if r.ok != expect_ok:
                    raise AssertionError(
                        f"{name} set {op['path']}: ok={r.ok} expected {expect_ok} err={r.error}"
                    )
                if not r.ok:
                    if k._state.version != before_v:
                        raise AssertionError(
                            f"{name} set {op['path']}: version changed on failure"
                        )
                    want = op.get("error")
                    if want:
                        code = (r.error_code or "").upper()
                        msg = (r.error or "").lower()
                        if want in ("type_conflict", "null_traversal") and code == "PATH":
                            pass
                        elif want == "path" and code == "PATH":
                            pass
                        elif want == "value" and code == "VALUE":
                            pass
                        elif want.replace("_", "") in msg.replace(" ", ""):
                            pass
                        else:
                            raise AssertionError(
                                f"{name} set {op['path']}: error_code={r.error_code!r} "
                                f"error={r.error!r} want {want}"
                            )
            elif kind == "lookup":
                lr = k.LOOKUP(op["path"])
                expect = PRESENCE_MAP[op["presence"]]
                if lr.presence is not expect:
                    raise AssertionError(
                        f"{name} lookup {op['path']}: {lr.presence.value} != {op['presence']}"
                    )
            elif kind == "version":
                if k._state.version != op["eq"]:
                    raise AssertionError(
                        f"{name} version: {k._state.version} != {op['eq']}"
                    )
            else:
                raise AssertionError(f"{name}: unknown op {kind}")

        fv = case.get("final_version")
        if fv is not None and k._state.version != fv:
            raise AssertionError(f"{name} final_version: {k._state.version} != {fv}")

        for path_key, expect in (case.get("final_paths") or {}).items():
            lr = k.LOOKUP(path_key)
            if expect is None:
                if lr.presence is not Presence.NULL:
                    raise AssertionError(
                        f"{name} final_paths {path_key}: want null got {lr.presence.value}"
                    )
            else:
                if lr.presence is not Presence.VALUE or lr.value != expect:
                    raise AssertionError(
                        f"{name} final_paths {path_key}: got presence={lr.presence.value} "
                        f"value={lr.value!r} want {expect!r}"
                    )


def test_parity():
    run_vectors(ROOT / "vectors" / "state_vectors.json")


if __name__ == "__main__":
    test_parity()
    print("parity OK")
