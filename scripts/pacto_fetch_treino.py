#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pacto_fetch_treino.py — COLETOR REAL (App Treino)

Parte 1 (por unidade, agregados de BI): dados/carteira/aprovar/avaliacao-fisica.
Parte 2 (Professores 360): bi-professores-vinculos.
Parte 3 (CRM 360 por ALUNO): /clientes/simples (carteira paginada) + /psec/alunos/alunoApp
  (usa o app?) por aluno elegivel. Classifica Engajado/Morno/Em risco (uso do app + contrato).

Saida: data/treino.json = {gerado_em, unidades[], professores[], alunos[], categorias{}}
Datas em epoch ms. Auth Bearer por unidade, header empresaId:1. Respostas {content:...}.
"""
import os, sys, json, time, random, datetime, unicodedata
import urllib.request, urllib.error, urllib.parse
from concurrent.futures import ThreadPoolExecutor

BASE = "https://apigw.pactosolucoes.com.br"
UNITS = [
    ("716Norte", "716 Norte", "PACTO_KEY_716NORTE"),
    ("905Sul",   "905 Sul",   "PACTO_KEY_905SUL"),
    ("604Norte", "604 Norte", "PACTO_KEY_604NORTE"),
    ("LagoNorte","Lago Norte","PACTO_KEY_LAGONORTE"),
    ("LagoSul",  "Lago Sul",  "PACTO_KEY_LAGOSUL"),
    ("Natal",    "Natal/RN",  "PACTO_KEY_NATAL"),
]
NOW = datetime.datetime.utcnow()
NOW_MS = int(NOW.timestamp() * 1000)

# ---------------------------------------------------------------- HTTP
def http_get(key, path, tries=4, timeout=35):
    for i in range(tries):
        req = urllib.request.Request(BASE + path, headers={
            "Authorization": "Bearer " + key, "Accept": "application/json", "empresaId": "1"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and i < tries - 1:
                time.sleep(min(10, 0.8 * (2 ** i)) + random.random()); continue
            return e.code, ""
        except Exception:
            if i < tries - 1:
                time.sleep(1 + i); continue
            return -1, ""
    return -1, ""

def content(key, path):
    st, body = http_get(key, path)
    if st != 200:
        print("  [warn] %s -> %s" % (path, st), file=sys.stderr)
        return {}
    try:
        j = json.loads(body)
        c = j.get("content", j)
        return c if isinstance(c, (dict, list)) else {"valor": c}
    except Exception:
        return {}

def q(**kw):
    return urllib.parse.urlencode({k: v for k, v in kw.items() if v is not None})

def num(d, *keys):
    for k in keys:
        if isinstance(d, dict) and d.get(k) is not None:
            try:
                return float(d[k])
            except Exception:
                return d[k]
    return None

# ---------------------------------------------------------------- CRM helpers
def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

# palavras que indicam publico NAO-elegivel ao App Treino (agua / lutas)
NAO_ELEG = ("AGUA","NATA","HIDRO","SWIM","LUTA","JIU","BOX","MUAY","KARATE","JUDO","TAEKW","MMA")
# palavras que indicam elegivel (fitness / musculacao / ambos)
ELEG = ("FIT","AMBOS","MUSCU","TREINO","CROSS","FUNCIONAL","GYM","PILATES","PESO","MUSC")

def elegivel(categoria):
    c = strip_accents(str(categoria or "")).upper()
    if not c:
        return True  # sem categoria -> incluir (nao perder aluno); ver distribuicao no log
    if any(x in c for x in NAO_ELEG):
        return False
    if any(x in c for x in ELEG):
        return True
    return True  # desconhecido -> incluir; refinar heuristica se a distribuicao pedir

def parse_date_ms(v):
    """Aceita epoch ms (int/str numerica) ou string ISO / dd-mm-aaaa / dd/mm/aaaa."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v).strip()
    if not s:
        return None
    if s.isdigit():
        return int(s)
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return int(datetime.datetime.strptime(s[:19], fmt).timestamp() * 1000)
        except Exception:
            continue
    try:
        return int(datetime.datetime.fromisoformat(s[:19]).timestamp() * 1000)
    except Exception:
        return None

def classifica(usa_app, fim_ms):
    """1a) uso do app + contrato. dias = quanto falta para o fim do contrato."""
    dias = (fim_ms - NOW_MS) / 86400000.0 if fim_ms else None
    contrato_risco = (dias is not None) and (dias <= 30)   # a vencer (<=30d) ou vencido (<0)
    contrato_ok = not contrato_risco
    if usa_app and contrato_ok:
        return "engajado"
    if (not usa_app) and contrato_risco:
        return "risco"
    return "morno"

