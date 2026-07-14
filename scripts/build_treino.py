#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_treino.py — GATE + injeta os dados reais no template -> public/index.html
Uso: python scripts/build_treino.py        (valida e gera public/)
     python scripts/build_treino.py --check (so valida)
"""
import os, sys, json, datetime, hashlib, re, unicodedata

RAW = "data/treino.json"
TEMPLATE = "template/index.html"
OUT_DIR = "public"
HIST = "history/serie.json"   # historico AGREGADO por dia (sem PII) — versionado no repo
MARKER = "/*__DATA__*/null"
AGENDA_FEED = "public/agenda_treino.json"   # Item 6 — fila do App Treino p/ a Agenda Tatica (origem='treino')
ISA_HIST = "history/isa_history.json"       # Item 10 — snapshot semanal do ISA por aluno (hasheado) p/ backtest

# ---- Item 10: porte fiel do ISA (mesma logica do template) para snapshot/backtest ----
ISA_W4 = {"eng":0.35, "tr":0.30, "ct":0.25, "vin":0.10}                 # sem presenca
ISA_W5 = {"pres":0.25, "eng":0.20, "tr":0.25, "ct":0.20, "vin":0.10}    # com presenca (ponte Frequencia)
def _pmh(m):
    return hashlib.sha256(str(m).encode("utf-8")).hexdigest()[:16]
def _isnum(x):
    return isinstance(x, (int, float))
def _naoprof(nome):
    s = unicodedata.normalize("NFD", str(nome or ""))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").upper()
    u = " " + s + " "
    if "PERSONAL EXTERNO" in u: return "Personal Externo"
    if re.search(r"TREINO POR IA|\bIA\b", u): return "Treino por IA"
    if re.search(r"PACTO|METODO DE GESTAO|\bGESTAO\b", u): return "Gestão"
    if re.search(r"NAO QUER PROFESSOR|SEM PROFESSOR|SOMENTE NATACAO", u): return "Sem Professor"
    return None
def isa_sub(a):
    d = a.get("recenciaDias")
    eng = (100 if d<=7 else 80 if d<=14 else 55 if d<=30 else 30 if d<=60 else 10) if _isnum(d) \
          else (55 if a.get("usaApp") is True else 20)
    ts = a.get("treinoStatus")
    tr = 100 if ts=="emdia" else (35 if ts=="vencido" else 10)
    dc = a.get("diasContrato")
    ct = (15 if dc<0 else 55 if dc<=30 else 82 if dc<=90 else 100) if _isnum(dc) else 75
    np_ = _naoprof(a.get("professor")); prof = a.get("professor")
    vin = 100 if (a.get("fazTreino") is True and prof and not np_) \
          else (25 if np_=="Sem Professor" else (85 if a.get("fazTreino") is True else 40))
    pd = a.get("presencaDias"); pres = None
    if _isnum(pd):
        pres = 100 if pd<=7 else 80 if pd<=14 else 50 if pd<=30 else 25 if pd<=60 else 8
        if a.get("presencaCai") is True: pres = max(0, pres-20)
    return {"pres":pres, "eng":eng, "tr":tr, "ct":ct, "vin":vin}
def isa_score(a):
    s = isa_sub(a); w = ISA_W5 if a.get("presencaDias") is not None else ISA_W4
    return round(sum((s.get(k) or 0) * w[k] for k in w))

def snapshot_isa(data):
    """Snapshot SEMANAL do ISA por aluno (matricula HASHEADA, sem PII) p/ backtest
    prospectivo. Chave = semana ISO (upsert: o ultimo build da semana vence).
    Guarda [isa, eng, tr, ct, vin, pres(-1=n/a), recenciaDias(-1=n/a), presCai(0/1)]
    — features suficientes p/ re-ajustar pesos contra o churn observado depois."""
    apta = [a for a in data.get("alunos", []) if "fitness" in str(a.get("modalidade") or "").lower()]
    y, w, _ = datetime.date.today().isocalendar()
    wk_key = "%04d-W%02d" % (y, w)
    snap = {}
    for a in apta:
        m = a.get("matricula")
        if not m: continue
        s = isa_sub(a)
        snap[_pmh(m)] = [isa_score(a), s["eng"], s["tr"], s["ct"], s["vin"],
                         (s["pres"] if s["pres"] is not None else -1),
                         (a["recenciaDias"] if _isnum(a.get("recenciaDias")) else -1),
                         (1 if a.get("presencaCai") is True else 0)]
    hist = {}
    if os.path.exists(ISA_HIST):
        try: hist = json.load(open(ISA_HIST, encoding="utf-8"))
        except Exception: hist = {}
    hist[wk_key] = snap                                  # upsert da semana corrente
    for k in sorted(hist.keys())[:-26]: hist.pop(k, None)   # mantem ~6 meses (26 semanas)
    os.makedirs(os.path.dirname(ISA_HIST), exist_ok=True)
    json.dump(hist, open(ISA_HIST, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("[isa] snapshot %s: %d aptos (hist %d semanas)" % (wk_key, len(snap), len(hist)), file=sys.stderr)
    return snap

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
    snapshot_isa(data)        # Item 10 — snapshot semanal do ISA por aluno p/ backtest prospectivo

if __name__ == "__main__":
    main()
