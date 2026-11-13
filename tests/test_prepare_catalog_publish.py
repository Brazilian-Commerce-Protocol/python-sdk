import copy
import json

import pytest
from prepare_catalog_publish import SchemaSource, prepare_catalog_publish
from preprocess_schemas import preprocess_full_schema


def write_schema(directory, name, value):
    path = directory / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def example_schemas(tmp_path, reverse=False):
    raw = tmp_path / "raw"
    processed = tmp_path / "processed"
    definitions = {
        "publish_product": {
            "allOf": [
                {"$ref": "types/product.json"},
                {
                    "properties": {
                        "id": {"type": "string"},
                        "title": {"type": "string"},
                        "variants": {"type": "array"},
                    }
                },
            ]
        },
        "publish_variant": {
            "allOf": [
                {"$ref": "types/variant.json"},
                {
                    "required": ["ncm"],
                    "properties": {"id": {"type": "string"}, "title": {"type": "string"}},
                },
            ]
        },
        "metadata": {
            "allOf": [
                {"$ref": "../ucp.json#/$defs/response"},
                {"required": ["capabilities"], "properties": {"capabilities": {"type": "object"}}},
            ]
        },
        "metadata_alias": {"allOf": [{"$ref": "#/$defs/metadata"}]},
        "publish_response": {
            "properties": {
                "ucp": {"allOf": [{"$ref": "#/$defs/metadata_alias"}, {"required": ["status"]}]}
            }
        },
    }
    if reverse:
        definitions = dict(reversed(list(definitions.items())))
    original = {"$defs": definitions}
    write_schema(raw, "shopping/catalog_publish.json", original)
    write_schema(
        raw,
        "shopping/types/product.json",
        {
            "required": ["id", "title", "variants"],
            "properties": {"variants": {"$ref": "limits.json#/$defs/variants"}},
        },
    )
    write_schema(
        raw,
        "shopping/types/limits.json",
        {"$defs": {"variants": {"type": "array", "minItems": 2, "maxItems": 4}}},
    )
    write_schema(raw, "shopping/types/variant.json", {"required": ["id", "title", "price"]})
    write_schema(raw, "ucp.json", {"$defs": {"response": {"required": ["version"]}}})
    prepared = copy.deepcopy(original)
    preprocess_full_schema(prepared)
    path = write_schema(processed, "shopping/catalog_publish.json", prepared)
    return raw, processed, path


@pytest.mark.parametrize("reverse", [False, True])
def test_restores_inheritance_independently_of_definition_order(tmp_path, reverse):
    raw, processed, path = example_schemas(tmp_path, reverse)
    assert prepare_catalog_publish(processed, raw)
    definitions = json.loads(path.read_text())["$defs"]
    product = definitions["publish_product"]
    assert set(product["required"]) == {"id", "title", "variants"}
    assert product["properties"]["variants"]["minItems"] == 2
    assert product["properties"]["variants"]["maxItems"] == 4
    assert product["allOf"] == [{"$ref": "types/product.json"}]
    assert set(definitions["publish_variant"]["required"]) == {"id", "title", "ncm"}
    assert definitions["publish_variant"]["allOf"] == [{"$ref": "types/variant.json"}]
    ucp = definitions["publish_response"]["properties"]["ucp"]
    assert set(ucp["required"]) == {"status", "capabilities"}
    assert ucp["allOf"] == [{"$ref": "../ucp.json#/$defs/response"}]
    assert ucp["properties"]["capabilities"] == {"type": "object"}


def test_preparation_is_idempotent_and_leaves_pristine_schemas_unchanged(tmp_path):
    raw, processed, path = example_schemas(tmp_path)
    originals = {p: p.read_bytes() for p in raw.rglob("*.json")}
    prepare_catalog_publish(processed, raw)
    first = path.read_bytes()
    prepare_catalog_publish(processed, raw)
    assert path.read_bytes() == first
    assert {p: p.read_bytes() for p in raw.rglob("*.json")} == originals


def test_other_schemas_are_untouched_and_older_specs_are_supported(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    path = write_schema(tmp_path / "processed", "other.json", {"title": "Untouched"})
    before = path.read_bytes()
    assert not prepare_catalog_publish(tmp_path / "processed", raw)
    assert path.read_bytes() == before


def test_conflicting_array_bounds_fail_before_writing_output(tmp_path):
    raw, processed, path = example_schemas(tmp_path)
    original = json.loads((raw / "shopping/catalog_publish.json").read_text())
    original["$defs"]["publish_product"]["allOf"][1]["properties"]["variants"]["maxItems"] = 1
    write_schema(raw, "shopping/catalog_publish.json", original)
    before = path.read_bytes()
    with pytest.raises(ValueError, match="Incompatible array bounds"):
        prepare_catalog_publish(processed, raw)
    assert path.read_bytes() == before


@pytest.mark.parametrize("reference", ["missing.json", "types/product.json#/$defs/missing"])
def test_missing_references_fail_before_writing_output(tmp_path, reference):
    raw, processed, path = example_schemas(tmp_path)
    original = json.loads((raw / "shopping/catalog_publish.json").read_text())
    original["$defs"]["publish_product"]["allOf"][0]["$ref"] = reference
    write_schema(raw, "shopping/catalog_publish.json", original)
    before = path.read_bytes()
    with pytest.raises((OSError, ValueError)):
        prepare_catalog_publish(processed, raw)
    assert path.read_bytes() == before


@pytest.mark.parametrize("reference", ["https://example.org/schema.json", "../outside.json"])
def test_reference_resolution_never_fetches_remote_or_external_files(tmp_path, reference):
    with pytest.raises(ValueError, match=r"relative local|escapes"):
        SchemaSource(tmp_path).resolve(reference, tmp_path / "schema.json")


def test_reference_resolution_handles_escaped_json_pointer_tokens(tmp_path):
    path = write_schema(tmp_path, "schema.json", {"$defs": {"a/b~c": {"type": "string"}}})
    node, origin = SchemaSource(tmp_path).resolve("#/$defs/a~1b~0c", path)
    assert node == {"type": "string"}
    assert origin == path


def test_cycles_fail_explicitly(tmp_path):
    path = write_schema(tmp_path, "schema.json", {"$defs": {"cycle": {"$ref": "#/$defs/cycle"}}})
    source = SchemaSource(tmp_path)
    with pytest.raises(ValueError, match="Cyclic"):
        list(source.branches({"$ref": "#/$defs/cycle"}, path))
    with pytest.raises(ValueError, match="Cyclic"):
        source.flatten_local({"$ref": "#/$defs/cycle"}, path)
