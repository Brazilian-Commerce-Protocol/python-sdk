import math

import pytest

from bcp_sdk.canonical import canonicalize


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (2.0, b"2"),
        (100, b"100"),
        (1e21, b"1e+21"),
        (1e-7, b"1e-7"),
        (123.456, b"123.456"),
        (0.0001234, b"0.0001234"),
        (-0.0, b"0"),
        (-2.5, b"-2.5"),
    ],
)
def test_number_encoding_matches_rfc8785_examples(value: object, expected: bytes) -> None:
    assert canonicalize({"v": value}) == b'{"v":' + expected + b"}"


def test_object_keys_sort_by_utf16_code_unit_order() -> None:
    assert (
        canonicalize({"b": 1, "a": 2, "c": {"z": 1, "y": 2}}) == b'{"a":2,"b":1,"c":{"y":2,"z":1}}'
    )


def test_non_ascii_strings_are_not_escaped() -> None:
    assert canonicalize({"nome": "acao"}) == b'{"nome":"acao"}'
    assert "é".encode() in canonicalize({"e": "é"})


def test_control_characters_are_escaped() -> None:
    assert canonicalize({"s": "a\nb"}) == b'{"s":"a\\nb"}'


def test_list_and_scalar_types() -> None:
    assert canonicalize({"list": [1, 2, "x", True, False, None]}) == (
        b'{"list":[1,2,"x",true,false,null]}'
    )


def test_same_document_different_key_order_yields_identical_bytes() -> None:
    doc_a = {"cnpj": "123", "endpoint": "http://x", "capabilities": ["a", "b"]}
    doc_b = {"capabilities": ["a", "b"], "endpoint": "http://x", "cnpj": "123"}
    assert canonicalize(doc_a) == canonicalize(doc_b)


def test_nan_and_infinity_are_rejected() -> None:
    with pytest.raises(ValueError, match="not representable"):
        canonicalize({"v": math.nan})
    with pytest.raises(ValueError, match="not representable"):
        canonicalize({"v": math.inf})


def test_non_string_keys_are_rejected() -> None:
    with pytest.raises(TypeError):
        canonicalize({1: "a"})  # ty: ignore[invalid-argument-type]


def test_returns_bytes() -> None:
    assert isinstance(canonicalize({"a": 1}), bytes)
