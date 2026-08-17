# -*- coding: utf-8 -*-
"""
Stage 1112 — SELF-State Kernel
Consolidated save/passable reference implementation.
Core model:
    SELF.GET(...)
    SELF.SET(...)
    QUERY(...)
    RUN(...)
    IF(...)
    CMD4(...)
    TRACE
    INTEGRITY
    explicit passthrough
Design principles:
    - Kernel is independent of UI.
    - Modules are separate from the kernel.
    - Boolean control decisions are strict and fail-closed.
    - Errors never masquerade as successful control values.
    - Results retain provenance through trace records.
    - State integrity is hashable and inspectable.
    - Modules can later provide thermal, geometry, CAN,
      compiler-provenance, or external-compute functionality.
Python 3.10+
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, Iterable, Tuple, Union
import copy
import hashlib
import json
import time
# ============================================================
# ERRORS
# ============================================================
class KernelError(Exception):
    """Base kernel exception."""
class KernelConditionError(KernelError):
    """Raised when a control condition is not safely boolean."""
class KernelDispatchError(KernelError):
    """Raised when a command cannot be dispatched."""
# ============================================================
# STRICT BOOLEAN SAFETY
# ============================================================
def strict_bool(
    value: Any,
    *,
    name: str = "condition",
) -> bool:
    """
    Accept ONLY an actual bool.
    Deliberately rejects Python truthiness such as:
        bool("false") -> True
        bool("0")     -> True
        bool(1)       -> True
    Kernel control paths therefore cannot accidentally interpret
    arbitrary data as permission.
    """
    if isinstance(value, bool):
        return value
    raise KernelConditionError(
        f"{name} must resolve to bool; "
        f"received {type(value).__name__}: {value!r}"
    )
# ============================================================
# RESULT
# ============================================================
@dataclass
class KernelResult:
    """
    Standard result envelope.
    value is valid only when ok=True.
    error is populated when ok=False.
    """
    ok: bool
    operation: str
    value: Any = None
    error: str | None = None
    trace_sequence: int | None = None
    def __bool__(self) -> bool:
        return self.ok
    def passthrough(self) -> Any:
        """
        Explicitly extract a successful result.
        A failed result cannot silently pass through.
        """
        if not self.ok:
            raise KernelError(
                f"Cannot passthrough failed result: {self.error}"
            )
        return self.value
# ============================================================
# TRACE
# ============================================================
@dataclass
class TraceRecord:
    sequence: int
    timestamp: float
    operation: str
    target: str
    inputs: Dict[str, Any]
    output: Any
    state_hash: str
# ============================================================
# STATE
# ============================================================
@dataclass
class KernelState:
    values: Dict[str, Any] = field(default_factory=dict)
    def get(
        self,
        path: str,
        default: Any = None,
    ) -> Any:
        current: Any = self.values
        for part in path.split("."):
            if not isinstance(current, dict):
                return default
            if part not in current:
                return default
            current = current[part]
        return current
    def set(
        self,
        path: str,
        value: Any,
    ) -> None:
        parts = path.split(".")
        if not parts or any(not p for p in parts):
            raise KernelError(
                f"Invalid state path: {path!r}"
            )
        current = self.values
        for part in parts[:-1]:
            if (
                part not in current
                or not isinstance(current[part], dict)
            ):
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value
    def snapshot(self) -> Dict[str, Any]:
        return copy.deepcopy(self.values)
# ============================================================
# SELF CONTEXT
# ============================================================
class SelfContext:
    """
    Public SELF interface.
        SELF.GET("thermal.temperature")
        SELF.SET("geometry.thickness", 8.0)
        SELF.SNAPSHOT()
    """
    def __init__(
        self,
        kernel: "Kernel",
    ):
        self._kernel = kernel
    def GET(
        self,
        path: str,
        default: Any = None,
    ) -> Any:
        value = self._kernel.state.get(
            path,
            default,
        )
        self._kernel._trace(
            operation="GET",
            target=path,
            inputs={
                "default": default,
            },
            output=value,
        )
        return copy.deepcopy(value)
    def SET(
        self,
        path: str,
        value: Any,
    ) -> Any:
        self._kernel.state.set(
            path,
            copy.deepcopy(value),
        )
        self._kernel._trace(
            operation="SET",
            target=path,
            inputs={
                "value": value,
            },
            output=value,
        )
        return value
    def SNAPSHOT(self) -> Dict[str, Any]:
        return self._kernel.state.snapshot()
# ============================================================
# KERNEL
# ============================================================
class Kernel:
    def __init__(self):
        self.state = KernelState()
        self.SELF = SelfContext(self)
        self.commands: Dict[
            str,
            Callable[..., Any],
        ] = {}
        self.modules: Dict[
            str,
            Any,
        ] = {}
        self.trace: list[
            TraceRecord
        ] = []
        self._sequence = 0
        self.state.set(
            "kernel.version",
            "1112",
        )
        self.state.set(
            "kernel.status",
            "READY",
        )
    # --------------------------------------------------------
    # REGISTRATION
    # --------------------------------------------------------
    def register_command(
        self,
        name: str,
        function: Callable[..., Any],
    ) -> None:
        name = name.upper()
        if not name:
            raise KernelDispatchError(
                "Command name cannot be empty."
            )
        self.commands[name] = function
    def register_module(
        self,
        name: str,
        module: Any,
    ) -> None:
        if not name:
            raise KernelError(
                "Module name cannot be empty."
            )
        self.modules[name] = module
        if hasattr(module, "attach"):
            module.attach(self)
    # --------------------------------------------------------
    # STATE SHORTCUTS
    # --------------------------------------------------------
    def GET(
        self,
        path: str,
        default: Any = None,
    ) -> Any:
        return self.SELF.GET(
            path,
            default,
        )
    def SET(
        self,
        path: str,
        value: Any,
    ) -> Any:
        return self.SELF.SET(
            path,
            value,
        )
    # --------------------------------------------------------
    # COMMAND DISPATCH
    # --------------------------------------------------------
    def RUN(
        self,
        command: str,
        *args,
        **kwargs,
    ) -> KernelResult:
        command = command.upper()
        function = self.commands.get(command)
        if function is None:
            error = (
                f"Unknown command: {command}"
            )
            self._trace(
                operation="RUN_ERROR",
                target=command,
                inputs={
                    "args": args,
                    "kwargs": kwargs,
                },
                output=error,
            )
            return KernelResult(
                ok=False,
                operation="RUN",
                error=error,
            )
        try:
            value = function(
                *args,
                **kwargs,
            )
            record = self._trace(
                operation="RUN",
                target=command,
                inputs={
                    "args": args,
                    "kwargs": kwargs,
                },
                output=value,
            )
            return KernelResult(
                ok=True,
                operation=command,
                value=value,
                trace_sequence=record.sequence,
            )
        except Exception as exc:
            error = (
                f"{type(exc).__name__}: {exc}"
            )
            self._trace(
                operation="RUN_ERROR",
                target=command,
                inputs={
                    "args": args,
                    "kwargs": kwargs,
                },
                output=error,
            )
            return KernelResult(
                ok=False,
                operation=command,
                error=error,
            )
    # --------------------------------------------------------
    # STRICT IF
    # --------------------------------------------------------
    def IF(
        self,
        condition: Any,
        then_command: str,
        else_command: str | None = None,
        *args,
        **kwargs,
    ) -> KernelResult:
        """
        Protected conditional dispatcher.
        TRUE  -> then_command
        FALSE -> else_command, if provided
        FAULT -> failed KernelResult
        No implicit truthiness.
        """
        try:
            decision = strict_bool(
                condition,
                name="IF condition",
            )
        except KernelConditionError as exc:
            self._trace(
                operation="IF_ERROR",
                target=then_command,
                inputs={
                    "condition": repr(condition),
                },
                output=str(exc),
            )
            return KernelResult(
                ok=False,
                operation="IF",
                error=str(exc),
            )
        if decision:
            return self.RUN(
                then_command,
                *args,
                **kwargs,
            )
        if else_command is not None:
            return self.RUN(
                else_command,
                *args,
                **kwargs,
            )
        self._trace(
            operation="IF_FALSE",
            target=then_command,
            inputs={},
            output=False,
        )
        return KernelResult(
            ok=True,
            operation="IF",
            value=False,
        )
    # --------------------------------------------------------
    # QUERY
    # --------------------------------------------------------
    def QUERY(
        self,
        query: str,
    ) -> Any:
        """
        Resolve a command, module, or state path.
        Examples:
            QUERY("kernel.version")
            QUERY("geometry.thickness")
            QUERY("CMD4")
            QUERY("module.angelic_cipher")
        """
        if not isinstance(query, str):
            raise KernelError(
                "QUERY requires a string."
            )
        upper_query = query.upper()
        if upper_query in self.commands:
            result = {
                "type": "command",
                "name": upper_query,
                "registered": True,
            }
            self._trace(
                operation="QUERY",
                target=query,
                inputs={},
                output=result,
            )
            return result
        if query.startswith("module."):
            module_name = query.split(
                ".",
                1,
            )[1]
            result = {
                "type": "module",
                "name": module_name,
                "registered": (
                    module_name in self.modules
                ),
            }
            self._trace(
                operation="QUERY",
                target=query,
                inputs={},
                output=result,
            )
            return result
        return self.GET(query)
    # --------------------------------------------------------
    # SPECIAL CASE DETECTION
    # --------------------------------------------------------
    def evaluate_special_case(
        self,
    ) -> Dict[str, Any]:
        thermal = self.GET(
            "thermal.temperature"
        )
        thickness = self.GET(
            "geometry.thickness"
        )
        target_thickness = self.GET(
            "geometry.target_thickness"
        )
        reasons = []
        if thermal is None:
            reasons.append(
                "thermal state unavailable"
            )
        if thickness is None:
            reasons.append(
                "thickness state unavailable"
            )
        if target_thickness is None:
            reasons.append(
                "target thickness unavailable"
            )
        special = bool(reasons)
        if (
            not special
            and target_thickness is not None
        ):
            variance = abs(
                thickness - target_thickness
            )
            allowed = self.GET(
                "geometry.allowed_variance",
                0.5,
            )
            if variance > allowed:
                special = True
                reasons.append(
                    "thickness variance "
                    f"{variance:.4f} exceeds "
                    f"{allowed:.4f}"
                )
        result = {
            "special_case": (
                special
                if isinstance(special, bool)
                else False
            ),
            "reasons": reasons,
            "thermal": thermal,
            "thickness": thickness,
            "target_thickness": target_thickness,
        }
        self._trace(
            operation="SPECIAL_CASE_CHECK",
            target="SELF",
            inputs={},
            output=result,
        )
        return result
    # --------------------------------------------------------
    # CMD4
    # --------------------------------------------------------
    def CMD4(self) -> Dict[str, Any]:
        """
        Higher-order state resolver.
        CMD4 evaluates state, validates the resulting control
        boolean, and fails closed if the state is malformed.
        """
        try:
            special_result = (
                self.evaluate_special_case()
            )
            special = strict_bool(
                special_result.get(
                    "special_case"
                ),
                name="special_case",
            )
            result = {
                "command": "CMD4",
                "action": (
                    "INSPECT_STATE"
                    if special
                    else "NORMAL_STATE"
                ),
                "special_case": special,
                "state": self.state.snapshot(),
                "integrity": self.integrity(),
            }
            self._trace(
                operation="CMD4",
                target="SELF",
                inputs={},
                output=result,
            )
            return result
        except Exception as exc:
            result = {
                "command": "CMD4",
                "action": "FAIL_SAFE",
                "special_case": False,
                "error": (
                    f"{type(exc).__name__}: {exc}"
                ),
                "integrity": self.integrity(),
            }
            self._trace(
                operation="CMD4_ERROR",
                target="SELF",
                inputs={},
                output=result,
            )
            return result
    # --------------------------------------------------------
    # EXPLICIT PASSTHROUGH
    # --------------------------------------------------------
    def PASSTHROUGH(
        self,
        result: KernelResult,
    ) -> Any:
        """
        Final-form passthrough.
        Success:
            return value
        Failure:
            raise KernelError
        This prevents a failed computation from being
        mistaken for valid downstream data.
        """
        if not isinstance(
            result,
            KernelResult,
        ):
            raise KernelError(
                "PASSTHROUGH requires KernelResult."
            )
        return result.passthrough()
    # --------------------------------------------------------
    # TRACE
    # --------------------------------------------------------
    def _trace(
        self,
        operation: str,
        target: str,
        inputs: Dict[str, Any],
        output: Any,
    ) -> TraceRecord:
        self._sequence += 1
        record = TraceRecord(
            sequence=self._sequence,
            timestamp=time.time(),
            operation=operation,
            target=target,
            inputs=self._json_safe(inputs),
            output=self._json_safe(output),
            state_hash=self.integrity(),
        )
        self.trace.append(record)
        return record
    def trace_export(self) -> list[dict]:
        return [
            asdict(record)
            for record in self.trace
        ]
    # --------------------------------------------------------
    # INTEGRITY
    # --------------------------------------------------------
    def integrity(self) -> str:
        payload = json.dumps(
            self.state.snapshot(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(
            payload
        ).hexdigest()
    # --------------------------------------------------------
    # SAFE SERIALIZATION
    # --------------------------------------------------------
    @staticmethod
    def _json_safe(
        value: Any,
    ) -> Any:
        try:
            json.dumps(value)
            return value
        except TypeError:
            if isinstance(value, tuple):
                return [
                    Kernel._json_safe(v)
                    for v in value
                ]
            if isinstance(value, dict):
                return {
                    str(k): Kernel._json_safe(v)
                    for k, v in value.items()
                }
            if isinstance(value, (list, set)):
                return [
                    Kernel._json_safe(v)
                    for v in value
                ]
            return repr(value)
# ============================================================
# ANGELIC CIPHER MODULE
# ============================================================
class AngelicCipherModule:
    """
    Original Angelic Cipher functionality,
    refactored as a kernel module.
    No UI dependency.
    """
    def __init__(
        self,
        gematria: Dict[str, int],
        angelic_pairs: Dict[
            str,
            Tuple[str, str],
        ],
        key_shift: int = 0,
    ):
        self.gematria = gematria
        self.angelic_pairs = angelic_pairs
        self.key_shift = key_shift
        self.letter_to_sum = {
            ch: str(
                self.gematria[a]
                + self.gematria[b]
                + self.key_shift
            )
            for ch, (a, b)
            in self.angelic_pairs.items()
        }
        self.letter_to_pair = dict(
            self.angelic_pairs
        )
        self.letter_to_translit = {
            "א": "Aleph",
            "ב": "Bet",
            "ג": "Gimel",
            "ד": "Dalet",
            "ה": "He",
            "ו": "Vav",
            "ז": "Zayin",
            "ח": "Het",
            "ט": "Tet",
            "י": "Yod",
            "כ": "Kaf",
            "ל": "Lamed",
            "מ": "Mem",
            "נ": "Nun",
            "ס": "Samekh",
            "ע": "Ayin",
            "פ": "Pe",
            "צ": "Tsadi",
            "ק": "Qof",
            "ר": "Resh",
            "ש": "Shin",
            "ת": "Tav",
        }
        self.sum_to_letter = {
            value: key
            for key, value
            in self.letter_to_sum.items()
        }
        self._check_collisions()
    def attach(
        self,
        kernel: Kernel,
    ) -> None:
        self.kernel = kernel
        kernel.register_command(
            "ANGELIC.ENCODE",
            self.encode,
        )
        kernel.register_command(
            "ANGELIC.DECODE",
            self.decode,
        )
        kernel.register_command(
            "ANGELIC.VERIFY",
            self.verify_integrity,
        )
        kernel.register_command(
            "ANGELIC.CHECKSUM",
            self.checksum,
        )
        kernel.SET(
            "modules.angelic_cipher.status",
            "READY",
        )
        kernel.SET(
            "modules.angelic_cipher.key_shift",
            self.key_shift,
        )
    def _check_collisions(self) -> None:
        if (
            len(self.letter_to_sum)
            != len(self.sum_to_letter)
        ):
            raise ValueError(
                "Collision detected in sums!"
            )
    def encode(
        self,
        text: str,
    ) -> list[
        Tuple[
            str,
            Tuple[str, str],
            Tuple[str, str],
        ]
    ]:
        if not isinstance(text, str):
            raise TypeError(
                "ANGELIC.ENCODE requires str."
            )
        output = []
        for char in text.upper():
            if char in self.letter_to_pair:
                pair = (
                    self.letter_to_pair[char]
                )
                value = (
                    self.letter_to_sum[char]
                )
                translit_pair = (
                    self.letter_to_translit[
                        pair[0]
                    ],
                    self.letter_to_translit[
                        pair[1]
                    ],
                )
                output.append(
                    (
                        value,
                        pair,
                        translit_pair,
                    )
                )
            else:
                output.append(
                    (
                        char,
                        (char, char),
                        (char, char),
                    )
                )
        return output
    def decode(
        self,
        encoded: Iterable[
            Union[str, int]
        ],
    ) -> str:
        output = []
        for value in encoded:
            output.append(
                self.sum_to_letter.get(
                    str(value),
                    str(value),
                )
            )
        return "".join(output)
    def verify_integrity(
        self,
        text: str,
    ) -> bool:
        encoded = self.encode(text)
        decoded = self.decode(
            item[0]
            for item in encoded
        )
        return decoded == text
    def checksum(
        self,
        text: str,
    ) -> str:
        if not isinstance(text, str):
            raise TypeError(
                "ANGELIC.CHECKSUM requires str."
            )
        return hashlib.sha256(
            text.encode("utf-8")
        ).hexdigest()
# ============================================================
# DEFAULT ANGELIC TABLES (placeholders — replace with full tables)
# ============================================================
DEFAULT_GEMATRIA = {
    "א": 1, "ב": 2, "ג": 3, "ד": 4, "ה": 5, "ו": 6, "ז": 7, "ח": 8, "ט": 9,
    "י": 10, "כ": 20, "ל": 30, "מ": 40, "נ": 50, "ס": 60, "ע": 70, "פ": 80,
    "צ": 90, "ק": 100, "ר": 200, "ש": 300, "ת": 400,
}

# Minimal bijective mapping sufficient for self_test ("ABC")
# Full Latin→Hebrew pair tables should be supplied by the operator.
DEFAULT_ANGELIC_PAIRS = {
    "A": ("א", "ב"),  # 1+2=3
    "B": ("ג", "ד"),  # 3+4=7
    "C": ("ה", "ו"),  # 5+6=11
    # ... extend as needed
}

# ============================================================
# KERNEL FACTORY
# ============================================================
def create_kernel() -> Kernel:
    kernel = Kernel()
    # --------------------------------------------------------
    # Core commands
    # --------------------------------------------------------
    kernel.register_command(
        "CMD4",
        kernel.CMD4,
    )
    kernel.register_command(
        "SPECIAL_CASE",
        kernel.evaluate_special_case,
    )
    # --------------------------------------------------------
    # Angelic module
    # --------------------------------------------------------
    angelic = AngelicCipherModule(
        DEFAULT_GEMATRIA,
        DEFAULT_ANGELIC_PAIRS,
    )
    kernel.register_module(
        "angelic_cipher",
        angelic,
    )
    # --------------------------------------------------------
    # Generic state domains
    # --------------------------------------------------------
    kernel.SET(
        "thermal.temperature",
        None,
    )
    kernel.SET(
        "thermal.target",
        None,
    )
    kernel.SET(
        "geometry.thickness",
        None,
    )
    kernel.SET(
        "geometry.target_thickness",
        None,
    )
    kernel.SET(
        "geometry.allowed_variance",
        0.5,
    )
    return kernel
# ============================================================
# SELF-TEST
# ============================================================
def self_test() -> bool:
    kernel = create_kernel()
    # --------------------------------------------------------
    # State
    # --------------------------------------------------------
    kernel.SELF.SET(
        "thermal.temperature",
        145.2,
    )
    kernel.SELF.SET(
        "geometry.thickness",
        8.6,
    )
    kernel.SELF.SET(
        "geometry.target_thickness",
        8.0,
    )
    # --------------------------------------------------------
    # Strict BOOL protection
    # --------------------------------------------------------
    assert strict_bool(True) is True
    assert strict_bool(False) is False
    try:
        strict_bool("false")
    except KernelConditionError:
        pass
    else:
        raise AssertionError(
            "String truthiness was not rejected."
        )
    # --------------------------------------------------------
    # Special case
    # --------------------------------------------------------
    special = kernel.RUN(
        "SPECIAL_CASE"
    )
    assert special.ok
    assert isinstance(
        special.value["special_case"],
        bool,
    )
    assert special.value[
        "special_case"
    ] is True
    # --------------------------------------------------------
    # CMD4
    # --------------------------------------------------------
    cmd4 = kernel.RUN(
        "CMD4"
    )
    assert cmd4.ok
    assert cmd4.value[
        "special_case"
    ] is True
    # --------------------------------------------------------
    # Angelic module
    # --------------------------------------------------------
    encoded = kernel.RUN(
        "ANGELIC.ENCODE",
        "ABC",
    )
    assert encoded.ok
    verified = kernel.RUN(
        "ANGELIC.VERIFY",
        "ABC",
    )
    assert verified.ok
    assert verified.value is True
    checksum = kernel.RUN(
        "ANGELIC.CHECKSUM",
        "ABC",
    )
    assert checksum.ok
    assert isinstance(
        checksum.value,
        str,
    )
    # --------------------------------------------------------
    # Query
    # --------------------------------------------------------
    assert kernel.QUERY(
        "kernel.version"
    ) == "1112"
    assert kernel.QUERY(
        "CMD4"
    )["registered"] is True
    assert kernel.QUERY(
        "module.angelic_cipher"
    )["registered"] is True
    # --------------------------------------------------------
    # Explicit passthrough
    # --------------------------------------------------------
    passed = kernel.PASSTHROUGH(
        kernel.RUN(
            "ANGELIC.VERIFY",
            "ABC",
        )
    )
    assert passed is True
    # --------------------------------------------------------
    # Integrity exists
    # --------------------------------------------------------
    digest = kernel.integrity()
    assert isinstance(
        digest,
        str,
    )
    assert len(digest) == 64
    # --------------------------------------------------------
    # Trace exists
    # --------------------------------------------------------
    assert len(kernel.trace) > 0
    return True
# ============================================================
# DEMO
# ============================================================
def demo() -> None:
    kernel = create_kernel()
    print("=" * 64)
    print("STAGE 1112 — SELF-STATE KERNEL")
    print("=" * 64)
    # --------------------------------------------------------
    # Establish state
    # --------------------------------------------------------
    kernel.SELF.SET(
        "thermal.temperature",
        145.2,
    )
    kernel.SELF.SET(
        "geometry.thickness",
        8.6,
    )
    kernel.SELF.SET(
        "geometry.target_thickness",
        8.0,
    )
    # --------------------------------------------------------
    # SELF.GET
    # --------------------------------------------------------
    print("\nSELF.GET thermal:")
    print(
        kernel.SELF.GET(
            "thermal"
        )
    )
    print("\nSELF.GET geometry:")
    print(
        kernel.SELF.GET(
            "geometry"
        )
    )
    # --------------------------------------------------------
    # Special-case query
    # --------------------------------------------------------
    print("\nSPECIAL_CASE:")
    special = kernel.RUN(
        "SPECIAL_CASE"
    )
    print(
        json.dumps(
            special.value,
            indent=2,
            ensure_ascii=False,
        )
    )
    # --------------------------------------------------------
    # Conditional dispatch
    # --------------------------------------------------------
    print("\nIF:")
    conditional = kernel.IF(
        special.value["special_case"],
        "CMD4",
    )
    print(
        conditional.value
    )
    # --------------------------------------------------------
    # Angelic cipher
    # --------------------------------------------------------
    print("\nANGELIC.ENCODE:")
    encoded = kernel.RUN(
        "ANGELIC.ENCODE",
        "ABC",
    )
    print(
        encoded.value
    )
    print("\nANGELIC.VERIFY:")
    verified = kernel.RUN(
        "ANGELIC.VERIFY",
        "ABC",
    )
    print(
        verified.value
    )
    # --------------------------------------------------------
    # Explicit passthrough
    # --------------------------------------------------------
    print("\nPASSTHROUGH:")
    passed = kernel.PASSTHROUGH(
        verified
    )
    print(
        passed
    )
    # --------------------------------------------------------
    # Query
    # --------------------------------------------------------
    print("\nQUERY CMD4:")
    print(
        kernel.QUERY(
            "CMD4"
        )
    )
    # --------------------------------------------------------
    # Integrity
    # --------------------------------------------------------
    print("\nINTEGRITY:")
    print(
        kernel.integrity()
    )
    # --------------------------------------------------------
    # Trace
    # --------------------------------------------------------
    print("\nTRACE:")
    for record in kernel.trace:
        print(
            f"[{record.sequence:04d}] "
            f"{record.operation:<22} "
            f"{record.target}"
        )
# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    if not self_test():
        raise SystemExit(
            "SELF-TEST FAILED"
        )
    print(
        "SELF-TEST PASSED"
    )
    demo()
