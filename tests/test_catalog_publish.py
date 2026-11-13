import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from bcp_sdk.models.schemas.shopping.catalog_publish import (
    Catalog,
    ErrorResponse,
    Identifier,
    PublishProduct,
    PublishResponse,
    PublishVariant,
    ReplaceRequest,
    Revision,
    UpdateRequest,
)

FIXTURES = Path(__file__).parent / "fixtures" / "catalog_publish"
CAPABILITY = "br.dev.bcp.shopping.catalog.publish"


def document(name, kind="valid"):
    return json.loads(
        (FIXTURES / kind / f"catalog-publish-{name}.json").read_text(encoding="utf-8")
    )


@pytest.mark.parametrize(
    "name,model",
    [
        ("replace", ReplaceRequest),
        ("empty", ReplaceRequest),
        ("options", ReplaceRequest),
        ("update", UpdateRequest),
        ("snapshot", Catalog),
        ("response", PublishResponse),
    ],
)
def test_official_valid_fixtures_round_trip(name, model):
    payload = document(name)
    parsed = model.model_validate(payload)
    assert parsed.model_dump(mode="json", by_alias=True, exclude_unset=True) == payload


@pytest.mark.parametrize(
    "path", sorted((FIXTURES / "invalid").glob("*.json")), ids=lambda p: p.stem
)
def test_official_structurally_invalid_fixtures_are_rejected(path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    model = (
        UpdateRequest
        if "upsert_products" in payload
        else Catalog
        if "ucp" in payload
        else ReplaceRequest
    )
    with pytest.raises(ValidationError):
        model.model_validate(payload)


def test_official_error_fixture_uses_the_existing_generic_error_model():
    parsed = ErrorResponse.model_validate(document("error"))
    assert parsed.root.ucp.root.status == "error"
    assert (
        parsed.root.model_dump(mode="json")["messages"][0]["code"] == "catalog_price_range_mismatch"
    )


@pytest.mark.parametrize("field", ["id", "title", "description", "price_range", "variants"])
@pytest.mark.parametrize("invalid", ["missing", "null"])
def test_product_inherits_required_nonnullable_fields(field, invalid):
    product = document("replace")["products"][0]
    if invalid == "missing":
        del product[field]
    else:
        product[field] = None
    with pytest.raises(ValidationError):
        PublishProduct.model_validate(product)


@pytest.mark.parametrize("field", ["id", "title", "description", "price", "ncm"])
@pytest.mark.parametrize("invalid", ["missing", "null"])
def test_variant_inherits_required_nonnullable_fields(field, invalid):
    variant = document("replace")["products"][0]["variants"][0]
    if invalid == "missing":
        del variant[field]
    else:
        variant[field] = None
    with pytest.raises(ValidationError):
        PublishVariant.model_validate(variant)


def test_product_requires_a_variant_but_catalog_can_be_empty():
    payload = document("replace")
    payload["products"][0]["variants"] = []
    with pytest.raises(ValidationError):
        ReplaceRequest.model_validate(payload)
    payload["products"] = []
    assert ReplaceRequest.model_validate(payload).products.root == []


@pytest.mark.parametrize("title", ["", " ", "\t\n", "\u00a0"])
@pytest.mark.parametrize("level", ["product", "variant"])
def test_publication_titles_require_visible_text(title, level):
    payload = document("replace")
    product = payload["products"][0]
    target = product if level == "product" else product["variants"][0]
    target["title"] = title
    with pytest.raises(ValidationError):
        ReplaceRequest.model_validate(payload)


@pytest.mark.parametrize(
    "value",
    [
        "",
        " id",
        "id ",
        "seller id",
        "id\tvalue",
        "id\n",
        "id\rvalue",
        "id\u00a0value",
        "id\u2003value",
    ],
)
def test_identifiers_reject_whitespace_without_trimming(value):
    with pytest.raises(ValidationError):
        Identifier.model_validate(value)


@pytest.mark.parametrize("level", ["product", "variant", "catalog", "merchant", "removal"])
def test_identifier_constraint_propagates_to_every_publication_reference(level):
    if level in {"catalog", "merchant"}:
        payload = document("response")
        payload[f"{level}_id"] = "bad id"
        model = PublishResponse
    elif level == "removal":
        payload = document("update")
        payload["remove_product_ids"] = ["bad id"]
        model = UpdateRequest
    else:
        payload = document("replace")
        target = payload["products"][0]
        if level == "variant":
            target = target["variants"][0]
        target["id"] = "bad id"
        model = ReplaceRequest
    with pytest.raises(ValidationError):
        model.model_validate(payload)


def test_identifiers_and_revisions_keep_frozen_root_model_behavior():
    identity = Identifier.model_validate("gid://loja.example/Variant/caneca-250")
    assert identity.root == "gid://loja.example/Variant/caneca-250"
    assert hash(identity)
    with pytest.raises(ValidationError):
        identity.root = "changed"
    revision = Revision.model_validate(1)
    with pytest.raises(ValidationError):
        revision.root = 2


@pytest.mark.parametrize("ncm", ["6912", "691200000", "69120000\n", "6912.00.00", "abcdefgh", None])
def test_publication_ncm_requires_exactly_eight_digits(ncm):
    variant = document("replace")["products"][0]["variants"][0]
    variant["ncm"] = ncm
    with pytest.raises(ValidationError):
        PublishVariant.model_validate(variant)


@pytest.mark.parametrize("price", [-1, 1.5])
def test_invalid_prices_are_rejected(price):
    variant = document("replace")["products"][0]["variants"][0]
    variant["price"]["amount"] = price
    with pytest.raises(ValidationError):
        PublishVariant.model_validate(variant)


def test_zero_price_is_valid():
    variant = document("replace")["products"][0]["variants"][0]
    variant["price"]["amount"] = 0
    assert PublishVariant.model_validate(variant).price.amount.root == 0


@pytest.mark.parametrize("field", ["version", "status", "capabilities"])
def test_receipt_requires_complete_metadata(field):
    payload = document("response")
    del payload["ucp"][field]
    with pytest.raises(ValidationError):
        PublishResponse.model_validate(payload)


@pytest.mark.parametrize("declarations", [None, [], [{"version": "2026-10-04"}] * 2])
@pytest.mark.parametrize("name,model", [("response", PublishResponse), ("snapshot", Catalog)])
def test_publication_capability_is_required_exactly_once(declarations, name, model):
    payload = document(name)
    if declarations is None:
        del payload["ucp"]["capabilities"][CAPABILITY]
    else:
        payload["ucp"]["capabilities"][CAPABILITY] = declarations
    with pytest.raises(ValidationError):
        model.model_validate(payload)


def test_receipt_rejects_error_status():
    payload = document("response")
    payload["ucp"]["status"] = "error"
    with pytest.raises(ValidationError):
        PublishResponse.model_validate(payload)


@pytest.mark.parametrize("value", [0, -1, None])
def test_update_requires_a_positive_base_revision(value):
    payload = document("update")
    payload["base_revision"] = value
    with pytest.raises(ValidationError):
        UpdateRequest.model_validate(payload)


def test_creation_revision_is_nullable_but_must_be_present():
    payload = document("replace")
    assert ReplaceRequest.model_validate(payload).base_revision is None
    del payload["base_revision"]
    with pytest.raises(ValidationError):
        ReplaceRequest.model_validate(payload)


def test_explicit_removals_must_be_unique():
    payload = document("update")
    payload["remove_product_ids"] = ["product-1", "product-1"]
    with pytest.raises(ValidationError):
        UpdateRequest.model_validate(payload)


def test_optional_product_variant_and_extra_fields_are_preserved():
    payload = document("options")
    product = payload["products"][0]
    product["categories"] = [{"value": "Canecas", "taxonomy": "merchant"}]
    product["metadata"] = {"campaign": "spring", "nested": [1, "two"]}
    product["extra_field"] = {"preserved": True}
    product["variants"][0]["sku"] = "SKU-250"
    expected = copy.deepcopy(payload)
    parsed = ReplaceRequest.model_validate(payload)
    assert parsed.model_dump(mode="json", by_alias=True, exclude_unset=True) == expected
