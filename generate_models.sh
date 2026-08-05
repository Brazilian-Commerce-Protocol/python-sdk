#!/usr/bin/env bash
# Regenerate the pydantic models from the BCP JSON Schemas.
#
# Mirrors the UCP python-sdk pipeline: clone the spec repo, preprocess, run
# datamodel-codegen with the UCP templates and flags, then postprocess the
# constraints the generator drops. The spec lives in the public /bcp repository;
# BCP_REPO accepts a URL or local path override, and an optional first argument
# selects a release branch (e.g. `2026-04-08` clones `release/2026-04-08`;
# default is `main`). The file header comes from [tool.datamodel-codegen] in this
# package's pyproject.toml.
#
# Only what is committed here ships: models generated from a non-public spec
# would publish that spec's text as docstrings. Use BCP_REPO for local checks,
# never for what goes into a commit.
set -euo pipefail

cd "$(dirname "$0")"                        # repo root (holds pyproject.toml)

BCP_REPO="${BCP_REPO:-https://github.com/ceia-br/bcp}"
OUTPUT_DIR="src/bcp_sdk/models"             # generated artifact, never edit by hand

if [ $# -ge 1 ]; then
    BRANCH="release/$1"
    echo "Cloning spec version $1 (branch: $BRANCH)..."
else
    BRANCH="main"
    echo "No version specified, cloning main..."
fi

# Mirror the UCP source/ layout in a throwaway build dir: schemas/ and discovery/
# as siblings, so discovery's `../schemas/ucp.json` refs resolve. Output mirrors it:
# models/schemas/** and models/discovery/**.
BUILD="$(mktemp -d)"
trap 'rm -rf "$BUILD"' EXIT
git clone -b "$BRANCH" --depth 1 "$BCP_REPO" "$BUILD/bcp"
mkdir -p "$BUILD/src/schemas" "$BUILD/src/discovery"
cp -R "$BUILD/bcp/schemas/." "$BUILD/src/schemas/"
cp -R "$BUILD/bcp/discovery/." "$BUILD/src/discovery/"

# Nothing inside the package records which spec produced it, by design: the link
# lives in the release tag and in CHANGELOG.md. Print the commit so it can be
# copied into the entry.
SPEC_COMMIT="$(git -C "$BUILD/bcp" rev-parse HEAD)"

# Snapshot the pristine schemas before preprocessing. postprocess_models.py reads
# array contains/minContains/maxContains from these, because preprocessing merges
# allOf and a JSON node holds only one contains keyword, so the second rule (e.g.
# "exactly one total") would be gone before the post-processor could see it.
cp -R "$BUILD/src/schemas" "$BUILD/raw_schemas"

# 1. Preprocess only schemas/ (flatten allOf + emit *_request.json variants); it holds
#    ucp.json with $defs.entity. discovery/ has no such coupling, so it stays raw.
uv run python preprocess_schemas.py "$BUILD/src/schemas"

# 2. Generate. custom-file-header is read from [tool.datamodel-codegen] (CWD here).
#    --target-python-version matches requires-python: without it the generator
#    picks its own default and may emit Optional[...] instead of `X | None`.
#    --no-allow-remote-refs keeps generation hermetic. Every $ref resolves inside
#    the build dir, but the generator still tried to fetch a mangled
#    https://bcp.dev.br/... URL (it 404s, so nothing was ever pulled in). Blocking
#    it removes the network from the pipeline; output is byte-identical.
rm -rf "$OUTPUT_DIR"
uv run datamodel-codegen \
    --input "$BUILD/src" \
    --input-file-type jsonschema \
    --output "$OUTPUT_DIR" \
    --output-model-type pydantic_v2.BaseModel \
    --target-python-version 3.10 \
    --no-allow-remote-refs \
    --use-schema-description \
    --field-constraints \
    --use-field-description \
    --enum-field-as-literal all \
    --disable-timestamp \
    --use-double-quotes \
    --no-use-annotated \
    --allow-extra-fields \
    --custom-template-dir templates \
    --additional-imports pydantic.ConfigDict \
    --formatters ruff-format

# 3. Restore the constraints datamodel-codegen drops silently: minProperties on
#    objects, contains/minContains/maxContains and uniqueItems on arrays.
uv run python postprocess_models.py "$BUILD/src/schemas" "$BUILD/raw_schemas" "$OUTPUT_DIR"

# 4. Reformat: the injected validators were written after the generator's own
#    formatting pass. models/ is excluded in .ruff.toml, so override it here.
uv run ruff format --config "extend-exclude = []" "$OUTPUT_DIR"

echo "OK: models generated in $OUTPUT_DIR"
echo "Spec commit: $SPEC_COMMIT (cite it in the CHANGELOG entry)"
