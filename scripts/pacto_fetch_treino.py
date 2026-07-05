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

# modo diagnostico: pula o alunoApp (coleta rapida) e so mede as distribuicoes
_d = (os.environ.get("PACTO_DIAG") or "").strip().lower()
DIAG = _d not in ("", "false", "0", "no")

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

# tokens que marcam cliente NAO-ativo (situacao / situacaoContrato)
INATIVO_TOK = ("INATIV","CANCEL","DESIST","TRANC","BLOQ","EXCLU","EXPIR","SUSPEN","DESLIG","TESTE")

def ativo(it):
    """Base ATIVA = situacao == 'ATIVO'. Confirmado por diagnostico (history/diag.json):
    ATIVO ~4,5k (bate com o BI); INATIVO/VISITANTE/TRANCADO ficam de fora. A base
    /clientes/simples devolve ~81k registros historicos — por isso o corte por situacao."""
    return strip_accents(str(it.get("situacao") or "")).strip().upper() == "ATIVO"

# --- Categoria / publico-alvo (LOGICA UNIFICADA com o dashboard de Frequencia) ---
# Fonte do texto: campo `descricao` do plano (em /clientes/{matricula}/dados-pessoais).
_AGUA  = ("NATAC","NATA","HIDRO","BEBE","AQUA")
_LUTAS = ("KARATE","MUAY","JIU","JUDO","HAPKIDO","CAPOEIRA","BOXE","TAEKWON","KUNG","LUTA")
_FIT   = ("TRANSITO LIVRE","FITNESS","MUSCULA","DANCA","PILATES","AULA COLETIVA","FUNCIONAL",
          "SPINNING","CROSS","ZUMBA","RITMO","GINASTICA","ALONGA","YOGA","TREINA")

def _up(s):
    return strip_accents(str(s or "")).upper().strip()

def _tok_cat(tok):
    t = _up(tok)                       # prioridade: Agua -> Fit -> Lutas (resolve ambiguidade)
    if any(k in t for k in _AGUA):  return "agua"
    if any(k in t for k in _FIT):   return "fit"
    if any(k in t for k in _LUTAS): return "lutas"
    return "outros"

def classify_grupo(descricao):
    """Devolve Fitness / Ambos / Agua / Lutas e Outros a partir do texto de modalidades."""
    toks = [t for t in str(descricao or "").replace(";", ",").split(",") if t.strip()]
    baldes = set(_tok_cat(t) for t in toks)
    if not baldes:                                        # sem modalidade -> Fitness (default)
        return "Fitness"
    if "agua" in baldes and ("fit" in baldes or "lutas" in baldes):
        return "Ambos"
    if "agua" in baldes:                                  # agua (ou agua+outros)
        return "Agua"
    if "fit" in baldes:
        return "Fitness"
    return "Lutas e Outros"                               # so lutas e/ou outros

