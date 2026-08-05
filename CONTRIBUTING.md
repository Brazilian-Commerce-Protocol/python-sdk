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

# Como contribuir

Este repositório é o binding Python do BCP: os modelos pydantic gerados a partir
dos JSON Schemas. A língua do protocolo não mora aqui.

## Antes de começar

Leia o [código de conduta](CODE_OF_CONDUCT.md). A aprovação de mudanças é dos
[maintainers](MAINTAINERS.md).

## O que vai aqui e o que vai na spec

Esta é a primeira coisa a checar, porque decide o repositório para onde a sua
contribuição deve ir.

**Vai na spec**, em [`ceia-br/bcp`](https://github.com/ceia-br/bcp): campo novo,
mudança de descrição, tipo novo, capability, handler, qualquer coisa que mude o
vocabulário do protocolo. Uma mudança de schema chega aqui depois, pela
regeneração, e nunca por edição manual.

**Vai aqui**: o pipeline de geração, a serialização canônica em
`src/bcp_sdk/canonical.py`, os testes, o empacotamento e a documentação do
próprio SDK.

## Os modelos são artefato, não código-fonte

Tudo sob `src/bcp_sdk/models/` é gerado e carrega o aviso `Do not edit` no topo.
Editar à mão parece funcionar até a próxima regeneração apagar a alteração, e
nada no CI avisa: a verificação de defasagem é manual, por decisão de projeto.

Para atualizar os modelos:

```bash
uv sync
./generate_models.sh
```

O script clona a spec pública, pré-processa, gera, reinjeta as restrições que o
gerador descarta e reformata. Ao final ele imprime o commit da spec usado, que
precisa ir para o [CHANGELOG](CHANGELOG.md) na release.

A variável `BCP_REPO` aponta o script para outra URL ou para um caminho local, o
que serve para conferir localmente como ficariam os modelos de uma spec que
ainda não é pública. O que sai desse uso não pode ser commitado: as descrições
dos schemas viram docstrings, então publicar esses modelos publicaria a spec.

## Código vendorado do UCP

`preprocess_schemas.py`, `postprocess_models.py` e `templates/` vêm do
[python-sdk do UCP](https://github.com/Universal-Commerce-Protocol/python-sdk),
sob Apache 2.0, e mantêm o cabeçalho original. A regra é ficar o mais perto
possível do upstream: não reescreva por estilo. Toda divergência necessária é
marcada com um comentário `BCP divergence` explicando o motivo, e vai declarada
no [NOTICE](NOTICE). Esses arquivos estão fora do lint por isso.

## Versão do gerador

`datamodel-code-generator` está fixado em uma versão exata, não em faixa. A
saída dele é artefato commitado e muda entre versões: a 0.70.0, por exemplo,
deixou de emitir a docstring do valor em `additionalProperties`. Subir a versão
é uma mudança deliberada, num pull request próprio, com o diff dos modelos
visível na revisão.

## Versionamento

O minor acompanha a versão da spec e o patch é correção do binding sobre a mesma
spec, como no python-sdk do UCP. Enquanto a spec estiver em `draft`, sem release
datada, o SDK fica em `0.1.x`. Toda entrada de changelog cita o commit da spec.

## Rodando os testes

```bash
uv run pytest
uv run ruff check .
```

Os testes cobrem a serialização canônica (vetores do RFC 8785) e um smoke dos
modelos gerados. Se a sua mudança recupera ou altera uma restrição de schema,
inclua um teste que rejeite o payload inválido: é o tipo de regressão que passa
despercebida, porque o modelo continua importando normalmente.

## Títulos de PR e mensagens de commit

Usamos [Conventional Commits](https://www.conventionalcommits.org/), em inglês,
no formato `type: description`, com `!` antes dos dois-pontos quando a mudança
quebra compatibilidade. Tipos comuns: `feat`, `fix`, `docs`, `refactor`, `test`,
`chore`.

O header tem no máximo 50 caracteres; o corpo vai em lista, com itens de até 100
caracteres explicando o porquê.

## Submetendo um pull request

1. Faça fork do repositório e crie sua branch a partir de `main`.
2. Faça as mudanças. Se elas envolvem schema, pare e vá para a spec.
3. Rode os testes e o lint.
4. Confira se o título do PR segue Conventional Commits.
5. Abra o PR descrevendo a motivação; referencie a issue ou discussão de origem.
6. Responda aos apontamentos da revisão.

## Licença

Ao contribuir, você concorda que sua contribuição é licenciada sob a
[Apache License 2.0](LICENSE).
