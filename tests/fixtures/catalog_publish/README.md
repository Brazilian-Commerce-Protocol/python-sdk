# Catalog publication fixtures

Copied verbatim from `fixtures/valid/catalog-publish-*.json` and
`fixtures/invalid/catalog-publish-*.json` in the
[BCP specification](https://github.com/Brazilian-Commerce-Protocol/bcp/tree/fe05774c34144355eddc2adceddc9f0400a0e1d5/fixtures),
commit `fe05774c34144355eddc2adceddc9f0400a0e1d5` (Apache-2.0).

The source repository is private; refreshing these fixtures requires authorized
access. Tests use the committed copies offline. The `fixtures/conformance/` cases
from the spec are deliberately
not used as SDK rejection cases: they test semantic rules enforced by the index,
such as price range consistency and duplicate product IDs, rather than JSON Schema
constraints represented by these models.
