#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_treino.py — GATE + injeta os dados reais no template -> public/index.html
Uso: python scripts/build_treino.py        (valida e gera public/)
     python scripts/build_treino.py --check (so valida)
"""
import os, sys, json

RAW = "data/treino.json"
TEMPLATE = "template/index.html"
OUT_DIR = "public"
MARKER = "/*__DATA__*/null"

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
    tpl = open(TEMPLATE, encoding="utf-8").read()
    if MARKER not in tpl:
        print("ERRO: marcador %r nao esta no template." % MARKER, file=sys.stderr); sys.exit(4)
    out = tpl.replace(MARKER, json.dumps(data, ensure_ascii=False))
    os.makedirs(OUT_DIR, exist_ok=True)
    open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8").write(out)
    print("OK -> %s/index.html" % OUT_DIR, file=sys.stderr)

if __name__ == "__main__":
    main()
