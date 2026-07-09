#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_treino.py — GATE + injeta os dados reais no template -> public/index.html
Uso: python scripts/build_treino.py        (valida e gera public/)
     python scripts/build_treino.py --check (so valida)
"""
import os, sys, json, datetime

RAW = "data/treino.json"
TEMPLATE = "template/index.html"
OUT_DIR = "public"
HIST = "history/serie.json"   # historico AGREGADO por dia (sem PII) — versionado no repo
MARKER = "/*__DATA__*/null"

def num(v):
    try: return float(v)
    except Exception: return 0.0

def snapshot(data):
    """Monta o snapshot AGREGADO de hoje (sem PII) para a serie historica."""
    unis = data.get("unidades", [])
    tot = sum(num(u.get("totalAlunos")) for u in unis) or 1
    usoApp = sum(num(u.get("percUtilizamApp")) * num(u.get("totalAlunos")) for u in unis) / tot
    emDia = sum(num(u.get("percentualEmDia")) * num(u.get("totalAlunos")) for u in unis) / tot
    # nota da rede: media ponderada por nº de avaliacoes (notaTotal) de cada unidade
    _nw = sum(num(u.get("notaTotal")) for u in unis)
    notaRede = (sum(num(u.get("notaMedia")) * num(u.get("notaTotal")) for u in unis) / _nw) if _nw else None
    execSemana = int(sum(num(u.get("execucoesSemana")) for u in unis))
    al = data.get("alunos", [])
    faixa = lambda f: sum(1 for a in al if a.get("faixa") == f)
    return {
        "data": datetime.date.today().isoformat(),
        "rede": {
            "usoApp": round(usoApp, 1), "emDiaPct": round(emDia, 1),
            "vencidos": int(sum(num(u.get("totalTreinosVencidos")) for u in unis)),
            "avalVencidas": int(sum(num(u.get("avaliacoesAtrasadas")) for u in unis)),
            "nota": round(notaRede, 2) if notaRede is not None else None,
            "execSemana": execSemana,
            "ativos": len(al), "engajado": faixa("engajado"), "morno": faixa("morno"),
            "risco": faixa("risco"), "semdado": faixa("semdado"),
            # uso do app por aluno (qualidade da coleta) e "faz treino" (via vinculo c/ prof.)
            "appSim": sum(1 for a in al if a.get("usaApp") is True),
            "appNao": sum(1 for a in al if a.get("usaApp") is False),
            "appFalha": sum(1 for a in al if a.get("usaApp") is None),
            "fazTreino": sum(1 for a in al if a.get("fazTreino") is True),
            "naoFazTreino": sum(1 for a in al if a.get("fazTreino") is False),
        },
        "unidades": [{"id": u.get("id"), "nome": u.get("nome"),
                      "usoApp": round(num(u.get("percUtilizamApp")), 1),
                      "emDiaPct": round(num(u.get("percentualEmDia")), 1),
                      "nota": (round(num(u.get("notaMedia")), 2) if u.get("notaMedia") is not None else None)} for u in unis],
    }

def atualiza_historico(data):
    """Le history/serie.json, faz upsert do dia de hoje, salva e devolve a serie (cap 365 dias)."""
    hist = []
    if os.path.exists(HIST):
        try: hist = json.load(open(HIST, encoding="utf-8"))
        except Exception: hist = []
    snap = snapshot(data)
    hist = [h for h in hist if h.get("data") != snap["data"]]  # substitui se ja houver hoje
    hist.append(snap)
    hist.sort(key=lambda h: h.get("data", ""))
    hist = hist[-365:]
    os.makedirs(os.path.dirname(HIST), exist_ok=True)
    json.dump(hist, open(HIST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("[historico] %d dia(s) acumulado(s) -> %s" % (len(hist), HIST), file=sys.stderr)
    return hist

def gate(data):
    problemas = []
    unis = data.get("unidades", [])
    if len(unis) < 3:
        problemas.append("poucas unidades: %d" % len(unis))
    com_dado = [u for u in unis if u.get("totalAlunos")]
    if len(com_dado) < 3:
        problemas.append("poucas unidades com totalAlunos > 0: %d" % len(com_dado))
    return problemas

def main():
    check = "--check" in sys.argv
    if not os.path.exists(RAW):
        print("ERRO: %s nao existe (rode o coletor)." % RAW, file=sys.stderr); sys.exit(2)
    data = json.load(open(RAW, encoding="utf-8"))
    probs = gate(data)
    if probs:
        print("GATE REPROVOU — nao publica (ultimo bom mantido):", file=sys.stderr)
        for p in probs: print("  -", p, file=sys.stderr)
        sys.exit(3)
    print("GATE OK (%d unidades)." % len(data.get("unidades", [])), file=sys.stderr)
    # resumo dos numeros reais (para conferencia no log)
    def sf(v):
        return "-" if v is None else (str(int(v)) if float(v) == int(v) else str(v))
    print("\n%-12s %8s %8s %8s %9s %9s %9s" % (
        "UNIDADE", "ALUNOS", "USO%APP", "EM_DIA", "VENCIDOS", "AVAL_OK", "AVAL_VEN"), file=sys.stderr)
    for u in data.get("unidades", []):
        print("%-12s %8s %8s %8s %9s %9s %9s" % (
            (u.get("nome") or "")[:12], sf(u.get("totalAlunos")), sf(u.get("percUtilizamApp")),
            sf(u.get("totalTreinosEmDia")), sf(u.get("totalTreinosVencidos")),
            sf(u.get("avaliacoesRealizadas")), sf(u.get("avaliacoesAtrasadas"))), file=sys.stderr)
    alunos = data.get("alunos", [])
    if alunos:
        eng = sum(1 for a in alunos if a.get("faixa") == "engajado")
        mor = sum(1 for a in alunos if a.get("faixa") == "morno")
        ris = sum(1 for a in alunos if a.get("faixa") == "risco")
        print("\nCRM por aluno: %d ativos (engajado %d · morno %d · risco %d) em %d professores"
              % (len(alunos), eng, mor, ris, len(data.get("professores", []))), file=sys.stderr)
    if check:
        return
    # acumula a serie historica (agregada, sem PII) e injeta junto
    data["historico"] = atualiza_historico(data)
    tpl = open(TEMPLATE, encoding="utf-8").read()
    if MARKER not in tpl:
        print("ERRO: marcador %r nao esta no template." % MARKER, file=sys.stderr); sys.exit(4)
    out = tpl.replace(MARKER, json.dumps(data, ensure_ascii=False))
    os.makedirs(OUT_DIR, exist_ok=True)
    open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8").write(out)
    print("OK -> %s/index.html" % OUT_DIR, file=sys.stderr)

if __name__ == "__main__":
    main()
