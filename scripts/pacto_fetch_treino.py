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
import os, sys, json, time, random, datetime, unicodedata, re, hashlib
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
_FIT   = ("TRANSITO LIVRE"," TL ","LIVRE ACESSO","FITNESS","MUSCULA","DANCA","PILATES","AULA COLETIVA","FUNCIONAL",
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

# --- Modalidade em 7 baldes (a partir da descricao do contrato/plano) ---
# Fonte: GET /v1/contrato/matricula/{matricula} -> content[].descricao
def _tok7(tok):
    t = " " + _up(tok) + " "                 # padding p/ casar " TL "
    if any(k in t for k in _AGUA):  return "agua"
    if any(k in t for k in _FIT):   return "fit"
    if any(k in t for k in _LUTAS): return "lutas"
    return "outros"

def categoria7(desc):
    """Fitness / Agua / Luta / Ambos(A+F) / Ambos(A+L) / Ambos(F+L) / Ambos(A+F+L) / Outros."""
    u = _up(desc)
    if "TODAS AS MODALIDADES" in u or "TODAS MODALIDADES" in u:
        return "Ambos (Agua+Fitness+Luta)"    # plano completo
    toks = [t for t in re.split(r"[;,+/]", str(desc or "")) if t.strip()]
    b = set(_tok7(t) for t in toks); b.discard("outros")
    A, F, L = "agua" in b, "fit" in b, "lutas" in b
    if A and F and L: return "Ambos (Agua+Fitness+Luta)"
    if A and F:       return "Ambos (Agua+Fitness)"
    if A and L:       return "Ambos (Agua+Luta)"
    if F and L:       return "Ambos (Fitness+Luta)"
    if A:             return "Agua"
    if F:             return "Fitness"
    if L:             return "Luta"
    return "Outros"

def contrato_modalidade(key, matricula):
    """GET /v1/contrato/matricula/{matricula} -> (categoria7, descricaoPrincipal).
    (None,None) se a chamada falhar; ('Outros',None) se vier sem contrato/descricao."""
    if matricula is None:
        return (None, None)
    st, body = http_get(key, "/v1/contrato/matricula/%s" % matricula, tries=2, timeout=20)
    if st != 200:
        return (None, None)
    try:
        j = json.loads(body); c = j.get("content", j)
        itens = c if isinstance(c, list) else (c.get("content") if isinstance(c, dict) else None)
        if not isinstance(itens, list) or not itens:
            return ("Outros", None)
        descs = [str(x.get("descricao") or "") for x in itens if str(x.get("descricao") or "").strip()]
        if not descs:
            return ("Outros", None)
        return (categoria7(" , ".join(descs)), descs[0])
    except Exception:
        return (None, None)

# --- Cache de modalidade (janela TTL dias) — evita re-consultar o contrato todo dia ---
# A modalidade quase nao muda; so re-consultamos quem esta sem cache ou checado ha +TTL dias.
# PII-safe: chave = HASH da matricula (nunca o numero cru); valor = {m: balde, d: data-checagem}.
MODAL_CACHE_PATH = "history/modalidade_cache.json"
MODAL_TTL = int(os.environ.get("MODAL_TTL_DAYS", "7"))
def _mhash(mat):
    return hashlib.sha256(("nadarte:" + str(mat)).encode("utf-8")).hexdigest()[:16]
def _fresh(dstr):
    try:
        return (datetime.date.today() - datetime.date.fromisoformat(str(dstr))).days < MODAL_TTL
    except Exception:
        return False
def load_modal_cache():
    try:
        c = json.load(open(MODAL_CACHE_PATH, encoding="utf-8"))
        return c if isinstance(c, dict) else {}
    except Exception:
        return {}
def save_modal_cache(cache):
    try:
        os.makedirs(os.path.dirname(MODAL_CACHE_PATH), exist_ok=True)
        json.dump(cache, open(MODAL_CACHE_PATH, "w", encoding="utf-8"), ensure_ascii=False)
    except Exception as ex:
        print("[cache] falha ao salvar: %s" % ex, file=sys.stderr)

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

def prof_treino(key, cid, treino_codes):
    """Le /v1/cliente/{cid}.vinculos e devolve (fazTreino, profNome, profCod):
    fazTreino = aluno vinculado a algum colaborador que e professor de treino
    (codigo no conjunto `treino_codes`, vindo de bi-professores-vinculos).
    Modelo confirmado por probe (join colaborador.codigo == professor.id).
    (fazTreino=None se a chamada falhar)."""
    st, body = http_get(key, "/v1/cliente/%s" % cid, tries=3, timeout=20)
    if st != 200:
        return (None, None, None, None)
    try:
        j = json.loads(body); c = j.get("content", j)
        foto = None
        pes = c.get("pessoa") if isinstance(c, dict) else None
        if isinstance(pes, dict):
            foto = pes.get("fotoUrl") or pes.get("urlFoto")
        vinc = c.get("vinculos") if isinstance(c, dict) else None
        if not isinstance(vinc, list):
            return (None, None, None, foto)
        for v in vinc:
            col = v.get("colaborador") or {}
            cod = str(col.get("codigo"))
            if cod in treino_codes:
                return (True, col.get("nome"), cod, foto)   # 1o professor de treino vinculado
        return (False, None, None, foto)                    # tem vinculos, mas nenhum professor de treino
    except Exception:
        return (None, None, None, None)

# ---------------------------------------------------------------- por unidade
def normmat(m):
    """Chave canonica de matricula: remove zeros a esquerda / normaliza int-vs-str.
    Ex.: '019613' e 19613 viram ambos '19613' (evita mismatch no cruzamento)."""
    if m is None:
        return None
    try:
        return str(int(str(m).strip()))
    except Exception:
        return str(m).strip()


def treino_status_map(key):
    """matricula(normalizada) -> 'emdia' | 'vencido' cruzando as listas por-aluno (cp=0 = unidade toda).
    Endpoints confirmados por probe: /psec/treino-bi/alunos-treino-{em-dia,vencido}/{cp}.
    So usamos matricula (sem PII). Paginacao com trava anti-loop."""
    out = {}
    for ep, status in (("alunos-treino-em-dia", "emdia"), ("alunos-treino-vencido", "vencido")):
        seen = -1
        for page in range(0, 20):  # 0-INDEXED (confirmado): comeca na pagina 0
            lst = content(key, "/psec/treino-bi/%s/0?page=%d&size=1000" % (ep, page))
            items = lst if isinstance(lst, list) else (lst.get("content") if isinstance(lst, dict) else None)
            if not items:
                break
            for it in items:
                m = normmat(it.get("matricula"))
                if m is not None:
                    out[m] = status
            if len(items) < 1000 or len(out) == seen:  # ultima pagina OU pagina nao avancou
                break
            seen = len(out)
    return out


def prof_nota(key, pid):
    """Nota (estrelas) + treino em dia POR PROFESSOR via dados?idProfessor={pid}. Confirmado por probe."""
    d = content(key, "/psec/treino-bi/dados?idProfessor=%s" % pid)
    if not isinstance(d, dict):
        return {}
    e = {i: num(d, "nr%destrelas" % i) for i in range(1, 6)}
    tot = sum(int(x or 0) for x in e.values())
    nmed = (sum(i * int(e[i] or 0) for i in range(1, 6)) / tot) if tot else None
    return {
        "notaMedia": round(nmed, 2) if nmed is not None else None,
        "notaTotal": int(tot),
        "percentualAvaliacoes": num(d, "percentualAvaliacoes"),
    }


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
    trbi  = content(key, "/psec/treino-bi/treinamento")   # execucoes por dia da semana (mediaExecucao)

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
                "id": pr.get("id"), "nome": pr.get("nome"), "foto": pr.get("imageUri"),
                "comTreino": num(bi, "alunosAtivosComTreino"),
                "semTreino": num(bi, "alunosAtivosSemTreino"),
                "emDia": num(bi, "alunosAtivosProgramaEmDia"),
                "vencidos": num(bi, "alunosProgramaVencidos"),
                "renovar": num(bi, "alunosProgramaRenovar"),
                "pctEmDia": num(bi, "porcentagemTreinosEmDia"),
                "renovar30": num(bi, "treinosRenovarEm30Dias"),
                "tempoMedio": num(tp, "medio") if isinstance(tp, dict) else None,
            })
    # Nota do treino POR PROFESSOR (KPI7 por prof) — dados?idProfessor={id}, em paralelo leve
    _pids = [p for p in profs if p.get("id") is not None]
    if _pids:
        def _pn(p):
            p.update(prof_nota(key, p["id"]))
        with ThreadPoolExecutor(max_workers=5) as _pex:
            list(_pex.map(_pn, _pids))
    # Treino em dia / vencido POR ALUNO (KPI2 por aluno) — cruzamento por matricula
    treino_status = treino_status_map(key)
    print("  [treino-status] %s: %d matriculas classificadas (em dia/vencido)" % (
        ulabel, len(treino_status)), file=sys.stderr)

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

    # Nota do treino (estrelas) — vem de graca no /psec/treino-bi/dados (KPI7)
    _estr = {i: num(dados, "nr%destrelas" % i) for i in range(1, 6)}
    _ntot = sum(_estr.values())
    _nmed = (sum(i * _estr[i] for i in range(1, 6)) / _ntot) if _ntot else None
    # Execucoes por dia da semana (KPI1) — treinamento.mediaExecucao[dia].total
    _me = (trbi.get("mediaExecucao") if isinstance(trbi, dict) else None) or {}
    _DIAS = ["segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo"]
    _execDia = {d: int(num((_me.get(d) or {}), "total")) for d in _DIAS}
    _execSem = sum(_execDia.values())

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
        # ---- Nota do treino (estrelas) — KPI7 ----
        "nr1estrelas": _estr[1], "nr2estrelas": _estr[2], "nr3estrelas": _estr[3],
        "nr4estrelas": _estr[4], "nr5estrelas": _estr[5],
        "notaMedia": round(_nmed, 2) if _nmed is not None else None,
        "notaTotal": int(_ntot),
        "percentualAvaliacoes": num(dados, "percentualAvaliacoes"),
        # ---- Execucoes por dia da semana (treinos realizados) — KPI1 ----
        "execucoesSemana": _execSem,
        "execucoesPorDia": _execDia,
    }
    # codigos dos professores de treino desta unidade (p/ o join do vinculo do aluno)
    treino_codes = set(str(p["id"]) for p in profs if p.get("id") is not None)
    return {"uk": uk, "ulabel": ulabel, "unit": unidade, "profs": profs, "ativos": ativos,
            "treino_codes": treino_codes, "treino_status": treino_status,
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
    tcodes = {uk: resultados[uk].get("treino_codes", set()) for uk in resultados}
    tarefas = []  # (uk, key, cid, mat)
    for uk in sorted(resultados):
        key = keys.get(uk)
        for it in resultados[uk].get("ativos", []):
            cid = it.get("codigoCliente") or it.get("matricula")
            mat = it.get("matricula") or cid
            tarefas.append((uk, key, cid, mat))
    app_res = {}  # (uk, cid) -> (usaApp, fazTreino, profNome, profId, foto, modalidade)
    n_true = n_false = n_fail = n_treino = 0
    modal_cache = load_modal_cache()   # cache versionado (matricula hasheada -> {m, d})
    HOJE = datetime.date.today().isoformat()
    new_cache = {}                     # cache reconstruido (so matriculas da base atual -> auto-poda)
    src_cnt = {"cache": 0, "fetch": 0, "stale": 0}
    if tarefas and not DIAG:
        def _one(t):
            uk, key, cid, mat = t
            ua = usa_app(key, cid)                              # 1) usa o app?
            faz, pnome, pcod, foto = prof_treino(key, cid, tcodes.get(uk, set()))  # 2) faz treino? prof? foto?
            h = _mhash(mat)                                    # 3) modalidade: cache ou contrato
            ce = modal_cache.get(h)
            if ce and _fresh(ce.get("d")):
                modal, src = ce.get("m"), "cache"
            else:
                modal, _desc = contrato_modalidade(key, mat)
                if modal is None and ce:                       # falhou -> usa valor antigo, re-tenta depois
                    modal, src = ce.get("m"), "stale"
                else:
                    src = "fetch"
            return (uk, cid, ua, faz, pnome, pcod, foto, modal, mat, src)
        with ThreadPoolExecutor(max_workers=6) as ex:          # <= gentil com a API (ate 3 chamadas/aluno)
            for uk, cid, ua, faz, pnome, pcod, foto, modal, mat, src in ex.map(_one, tarefas):
                app_res[(uk, cid)] = (ua, faz, pnome, pcod, foto, modal)
                src_cnt[src] = src_cnt.get(src, 0) + 1
                h = _mhash(mat)
                if src == "fetch" and modal is not None:
                    new_cache[h] = {"m": modal, "d": HOJE}
                elif src == "cache":
                    new_cache[h] = modal_cache.get(h, {"m": modal, "d": HOJE})
                elif src == "stale" and modal_cache.get(h):
                    new_cache[h] = modal_cache[h]              # mantem data antiga -> re-consulta na proxima
        # 2a tentativa (sequencial e leve) so para os que falharam no uso do app
        faltas = [(uk, key, cid, mat) for (uk, key, cid, mat) in tarefas if app_res.get((uk, cid), (None,)*6)[0] is None]
        if faltas:
            print("  [app] re-tentando %d chamadas que falharam..." % len(faltas), file=sys.stderr)
            for uk, key, cid, mat in faltas:
                time.sleep(0.12)
                prev = app_res.get((uk, cid), (None,)*6)
                app_res[(uk, cid)] = (usa_app(key, cid), prev[1], prev[2], prev[3], prev[4], prev[5])
        for ua, faz, _pn, _pc, _f, _m in app_res.values():
            n_true  += 1 if ua is True else 0
            n_false += 1 if ua is False else 0
            n_fail  += 1 if ua is None else 0
            n_treino += 1 if faz is True else 0
        print("[app] usaApp -> sim %d | nao %d | falha %d | fazTreino %d (de %d ativos)"
              % (n_true, n_false, n_fail, n_treino, len(tarefas)), file=sys.stderr)
        save_modal_cache(new_cache)
        print("[modalidade] cache -> %d hit | %d fetch | %d stale | %d entradas salvas (TTL %dd)"
              % (src_cnt["cache"], src_cnt["fetch"], src_cnt["stale"], len(new_cache), MODAL_TTL), file=sys.stderr)

    # ---- FASE 3: montar alunos + resumo por unidade ----
    for uk in sorted(resultados):
        r = resultados[uk]
        tstat = r.get("treino_status", {})
        u_alunos = []
        for it in r.get("ativos", []):
            cid = it.get("codigoCliente") or it.get("matricula")
            fim_ms = parse_date_ms(it.get("fimContrato"))
            ua, faz, pnome, pcod, foto, modal = app_res.get((uk, cid), (None, None, None, None, None, None))
            faixa = classifica(bool(ua), fim_ms) if ua is not None else "semdado"
            _mat = it.get("matricula")
            treino_st = tstat.get(normmat(_mat)) if _mat is not None else None
            u_alunos.append({
                "unit": uk, "unitNome": r["ulabel"],
                "nome": it.get("nome"), "matricula": it.get("matricula"),
                "foto": foto,   # pessoa.fotoUrl (via /v1/cliente)
                "modalidade": modal,   # 7 baldes (via /v1/contrato/matricula)
                "treinoStatus": treino_st,   # 'emdia' | 'vencido' | None (via listas por-aluno)
                "fazTreino": faz, "professor": pnome, "professorId": pcod,
                "elegivel": faz,   # elegivel ao App Treino = faz treino (vinculo com prof. de treino)
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
            "treinoEmDia": sum(1 for a in u_alunos if a.get("treinoStatus") == "emdia"),
            "treinoVencido": sum(1 for a in u_alunos if a.get("treinoStatus") == "vencido"),
            "fazTreino": sum(1 for a in u_alunos if a["fazTreino"] is True),
            "naoFazTreino": sum(1 for a in u_alunos if a["fazTreino"] is False),
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

    # carteira real do professor: nº de alunos ativos vinculados a cada professor
    cart_por_prof = {}
    for a in alunos:
        pid = a.get("professorId")
        if pid: cart_por_prof[str(pid)] = cart_por_prof.get(str(pid), 0) + 1
    for p in professores:
        p["carteiraReal"] = cart_por_prof.get(str(p.get("id")), 0)

    out = {"gerado_em": NOW.isoformat() + "Z",
           "unidades": unidades, "professores": professores,
           "alunos": alunos, "categorias": cat_total}
    with open("data/treino.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    # diagnostico (agregado, SEM PII) — versionado no repo para inspecionar sem depender do log
    os.makedirs("history", exist_ok=True)
    faz = sum(1 for a in alunos if a.get("fazTreino") is True)
    nfaz = sum(1 for a in alunos if a.get("fazTreino") is False)
    diag = {"gerado_em": NOW.isoformat() + "Z", "diagMode": DIAG,
            "carteiraTotal": carteira_total, "ativos": ativos_total,
            "usoApp": {"sim": n_true, "nao": n_false, "falha": n_fail},
            "faixas": {f: sum(1 for a in alunos if a["faixa"] == f)
                       for f in ("engajado", "morno", "risco", "semdado")},
            "fazTreino": {"sim": faz, "nao": nfaz, "semVinculo": ativos_total - faz - nfaz},
            "professoresComCarteira": sum(1 for p in professores if p.get("carteiraReal")),
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
