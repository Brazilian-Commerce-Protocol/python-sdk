<!--
   Copyright 2026 BCP Authors

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
-->

# BCP Python SDK

O SDK Python oficial do [Brazilian Commerce Protocol (BCP)](https://bcp.dev.br):
os modelos pydantic gerados a partir dos JSON Schemas do protocolo, que vivem
no repositório da spec, [`bcp`](https://github.com/Brazilian-Commerce-Protocol/bcp). Espelha o
`python-sdk` do UCP: a língua fica na spec, o binding Python fica aqui.

## Instalação

```bash
pip install bcp-sdk
```

## Uso

`bcp_sdk` é um namespace package sem fachada, como o `ucp_sdk`: o import é
sempre pelo caminho completo do módulo, sem reexports.

```python
from bcp_sdk.models.discovery.profile_schema import BusinessProfile
from bcp_sdk.models.schemas.shopping.checkout import Checkout

checkout = Checkout.model_validate(payload)
```

Além dos modelos, `bcp_sdk.canonical` traz a serialização canônica (JCS,
RFC 8785) usada para assinatura.

## Estrutura

```
generate_models.sh                     # pipeline de geração (clona a spec e gera)
preprocess_schemas.py                  # pré-processador, vendorado byte a byte do UCP
prepare_catalog_publish.py             # recupera a herança dos modelos de publicação
postprocess_models.py                  # reinjeta as restrições que o gerador descarta
templates/pydantic_v2/RootModel.jinja2 # template custom (injeta frozen=True nos RootModel)
src/bcp_sdk/
├── canonical.py                       # serialização canônica (JCS) para assinatura
└── models/                            # ARTEFATO gerado, nunca editar à mão
    ├── schemas/                       # espelha bcp/schemas/
    │   ├── ucp.py  capability.py  service.py  payment_handler.py
    │   ├── shopping/                  # cart.py checkout.py order.py ... + *_request.py
    │   │   ├── types/                 # os value objects
    │   │   └── discount/              # extensão vira PACOTE
    │   │       └── br/dev/bcp/shopping.py  # subclasses: Cart, Checkout estendidos
    │   ├── common/  handlers/  transports/
    │   └── ucp_create_request.py ...
    └── discovery/profile_schema.py
```

Três convenções herdadas do pipeline do UCP:

- **1 módulo por schema**: a árvore de `models/` espelha a da spec; `$ref`
  cross-file vira import e subclasse.
- **Extensões viram pacotes**: um schema de extensão (ex. `discount.json`, que
  faz `allOf` sobre cart e checkout) precisa de subpastas para as classes
  reverse-domain, então `br.dev.bcp.shopping` vira o caminho
  `discount/br/dev/bcp/shopping.py`, com as subclasses do recurso base.
- **Variantes `*_request`**: campos anotados com `ucp_request`
  (omit/optional/required por operação) geram `checkout_create_request.py`,
  `checkout_update_request.py` etc., além do módulo completo.

Os RootModel (schemas cujo topo é uma union ou escalar) saem imutáveis
(`frozen=True`) pelo template custom, virando value objects hasháveis.

## Regenerar os modelos

O `generate_models.sh` clona o repositório da spec, roda o
`preprocess_schemas.py` (achata `allOf`, normaliza o envelope `ucp`, gera as
variantes de request), prepara as restrições de `catalog.publish`, chama o `datamodel-codegen` com as flags e templates
do UCP e termina no `postprocess_models.py`:

```bash
uv sync
./generate_models.sh              # main da spec
./generate_models.sh 2026-04-08   # ou uma branch release/YYYY-MM-DD
BCP_REF=fe05774c34144355eddc2adceddc9f0400a0e1d5 ./generate_models.sh
```

`BCP_REF` aceita commit, tag ou branch e não pode ser combinado com o argumento
de release datada. Sem ambos, a fonte é `main` da spec pública. Use o commit do
changelog para reproduzir uma release. A CI acusa diferenças e arquivos gerados
novos não rastreados. No Windows, execute pelo Git Bash ou outro Bash compatível,
com `uv` no `PATH`.

Ao final ele imprime o commit da spec usado. Esse commit vai para o
[CHANGELOG](CHANGELOG.md) na release: é o único registro de qual spec gerou
determinada versão do pacote.

`BCP_REPO` aceita outra URL ou um caminho local da spec, útil para conferir
localmente como ficariam os modelos de uma spec ainda não publicada. O que sai
desse uso não se commita: as descrições dos schemas viram docstrings, então
publicar esses modelos publicaria a spec.

```bash
BCP_REPO=../bcp ./generate_models.sh
```

### Por que existe um pós-processamento

O `datamodel-codegen` descarta em silêncio restrições que não têm
equivalente direto em `Field(...)`, porque exigiriam escrever uma função de
validação: `minProperties` em objeto com propriedades declaradas, `contains`
com `minContains`/`maxContains` em lista, `uniqueItems` e `not: {pattern: ...}`
em strings. Sem elas, um
`Totals` vazio passaria, embora o schema exija exatamente uma entrada
`subtotal` e uma `total`. O `postprocess_models.py` reabre os arquivos gerados
e injeta os validadores correspondentes.

O `prepare_catalog_publish.py` lê a herança dos schemas originais e restaura
obrigatoriedade e cardinalidade nos campos sobrescritos de produto/variante.
Também preserva a ligação dos metadados do recibo ao modelo base, que exige
`ucp.version`. Essa etapa é exclusiva do catálogo e mantém o pré-processador
vendorado do UCP intacto. Specs anteriores sem publicação continuam suportadas.

A versão do `datamodel-code-generator` fica fixada em uma versão exata, não em
faixa: a saída é artefato commitado e muda entre versões da ferramenta.

## Testes

```bash
uv run pytest
```

Cobrem a serialização canônica (vetores do RFC 8785), um smoke dos modelos
gerados (todo módulo importa e os tipos principais validam) e as restrições
recuperadas pelo pós-processamento, que passariam despercebidas justamente
porque o módulo continua importando normalmente.

## Publicação de catálogo

```python
from bcp_sdk.models.schemas.shopping.catalog_publish import (
    Catalog,
    PublishProduct,
    PublishResponse,
    PublishVariant,
    ReplaceRequest,
    UpdateRequest,
)

request = ReplaceRequest.model_validate({"base_revision": None, "products": []})
assert request.products.root == []
```

Esses modelos seguem o contrato de
`PUT/PATCH /merchants/{merchant_id}/catalogs/{catalog_id}`. Os corpos de escrita
não exigem `merchant_id` nem `ucp`; o snapshot e o recibo incluem os metadados.
Identificadores e revisões são `RootModel` imutáveis; seus valores Python ficam
em `.root`, e a serialização JSON produz os valores escalares do protocolo.
Use `model_dump(mode="json", by_alias=True, exclude_unset=True)` para conservar
os nomes oficiais e a presença dos campos recebidos nos seis modelos acima.

Os modelos validam restrições estruturais. Autenticação, autorização,
consistência entre preços/opções/IDs e normalização são responsabilidades do
índice. A coerção de tipos do restante do SDK permanece a mesma. As fixtures
dos testes registram o commit de origem e funcionam offline.

A versão preparada no código só chega ao PyPI quando uma GitHub Release é
publicada, pelo workflow existente. Aprovar ou mesclar a PR não dispara a
publicação do pacote.

## Atribuição

O pipeline de geração deriva do
[python-sdk do UCP](https://github.com/Universal-Commerce-Protocol/python-sdk),
Copyright 2026 UCP Authors, licenciado sob a Apache License 2.0.
`preprocess_schemas.py` e `templates/` são vendorados byte a byte;
`postprocess_models.py` conserva as adaptações de paths e RootModel e restaura
`not.pattern`. O `prepare_catalog_publish.py` é uma etapa própria do BCP.
Os arquivos vendorados mantêm o header original. Os modelos
são gerados dos schemas do BCP com header neutro; atribuição e declaração de
modificações vivem em [`NOTICE`](NOTICE).

## Sobre

O BCP é um projeto open-source sob a [Apache License 2.0](LICENSE), aberto a
contribuições da comunidade. Os modelos são gerados, nunca editados à mão.
