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
AGENDA_FEED = "public/agenda_treino.json"   # Item 6 — fila do App Treino p/ a Agenda Tatica (origem='treino')

def num(v):
    try: return float(v)
    except Exception: return 0.0

# ---- Item 6: feed CRM do App Treino para o MOTOR da Agenda Tatica ----
# O motor.mjs (repo Frequencia) ja tem um slot `crm:[]` (hoje vazio) que consome
# {unidade,matricula,nome,cat,foto,faixa,usaApp,treinoVencido}. Publicamos exatamente
# esse formato: o motor faz o dedup (1 aluno = 1 card), soma pontos de CRM aos sinais
# de frequencia do mesmo aluno, pontua e distribui em blocos. Sem alterar a engine.
# Gatilho de card = sinal ACIONAVEL (faixa risco OU treino vencido). morno/sem-app
# NAO disparam card sozinhos (o motor promove todo candidato abaixo do teto, entao
# alimenta-los encheria a Agenda com ruido de baixo valor); eles seguem no payload
# apenas como enriquecimento de quem ja passou pelo gatilho. recenciaDias/presencaCai
# vao como contexto (o motor ignora campos extras; abrem caminho p/ evolucao futura).
AG_SLUG = {"716Norte":"716-norte","905Sul":"905-sul","604Norte":"604-norte",
           "LagoNorte":"lago-norte","LagoSul":"lago-sul","Natal":"natal-rn"}

def build_agenda_feed(data):
    al = data.get("alunos", [])
    isn = lambda x: isinstance(x, (int, float))
    apta = [a for a in al if "fitness" in str(a.get("modalidade") or "").lower()]
    crm = []
    for a in apta:
        slug = AG_SLUG.get(a.get("unit"))
        if not slug:
            continue
        faixa = a.get("faixa")
        venc = a.get("treinoStatus") == "vencido"
        ua = a.get("usaApp")
        # Gatilho de card = sinal ACIONAVEL: faixa risco OU treino vencido.
        # (morno/sem-app entram no payload como enriquecimento de quem ja passou por
        #  este filtro, mas nunca disparam card sozinhos -> evita encher o teto com ruido.)
        if not (faixa == "risco" or venc):
            continue
        rec = a.get("recenciaDias")
        crm.append({
            "unidade": slug, "matricula": str(a.get("matricula") or ""),
            "nome": a.get("nome") or "", "cat": "fitness", "foto": a.get("foto") or "",
            "faixa": faixa, "usaApp": ua, "treinoVencido": venc,
            "recenciaDias": rec if isn(rec) else None,
            "presencaCai": (a.get("presencaCai") is True),
        })
    feed = {"gerado": datetime.date.today().isoformat(), "origem": "treino", "crm": crm}
    os.makedirs(os.path.dirname(AGENDA_FEED), exist_ok=True)
    json.dump(feed, open(AGENDA_FEED, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    porf = {}
    for c in crm:
        k = c["faixa"] or "—"
        porf[k] = porf.get(k, 0) + 1
    print("[agenda] %s: %d candidatos CRM p/ o motor %s" % (AGENDA_FEED, len(crm), porf), file=sys.stderr)
    return feed

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
    # Item 7 — metricas de risco (base apta) para tendencia historica
    _isnum = lambda x: isinstance(x, (int, float))
    apta = [a for a in al if "fitness" in str(a.get("modalidade") or "").lower()]
    recRec = sum(1 for a in apta if _isnum(a.get("recenciaDias")) and a["recenciaDias"] <= 14)
    aband = sum(1 for a in apta if _isnum(a.get("diasContrato")) and a["diasContrato"] >= 0 and a.get("fazTreino") is True
                and ((_isnum(a.get("recenciaDias")) and a["recenciaDias"] >= 30) or a.get("treinoStatus") == "vencido"))
    comp = sum(1 for a in apta if (a.get("presencaCai") is True or (_isnum(a.get("presencaDias")) and a["presencaDias"] >= 15))
               and (_isnum(a.get("recenciaDias")) and a["recenciaDias"] >= 15))
    presCob = sum(1 for a in apta if _isnum(a.get("presencaDias")))
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
            # Item 7 — risco (base apta) p/ tendencia
            "aptos": len(apta), "recRecente": recRec, "abandonados": aband,
            "riscoComposto": comp, "presencaCobertura": presCob,
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
    build_agenda_feed(data)   # Item 6 — publica a fila do App Treino p/ a Agenda Tatica

if __name__ == "__main__":
    main()
