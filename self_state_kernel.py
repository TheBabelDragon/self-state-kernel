# -*- coding: utf-8 -*-
"""
Stage 1112 — SELF-State Kernel (corrected reference)

Authoritative application/system state semantics for TheBabelDragon.

Owns: state transitions, invariants, integrity scopes, deterministic sequence.
Does not own: platform/boot (ActionOS), execution authz/journal (BabelForge),
codec Unicode engine (BabelCodec).

Python 3.10+
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence
import copy
import hashlib
import json
import math
from abc import ABC, abstractmethod


class KernelError(Exception):
    def __init__(self, message: str, *, code: str = "KERNEL_ERROR"):
        super().__init__(message)
        self.code = code
        self.message = message


class KernelConditionError(KernelError):
    def __init__(self, message: str):
        super().__init__(message, code="CONDITION")


class KernelDispatchError(KernelError):
    def __init__(self, message: str):
        super().__init__(message, code="DISPATCH")


class KernelPathError(KernelError):
    def __init__(self, message: str):
        super().__init__(message, code="PATH")


class KernelValueError(KernelError):
    def __init__(self, message: str):
        super().__init__(message, code="VALUE")


class KernelRegistryError(KernelError):
    def __init__(self, message: str):
        super().__init__(message, code="REGISTRY")


def strict_bool(value: Any, *, name: str = "condition") -> bool:
    if isinstance(value, bool):
        return value
    raise KernelConditionError(
        f"{name} must resolve to bool; received {type(value).__name__}: {value!r}"
    )


class Clock(ABC):
    @abstractmethod
    def next_sequence(self) -> int:
        ...

    @abstractmethod
    def wall_time(self) -> Optional[float]:
        ...


class LogicalClock(Clock):
    def __init__(self, start: int = 0):
        self._seq = start

    def next_sequence(self) -> int:
        self._seq += 1
        return self._seq

    def wall_time(self) -> Optional[float]:
        return None


class HostClock(Clock):
    def __init__(self):
        self._seq = 0

    def next_sequence(self) -> int:
        self._seq += 1
        return self._seq

    def wall_time(self) -> Optional[float]:
        import time
        return time.time()


@dataclass(frozen=True)
class KernelResult:
    ok: bool
    operation: str
    value: Any = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    trace_sequence: Optional[int] = None

    def __bool__(self) -> bool:  # type: ignore[override]
        raise TypeError(
            "KernelResult has no truth value; inspect .ok, .value, .error explicitly"
        )

    def passthrough(self) -> Any:
        if not self.ok:
            raise KernelError(
                f"Cannot passthrough failed result: {self.error}",
                code=self.error_code or "PASSTHROUGH",
            )
        return self.value


@dataclass(frozen=True)
class TraceRecord:
    sequence: int
    wall_time: Optional[float]
    operation: str
    target: str
    inputs: Dict[str, Any]
    output: Any
    state_hash: str


def _reject_nonfinite(value: float, path: str = "") -> None:
    if math.isnan(value) or math.isinf(value):
        raise KernelValueError(f"Non-finite float rejected at {path or '<root>'}: {value!r}")


def validate_value(value: Any, *, path: str = "", _seen: Optional[set] = None) -> Any:
    if _seen is None:
        _seen = set()
    tid = id(value)
    if isinstance(value, (dict, list)):
        if tid in _seen:
            raise KernelValueError(f"Cyclic value rejected at {path or '<root>'}")
        _seen.add(tid)
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        _reject_nonfinite(value, path)
        return value
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return value
    if isinstance(value, list):
        for i, item in enumerate(value):
            validate_value(item, path=f"{path}[{i}]", _seen=_seen)
        return value
    if isinstance(value, dict):
        for k, v in value.items():
            if not isinstance(k, str):
                raise KernelValueError(f"Invalid dict key type at {path}: {type(k).__name__}")
            if not k or "." in k:
                raise KernelValueError(f"Invalid dict key at {path}: {k!r}")
            validate_value(v, path=f"{path}.{k}" if path else k, _seen=_seen)
        return value
    raise KernelValueError(
        f"Unsupported value type at {path or '<root>'}: {type(value).__name__}"
    )


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class Presence(str, Enum):
    ABSENT = "absent"
    NULL = "null"
    VALUE = "value"


@dataclass(frozen=True)
class LookupResult:
    presence: Presence
    value: Any = None
    path: str = ""


class KernelState:
    def __init__(self) -> None:
        self._values: Dict[str, Any] = {}
        self._version: int = 0

    @property
    def version(self) -> int:
        return self._version

    def lookup(self, path: str) -> LookupResult:
        parts = _split_path(path)
        current: Any = self._values
        for part in parts:
            if not isinstance(current, dict) or part not in current:
                return LookupResult(Presence.ABSENT, path=path)
            current = current[part]
        if current is None:
            return LookupResult(Presence.NULL, value=None, path=path)
        return LookupResult(Presence.VALUE, value=copy.deepcopy(current), path=path)

    def get(self, path: str, default: Any = None) -> Any:
        lr = self.lookup(path)
        if lr.presence is Presence.ABSENT:
            return default
        return lr.value

    def contains(self, path: str) -> bool:
        return self.lookup(path).presence is not Presence.ABSENT

    def set(self, path: str, value: Any) -> None:
        parts = _split_path(path)
        validate_value(value, path=path)
        new_root = copy.deepcopy(self._values)
        current = new_root
        for i, part in enumerate(parts[:-1]):
            if part not in current:
                current[part] = {}
            elif not isinstance(current[part], dict):
                raise KernelPathError(
                    f"Cannot descend into non-map at '{'.'.join(parts[:i+1])}': "
                    f"found {type(current[part]).__name__}"
                )
            current = current[part]
        current[parts[-1]] = copy.deepcopy(value)
        self._values = new_root
        self._version += 1

    def snapshot(self) -> Dict[str, Any]:
        return copy.deepcopy(self._values)


def _split_path(path: str) -> List[str]:
    if not isinstance(path, str):
        raise KernelPathError(f"Path must be str, got {type(path).__name__}")
    if not path or path.strip() != path:
        raise KernelPathError(f"Invalid state path: {path!r}")
    parts = path.split(".")
    if any(not p for p in parts):
        raise KernelPathError(f"Empty path segment in: {path!r}")
    return parts


class DecisionStatus(str, Enum):
    NORMAL_STATE = "NORMAL_STATE"
    INSPECT_STATE = "INSPECT_STATE"
    FAIL_SAFE = "FAIL_SAFE"


@dataclass(frozen=True)
class Decision:
    status: DecisionStatus
    special_case: Optional[bool]
    reason: str
    details: Dict[str, Any] = field(default_factory=dict)


class SelfContext:
    def __init__(self, kernel: "Kernel") -> None:
        self._kernel = kernel

    def GET(self, path: str, default: Any = None) -> Any:
        return self._kernel.GET(path, default)

    def SET(self, path: str, value: Any) -> KernelResult:
        return self._kernel.SET(path, value)

    def SNAPSHOT(self) -> Dict[str, Any]:
        return self._kernel.SNAPSHOT()

    def LOOKUP(self, path: str) -> LookupResult:
        return self._kernel.LOOKUP(path)

    def CONTAINS(self, path: str) -> bool:
        return self._kernel.CONTAINS(path)


class Kernel:
    SCHEMA_VERSION = "self-state-kernel/0.1"

    def __init__(self, clock: Optional[Clock] = None) -> None:
        self._state = KernelState()
        self._clock: Clock = clock or LogicalClock()
        self._commands: Dict[str, Callable[..., Any]] = {}
        self._modules: Dict[str, Any] = {}
        self._trace: List[TraceRecord] = []
        self.SELF = SelfContext(self)

    @property
    def state(self) -> Dict[str, Any]:
        return self._state.snapshot()

    def GET(self, path: str, default: Any = None) -> Any:
        value = self._state.get(path, default)
        self._emit("GET", path, {"default": default}, value)
        return value

    def LOOKUP(self, path: str) -> LookupResult:
        lr = self._state.lookup(path)
        self._emit("LOOKUP", path, {}, {"presence": lr.presence.value})
        return lr

    def CONTAINS(self, path: str) -> bool:
        return self._state.contains(path)

    def SET(self, path: str, value: Any) -> KernelResult:
        try:
            self._state.set(path, value)
            seq = self._emit("SET", path, {"value": _diag(value)}, True)
            return KernelResult(ok=True, operation="SET", value=value, trace_sequence=seq)
        except KernelError as exc:
            seq = self._emit("SET_ERROR", path, {"value": _diag(value)}, exc.message)
            return KernelResult(
                ok=False, operation="SET", error=exc.message,
                error_code=exc.code, trace_sequence=seq,
            )

    def SNAPSHOT(self) -> Dict[str, Any]:
        snap = self._state.snapshot()
        self._emit("SNAPSHOT", "SELF", {}, {"keys": list(snap.keys())})
        return snap

    def register_command(self, name: str, fn: Callable[..., Any]) -> None:
        if not name or not isinstance(name, str):
            raise KernelRegistryError(f"Invalid command name: {name!r}")
        if name in self._commands:
            raise KernelRegistryError(f"Command already registered: {name}")
        self._commands[name] = fn
        self._emit("REGISTER_COMMAND", name, {}, True)

    def register_module(self, name: str, module: Any) -> None:
        if not name or not isinstance(name, str):
            raise KernelRegistryError(f"Invalid module name: {name!r}")
        if name in self._modules:
            raise KernelRegistryError(f"Module already registered: {name}")
        prior_commands = set(self._commands.keys())
        try:
            if hasattr(module, "attach"):
                module.attach(self)
            self._modules[name] = module
            self.SET(f"modules.{name}.status", "attached")
        except Exception as exc:
            for cmd in list(self._commands.keys()):
                if cmd not in prior_commands:
                    del self._commands[cmd]
            self._modules.pop(name, None)
            raise KernelRegistryError(f"Module attachment failed for {name}: {exc}") from exc
        self._emit("REGISTER_MODULE", name, {}, True)

    def RUN(self, command: str, *args: Any, **kwargs: Any) -> KernelResult:
        fn = self._commands.get(command)
        if fn is None:
            seq = self._emit("RUN_ERROR", command, {}, "not registered")
            return KernelResult(
                ok=False, operation=command,
                error=f"Command not registered: {command}",
                error_code="DISPATCH", trace_sequence=seq,
            )
        try:
            value = fn(*args, **kwargs)
            if isinstance(value, KernelResult):
                return value
            seq = self._emit("RUN", command, {"args": _diag(args)}, _diag(value))
            return KernelResult(ok=True, operation=command, value=value, trace_sequence=seq)
        except Exception as exc:
            err = f"{type(exc).__name__}: {exc}"
            seq = self._emit("RUN_ERROR", command, {}, err)
            code = getattr(exc, "code", "RUN_ERROR")
            return KernelResult(
                ok=False, operation=command, error=err,
                error_code=str(code), trace_sequence=seq,
            )

    def IF(
        self, condition: Any, then_command: str,
        else_command: Optional[str] = None, *args: Any, **kwargs: Any,
    ) -> KernelResult:
        try:
            decision = strict_bool(condition, name="IF condition")
        except KernelConditionError as exc:
            seq = self._emit("IF_ERROR", then_command, {"condition": repr(condition)}, str(exc))
            return KernelResult(
                ok=False, operation="IF", error=str(exc),
                error_code="CONDITION", trace_sequence=seq,
            )
        if decision:
            return self.RUN(then_command, *args, **kwargs)
        if else_command is not None:
            return self.RUN(else_command, *args, **kwargs)
        seq = self._emit("IF_FALSE", then_command, {}, False)
        return KernelResult(ok=True, operation="IF", value=False, trace_sequence=seq)

    def QUERY(self, name: str) -> KernelResult:
        if name in self._commands:
            value = {"type": "command", "name": name, "registered": True}
        elif name in self._modules:
            value = {"type": "module", "name": name, "registered": True}
        else:
            seq = self._emit("QUERY", name, {}, None)
            return KernelResult(
                ok=False, operation="QUERY", error=f"Unknown: {name}",
                error_code="DISPATCH", trace_sequence=seq,
            )
        seq = self._emit("QUERY", name, {}, value)
        return KernelResult(ok=True, operation="QUERY", value=value, trace_sequence=seq)

    def evaluate_special_case(self) -> Decision:
        details: Dict[str, Any] = {}
        try:
            t_lr = self._state.lookup("thermal.temperature")
            g_lr = self._state.lookup("geometry.thickness")
            gt_lr = self._state.lookup("geometry.target_thickness")
            av_lr = self._state.lookup("geometry.allowed_variance")
            for label, lr in (
                ("thermal.temperature", t_lr),
                ("geometry.thickness", g_lr),
                ("geometry.target_thickness", gt_lr),
                ("geometry.allowed_variance", av_lr),
            ):
                if lr.presence is Presence.ABSENT:
                    return Decision(DecisionStatus.FAIL_SAFE, None, f"missing required path: {label}", details)
                if lr.presence is Presence.NULL:
                    return Decision(DecisionStatus.FAIL_SAFE, None, f"null required path: {label}", details)
            temp, thick, target, allowed = t_lr.value, g_lr.value, gt_lr.value, av_lr.value
            for name, v in (
                ("temperature", temp), ("thickness", thick),
                ("target_thickness", target), ("allowed_variance", allowed),
            ):
                if not isinstance(v, (int, float)) or isinstance(v, bool):
                    return Decision(DecisionStatus.FAIL_SAFE, None, f"non-numeric {name}: {type(v).__name__}", details)
                if isinstance(v, float):
                    _reject_nonfinite(v, name)
            if float(allowed) < 0:
                return Decision(DecisionStatus.FAIL_SAFE, None, "allowed_variance must be non-negative", details)
            delta = abs(float(thick) - float(target))
            details["delta"] = delta
            details["allowed"] = float(allowed)
            if delta > float(allowed):
                return Decision(DecisionStatus.INSPECT_STATE, True, "thickness variance exceeds allowance", details)
            return Decision(DecisionStatus.NORMAL_STATE, False, "within tolerance", details)
        except KernelError as exc:
            return Decision(DecisionStatus.FAIL_SAFE, None, exc.message, details)

    def CMD4(self) -> KernelResult:
        decision = self.evaluate_special_case()
        seq = self._emit("CMD4", "SELF", {}, {"status": decision.status.value, "reason": decision.reason})
        return KernelResult(
            ok=True, operation="CMD4",
            value={
                "status": decision.status.value,
                "special_case": decision.special_case,
                "reason": decision.reason,
                "details": decision.details,
            },
            trace_sequence=seq,
        )

    def state_integrity(self) -> str:
        return hashlib.sha256(canonical_json(self._state.snapshot()).encode("utf-8")).hexdigest()

    def registry_identity(self) -> str:
        payload = canonical_json({
            "commands": sorted(self._commands.keys()),
            "modules": sorted(self._modules.keys()),
            "schema": self.SCHEMA_VERSION,
        })
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def trace_integrity(self) -> str:
        records = [{
            "sequence": r.sequence, "operation": r.operation, "target": r.target,
            "inputs": r.inputs, "output": r.output, "state_hash": r.state_hash,
        } for r in self._trace]
        return hashlib.sha256(canonical_json(records).encode("utf-8")).hexdigest()

    def config_identity(self) -> str:
        payload = canonical_json({"schema": self.SCHEMA_VERSION, "clock": type(self._clock).__name__})
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def integrity(self) -> str:
        return self.state_integrity()

    def integrity_report(self) -> Dict[str, str]:
        return {
            "state": self.state_integrity(),
            "registry": self.registry_identity(),
            "trace": self.trace_integrity(),
            "config": self.config_identity(),
        }

    def TRACE(self) -> List[TraceRecord]:
        return list(self._trace)

    def _emit(self, operation: str, target: str, inputs: Dict[str, Any], output: Any) -> int:
        seq = self._clock.next_sequence()
        self._trace.append(TraceRecord(
            sequence=seq, wall_time=self._clock.wall_time(), operation=operation,
            target=target, inputs=inputs, output=output, state_hash=self.state_integrity(),
        ))
        return seq


def _diag(value: Any) -> Any:
    try:
        if isinstance(value, (str, int, float, bool, type(None))):
            return value
        if isinstance(value, (list, tuple)):
            return [_diag(v) for v in value[:20]]
        if isinstance(value, dict):
            return {str(k): _diag(v) for k, v in list(value.items())[:20]}
        return repr(value)
    except Exception:
        return "<unreprable>"


DEFAULT_GEMATRIA: Dict[str, int] = {
    "A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6, "G": 7, "H": 8, "I": 9, "J": 10,
    "K": 20, "L": 30, "M": 40, "N": 50, "O": 60, "P": 70, "Q": 80, "R": 90, "S": 100,
    "T": 200, "U": 300, "V": 400, "W": 500, "X": 600, "Y": 700, "Z": 800,
}
DEFAULT_ANGELIC_PAIRS: Dict[str, str] = {"AB": "11", "CD": "22"}


class AngelicCipherModule:
    def __init__(self, gematria: Optional[Mapping[str, int]] = None, pairs: Optional[Mapping[str, str]] = None) -> None:
        self.gematria = dict(gematria or DEFAULT_GEMATRIA)
        self.pairs = dict(pairs or DEFAULT_ANGELIC_PAIRS)
        self._validate_tables()

    def _validate_tables(self) -> None:
        seen_vals: Dict[int, str] = {}
        for k, v in self.gematria.items():
            if not isinstance(k, str) or len(k) != 1:
                raise KernelValueError(f"Invalid gematria key: {k!r}")
            if not isinstance(v, int):
                raise KernelValueError(f"Invalid gematria value for {k}: {v!r}")
            if v in seen_vals:
                raise KernelValueError(f"Gematria collision: {k} and {seen_vals[v]} both map to {v}")
            seen_vals[v] = k

    def attach(self, kernel: Kernel) -> None:
        kernel.register_command("ANGELIC.ENCODE", self.encode)
        kernel.register_command("ANGELIC.DECODE", self.decode)
        kernel.register_command("ANGELIC.VERIFY", self.verify)
        kernel.register_command("ANGELIC.CHECKSUM", self.checksum)

    def encode(self, text: str) -> Dict[str, Any]:
        if not isinstance(text, str):
            raise KernelValueError("encode requires str")
        codes = []
        for ch in text.upper():
            if ch == " ":
                codes.append(0)
                continue
            if ch not in self.gematria:
                raise KernelValueError(f"Unmapped character: {ch!r}")
            codes.append(self.gematria[ch])
        return {"input": text, "codes": codes, "checksum": sum(codes)}

    def decode(self, codes: Sequence[int]) -> str:
        inv = {v: k for k, v in self.gematria.items()}
        out = []
        for c in codes:
            if c == 0:
                out.append(" ")
                continue
            if c not in inv:
                raise KernelValueError(f"Unmapped code: {c}")
            out.append(inv[c])
        return "".join(out)

    def verify(self, text: str) -> Dict[str, Any]:
        encoded = self.encode(text)
        decoded = self.decode(encoded["codes"])
        return {"ok": decoded == text.upper(), "original": text, "decoded": decoded, "codes": encoded["codes"]}

    def checksum(self, text: str) -> int:
        return int(self.encode(text)["checksum"])


def create_kernel(clock: Optional[Clock] = None) -> Kernel:
    kernel = Kernel(clock=clock or LogicalClock())
    kernel.register_command("CMD4", kernel.CMD4)
    kernel.register_command("SPECIAL_CASE", lambda: kernel.evaluate_special_case())
    kernel.register_module("angelic_cipher", AngelicCipherModule())
    kernel.SET("thermal.temperature", None)
    kernel.SET("thermal.target", None)
    kernel.SET("geometry.thickness", None)
    kernel.SET("geometry.target_thickness", None)
    kernel.SET("geometry.allowed_variance", 0.5)
    return kernel


def self_test() -> bool:
    kernel = create_kernel()
    kernel.SELF.SET("thermal.temperature", 145.2)
    kernel.SELF.SET("geometry.thickness", 8.6)
    kernel.SELF.SET("geometry.target_thickness", 8.0)
    assert strict_bool(True) is True
    try:
        strict_bool("false")
    except KernelConditionError:
        pass
    else:
        raise AssertionError("String truthiness was not rejected.")
    special = kernel.RUN("SPECIAL_CASE")
    assert special.ok is True
    cmd4 = kernel.RUN("CMD4")
    assert cmd4.ok is True and "status" in cmd4.value
    enc = kernel.RUN("ANGELIC.ENCODE", "AB")
    assert enc.ok is True
    ver = kernel.RUN("ANGELIC.VERIFY", "AB")
    assert ver.ok is True
    q = kernel.QUERY("CMD4")
    assert q.ok is True and q.value["registered"] is True
    assert isinstance(kernel.integrity(), str) and len(kernel.integrity()) == 64
    assert kernel.TRACE()
    assert kernel.LOOKUP("no.such.path").presence is Presence.ABSENT
    kernel.SET("explicit.null", None)
    assert kernel.LOOKUP("explicit.null").presence is Presence.NULL
    assert kernel.GET("no.such.path", default="D") == "D"
    assert kernel.GET("explicit.null", default="D") is None
    kernel.SET("machine", 42)
    bad = kernel.SET("machine.temperature", 80)
    assert bad.ok is False and kernel.GET("machine") == 42
    try:
        bool(cmd4)
        raise AssertionError("KernelResult should not be bool-coercible")
    except TypeError:
        pass
    assert kernel.SET("bad.nan", float("nan")).ok is False
    return True


def demo() -> None:
    kernel = create_kernel()
    print(self_test())
    print("PASSTHROUGH:")
    print(kernel.RUN("CMD4").passthrough() is not None)
    print("QUERY CMD4:")
    print(kernel.QUERY("CMD4").value)
    print("INTEGRITY:")
    print(kernel.integrity())
    print("INTEGRITY REPORT:")
    print(kernel.integrity_report())
    print("TRACE:")
    for rec in kernel.TRACE()[-12:]:
        print(f"[{rec.sequence:04d}] {rec.operation:22s} {rec.target}")


if __name__ == "__main__":
    demo()