ELEGIVEIS = ("Fitness", "Ambos")   # quem usa o App Treino

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
    """Base ativa via /clientes/simples com paginacao ROBUSTA (KB 5.2 — a base historica
    e instavel: totais oscilam e ha paginas vazias no meio). Estrategia:
      1) tenta filtrar situacao=ATIVO no servidor (muito mais rapido); se o filtro for
         ignorado, cai para varredura completa;
      2) le o total, pagina direcionado pelo total (size=200), re-tenta paginas vazias
         numa 2a passada e faz dedup por codigoCliente."""
    SIZE = 200

    def fetch_page(pg, extra, tries=3):
        for _ in range(tries):
            st, body = http_get(key, "/clientes/simples?" + q(page=pg, size=SIZE) + extra)
            if st != 200:
                time.sleep(0.5); continue
            try:
                j = json.loads(body)
            except Exception:
                time.sleep(0.5); continue
            c = j.get("content", j)
            if isinstance(c, dict):
                c = c.get("lista") or c.get("content") or []
            total = j.get("totalElements") or j.get("total") or j.get("totalRegistros")
            return (c if isinstance(c, list) else []), (int(total) if total else None)
        return [], None

    # 1) tenta o filtro situacao=ATIVO
    extra = "&situacao=ATIVO"
    first, total = fetch_page(0, extra)
    filtro_ok = bool(first) and all(strip_accents(str(x.get("situacao") or "")).upper() == "ATIVO" for x in first)
    if not filtro_ok:
        extra = ""                       # filtro ignorado/indisponivel -> varredura completa
        first, total = fetch_page(0, extra)

    seen = {}
    def add(items):
        for it in items:
            cid = it.get("codigoCliente") or it.get("matricula")
            if cid is not None and cid not in seen:
                seen[cid] = it
    add(first)

    n_pages = ((total + SIZE - 1) // SIZE + 2) if total else 450
    vazias, consec = [], 0
    for pg in range(1, n_pages):
        if total and len(seen) >= total:
            break
        items, _ = fetch_page(pg, extra)
        if not items:
            vazias.append(pg); consec += 1
            if not total and consec >= 8:   # sem total conhecido: para apos varias vazias seguidas
                break
            continue
        consec = 0
        add(items)
    # 2) 2a passada: re-tenta SO as paginas que vieram vazias (instabilidade)
    for pg in vazias:
        add(fetch_page(pg, extra)[0])

    print("  [carteira] %s: %d registros (filtro=%s, total=%s)" % (
        ulabel, len(seen), "ATIVO" if extra else "todos", total if total is not None else "?"), file=sys.stderr)
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

def categoria_aluno(key, matricula):
    """Publico-alvo do aluno: le `descricao` (modalidades) em dados-pessoais e classifica.
    Retorna a categoria (Fitness/Ambos/Agua/Lutas e Outros) ou None se a chamada falhar."""
    if matricula is None:
        return None
    st, body = http_get(key, "/clientes/%s/dados-pessoais" % matricula, tries=3, timeout=20)
    if st != 200:
        return None
    try:
        j = json.loads(body); c = j.get("content", j)
        desc = c.get("descricao") if isinstance(c, dict) else None   # so a modalidade (ignora cpf/PII)
        return classify_grupo(desc)
    except Exception:
        return None

# ---------------------------------------------------------------- por unidade
def coleta_unidade(uk, ulabel, key):
    print("[coleta] %s..." % ulabel, file=sys.stderr)
    df = NOW_MS
    di = int((NOW - datetime.timedelta(days=365)).timestamp() * 1000)

    dados = content(key, "/psec/treino-bi/dados?idProfessor=0")  # 0 = TOTAL da unidade
    # guarda: se a unidade voltar vazia/zerada (falha transitoria), tenta de novo
    for _try in range(3):
        if num(dados, "totalAlunos"):
            break
        time.sleep(2 + _try)
        print("  [retry] %s: BI dados veio vazio, tentando de novo (%d)" % (ulabel, _try + 1), file=sys.stderr)
        dados = content(key, "/psec/treino-bi/dados?idProfessor=0")
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

    # ---- Carteira ativa (o uso do app roda DEPOIS, em fila global controlada) ----
    carteira = fetch_carteira(key, ulabel)
    cat_dist, sit_dist, sitc_dist = {}, {}, {}
    ativos = []
    for it in carteira:
        cat = str(it.get("categoria") or "").strip() or "(sem categoria)"
        cat_dist[cat] = cat_dist.get(cat, 0) + 1
        sit = str(it.get("situacao") or "").strip() or "(sem situacao)"
        sit_dist[sit] = sit_dist.get(sit, 0) + 1
        sc = str(it.get("situacaoContrato") or "").strip() or "(sem situacaoContrato)"
        sitc_dist[sc] = sitc_dist.get(sc, 0) + 1
        if ativo(it):
            ativos.append(it)
    bi_total = num(dados, "totalAlunos")
    CAP = 4000  # teto de seguranca p/ nao estourar tempo se o filtro falhar
    if len(ativos) > CAP:
        print("  [aviso] %s: %d ativos > teto %d — limitando (revisar filtro)" % (ulabel, len(ativos), CAP), file=sys.stderr)
        ativos = ativos[:CAP]
    print("  [ativos] %s: %d ativos (carteira %d | BI diz %s)" % (
        ulabel, len(ativos), len(carteira), "-" if bi_total is None else str(int(bi_total))), file=sys.stderr)

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
    }
    return {"uk": uk, "ulabel": ulabel, "unit": unidade, "profs": profs, "ativos": ativos,
            "cat_dist": cat_dist, "sit_dist": sit_dist, "sitc_dist": sitc_dist,
            "carteiraTotal": len(carteira), "biTotal": bi_total}

