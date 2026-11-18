# -*- coding: utf-8 -*-
"""
Angelic Cipher calculation module (v0.2)

Independently usable calculation authority for character/sequence encoding.
This module owns mapping profiles, encoding/decoding rules, checksums, and
calculation provenance. It does **not** own kernel state semantics.

Important:
- Current A–Z mappings and AB/CD pair defaults are an **experimental legacy**
  profile. They are not presented as historically authoritative angelic cipher
  rules.
- The pairs table is **not** used by the legacy character-sum encoder. Pair
  processing is a separately declared, tested rule profile.
- No undocumented mappings are invented or presented as canonical.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
import copy
import hashlib
import json


# ---------------------------------------------------------------------------
# Version & identity constants
# ---------------------------------------------------------------------------

AUTHORITY = "angelic-cipher"
AUTHORITY_VERSION = "0.2.0"
RESULT_CONTRACT_VERSION = "1.0.0"

# Explicit profile identifiers
PROFILE_LEGACY_EXPERIMENTAL = "legacy-experimental"
PROFILE_LEGACY_EXPERIMENTAL_VERSION = "1.0.0"
MAPPING_ID_LEGACY_AZ = "legacy-az-hebrewish-v1"

# Normalization policies (declared; no silent BabelCodec divergence)
NORM_LEGACY_UPPER = "legacy-upper-ascii"
# Future: "nfc", "nfd", "identity" — not implemented here without BabelCodec

# Character eligibility for legacy profile
LEGACY_ELIGIBLE = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ ")


class CalculationStatus(str, Enum):
    VALID = "valid"
    UNMAPPED_INPUT = "unmapped_input"
    AMBIGUOUS_MAPPING = "ambiguous_mapping"
    NON_INVERTIBLE = "non_invertible"
    NORMALIZATION_MISMATCH = "normalization_mismatch"
    UNSUPPORTED_OPERATION = "unsupported_operation"
    INVALID_INPUT = "invalid_input"
    COLLISION = "collision"


class AngelicCipherError(Exception):
    """Structured calculation error (distinct from kernel KernelError)."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "CIPHER_ERROR",
        status: CalculationStatus = CalculationStatus.INVALID_INPUT,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status
        self.details = details or {}


# ---------------------------------------------------------------------------
# Legacy experimental mapping (preserved exactly; not canonical authority)
# ---------------------------------------------------------------------------

DEFAULT_GEMATRIA: Dict[str, int] = {
    "A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6, "G": 7, "H": 8, "I": 9, "J": 10,
    "K": 20, "L": 30, "M": 40, "N": 50, "O": 60, "P": 70, "Q": 80, "R": 90, "S": 100,
    "T": 200, "U": 300, "V": 400, "W": 500, "X": 600, "Y": 700, "Z": 800,
}

# Experimental pair table — NOT consumed by the legacy character-sum encoder.
# Exposed for the separate pair-profile experiments only.
DEFAULT_ANGELIC_PAIRS: Dict[str, str] = {"AB": "11", "CD": "22"}


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


# ---------------------------------------------------------------------------
# Result contract (versioned, JSON-serializable)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CipherResult:
    """Versioned calculation result contract.

    Distinguishes valid calculation from unmapped, ambiguous, non-invertible,
    normalization mismatch, and unsupported operations. Never uses zero as a
    substitute for missing/invalid values.
    """

    authority: str
    authority_version: str
    profile_id: str
    profile_version: str
    mapping_id: str
    operation: str
    input: Any
    normalization_profile: str
    status: str  # CalculationStatus value
    encoded_sequence: Optional[List[int]] = None
    decoded_text: Optional[str] = None
    total: Optional[int] = None
    checksum: Optional[str] = None
    ok: bool = False
    warnings: Tuple[str, ...] = ()
    errors: Tuple[str, ...] = ()
    provenance: Dict[str, Any] = field(default_factory=dict)
    result_contract_version: str = RESULT_CONTRACT_VERSION

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # Ensure tuples become lists for JSON
        d["warnings"] = list(self.warnings)
        d["errors"] = list(self.errors)
        return d

    def to_json(self) -> str:
        return _canonical_json(self.to_dict())

    def legacy_compat(self) -> Dict[str, Any]:
        """Compatibility adapter for pre-v0.2 call sites expecting old shapes."""
        if self.operation == "encode":
            return {
                "input": self.input,
                "codes": list(self.encoded_sequence or []),
                "checksum": self.total if self.total is not None else 0,
                # Extended fields (non-breaking)
                "_cipher_result": self.to_dict(),
            }
        if self.operation == "decode":
            return self.decoded_text if self.decoded_text is not None else ""
        if self.operation == "verify":
            return {
                "ok": self.ok,
                "original": self.input,
                "decoded": self.decoded_text,
                "codes": list(self.encoded_sequence or []),
                "_cipher_result": self.to_dict(),
            }
        if self.operation == "checksum":
            return int(self.total) if self.total is not None else 0
        return self.to_dict()


