# Nad'Arte — Dashboard App Treino (pipeline API PACTO → Cloudflare)

Mesmo padrão dos dashboards de **Frequência** e **Ocupação**: um robô (GitHub Actions)
lê a **API PACTO** com as chaves guardadas nos **Secrets**, monta os dados, valida (gate)
e publica no **Cloudflare Pages**. A página se atualiza sozinha.

> **Estado atual:** de 8 indicadores, **1 confirmado** na doc (`usaApp`). Os outros 7
> (ficha, execução, avaliação física, nota, atendimento) **ainda precisam ser descobertos**
> na API — é a **Fase 1** abaixo. Enquanto isso, o coletor já traz o que é confirmado e
> deixa marcado `# TODO(PROBE)` o resto.

---

## Estrutura
```
scripts/probe_treino.py       # Fase 1: descobre os endpoints (roda no Actions, PII-safe)
scripts/pacto_fetch_treino.py # Coletor: lê a API -> data/treino_raw.json
scripts/build_treino.py       # Motor + GATE + injeta no template -> public/index.html
template/index.html           # o dashboard (este que construímos)
.github/workflows/probe.yml   # botão manual do probe
.github/workflows/deploy.yml  # coleta agendada + publicação
```

---

## Fase 0 — Preparar (uma vez)

1. Crie um repositório no GitHub e suba estes arquivos.
2. Em **Settings → Secrets and variables → Actions → New repository secret**, cadastre:
   - `PACTO_KEY_716NORTE`, `PACTO_KEY_905SUL`, `PACTO_KEY_604NORTE`, `PACTO_KEY_LAGONORTE`, `PACTO_KEY_LAGOSUL` (as mesmas dos outros dashboards)
   - `CLOUDFLARE_API_TOKEN` e `CLOUDFLARE_ACCOUNT_ID`
3. No **Cloudflare → Workers & Pages → Create → Pages**, crie um projeto chamado
   `nadarte-apptreino` (ou ajuste o nome no `deploy.yml`).

> As chaves ficam **só** nos Secrets. Ninguém (nem eu) as vê. `data/` e `public/` estão no
> `.gitignore` — **dados com PII nunca vão pro git**, ficam efêmeros no runner.

---

## Fase 1 — Descobrir os endpoints que faltam

Objetivo: achar os endereços reais de ficha, execução, avaliação, nota e atendimento.

1. **Actions → "Probe (descobrir endpoints App Treino)" → Run workflow.**
2. Abra o log do job. Você verá, para cada caminho testado, o `STATUS` e o formato da
   resposta (só chaves/contagens, sem PII). Os que derem **200** são os bons.
3. Me mande esse trecho do log (ou os prints da doc). Eu **travo os campos** e preencho
   os `# TODO(PROBE)` no `pacto_fetch_treino.py`.

> Em paralelo, se conseguir as **seções da doc** (Ficha/Treino, Avaliação Física,
> nota/feedback, chat), melhor ainda — acelera e confirma nomes de campo.

---

## Fase 2 — Ligar o pipeline

1. **Rode em modo teste** (sem publicar): Actions → "Coleta + Publica" → Run workflow com
   **deploy = false**. Isso coleta e roda o **GATE**. Confira no log que os volumes fecham.
2. Com os números batendo, rode de novo com **deploy = true** para publicar no Cloudflare.
3. O `cron` do `deploy.yml` já deixa a atualização **automática** de madrugada.

> O GATE **nunca publica dado quebrado**: se faltar unidade ou os ativos vierem abaixo do
> mínimo, ele falha e o último site bom permanece no ar.

---

## Passo de *wiring* (fazer uma vez, no fim da Fase 1)

Hoje o `template/index.html` gera dados fictícios internamente. Para ele passar a **ler os
dados reais**, trocamos o gerador por um bloco `window.DATA` que o `build_treino.py` injeta.
Onde a página monta os dados, entra:

```js
const DATA = /*__DATA__*/null ;   // o build substitui isto pelo JSON real
// se DATA existir, usa DATA.unidades / DATA.alunos; senão, cai no mock (fallback)
```

Eu faço essa troca **depois** que soubermos os campos reais (Fase 1) — assim o contrato
casa exatamente com o que a API devolve, sem retrabalho.

### Contrato de dados (o que o coletor entrega)
```json
{
  "gerado_em": "2026-07-02T09:00:00Z",
  "janela": "2026-06",
  "unidades": [{ "id": "716Norte", "nome": "716 Norte", "ativos": 760 }],
  "alunos": [{
    "id": "A1a2b3c4",           // pseudônimo (sem nome/CPF)
    "unit": "716Norte",
    "publico": "Fitness",       // Fitness | Ambos | Água | Lutas
    "usaApp": true,
    "prof": null,               // + KPIs 1..8 quando os endpoints forem mapeados
    "treinos": null, "fichaStatus": null, "avalStatus": null,
    "nota": null, "atend": null
  }]
}
```

---

## ⚠️ Decisão importante — PRIVACIDADE (PII)

Os dashboards de Frequência/Ocupação publicam **só agregados**. Este tem uma aba de
**CRM por aluno**. Uma URL pública do Cloudflare com **nome + engajamento + risco por aluno**
é exposição de dado pessoal. Três caminhos (escolha um):

1. **Publicar só agregado** (rede/unidade/professor) na URL pública; a lista por aluno
   fica num ambiente **restrito** (login). — *mais seguro.*
2. **Pseudonimizar** o aluno na versão pública (mostrar matrícula/ID, sem nome). É o que o
   coletor já faz por padrão (`id` = hash).
3. **Cloudflare Access** (login) na página inteira, aí pode ter nome.

Recomendo **(1) ou (3)** para a visão com nomes, e **(2)** se a URL for pública.
Me diga qual você quer e eu ajusto o coletor/dashboard.

---

## Rodar local (opcional, para testar sem Actions)
```bash
PACTO_KEY_716NORTE=xxxxx python scripts/probe_treino.py       # Fase 1
PACTO_KEY_716NORTE=xxxxx python scripts/pacto_fetch_treino.py # coleta
python scripts/build_treino.py --check                        # só o gate
```

*Pipeline montado pela Connect-IN, reusando os padrões da migração dos dashboards Nad'Arte para a API PACTO.*
