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

# Changelog

Nada dentro do pacote registra de qual spec ele saiu. Esse vínculo mora aqui:
**toda release precisa citar o commit da spec que gerou os modelos**. O
`generate_models.sh` imprime esse commit ao terminar, justamente para ser
copiado para cá.

O versionamento segue o do `python-sdk` do UCP: o minor acompanha a versão da
spec e o patch é correção do binding sobre a mesma spec. Enquanto a spec BCP
estiver em `draft`, sem release datada, o SDK fica em `0.1.x`.

## 0.1.0a2 (09/10/2026)

Modelos regenerados a partir da spec pública atualizada. O código gerado é o
mesmo da `0.1.0a1`: a única mudança de schema no período foi o `$id` de
`discovery/profile_schema.json` (de `https://bcp.dev.br/schemas/discovery/profile.json`
para `https://bcp.dev.br/discovery/profile.json`), que não aparece nos modelos.

- Spec: [`ceia-br/bcp`](https://github.com/ceia-br/bcp), branch `main`, commit
  `f596b776d5b0504a258f7683725c9c1493d02c6c`.

## 0.1.0a1 (11/08/2026)

Primeira versão publicada, a partir do repositório de incubação. Alpha de
propósito: o pacote existe para reservar o nome no PyPI e exercitar o fluxo de
release, não para uso em produção.

- Spec: [`ceia-br/bcp`](https://github.com/ceia-br/bcp), branch `main`, commit
  `f9b6bc681513e910883a1eaab5ebbce04a4b5a75`.
- Modelos pydantic gerados de `schemas/` e `discovery/`, com as variantes
  `*_request` e as extensões `br.dev.bcp.*`.
- `bcp_sdk.canonical`: serialização canônica JCS (JSON Canonicalization Scheme,
  RFC 8785) usada para assinatura.
- Restrições que o `datamodel-code-generator` descarta são reinjetadas pelo
  `postprocess_models.py`: `minProperties` em objetos, `contains` com
  `minContains`/`maxContains` e `uniqueItems` em listas. Sem isso, `Totals`
  aceitaria lista vazia, contrariando o schema, que exige exatamente uma entrada
  `subtotal` e uma `total`.
- Gerador travado em `datamodel-code-generator==0.69.0`. A 0.70.0 parou de
  emitir a docstring do valor em `additionalProperties`, e os modelos são
  artefato commitado, lido como documentação da API.
- Piso `>=3.10`, alinhado ao `ucp-sdk` e ao `a2a-sdk`.
