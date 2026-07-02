#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
probe_treino.py — explorador de endpoints (referencia). Ja usado na descoberta.
Mantido no repo para futuras investigacoes (ex.: KPI7 nota, feed por aluno).
"""
import os, sys, json, urllib.request, urllib.error

BASE = "https://apigw.pactosolucoes.com.br"
KEYS = ["PACTO_KEY_716NORTE", "PACTO_KEY_905SUL", "PACTO_KEY_604NORTE",
        "PACTO_KEY_LAGONORTE", "PACTO_KEY_LAGOSUL", "PACTO_KEY_NATAL"]

def get(key, path, empresa=1, timeout=25):
    h = {"Authorization": "Bearer " + key, "Accept": "application/json"}
    if empresa is not None:
        h["empresaId"] = str(empresa)
    try:
        with urllib.request.urlopen(urllib.request.Request(BASE + path, headers=h), timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, (e.read().decode("utf-8", "replace") if e.fp else "")
    except Exception as ex:
        return -1, str(ex)[:80]

def shape(body):
    try:
        j = json.loads(body)
    except Exception:
        return "(nao-JSON %d chars)" % len(body)
    def d(x, depth=0):
        if isinstance(x, dict):
            inner = " ->" + d(x["content"], depth + 1) if ("content" in x and depth == 0) else ""
            return "obj{%s}%s" % (", ".join(list(x.keys())[:30]), inner)
        if isinstance(x, list):
            return "lista[%d]%s" % (len(x), (" item0=" + d(x[0], depth + 1) if x else ""))
        return type(x).__name__
    return d(j)

def main():
    key = None
    for k in KEYS:
        if os.environ.get(k):
            key = os.environ[k]; break
    if not key:
        print("sem chave", file=sys.stderr); sys.exit(1)
    endpoints = [
        "/psec/treino-bi/dados?idProfessor=1",
        "/psec/treino-bi/gerados-executados",
        "/psec/treino-bi/resumo-execucoes-periodo/1",
        "/psec/treino-bi/carteira",
        "/psec/treino-bi/contagem-treinos-aprovar",
        "/psec/avaliacao-fisica-bi?dataInicio=1704067200000&dataFim=1798761600000",
    ]
    for p in endpoints:
        st, body = get(key, p)
        print("%5s  %-52s  %s" % (st, p[:52], shape(body)[:220]), file=sys.stderr)

if __name__ == "__main__":
    main()