# ---------------------------------------------------------------------------
# Profile definition
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MappingProfile:
    profile_id: str
    profile_version: str
    mapping_id: str
    char_map: Mapping[str, int]
    inverse_map: Mapping[int, str]
    eligible_chars: frozenset
    normalization: str
    space_code: Optional[int]  # 0 in legacy; None = spaces not allowed
    case_policy: str  # "upper" | "preserve" | "lower"
    description: str
    experimental: bool = True

    def validate(self) -> List[str]:
        """Return list of validation problems (empty = ok)."""
        problems: List[str] = []
        seen_vals: Dict[int, str] = {}
        for k, v in self.char_map.items():
            if not isinstance(k, str) or len(k) != 1:
                problems.append(f"Invalid key: {k!r}")
            if not isinstance(v, int):
                problems.append(f"Non-int value for {k}: {v!r}")
            elif v in seen_vals:
                problems.append(f"Collision: {k} and {seen_vals[v]} both map to {v}")
            else:
                seen_vals[v] = k
        # inverse consistency
        for code, ch in self.inverse_map.items():
            if self.char_map.get(ch) != code:
                problems.append(f"Inverse inconsistency: {code} -> {ch}")
        return problems


def build_legacy_experimental_profile(
    gematria: Optional[Mapping[str, int]] = None,
) -> MappingProfile:
    cmap = dict(gematria or DEFAULT_GEMATRIA)
    inv = {v: k for k, v in cmap.items()}
    return MappingProfile(
        profile_id=PROFILE_LEGACY_EXPERIMENTAL,
        profile_version=PROFILE_LEGACY_EXPERIMENTAL_VERSION,
        mapping_id=MAPPING_ID_LEGACY_AZ,
        char_map=cmap,
        inverse_map=inv,
        eligible_chars=LEGACY_ELIGIBLE,
        normalization=NORM_LEGACY_UPPER,
        space_code=0,
        case_policy="upper",
        description=(
            "Experimental legacy A–Z character-sum mapping preserved from "
            "SELF-State Kernel v0.1.x. Not historically authoritative."
        ),
        experimental=True,
    )


# ---------------------------------------------------------------------------
# Normalization boundary (declared; no silent different behavior)
# ---------------------------------------------------------------------------

def apply_normalization(text: str, policy: str) -> Tuple[str, List[str]]:
    """Apply declared normalization. Returns (normalized, warnings)."""
    warnings: List[str] = []
    if policy == NORM_LEGACY_UPPER:
        # Legacy: .upper() only. Non-ASCII letters become multi-char or stay;
        # we do not claim NFC/NFD. Characters outside eligible set are left for
        # the encoder to reject as unmapped.
        return text.upper(), warnings
    if policy == "identity":
        return text, warnings
    raise AngelicCipherError(
        f"Unsupported normalization policy: {policy}",
        code="NORM_UNSUPPORTED",
        status=CalculationStatus.UNSUPPORTED_OPERATION,
    )


# ---------------------------------------------------------------------------
# Core calculator
# ---------------------------------------------------------------------------

