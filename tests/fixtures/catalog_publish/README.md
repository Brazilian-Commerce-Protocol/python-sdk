# Catalog publication fixtures

Copied verbatim from `fixtures/valid/catalog-publish-*.json` and
`fixtures/invalid/catalog-publish-*.json` in the
[BCP specification](https://github.com/ceia-br/bcp/tree/a4e33aad8f1e1920d1a623e4bed5204406920c57/fixtures),
commit `a4e33aad8f1e1920d1a623e4bed5204406920c57` (Apache-2.0).

Tests use the committed copies offline. The `fixtures/conformance/` cases
from the spec are deliberately
not used as SDK rejection cases: they test semantic rules enforced by the index,
such as price range consistency and duplicate product IDs, rather than JSON Schema
constraints represented by these models.