# ---------------------------------------------------------------- main
def main():
    resultados = {}
    keys = {}
    # ---- FASE 1: agregados por unidade + carteira (paralelo entre unidades) ----
    def run(u):
        uk, ulabel, env = u
        key = os.environ.get(env)
        if not key:
            print("[skip] %s: sem %s" % (ulabel, env), file=sys.stderr); return
        keys[uk] = key
        try:
            resultados[uk] = coleta_unidade(uk, ulabel, key)
        except Exception as ex:
            print("[erro] %s: %s" % (ulabel, ex), file=sys.stderr)
    with ThreadPoolExecutor(max_workers=len(UNITS)) as ex:
        list(ex.map(run, UNITS))

    # ---- FASE 2: uso do app + categoria numa FILA GLOBAL (concorrencia limitada) ----
    tarefas = []  # (uk, key, cid, matricula)
    for uk in sorted(resultados):
        key = keys.get(uk)
        for it in resultados[uk].get("ativos", []):
            cid = it.get("codigoCliente") or it.get("matricula")
            tarefas.append((uk, key, cid, it.get("matricula")))
    app_res = {}  # (uk, cid) -> (usaApp True/False/None, categoria/None)
    n_true = n_false = n_fail = 0
    if tarefas and not DIAG:
        def _one(t):
            uk, key, cid, mat = t
            # categoria/publico-alvo NAO vem da API (categoria vazio, descricao ausente,
            # /v1/cliente sem plano, /v1/contrato 500) -> modalidade so na planilha.
            return (uk, cid, usa_app(key, cid), None)
        with ThreadPoolExecutor(max_workers=6) as ex:   # <= gentil com a API (1 chamada/aluno)
            for uk, cid, ua, cat in ex.map(_one, tarefas):
                app_res[(uk, cid)] = (ua, cat)
        # 2a tentativa (sequencial e leve) so para os que falharam no uso do app
        faltas = [(uk, key, cid, mat) for (uk, key, cid, mat) in tarefas if app_res.get((uk, cid), (None, None))[0] is None]
        if faltas:
            print("  [app] re-tentando %d chamadas que falharam..." % len(faltas), file=sys.stderr)
            for uk, key, cid, mat in faltas:
                time.sleep(0.12)
                app_res[(uk, cid)] = (usa_app(key, cid), None)
        for ua, _cat in app_res.values():
            n_true  += 1 if ua is True else 0
            n_false += 1 if ua is False else 0
            n_fail  += 1 if ua is None else 0
        print("[app] usaApp -> sim %d | nao %d | falha %d (de %d ativos)"
              % (n_true, n_false, n_fail, len(tarefas)), file=sys.stderr)

    # ---- FASE 3: montar alunos + resumo por unidade ----
    for uk in sorted(resultados):
        r = resultados[uk]
        u_alunos = []
        for it in r.get("ativos", []):
            cid = it.get("codigoCliente") or it.get("matricula")
            fim_ms = parse_date_ms(it.get("fimContrato"))
            ua, cat = app_res.get((uk, cid), (None, None))   # usaApp, categoria(publico-alvo)
            faixa = classifica(bool(ua), fim_ms) if ua is not None else "semdado"
            u_alunos.append({
                "unit": uk, "unitNome": r["ulabel"],
                "nome": it.get("nome"), "matricula": it.get("matricula"),
                "foto": it.get("urlFoto"),
                "categoria": cat, "elegivel": (cat in ELEGIVEIS) if cat else None,
                "situacao": it.get("situacao"), "situacaoContrato": it.get("situacaoContrato"),
                "inicioContrato": parse_date_ms(it.get("inicioContrato")), "fimContrato": fim_ms,
                "diasContrato": round((fim_ms - NOW_MS) / 86400000.0) if fim_ms else None,
                "telefone": it.get("telefone"), "email": it.get("email"),
                "usaApp": ua, "faixa": faixa,
            })
        r["alunos"] = u_alunos
        r["unit"]["crm"] = {
            "carteiraTotal": r.get("carteiraTotal", 0), "ativos": len(u_alunos),
            "appSim": sum(1 for a in u_alunos if a["usaApp"] is True),
            "appNao": sum(1 for a in u_alunos if a["usaApp"] is False),
            "appFalha": sum(1 for a in u_alunos if a["usaApp"] is None),
            "engajado": sum(1 for a in u_alunos if a["faixa"] == "engajado"),
            "morno": sum(1 for a in u_alunos if a["faixa"] == "morno"),
            "risco": sum(1 for a in u_alunos if a["faixa"] == "risco"),
            "semdado": sum(1 for a in u_alunos if a["faixa"] == "semdado"),
            "elegiveis": sum(1 for a in u_alunos if a["elegivel"] is True),
        }

    os.makedirs("data", exist_ok=True)
    unidades, professores, alunos = [], [], []
    cat_total, sit_total, sitc_total = {}, {}, {}
    carteira_total = ativos_total = 0
    for k in sorted(resultados):
        r = resultados[k]
        unidades.append(r["unit"])
        professores.extend(r.get("profs", []))
        alunos.extend(r.get("alunos", []))
        carteira_total += r.get("carteiraTotal", 0)
        ativos_total += len(r.get("alunos", []))
        for cat, n in r.get("cat_dist", {}).items():
            cat_total[cat] = cat_total.get(cat, 0) + n
        for sit, n in r.get("sit_dist", {}).items():
            sit_total[sit] = sit_total.get(sit, 0) + n
        for sc, n in r.get("sitc_dist", {}).items():
            sitc_total[sc] = sitc_total.get(sc, 0) + n

    out = {"gerado_em": NOW.isoformat() + "Z",
           "unidades": unidades, "professores": professores,
           "alunos": alunos, "categorias": cat_total}
    with open("data/treino.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    # diagnostico (agregado, SEM PII) — versionado no repo para inspecionar sem depender do log
    os.makedirs("history", exist_ok=True)
    diag = {"gerado_em": NOW.isoformat() + "Z", "diagMode": DIAG,
            "carteiraTotal": carteira_total, "ativos": ativos_total,
            "usoApp": {"sim": n_true, "nao": n_false, "falha": n_fail},
            "faixas": {f: sum(1 for a in alunos if a["faixa"] == f)
                       for f in ("engajado", "morno", "risco", "semdado")},
            "publicoAlvo": {c: sum(1 for a in alunos if a.get("categoria") == c)
                            for c in ("Fitness", "Ambos", "Agua", "Lutas e Outros")},
            "elegiveis": sum(1 for a in alunos if a.get("elegivel") is True),
            "biTotalPorUnidade": {r_["unit"]["nome"]: r_["unit"].get("totalAlunos")
                                  for r_ in resultados.values()},
            "situacao": dict(sorted(sit_total.items(), key=lambda x: -x[1])),
            "situacaoContrato": dict(sorted(sitc_total.items(), key=lambda x: -x[1])),
            "categoria": dict(sorted(cat_total.items(), key=lambda x: -x[1])[:15])}
    with open("history/diag.json", "w", encoding="utf-8") as f:
        json.dump(diag, f, ensure_ascii=False, indent=1)
    print("[diag] -> history/diag.json (carteira %d | ativos-heuristica %d | DIAG=%s)"
          % (carteira_total, ativos_total, DIAG), file=sys.stderr)

    print("OK -> data/treino.json (%d unidades, %d professores, %d alunos ATIVOS)"
          % (len(unidades), len(professores), len(alunos)), file=sys.stderr)
    print("[situacao] distribuicao na base (para conferir o filtro de ativos):", file=sys.stderr)
    for sit, n in sorted(sit_total.items(), key=lambda x: -x[1])[:12]:
        print("    %6d  %s" % (n, sit), file=sys.stderr)
    print("[categorias] distribuicao (campo categoria — hoje vazio nesta base):", file=sys.stderr)
    for cat, n in sorted(cat_total.items(), key=lambda x: -x[1])[:8]:
        print("    %6d  %s" % (n, cat), file=sys.stderr)

if __name__ == "__main__":
    main()