class AngelicCipher:
    """Independently usable Angelic Cipher calculator.

    Does not require a Kernel instance.
    """

    def __init__(
        self,
        profile: Optional[MappingProfile] = None,
        *,
        gematria: Optional[Mapping[str, int]] = None,
        pairs: Optional[Mapping[str, str]] = None,
        legacy_compat: bool = True,
    ) -> None:
        if profile is not None:
            self.profile = profile
        else:
            self.profile = build_legacy_experimental_profile(gematria)
        self.pairs = dict(pairs or DEFAULT_ANGELIC_PAIRS)
        self.legacy_compat = legacy_compat
        problems = self.profile.validate()
        if problems:
            raise AngelicCipherError(
                "Profile validation failed: " + "; ".join(problems),
                code="PROFILE_INVALID",
                status=CalculationStatus.COLLISION,
                details={"problems": problems},
            )
        # Public aliases for backward compatibility
        self.gematria = dict(self.profile.char_map)

    @property
    def profile_id(self) -> str:
        return self.profile.profile_id

    @property
    def profile_version(self) -> str:
        return self.profile.profile_version

    def _base_result(
        self,
        operation: str,
        input_value: Any,
        *,
        status: CalculationStatus,
        ok: bool = False,
        encoded_sequence: Optional[List[int]] = None,
        decoded_text: Optional[str] = None,
        total: Optional[int] = None,
        warnings: Sequence[str] = (),
        errors: Sequence[str] = (),
        extra_prov: Optional[Dict[str, Any]] = None,
    ) -> CipherResult:
        prov: Dict[str, Any] = {
            "authority": AUTHORITY,
            "authority_version": AUTHORITY_VERSION,
            "profile_id": self.profile.profile_id,
            "profile_version": self.profile.profile_version,
            "mapping_id": self.profile.mapping_id,
            "experimental": self.profile.experimental,
        }
        if extra_prov:
            prov.update(extra_prov)
        # Deterministic checksum of the calculation identity
        identity = {
            "op": operation,
            "input": input_value,
            "seq": encoded_sequence,
            "decoded": decoded_text,
            "total": total,
            "status": status.value,
            "profile": self.profile.profile_id,
            "mapping": self.profile.mapping_id,
        }
        csum = hashlib.sha256(_canonical_json(identity).encode("utf-8")).hexdigest()[:16]
        return CipherResult(
            authority=AUTHORITY,
            authority_version=AUTHORITY_VERSION,
            profile_id=self.profile.profile_id,
            profile_version=self.profile.profile_version,
            mapping_id=self.profile.mapping_id,
            operation=operation,
            input=input_value,
            normalization_profile=self.profile.normalization,
            status=status.value,
            encoded_sequence=encoded_sequence,
            decoded_text=decoded_text,
            total=total,
            checksum=csum,
            ok=ok,
            warnings=tuple(warnings),
            errors=tuple(errors),
            provenance=prov,
        )

    def encode(self, text: str, *, strict: bool = True) -> CipherResult:
        if not isinstance(text, str):
            r = self._base_result(
                "encode",
                text,
                status=CalculationStatus.INVALID_INPUT,
                errors=[f"encode requires str, got {type(text).__name__}"],
            )
            if strict:
                raise AngelicCipherError(r.errors[0], code="TYPE", status=r.status)  # type: ignore[index]
            return r

        normalized, norm_warnings = apply_normalization(text, self.profile.normalization)
        codes: List[int] = []
        unmapped: List[str] = []
        for ch in normalized:
            if ch == " " and self.profile.space_code is not None:
                codes.append(self.profile.space_code)
                continue
            if ch not in self.profile.char_map:
                unmapped.append(ch)
                continue
            codes.append(self.profile.char_map[ch])

        if unmapped:
            r = self._base_result(
                "encode",
                text,
                status=CalculationStatus.UNMAPPED_INPUT,
                encoded_sequence=codes if codes else None,
                warnings=norm_warnings,
                errors=[f"Unmapped character(s): {unmapped!r}"],
                extra_prov={"unmapped": unmapped, "normalized": normalized},
            )
            if strict:
                raise AngelicCipherError(
                    r.errors[0],  # type: ignore[index]
                    code="UNMAPPED",
                    status=CalculationStatus.UNMAPPED_INPUT,
                    details={"unmapped": unmapped},
                )
            return r

        total = sum(codes)
        return self._base_result(
            "encode",
            text,
            status=CalculationStatus.VALID,
            ok=True,
            encoded_sequence=codes,
            total=total,
            warnings=norm_warnings,
            extra_prov={"normalized": normalized},
        )

    def decode(self, codes: Sequence[int], *, strict: bool = True) -> CipherResult:
        if not isinstance(codes, (list, tuple)):
            r = self._base_result(
                "decode",
                codes,
                status=CalculationStatus.INVALID_INPUT,
                errors=[f"decode requires sequence of int, got {type(codes).__name__}"],
            )
            if strict:
                raise AngelicCipherError(r.errors[0], code="TYPE", status=r.status)  # type: ignore[index]
            return r

        out: List[str] = []
        unknown: List[int] = []
        for c in codes:
            if not isinstance(c, int) or isinstance(c, bool):
                r = self._base_result(
                    "decode",
                    codes,
                    status=CalculationStatus.INVALID_INPUT,
                    errors=[f"Non-integer code: {c!r}"],
                )
                if strict:
                    raise AngelicCipherError(r.errors[0], code="TYPE", status=r.status)  # type: ignore[index]
                return r
            if self.profile.space_code is not None and c == self.profile.space_code:
                out.append(" ")
                continue
            if c not in self.profile.inverse_map:
                unknown.append(c)
                continue
            out.append(self.profile.inverse_map[c])

        if unknown:
            r = self._base_result(
                "decode",
                list(codes),
                status=CalculationStatus.NON_INVERTIBLE,
                decoded_text="".join(out) if out else None,
                errors=[f"Unmapped code(s): {unknown!r}"],
                extra_prov={"unknown_codes": unknown},
            )
            if strict:
                raise AngelicCipherError(
                    r.errors[0],  # type: ignore[index]
                    code="UNMAPPED_CODE",
                    status=CalculationStatus.NON_INVERTIBLE,
                    details={"unknown_codes": unknown},
                )
            return r

        text = "".join(out)
        return self._base_result(
            "decode",
            list(codes),
            status=CalculationStatus.VALID,
            ok=True,
            encoded_sequence=list(codes),
            decoded_text=text,
        )

    def verify(self, text: str, *, strict: bool = True) -> CipherResult:
        try:
            enc = self.encode(text, strict=True)
        except AngelicCipherError as exc:
            r = self._base_result(
                "verify",
                text,
                status=exc.status,
                ok=False,
                errors=[exc.message],
            )
            if strict:
                raise
            return r
        assert enc.encoded_sequence is not None
        dec = self.decode(enc.encoded_sequence, strict=True)
        match = dec.decoded_text == (text.upper() if self.profile.case_policy == "upper" else text)
        return self._base_result(
            "verify",
            text,
            status=CalculationStatus.VALID if match else CalculationStatus.NON_INVERTIBLE,
            ok=match,
            encoded_sequence=enc.encoded_sequence,
            decoded_text=dec.decoded_text,
            total=enc.total,
            warnings=enc.warnings,
            errors=() if match else ("round-trip mismatch",),
        )

    def checksum(self, text: str, *, strict: bool = True) -> CipherResult:
        enc = self.encode(text, strict=strict)
        if not enc.ok:
            return enc  # already structured
        return self._base_result(
            "checksum",
            text,
            status=CalculationStatus.VALID,
            ok=True,
            encoded_sequence=enc.encoded_sequence,
            total=enc.total,
            warnings=enc.warnings,
        )

    # ---- Pair processing (separate declared profile; not used by legacy encode) ----

    def encode_with_pairs(self, text: str, *, strict: bool = True) -> CipherResult:
        """Experimental pair-aware encoding.

        Longest-match greedy left-to-right over self.pairs, then fall back to
        character mapping. This is a **separately declared** rule profile and
        is not the legacy character-sum algorithm.
        """
        if not isinstance(text, str):
            r = self._base_result(
                "encode_with_pairs",
                text,
                status=CalculationStatus.INVALID_INPUT,
                errors=[f"encode_with_pairs requires str, got {type(text).__name__}"],
            )
            if strict:
                raise AngelicCipherError(r.errors[0], code="TYPE", status=r.status)  # type: ignore[index]
            return r

        normalized, norm_warnings = apply_normalization(text, self.profile.normalization)
        # Sort pairs longest first for greedy match
        pair_keys = sorted(self.pairs.keys(), key=len, reverse=True)
        codes: List[Any] = []  # may contain str tokens from pairs or int codes
        i = 0
        unmapped: List[str] = []
        while i < len(normalized):
            matched = False
            for pk in pair_keys:
                if normalized.startswith(pk, i):
                    codes.append(self.pairs[pk])  # string token as declared
                    i += len(pk)
                    matched = True
                    break
            if matched:
                continue
            ch = normalized[i]
            if ch == " " and self.profile.space_code is not None:
                codes.append(self.profile.space_code)
                i += 1
                continue
            if ch in self.profile.char_map:
                codes.append(self.profile.char_map[ch])
                i += 1
                continue
            unmapped.append(ch)
            i += 1

        if unmapped:
            r = self._base_result(
                "encode_with_pairs",
                text,
                status=CalculationStatus.UNMAPPED_INPUT,
                errors=[f"Unmapped character(s): {unmapped!r}"],
                warnings=norm_warnings,
                extra_prov={"unmapped": unmapped, "partial_codes": codes},
            )
            if strict:
                raise AngelicCipherError(
                    r.errors[0],  # type: ignore[index]
                    code="UNMAPPED",
                    status=CalculationStatus.UNMAPPED_INPUT,
                )
            return r

        # total only defined over integer codes
        int_codes = [c for c in codes if isinstance(c, int)]
        total = sum(int_codes) if int_codes else None
        pair_warnings = list(norm_warnings) + [
            "pair profile is experimental; encoded_sequence left null; see provenance.tokens",
        ]
        return self._base_result(
            "encode_with_pairs",
            text,
            status=CalculationStatus.VALID,
            ok=True,
            encoded_sequence=None,  # mixed; see provenance
            total=total,
            warnings=pair_warnings,
            extra_prov={
                "normalized": normalized,
                "tokens": codes,
                "pair_keys": list(self.pairs.keys()),
            },
        )


