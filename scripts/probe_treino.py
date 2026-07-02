#!/usr/bin/env python3

# -*- coding: utf-8 -*-

"""

probe_treino.py (v4 FINAL) — confirma avaliacao-fisica-bi (KPI4/5) e avaliacao-treino (KPI7).

empresaId=1. PII-safe.

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

def line(st, name, body):

    print("%5s  %-40s  %s" % (st, name, shape(body)[:300]), file=sys.stderr)

def main():

    key = None

    for k in KEYS:

        if os.environ.get(k):

            key = os.environ[k]; break

    if not key:

        print("sem chave", file=sys.stderr); sys.exit(1)

    di, df = 1704067200000, 1798761600000  # 2024-01 .. 2026-12 (janela ampla)

    # KPI 4/5 — Avaliacao Fisica BI (dataInicio/dataFim + empresaId)

    st, body = get(key, "/psec/avaliacao-fisica-bi?dataInicio=%d&dataFim=%d" % (di, df))

    line(st, "avaliacao-fisica-bi (KPI4/5)", body)

    # KPI 7 — nota do treino: tipoBusca 0=todas; e por estrela (1..5) p/ distribuicao (NPS)

    for tb in [0, 5, 4, 3, 2, 1]:

        st, body = get(key, "/psec/treino-bi/avaliacao-treino/%d/1?professorId=1&size=3" % tb)

        line(st, "avaliacao-treino tipoBusca=%d" % tb, body)

if __name__ == "__main__":

    main()
