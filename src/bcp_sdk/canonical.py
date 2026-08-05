import json
import math
from collections.abc import Mapping, Sequence
from typing import Any


def canonicalize(obj: Mapping[str, Any]) -> bytes:
    """Serializes obj to JCS (RFC 8785) canonical JSON bytes, ready to sign/verify."""
    return _encode(obj).encode("utf-8")


def _encode(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return _encode_number(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, Mapping):
        return _encode_object(value)
    if isinstance(value, Sequence):
        return "[" + ",".join(_encode(item) for item in value) + "]"
    msg = f"cannot canonicalize value of type {type(value).__name__}"
    raise TypeError(msg)


def _encode_object(value: Mapping[str, Any]) -> str:
    for key in value:
        if not isinstance(key, str):
            msg = f"object keys must be str, got {type(key).__name__}"
            raise TypeError(msg)
    items = sorted(value.items(), key=lambda kv: _utf16_code_units(kv[0]))
    body = ",".join(f"{json.dumps(key, ensure_ascii=False)}:{_encode(val)}" for key, val in items)
    return "{" + body + "}"


def _utf16_code_units(value: str) -> tuple[int, ...]:
    """Sort key matching RFC 8785 key ordering: UTF-16 code unit order, not code point order."""
    encoded = value.encode("utf-16-be")
    return tuple(int.from_bytes(encoded[i : i + 2], "big") for i in range(0, len(encoded), 2))


def _encode_number(value: float) -> str:
    if math.isnan(value) or math.isinf(value):
        msg = "NaN and Infinity are not representable in JSON"
        raise ValueError(msg)
    if value == 0:
        return "0"
    sign = "-" if value < 0 else ""
    digits, point = _shortest_digits(abs(value))
    k = len(digits)
    if k <= point <= 21:
        return sign + digits + "0" * (point - k)
    if 0 < point <= 21:
        return sign + digits[:point] + "." + digits[point:]
    if -6 < point <= 0:
        return sign + "0." + "0" * -point + digits
    exponent = point - 1
    mantissa = digits[0] + ("." + digits[1:] if k > 1 else "")
    exp_sign = "+" if exponent >= 0 else "-"
    return f"{sign}{mantissa}e{exp_sign}{abs(exponent)}"


def _shortest_digits(value: float) -> tuple[str, int]:
    """Extracts the shortest round-trip digit string and decimal point position from repr().

    Returns (digits, n) such that value == 0.<digits> * 10**n, matching the (s, k, n)
    triple of ECMA-262 Number::toString: digits has no leading/trailing zero and is the
    shortest sequence that round-trips to the same float (guaranteed by Python's repr).
    """
    text = repr(value)
    mantissa, _, exp_text = text.partition("e")
    exponent = int(exp_text) if exp_text else 0
    int_part, _, frac_part = mantissa.partition(".")
    all_digits = int_part + frac_part
    point = len(int_part) + exponent

    stripped = all_digits.lstrip("0")
    point -= len(all_digits) - len(stripped)
    stripped = stripped.rstrip("0")
    if not stripped:
        return "0", 1
    return stripped, point
