#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pacto_fetch_treino.py — COLETOR do App Treino (API PACTO)

Reusa os padrões PROVADOS da migração dos dashboards de Frequência/Ocupação:
- Auth Bearer por unidade (Secrets), Accept json
- roster robusto de /clientes/simples (paginação instável -> re-tenta páginas vazias)
- backoff exponencial + jitter em 429/5xx
- 1 chave por unidade, unidades em paralelo (chaves independentes)

Escreve data/treino_raw.json (efêmero no runner; NÃO vai pro git).

⚠️ ENDPOINTS AINDA NÃO MAPEADOS: ficha, execução, avaliação, nota, atendimento.
   Rode antes o scripts/probe_treino.py, descubra os caminhos e preencha os
   trechos marcados com  # TODO(PROBE).
"""
import os, sys, json, time, random, hashlib, threading
import urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

BASE = "https://apigw.pactosolucoes.com.br"
JAN_MES_FECHADO = os.environ.get("JANELA_MES", "")  # ex.: "2026-06" (último mês completo)

UNITS = [
    ("716Norte", "716 Norte", "PACTO_KEY_716NORTE"),
    ("905Sul",   "905 Sul",   "PACTO_KEY_905SUL"),
    ("604Norte", "604 Norte", "PACTO_KEY_604NORTE"),
    ("LagoNorte","Lago Norte","PACTO_KEY_LAGONORTE"),
    ("LagoSul",  "Lago Sul",  "PACTO_KEY_LAGOSUL"),
    ("Natal",    "Natal/RN",  "PACTO_KEY_NATAL"),
]

# Mapa categoria PACTO -> Público Alvo do app. AJUSTAR com os valores reais de /clientes/simples.
# Só FITNESS e AMBOS usam o App Treino; ÁGUA e LUTAS ficam fora do denominador.
CATEGORIA_ELEGIVEL = {  # TODO: confirmar as strings exatas do campo `categoria`
    # "MUSCULACAO": "Fitness", "MUSC+NATACAO": "Ambos", ...
}
ELEGIVEIS = {"Fitness", "Ambos"}

def http_get(key, path, tries=5, timeout=30):
    url = BASE + path
    for i in range(tries):
        req = urllib.request.Request(url, headers={
            "Authorization": "Bearer " + key, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and i < tries - 1:
                time.sleep(min(12, 0.8 * (2 ** i)) + random.random()); continue
            return e.code, (e.read().decode("utf-8", "replace") if e.fp else "")
        except Exception:
            if i < tries - 1:
                time.sleep(1 + i); continue
            return -1, ""
    return -1, ""

def get_json(key, path):
    st, body = http_get(key, path)
    if st != 200:
        return None
    try:
        return json.loads(body)
    except Exception:
        return None

def roster_full(key):
    """Lista de clientes ATIVOS da unidade, tolerante à paginação instável."""
    first = get_json(key, "/clientes/simples?page=0&size=200") or {}
    total = first.get("totalElements") or first.get("total") or 0
    got = {}
    def add(page_obj):
        for c in (page_obj.get("content") or []):
            cid = c.get("codigoCliente")
            if cid is not None:
                got[cid] = c
    add(first)
    npages = (total // 200 + 3) if total else 60
    for passada in range(2):  # 2 passadas para preencher lacunas
        for p in range(npages):
            if total and len(got) >= total:
                break
            obj = get_json(key, f"/clientes/simples?page={p}&size=200")
            if obj:
                add(obj)
    return list(got.values())

def hash_matricula(unit_key, matricula):
    """Pseudônimo estável (sem PII) para publicar — NÃO expõe matrícula real."""
    return "A" + hashlib.sha1(f"{unit_key}:{matricula}".encode()).hexdigest()[:8]

def aluno_app(key, aluno):
    """Endpoint CONFIRMADO: usaApp + dataRegistroUsoApp por aluno."""
    matricula = aluno.get("matricula")
    if matricula is None:
        return None
    # a doc aceita alunoId/pessoa/cliente via query + header empresaId
    obj = get_json(key, f"/psec/alunos/alunoApp?cliente={aluno.get('codigoCliente')}")
    c = (obj or {}).get("content") or {}
    return {"usaApp": bool(c.get("usaApp")), "dataRegistroUsoApp": c.get("dataRegistroUsoApp")}

def coleta_unidade(uk, ulabel, key):
    roster = roster_full(key)
    ativos = [c for c in roster if (c.get("situacao") == "ATIVO")]
    alunos = []
    def do(c):
        cat_raw = c.get("categoria")
        publico = CATEGORIA_ELEGIVEL.get(cat_raw, None)  # None até mapear
        rec = {
            "id": hash_matricula(uk, c.get("matricula")),
            "unit": uk,
            "publico": publico,                 # Fitness/Ambos/Água/Lutas (após mapear)
            "usaApp": None,
            # ---- KPIs a preencher quando os endpoints forem mapeados ----
            "prof": None,                       # TODO(PROBE): professor da ficha
            "treinos": None,                    # TODO(PROBE): execução de treino
            "fichaStatus": None,                # TODO(PROBE): em_dia / vencida / sem_ficha
            "fichaAtualNoMes": None,            # TODO(PROBE)
            "avalStatus": None,                 # TODO(PROBE): em_dia / vencida / nunca
            "avalNoMes": None,                  # TODO(PROBE)
            "nota": None,                       # TODO(PROBE): nota do treino
            "atend": None,                      # TODO(PROBE): atendimentos recebidos
        }
        app = aluno_app(key, c)
        if app:
            rec["usaApp"] = app["usaApp"]
        alunos.append(rec)
    # ~2 workers por chave (gentil com rate-limit)
    with ThreadPoolExecutor(max_workers=2) as ex:
        list(ex.map(do, ativos))
    return {"unit": uk, "label": ulabel, "ativos": len(ativos), "alunos": alunos}

def main():
    resultados = {}
    def run(u):
        uk, ulabel, env = u
        key = os.environ.get(env)
        if not key:
            print(f"[skip] {ulabel}: sem {env} nos Secrets", file=sys.stderr); return
        print(f"[coleta] {ulabel}…", file=sys.stderr)
        resultados[uk] = coleta_unidade(uk, ulabel, key)
    # unidades em paralelo (chaves independentes)
    with ThreadPoolExecutor(max_workers=len(UNITS)) as ex:
        list(ex.map(run, UNITS))
    os.makedirs("data", exist_ok=True)
    with open("data/treino_raw.json", "w", encoding="utf-8") as f:
        json.dump({"janela": JAN_MES_FECHADO, "unidades": resultados}, f, ensure_ascii=False)
    print("OK -> data/treino_raw.json", file=sys.stderr)

if __name__ == "__main__":
    main()
