#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
calibrate_isa.py — Backtest prospectivo do ISA (Item 10).

Junta o ISA medido em uma semana passada T (history/isa_history.json, por aluno
HASHEADO) com o churn observado DEPOIS (presenca.json do repo Frequencia, mesma
matricula hasheada). Mede o poder preditivo do ISA e de cada dimensao contra o
churn real e sugere pesos calibrados.

Definicao de churn (observada no presente): o aluno nao registrou NENHUMA visita
nas 2 ultimas semanas da serie de presenca (wk[-2:] == 0).

Uso:
  python scripts/calibrate_isa.py [isa_history.json] [presenca.json] [--horizonte N]
    isa_history.json  padrao: history/isa_history.json
    presenca.json     padrao: ../nadarte-dashboard-automacao/presenca.json
    --horizonte N     semanas minimas entre T e o presente (padrao 4)

Enquanto nao houver >= horizonte semanas acumuladas, o script explica quanto falta.
"""
import os, sys, json, math, datetime

FEAT = ["eng", "tr", "ct", "vin", "pres"]         # indices 1..5 no vetor do snapshot
IDX = {"isa":0, "eng":1, "tr":2, "ct":3, "vin":4, "pres":5, "rec":6, "presCai":7}
FAIXAS = [("Saudável",80), ("Atenção",60), ("Risco moderado",40), ("Risco alto",20), ("Crítico",0)]

def auc(scores_pos, scores_neg):
    """AUC de Mann-Whitney: P(score_pos > score_neg). 'pos' = quem deu churn."""
    if not scores_pos or not scores_neg:
        return None
    allv = sorted(scores_pos + scores_neg)
    rank = {}; i = 0
    while i < len(allv):
        j = i
        while j < len(allv) and allv[j] == allv[i]:
            j += 1
        r = (i + j - 1) / 2.0 + 1
        for k in range(i, j):
            rank[allv[k]] = r
        i = j
    rp = sum(rank[s] for s in scores_pos)
    n1, n0 = len(scores_pos), len(scores_neg)
    return (rp - n1 * (n1 + 1) / 2.0) / (n1 * n0)

def wk_to_int(k):
    y, w = k.split("-W"); return int(y) * 100 + int(w)

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    hist_path = args[0] if len(args) > 0 else "history/isa_history.json"
    pres_path = args[1] if len(args) > 1 else "../nadarte-dashboard-automacao/presenca.json"
    horizonte = 4
    if "--horizonte" in sys.argv:
        horizonte = int(sys.argv[sys.argv.index("--horizonte") + 1])

    if not os.path.exists(hist_path):
        print("ERRO: %s nao existe (o snapshot ainda nao rodou)." % hist_path); sys.exit(2)
    if not os.path.exists(pres_path):
        print("ERRO: presenca.json nao encontrado em %s." % pres_path); sys.exit(2)
    hist = json.load(open(hist_path, encoding="utf-8"))
    pres = json.load(open(pres_path, encoding="utf-8"))
    alunos = pres.get("alunos", {})
    week_ref = pres.get("weekRef", "?")

    weeks = sorted([w for w in hist.keys() if hist[w]], key=wk_to_int)
    if not weeks:
        print("Historico do ISA vazio — nada a calibrar ainda."); sys.exit(0)

    # "presente" = semana ISO do weekRef da presenca (data de observacao do churn)
    try:
        yy, ww, _ = datetime.date.fromisoformat(str(week_ref)).isocalendar()
        now_int = yy * 100 + ww
    except Exception:
        now_int = wk_to_int(weeks[-1])
    # semana-alvo T = a mais antiga que esta >= horizonte semanas antes do presente
    candidatas = [w for w in weeks if now_int - wk_to_int(w) >= horizonte]
    if not candidatas:
        atual = now_int - wk_to_int(weeks[0])
        print("== Backtest prospectivo do ISA ==")
        print("Historico atual: %d semana(s) [%s .. %s] · presente %s." % (len(weeks), weeks[0], weeks[-1], week_ref))
        print("Preciso de >= %d semanas entre a medicao e o presente para observar o churn." % horizonte)
        print("Maior horizonte disponivel: %d semana(s). Faltam ~%d." % (max(0, atual), max(1, horizonte - atual)))
        print("(A infraestrutura ja esta coletando o snapshot semanal — nada a fazer agora.)")
        sys.exit(0)

    T = candidatas[0]
    snap = hist[T]
    # churn observado no presente, por aluno presente em AMBOS
    pos_isa, neg_isa = [], []           # pos = churnou
    dim_pos = {d: [] for d in FEAT}; dim_neg = {d: [] for d in FEAT}
    faixa_ct = {f[0]: [0, 0] for f in FAIXAS}   # nome -> [churn, total]
    n_join = 0
    for hmat, vec in snap.items():
        a = alunos.get(hmat)
        if not a: continue
        wk = a.get("wk", [])
        if len(wk) < 2: continue
        churn = 1 if sum(wk[-2:]) == 0 else 0
        n_join += 1
        isa = vec[IDX["isa"]]
        (pos_isa if churn else neg_isa).append(100 - isa)   # risco = 100-ISA
        for d in FEAT:
            v = vec[IDX[d]]
            if v is None or v == -1:  # pres pode ser -1 (n/a)
                continue
            (dim_pos[d] if churn else dim_neg[d]).append(100 - v)
        for nome, lo in FAIXAS:
            if isa >= lo:
                faixa_ct[nome][0] += churn; faixa_ct[nome][1] += 1
                break

    print("== Backtest prospectivo do ISA ==")
    print("Medicao em %s -> churn observado em %s (horizonte %d sem)." % (T, week_ref, now_int - wk_to_int(T)))
    print("Alunos cruzados (ISA em T x presenca agora): %d" % n_join)
    if n_join < 50:
        print("Amostra pequena (<50) — resultado apenas indicativo.")
    a_isa = auc(pos_isa, neg_isa)
    print("\nAUC do ISA -> churn: %s  (0,5=aleatorio; >0,70=bom)" % ("%.3f" % a_isa if a_isa else "n/d"))
    print("\nTaxa de churn por faixa do ISA (esperado: cai da Critico p/ Saudavel):")
    for nome, _ in FAIXAS:
        c, t = faixa_ct[nome]
        if t: print("  %-16s n=%-5d churn=%.1f%%" % (nome, t, 100 * c / t))
    print("\nPoder preditivo por dimensao (AUC) e peso sugerido:")
    aucs = {}
    for d in FEAT:
        ad = auc(dim_pos[d], dim_neg[d]); aucs[d] = ad
        print("  %-5s AUC=%s" % (d, "%.3f" % ad if ad else "n/d"))
    # peso sugerido ~ (AUC-0,5) normalizado entre as dimensoes com sinal
    edge = {d: max(0.0, (aucs[d] or 0.5) - 0.5) for d in FEAT}
    tot = sum(edge.values())
    if tot > 0:
        print("\nPesos sugeridos (proporcionais ao ganho sobre o acaso):")
        for d in FEAT:
            print("  %-5s %.2f" % (d, edge[d] / tot))
        print("Compare com ISA_W5 atual: pres .25 · eng .20 · tr .25 · ct .20 · vin .10")
    print("\n(Interprete com cuidado: 1 janela, churn definido por 2 semanas sem catraca.)")

if __name__ == "__main__":
    main()