def fetch_carteira(key, ulabel):
    """Puxa a base ativa paginando /clientes/simples de forma adaptativa.
    Lida com: size respeitado (paginas grandes), size ignorado (20/pag mas page ok),
    e page ignorado (para apos detectar nao-avanco)."""
    seen = {}
    prev_first = None
    page = 0
    while page < 300:
        st, body = http_get(key, "/clientes/simples?" + q(page=page, size=200))
        try:
            j = json.loads(body); c = j.get("content", j)
        except Exception:
            c = None
        if st != 200 or not isinstance(c, list) or not c:
            break
        fid = c[0].get("codigoCliente") or c[0].get("matricula")
        if fid == prev_first and page > 0:
            break  # paginacao nao avancou (page ignorado)
        novos = 0
        for it in c:
            cid = it.get("codigoCliente") or it.get("matricula")
            if cid is not None and cid not in seen:
                seen[cid] = it; novos += 1
        if novos == 0:
            break
        prev_first = fid
        page += 1
    print("  [carteira] %s: %d alunos em %d pagina(s)" % (ulabel, len(seen), page), file=sys.stderr)
    return list(seen.values())

def usa_app(key, cid):
    st, body = http_get(key, "/psec/alunos/alunoApp?" + q(cliente=cid), tries=3, timeout=20)
    if st != 200:
        return None
    try:
        j = json.loads(body); c = j.get("content", j)
        v = c.get("usaApp") if isinstance(c, dict) else None
        return bool(v)
    except Exception:
        return None

# ---------------------------------------------------------------- por unidade
def coleta_unidade(uk, ulabel, key):
    print("[coleta] %s..." % ulabel, file=sys.stderr)
    df = NOW_MS
    di = int((NOW - datetime.timedelta(days=365)).timestamp() * 1000)

    dados = content(key, "/psec/treino-bi/dados?idProfessor=0")  # 0 = TOTAL da unidade
    cart  = content(key, "/psec/treino-bi/carteira")
    aprov = content(key, "/psec/treino-bi/contagem-treinos-aprovar")
    avf   = content(key, "/psec/avaliacao-fisica-bi?dataInicio=%d&dataFim=%d" % (di, df))

    # Professores 360
    profs = []
    raw = content(key, "/psec/colaboradores/bi-professores-vinculos")
    if isinstance(raw, list):
        for p in raw:
            pr = p.get("professor", {}) or {}
            bi = p.get("biTreinoTreinamentoDTO", {}) or {}
            tp = bi.get("tempoPermanenciaPrograma") or {}
            profs.append({
                "unit": uk, "unitNome": ulabel,
                "id": pr.get("id"), "nome": pr.get("nome"),
                "comTreino": num(bi, "alunosAtivosComTreino"),
                "semTreino": num(bi, "alunosAtivosSemTreino"),
                "emDia": num(bi, "alunosAtivosProgramaEmDia"),
                "vencidos": num(bi, "alunosProgramaVencidos"),
                "renovar": num(bi, "alunosProgramaRenovar"),
                "pctEmDia": num(bi, "porcentagemTreinosEmDia"),
                "renovar30": num(bi, "treinosRenovarEm30Dias"),
                "tempoMedio": num(tp, "medio") if isinstance(tp, dict) else None,
            })

    # ---- CRM por aluno ----
    carteira = fetch_carteira(key, ulabel)
    cat_dist = {}
    elegiveis = []
    for it in carteira:
        cat = str(it.get("categoria") or "").strip() or "(sem categoria)"
        cat_dist[cat] = cat_dist.get(cat, 0) + 1
        if elegivel(it.get("categoria")):
            elegiveis.append(it)

    # uso do app (concorrente) apenas para elegiveis
    def _app(it):
        cid = it.get("codigoCliente") or it.get("matricula")
        return cid, usa_app(key, cid)
    app_map = {}
    if elegiveis:
        with ThreadPoolExecutor(max_workers=8) as ex:
            for cid, v in ex.map(_app, elegiveis):
                app_map[cid] = v

    alunos = []
    for it in elegiveis:
        cid = it.get("codigoCliente") or it.get("matricula")
        fim_ms = parse_date_ms(it.get("fimContrato"))
        ua = app_map.get(cid)
        faixa = classifica(bool(ua), fim_ms)
        alunos.append({
            "unit": uk, "unitNome": ulabel,
            "nome": it.get("nome"),
            "matricula": it.get("matricula"),
            "foto": it.get("urlFoto"),
            "categoria": it.get("categoria"),
            "situacao": it.get("situacao"),
            "situacaoContrato": it.get("situacaoContrato"),
            "inicioContrato": parse_date_ms(it.get("inicioContrato")),
            "fimContrato": fim_ms,
            "diasContrato": round((fim_ms - NOW_MS) / 86400000.0) if fim_ms else None,
            "telefone": it.get("telefone"),
            "email": it.get("email"),
            "usaApp": ua,
            "faixa": faixa,
        })

    resumo = {
        "carteiraTotal": len(carteira),
        "elegiveis": len(elegiveis),
        "appSim": sum(1 for a in alunos if a["usaApp"] is True),
        "appNao": sum(1 for a in alunos if a["usaApp"] is False),
        "engajado": sum(1 for a in alunos if a["faixa"] == "engajado"),
        "morno":    sum(1 for a in alunos if a["faixa"] == "morno"),
        "risco":    sum(1 for a in alunos if a["faixa"] == "risco"),
    }

    unidade = {
        "id": uk, "nome": ulabel,
        "totalAlunos": num(dados, "totalAlunos"),
        "totalAlunosAtivos": num(dados, "totalAlunosAtivos"),
        "totalAlunosComTreino": num(dados, "totalAlunosComTreino"),
        "totalAlunosSemTreino": num(dados, "totalAlunosSemTreino"),
        "percUtilizamApp": num(dados, "percUtilizamApp"),
        "percentualEmDia": num(dados, "percentualEmDia"),
        "totalTreinosVencidos": num(dados, "totalTreinosVencidos"),
        "totalTreinosEmDia": num(dados, "totalTreinosEmdia", "totalTreinosEmDia"),
        "totalTreinosRenovar": num(dados, "totalTreinosRenovar"),
        "tempoMedioPermanenciaTreino": num(dados, "tempoMedioPermanenciaTreino"),
        "agendamentos": num(dados, "agendamentos"),
        "compareceram": num(dados, "compareceram"),
        "acompanhamentoEm": num(cart, "totalAlunosEmAcompanhamento"),
        "acompanhamentoSem": num(cart, "totalAlunosSemAcompanhamento"),
        "taxaRenovacao": num(cart, "taxaRenovacaoZW", "taxaRenovacao"),
        "treinosAprovar": num(aprov, "valor") if isinstance(aprov, dict) else aprov,
        "avaliacoesRealizadas": num(avf, "realizadas"),
        "avaliacoesAtrasadas": num(avf, "atrasadas"),
        "avaliacoesReavaliacoes": num(avf, "reavaliacoes"),
        "avaliacoesPrevistas": num(avf, "previstas"),
        "avaliacoesSem": num(avf, "semAvaliacao"),
        "crm": resumo,
    }
    return {"unit": unidade, "profs": profs, "alunos": alunos, "cat_dist": cat_dist}

