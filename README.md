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
no repositório da spec, [`bcp`](https://github.com/ceia-br/bcp). Espelha o
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
variantes de request), chama o `datamodel-codegen` com as flags e templates
do UCP e termina no `postprocess_models.py`:

```bash
uv sync
./generate_models.sh              # main da spec
./generate_models.sh 2026-04-08   # ou uma branch release/YYYY-MM-DD
```

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

O `datamodel-codegen` descarta em silêncio três restrições que não têm
equivalente direto em `Field(...)`, porque exigiriam escrever uma função de
validação: `minProperties` em objeto com propriedades declaradas, `contains`
com `minContains`/`maxContains` em lista, e `uniqueItems`. Sem elas, um
`Totals` vazio passaria, embora o schema exija exatamente uma entrada
`subtotal` e uma `total`. O `postprocess_models.py` reabre os arquivos gerados
e injeta os validadores correspondentes.

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

## Atribuição

O pipeline de geração deriva do
[python-sdk do UCP](https://github.com/Universal-Commerce-Protocol/python-sdk),
Copyright 2026 UCP Authors, licenciado sob a Apache License 2.0.
`preprocess_schemas.py` e `templates/` são vendorados byte a byte;
`postprocess_models.py` é vendorado com duas adaptações, marcadas no arquivo
com o comentário `BCP divergence`. Todos mantêm o header original. Os modelos
são gerados dos schemas do BCP com header neutro; atribuição e declaração de
modificações vivem em [`NOTICE`](NOTICE).

## Sobre

O BCP é um projeto open-source sob a [Apache License 2.0](LICENSE), aberto a
contribuições da comunidade. Os modelos são gerados, nunca editados à mão.
