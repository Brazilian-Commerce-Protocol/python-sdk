# Copyright 2026 BCP Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Restore catalog publication inheritance before Python model generation.

This BCP-specific step runs after the unchanged, vendored UCP preprocessor and
before datamodel-code-generator. The preprocessor's allOf and metadata flattening
can lose constraints needed by catalog.publish; repairing the intermediate schema
keeps the UCP source intact and avoids hand-editing generated Python models.

The pristine schemas supply the inheritance rules used to repair only
shopping/catalog_publish.json:

* Restore inherited required fields on redeclared product/variant properties,
  including identifiers and titles, and inherited array bounds such as the
  minimum of one variant. Fields that are not redeclared retain their typed
  base-model definitions, including price and description.
* Resolve nested local metadata references while preserving external inheritance,
  so publication receipts inherit the base model's required ucp.version field.
  External references retain their original document as the resolution base.

Required references that cannot be resolved stop generation. Specs without
catalog publication are left unchanged. Constraints discarded by the model
generator itself, such as Identifier's not.pattern, are handled later by
postprocess_models.py.
"""

import argparse
import copy
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import urldefrag

Schema = dict[str, Any]
CATALOG_PATH = Path("shopping/catalog_publish.json")


class SchemaSource:
    """Read inheritance from pristine local schemas without fetching references."""

    def __init__(self, directory: Path):
        self.directory = directory.resolve()
        self.documents: dict[Path, Schema] = {}

    def load(self, document: Path) -> Schema:
        """Load a JSON object inside the schema directory."""
        document = document.resolve()
        if not document.is_relative_to(self.directory):
            raise ValueError(f"Reference escapes the schema directory: {document}")
        if document not in self.documents:
            value = json.loads(document.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                raise ValueError(f"Expected an object schema: {document}")
            self.documents[document] = value
        return self.documents[document]

    def resolve(self, reference: str, document: Path) -> tuple[Schema, Path]:
        """Resolve a relative file reference and its JSON Pointer."""
        location, fragment = urldefrag(reference)
        if ":" in location or location.startswith(("/", "\\")):
            raise ValueError(f"Only relative local references are supported: {reference}")
        target = (document.parent / location).resolve() if location else document
        value: Any = self.load(target)
        if fragment:
            if not fragment.startswith("/"):
                raise ValueError(f"Expected a JSON Pointer: {reference}")
            try:
                for part in fragment[1:].split("/"):
                    key = part.replace("~1", "/").replace("~0", "~")
                    value = value[int(key)] if isinstance(value, list) else value[key]
            except (KeyError, IndexError, TypeError, ValueError) as error:
                raise ValueError(f"Unresolved reference {reference} in {document}") from error
        if not isinstance(value, dict):
            raise ValueError(f"Reference is not an object schema: {reference}")
        return value, target

    def branches(
        self, node: Schema, document: Path, ancestors: frozenset[tuple[Path, str]] = frozenset()
    ) -> Iterator[tuple[Schema, Path]]:
        """Visit object inheritance, without expanding property or item references."""
        yield node, document
        if "$ref" in node:
            reference = node["$ref"]
            identity = (document, reference)
            if identity in ancestors:
                raise ValueError(f"Cyclic inheritance reference: {reference} in {document}")
            resolved, target = self.resolve(reference, document)
            yield from self.branches(resolved, target, ancestors | {identity})
        for branch in node.get("allOf", []):
            if not isinstance(branch, dict):
                raise ValueError(f"Expected an object in allOf: {document}")
            yield from self.branches(branch, document, ancestors)

    def flatten_local(
        self, node: Schema, document: Path, ancestors: frozenset[str] = frozenset()
    ) -> Schema:
        """Flatten local metadata composition while retaining external inheritance."""
        result: Schema = {}
        reference = node.get("$ref")
        if reference is not None:
            resolved, target = self.resolve(reference, document)
            if reference.startswith("#"):
                if reference in ancestors:
                    raise ValueError(f"Cyclic local reference: {reference}")
                _merge_metadata(
                    result, self.flatten_local(resolved, target, ancestors | {reference})
                )
            else:
                # External nodes are not copied: their references keep the correct base URI.
                result["allOf"] = [{"$ref": reference}]
        for branch in node.get("allOf", []):
            _merge_metadata(result, self.flatten_local(branch, document, ancestors))
        _merge_metadata(
            result, {key: value for key, value in node.items() if key not in {"$ref", "allOf"}}
        )
        return result


def _merge_metadata(destination: Schema, addition: Schema) -> None:
    """Combine the object metadata used by the publication profile."""
    for key, value in addition.items():
        if key == "required":
            destination[key] = list(dict.fromkeys([*destination.get(key, []), *value]))
        elif key == "properties":
            destination.setdefault(key, {}).update(copy.deepcopy(value))
        elif key == "allOf":
            destination.setdefault(key, []).extend(copy.deepcopy(value))
        elif (
            key in destination
            and destination[key] != value
            and key not in {"title", "description", "description_pt"}
        ):
            raise ValueError(f"Unsupported metadata intersection for {key}")
        else:
            destination[key] = copy.deepcopy(value)


def _restore_inherited_fields(
    prepared: Schema, original: Schema, document: Path, source: SchemaSource
) -> None:
    """Keep inherited required fields and array bounds on redeclared properties."""
    required = list(prepared.get("required", []))
    bounds: dict[str, dict[str, int]] = {}
    for branch, origin in source.branches(original, document):
        # Redeclare only overridden fields. Listing an inherited field without its
        # schema makes codegen replace its typed base field with Any.
        required.extend(
            name for name in branch.get("required", []) if name in prepared.get("properties", {})
        )
        for name, prop in branch.get("properties", {}).items():
            for constraint, _ in source.branches(prop, origin):
                limits = bounds.setdefault(name, {})
                for key, combine in (("minItems", max), ("maxItems", min)):
                    if key in constraint:
                        value = constraint[key]
                        limits[key] = combine(limits[key], value) if key in limits else value
    prepared["required"] = list(dict.fromkeys(required))
    for name, prop in prepared.get("properties", {}).items():
        limits = bounds.get(name, {})
        if limits.get("minItems", 0) > limits.get("maxItems", float("inf")):
            raise ValueError(f"Incompatible array bounds for {name}")
        prop.update(limits)


def prepare_catalog_publish(preprocessed: Path, pristine: Path) -> bool:
    """Repair only catalog_publish.json; older specs without publication are unchanged."""
    source = SchemaSource(pristine)
    original_path = (pristine / CATALOG_PATH).resolve()
    if not original_path.exists():
        return False
    original = source.load(original_path)
    destination = preprocessed / CATALOG_PATH
    prepared = json.loads(destination.read_text(encoding="utf-8"))
    try:
        definitions = prepared["$defs"]
        raw_definitions = original["$defs"]
        for name in ("publish_product", "publish_variant"):
            _restore_inherited_fields(
                definitions[name], raw_definitions[name], original_path, source
            )
        definitions["metadata"] = source.flatten_local(raw_definitions["metadata"], original_path)
        definitions["publish_response"]["properties"]["ucp"] = source.flatten_local(
            raw_definitions["publish_response"]["properties"]["ucp"], original_path
        )
    except KeyError as error:
        raise ValueError(f"Unsupported catalog publication schema: missing {error}") from error
    destination.write_text(
        json.dumps(prepared, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return True


def main() -> None:
    """Prepare publication schemas for datamodel-codegen."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("preprocessed", type=Path)
    parser.add_argument("pristine", type=Path)
    args = parser.parse_args()
    try:
        changed = prepare_catalog_publish(args.preprocessed, args.pristine)
    except (OSError, ValueError) as error:
        parser.exit(1, f"catalog.publish preparation failed: {error}\n")
    print(
        "catalog.publish: constraints restored" if changed else "catalog.publish: not in this spec"
    )


if __name__ == "__main__":
    main()