# ---------------------------------------------------------------- main
def main():
    resultados = {}
    def run(u):
        uk, ulabel, env = u
        key = os.environ.get(env)
        if not key:
            print("[skip] %s: sem %s" % (ulabel, env), file=sys.stderr); return
        try:
            resultados[uk] = coleta_unidade(uk, ulabel, key)
        except Exception as ex:
            print("[erro] %s: %s" % (ulabel, ex), file=sys.stderr)
    with ThreadPoolExecutor(max_workers=len(UNITS)) as ex:
        list(ex.map(run, UNITS))

    os.makedirs("data", exist_ok=True)
    unidades, professores, alunos = [], [], []
    cat_total = {}
    for k in sorted(resultados):
        r = resultados[k]
        unidades.append(r["unit"])
        professores.extend(r.get("profs", []))
        alunos.extend(r.get("alunos", []))
        for cat, n in r.get("cat_dist", {}).items():
            cat_total[cat] = cat_total.get(cat, 0) + n

    out = {"gerado_em": NOW.isoformat() + "Z",
           "unidades": unidades, "professores": professores,
           "alunos": alunos, "categorias": cat_total}
    with open("data/treino.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print("OK -> data/treino.json (%d unidades, %d professores, %d alunos elegiveis)"
          % (len(unidades), len(professores), len(alunos)), file=sys.stderr)
    print("[categorias] distribuicao na base ativa (para conferir o corte elegivel):", file=sys.stderr)
    for cat, n in sorted(cat_total.items(), key=lambda x: -x[1]):
        print("    %6d  %s" % (n, cat), file=sys.stderr)

if __name__ == "__main__":
    main()