# ---------------------------------------------------------------------------
# Kernel module adapter (preserves ANGELIC.* command names)
# ---------------------------------------------------------------------------

class AngelicCipherModule:
    """Kernel-attachable adapter around AngelicCipher.

    Preserves existing command names:
      ANGELIC.ENCODE / DECODE / VERIFY / CHECKSUM

    Return shapes:
    - When legacy_compat=True (default), commands return the pre-v0.2 shapes
      with an additional `_cipher_result` key carrying the full contract.
    - The full CipherResult is always available via the independent AngelicCipher API.
    """

    def __init__(
        self,
        gematria: Optional[Mapping[str, int]] = None,
        pairs: Optional[Mapping[str, str]] = None,
        *,
        legacy_compat: bool = True,
        profile: Optional[MappingProfile] = None,
    ) -> None:
        self._calc = AngelicCipher(
            profile=profile,
            gematria=gematria,
            pairs=pairs,
            legacy_compat=legacy_compat,
        )
        self.legacy_compat = legacy_compat
        # Public surface expected by existing tests / imports
        self.gematria = dict(self._calc.gematria)
        self.pairs = dict(self._calc.pairs)

    @property
    def calculator(self) -> AngelicCipher:
        return self._calc

    def attach(self, kernel: Any) -> None:
        kernel.register_command("ANGELIC.ENCODE", self.encode)
        kernel.register_command("ANGELIC.DECODE", self.decode)
        kernel.register_command("ANGELIC.VERIFY", self.verify)
        kernel.register_command("ANGELIC.CHECKSUM", self.checksum)

    def encode(self, text: str) -> Any:
        try:
            result = self._calc.encode(text, strict=True)
        except AngelicCipherError as exc:
            # Re-raise as a value error recognizable by kernel dispatch
            from _kernel_impl import KernelValueError  # local import to avoid cycle at module load
            raise KernelValueError(exc.message) from exc
        if self.legacy_compat:
            return result.legacy_compat()
        return result.to_dict()

    def decode(self, codes: Sequence[int]) -> Any:
        try:
            result = self._calc.decode(codes, strict=True)
        except AngelicCipherError as exc:
            from _kernel_impl import KernelValueError
            raise KernelValueError(exc.message) from exc
        if self.legacy_compat:
            return result.legacy_compat()
        return result.to_dict()

    def verify(self, text: str) -> Any:
        try:
            result = self._calc.verify(text, strict=True)
        except AngelicCipherError as exc:
            from _kernel_impl import KernelValueError
            raise KernelValueError(exc.message) from exc
        if self.legacy_compat:
            return result.legacy_compat()
        return result.to_dict()

    def checksum(self, text: str) -> Any:
        try:
            result = self._calc.checksum(text, strict=True)
        except AngelicCipherError as exc:
            from _kernel_impl import KernelValueError
            raise KernelValueError(exc.message) from exc
        if self.legacy_compat:
            return result.legacy_compat()
        return result.to_dict()
