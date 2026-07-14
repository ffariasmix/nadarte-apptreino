# Calibração do ISA — Backtest (Item 10)

**Índice de Saúde do Aluno (ISA)** · CRM 360 App Treino · Nad'Arte
Data: 2026-07-14 · Base de evidência: presença real de 3.422 alunos (ponte Frequência)

---

## 1. A pergunta

O ISA combina cinco dimensões com pesos fixos. A pergunta do item 10 é simples: **esses pesos estão certos?** Ou seja, um ISA baixo hoje realmente prevê o abandono do aluno amanhã?

Pesos atuais:

| Cenário | pres | eng | tr | ct | vin |
|---|---|---|---|---|---|
| **ISA_W5** (com presença — ponte Frequência) | 0,25 | 0,20 | 0,25 | 0,20 | 0,10 |
| **ISA_W4** (sem presença) | — | 0,35 | 0,30 | 0,25 | 0,10 |

`pres` = recência de presença na catraca · `eng` = engajamento no app (recência de acesso ao treino) · `tr` = treino em dia · `ct` = vigência de contrato · `vin` = vínculo com professor.

---

## 2. A realidade dos dados

Um backtest clássico de churn exige **ISA medido em T** e **desfecho observado em T+N**. Hoje isso ainda não existe de forma histórica:

- O coletor do App Treino só puxa alunos **ATIVOS** — quem cancelou já saiu da base, então não há rótulo de "perda confirmada" para treinar.
- O `score_history` do Frequência tem **1 dia**; o `ledger` é de identidade (primeira aparição), não de perdas datadas.
- Os dados por-aluno do App Treino **não são versionados** (só injetados no HTML publicado).

Conclusão honesta: **não dá para rodar o backtest longitudinal completo hoje.** O que dá para fazer — e foi feito — é (a) uma **validação concorrente com dado real** do sinal mais importante e (b) **montar a infraestrutura** para o backtest prospectivo rodar sozinho daqui para frente.

---

## 3. Evidência concorrente (dado real, hoje)

Usando a série de presença real (10 semanas, 3.422 alunos), tratei as **semanas 1–8 como o "estado em T"** e as **semanas 9–10 como o "futuro"**, e medi se a recência prevê o abandono à frente (churn = nenhuma visita nas 2 semanas seguintes). É um mini-backtest dentro da própria série — passado prevendo futuro, sem circularidade.

**Churn (2 semanas à frente) por recência em T:**

| Recência em T | n | Churn à frente |
|---|---|---|
| Veio na última semana | 2.226 | 21,9% |
| 1 semana sem vir | 610 | 53,9% |
| 2 semanas sem vir | 200 | 65,5% |
| 3+ semanas sem vir | 386 | **77,5%** |

**Tendência (últimas 4 sem vs 4 anteriores):** caindo → 56,6% de churn · estável/subindo → 30,9%.

**Poder discriminante da recência sozinha: AUC = 0,716** (0,5 = aleatório; > 0,70 = bom para uma única variável).

### O que isso valida

1. **O peso alto em presença/recência está correto.** A recência sozinha separa quem vai abandonar com AUC 0,72 — é de fato o "sinal nº 1 de churn precoce", como a auditoria do Frequência já apontava. Manter `pres` = 0,25 no ISA_W5 e o forte peso de `eng` (recência de app) é justificado por dado.
2. **A penalidade do `presencaCai` (−20) faz sentido.** Tendência caindo quase dobra o churn (56,6% vs 30,9%).
3. **Os buckets decrescentes da dimensão presença estão bem ordenados** — o churn sobe de forma monotônica de 22% a 78% conforme a recência piora. Único ajuste sugerido: o degrau `≤7d→100` vs `≤14d→80` é suave demais perto do salto de churn (22%→54%); vale **acentuar** para `≤14d→70` numa próxima iteração.

---

## 4. Infraestrutura do backtest prospectivo (entregue)

Para que o backtest completo passe a existir sem intervenção:

- **`scripts/build_treino.py` → `snapshot_isa()`**: a cada build, grava um snapshot **semanal** do ISA por aluno em `history/isa_history.json` — matrícula **hasheada** (sem PII), com `[isa, eng, tr, ct, vin, pres, recência, presCai]`. Chave por semana ISO (upsert), retenção de 26 semanas. O porte do ISA para Python é **idêntico** ao do template (validado: casos batem em 96 e 27).
- **`scripts/calibrate_isa.py`**: junta o ISA medido em uma semana passada com o churn observado depois (via `presenca.json` do Frequência) e reporta AUC do ISA, taxa de churn por faixa, **AUC por dimensão** e **pesos sugeridos** (proporcionais ao ganho de cada dimensão sobre o acaso). Enquanto não há semanas suficientes, ele avisa quanto falta.

Como rodar (a partir de ~4–8 semanas de acúmulo):

```
cd ~/Documents/GitHub/nadarte-apptreino
python scripts/calibrate_isa.py history/isa_history.json \
       ../nadarte-dashboard-automacao/presenca.json --horizonte 4
```

Saída valida sobre dado real (teste de função, medindo só presença): AUC 0,718, churn caindo por faixa — a máquina está correta; os números por dimensão preencherão quando o histórico real acumular.

---

## 5. Veredito e recomendação

**Os pesos atuais do ISA são defensáveis e não devem ser mexidos às cegas agora.** A dimensão de maior peso (presença/recência) está empiricamente validada como o melhor preditor isolado de churn. As demais dimensões (treino em dia, contrato, vínculo) são teoricamente sólidas, mas seu peso preditivo **ainda não foi medido** por falta de histórico — mexer neles hoje seria chute.

**Plano:**

1. **Agora:** manter ISA_W5 / ISA_W4 como estão. O snapshot semanal já começa a acumular no próximo build.
2. **Em ~6–8 semanas:** rodar `calibrate_isa.py`. Se uma dimensão mostrar AUC ≈ 0,50 (sem poder preditivo) de forma estável, **reduzir seu peso** e redistribuir para as que discriminam; se `eng`/`pres` dominarem, **subir** seu peso.
3. **Micro-ajuste candidato** (opcional, baixo risco): acentuar o bucket de presença `≤14d` de 80 → ~70, refletindo o salto de churn observado.
4. **Regra de ouro:** só alterar um peso com ≥ 2 janelas de backtest concordando na mesma direção.

> Item 10 = **capacidade de calibração instalada + validação concorrente do sinal central**. O backtest longitudinal roda sozinho a partir daqui; a decisão de re-pesar fica lastreada em dado, não em opinião.
