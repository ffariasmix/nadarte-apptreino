# Post-mortem — "Treinos em dia / vencidos = 0" no CRM 360

**Sistema:** CRM 360 - Aluno & Professor (App Treino · Pacto)
**Data do incidente:** 05/08/2026 · **Status:** Resolvido

---

## Resumo

Por alguns deploys, a Visão Geral do dashboard exibiu **0 treinos em dia** e **0 treinos vencidos** (0% da base apta), quando o correto eram centenas em cada. O status de treino por aluno ("Em dia"/"Vencido") e a recência de acesso ("Últ. acesso") apareceram como "—" para toda a base. Nenhum dado foi perdido — apenas exibido incorretamente enquanto o problema esteve no ar.

## Impacto

- KPIs de treino (em dia / vencidos) e recência zerados na Visão Geral e no CRM.
- Índice de Saúde do Aluno (ISA) e faixas afetados indiretamente (a dimensão de treino/engajamento ficou sem sinal).
- Sem impacto em cadastro, contratos, nota do treino ou avaliações.

## Linha do tempo (resumo)

1. Coleta rodou com a **API da Pacto degradada** (a coleta levou ~1h49 em vez de minutos).
2. Com a lentidão, o filtro `situacao=ATIVO` da Pacto foi ignorado e a coleta caiu na **varredura da base histórica**, trazendo linhas de contratos antigos.
3. Uma alteração recente no coletor (dedup de carteira) **trocava a linha inteira do cliente** — e a matrícula junto — ao preferir o contrato de maior data de fim.
4. Resultado: a matrícula usada no cruzamento não batia mais com as listas de status de treino → **join vazio** → treino/recência "—".
5. O `GATE` de qualidade da época só checava número de unidades, então o dado ruim **foi publicado**.

## Causa-raiz

Combinação de dois fatores:

- **Externo:** instabilidade/lentidão da API da Pacto, que degradou a coleta e ativou o caminho de varredura da base histórica (matrículas de contratos antigos).
- **Interno:** o dedup de carteira, ao corrigir a *renovação antecipada*, substituía a linha inteira do cliente (incluindo a matrícula), desalinhando do join de status de treino — que é feito **por matrícula**.

## Correção

1. **Dedup cirúrgico** (`scripts/pacto_fetch_treino.py`): agora mantém a **linha e a matrícula originais** (preservando o join de treino) e, na renovação antecipada, adota **apenas as datas** do contrato mais novo/ativo. A correção de contrato futuro continua valendo, sem quebrar o treino.
2. Publicação corrigida no deploy **#94**, com a base de volta ao normal (≈2.395 aptos / 5.104 ativos) e treino em dia/vencidos novamente populados (332 / 238).

## Prevenção (garantir que não se repita)

- **GATE anti-0/0** (`scripts/build_treino.py` → `gate()`): se o **status de treino** ou a **recência** cobrirem menos de **5%** da base, o build **não publica** e mantém o último bom no ar (sai vermelho no passo "Montar + GATE"). Ou seja, uma coleta degradada não consegue mais subir 0/0 — na pior das hipóteses o site mantém a última versão íntegra até a API normalizar.

## Follow-ups sugeridos

- Se a API da Pacto degradar de forma recorrente, avaliar um **retry/backoff mais curto** ou pular a coleta cedo (fail-fast) quando o tempo estourar um teto.
- Considerar um **alerta** (ex.: mensagem no log/observabilidade) quando o GATE reprovar, para saber que houve uma coleta ruim mesmo sem olhar o deploy.
- Rollback rápido: em incidente publicado, o **Cloudflare Pages** permite reverter para um deploy anterior bom — caminho mais rápido de recuperação enquanto a coleta não normaliza.
