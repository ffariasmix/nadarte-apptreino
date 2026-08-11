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

---

## Episódio 2 — colapso PARCIAL ("só treino em dia") · 07/08/2026

**O que houve:** com a API da Pacto ainda instável (uma coleta chegou a levar **4h31m**), a lista **`alunos-treino-em-dia`** voltou vazia enquanto a **`alunos-treino-vencido`** trouxe dado parcial (223, todos no Lago Norte). Resultado no painel: **"Treinos em dia" = 0 em todas as unidades**, "vencidos" só no Lago Norte. Um gestor de unidade (Lago Sul) reportou os números zerados.

**Por que o GATE do episódio 1 não pegou:** ele checava a cobertura **combinada** (em dia + vencido). Como o "vencido" segurou acima do piso, o "em dia" zerado passou despercebido.

**Correções (2º round):**

1. **GATE por lado** (`build_treino.py` → `gate()`): agora checa **em dia** e **vencido** **separadamente**, com piso absoluto de 30 registros cada. Se qualquer um dos dois colapsar, não publica. (Numa rede saudável há centenas em cada lado.)
2. **Retry na página 0** (`pacto_fetch_treino.py` → `treino_status_map()`): re-tenta a 1ª página de cada lista de treino até 4× antes de aceitar "vazio" — ataca o "0 transitório" na origem.

**Comportamento observado (correto):** o GATE **reprovou** os runs com dado ruim (ex.: `#97` vermelho — "status de treino praticamente ausente: 0/5073"), mantendo o último bom e não publicando zero.

## Playbook de recuperação (quando o site já está mostrando dado ruim)

Enquanto a Pacto não normaliza, todo run colhe treino ruim e o GATE barra (correto) — mas o site fica parado no último publicado, que pode ser um ruim. Para restaurar na hora, **rollback no Cloudflare Pages**:

1. Cloudflare → **Workers & Pages** → **nadarte-apptreino** → aba **Implantações/Deployments**.
2. Os horários são relativos ("2 days ago"); para achar o deploy **bom**, abrir a URL única de cada candidato (`https://<hash>.nadarte-apptreino.pages.dev`) e conferir no header o **"Atualizado"** e os cards de treino (o bom tem em dia/vencido com centenas).
3. Na linha do deploy bom → **⋯** → **Rollback to this deployment** → confirmar.
4. Recuperação automática: com deploy automático ligado, **o próximo run verde republica por cima** do rollback (dado fresco). O rollback é uma ponte, não um estado permanente.

> Exemplo real (07/08): rollback para o deploy `186e7f4c` (05/08 15:03 · em dia 332 / vencidos 238) restaurou o painel imediatamente.

## Follow-up adicional

- A coleta chegou a **4h31m** sob instabilidade da Pacto. Avaliar um **teto de tempo (fail-fast)** no coletor para não segurar o runner por horas quando a API está fora.
