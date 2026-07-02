#!/usr/bin/env python3

# -*- coding: utf-8 -*-

"""

probe_treino.py (v6 fase2) — caca execucoes (KPI1) e nota do treino (KPI7).

PII-safe: chaves/valores agregados; usa 1 codigoPessoa real so para abrir o endpoint de nota.

"""

import os, sys, json, datetime, urllib.request, urllib.error

BASE = "https://apigw.pactosolucoes.com.br"

KEYS = ["PACTO_KEY_716NORTE", "PACTO_KEY_905SUL", "PACTO_KEY_604NORTE",

        "PACTO_KEY_LAGONORTE", "PACTO_KEY_LAGOSUL", "PACTO_KEY_NATAL"]

def get(key, path, timeout=25):

    h = {"Authorization": "Bearer " + key, "Accept": "application/json", "empresaId": "1"}

    try:

        with urllib.request.urlopen(urllib.request.Request(BASE + path, headers=h), timeout=timeout) as r:

            return r.status, r.read().decode("utf-8", "replace")

    except urllib.error.HTTPError as e:

        return e.code, (e.read().decode("utf-8", "replace") if e.fp else "")

    except Exception as ex:

        return -1, str(ex)[:80]

def shape(body, full=False):

    try:

        j = json.loads(body)

    except Exception:

        return "(nao-JSON %d)" % len(body)

    def d(x, depth=0):

        if isinstance(x, dict):

            ks = list(x.keys())

            inner = " ->" + d(x["content"], depth + 1) if ("content" in x and depth == 0) else ""

            return "obj{%s}%s" % (", ".join(ks[:40 if full else 20]), inner)

        if isinstance(x, list):

            return "lista[%d]%s" % (len(x), (" item0=" + d(x[0], depth + 1) if x else ""))

        return type(x).__name__

    return d(j)

def line(st, name, body, full=False):

    print("%5s  %-40s  %s" % (st, name, shape(body, full)[:340]), file=sys.stderr)

def main():

    key = None

    for k in KEYS:

        if os.environ.get(k):

            key = os.environ[k]; break

    if not key:

        print("sem chave", file=sys.stderr); sys.exit(1)

    # codigoPessoa real

    st, body = get(key, "/clientes/simples?page=0&size=1")

    cp = mat = None

    try:

        c = (json.loads(body).get("content") or [])[0]; mat = c.get("matricula")

    except Exception:

        pass

    if mat is not None:

        st, body = get(key, "/clientes/%s/dados-pessoais" % mat)

        try:

            cp = json.loads(body).get("content", {}).get("codigoPessoa")

        except Exception:

            pass

    print("codigoPessoa obtido:", "sim" if cp else "nao", file=sys.stderr)

    now = datetime.datetime.utcnow()

    df = int(now.timestamp() * 1000); di = int((now - datetime.timedelta(days=365)).timestamp() * 1000)

    # KPI1 — execucoes: ver /dados completo + endpoints de execucao

    st, body = get(key, "/psec/treino-bi/dados?idProfessor=0")

    line(st, "dados?idProfessor=0 (COMPLETO)", body, full=True)

    for path in [

        "/psec/treino-bi/lista-alunos-execucao-treino-ultimos-dias/1/30/1",

        "/psec/treino-bi/lista-alunos-execucao-treino-ultimos-dias/1/7/0",

        "/psec/treino-bi/resumo-execucoes-periodo/1?dataInicio=%d&dataFim=%d" % (di, df),

    ]:

        st, body = get(key, path)

        line(st, path.split("/psec/treino-bi/")[1][:40], body)

    # KPI7 — nota do treino com codigoPessoa real

    P = cp if cp is not None else 1

    for tb in [0, 5, 1]:

        st, body = get(key, "/psec/treino-bi/avaliacao-treino/%d/%s?professorId=1&size=3" % (tb, P))

        line(st, "avaliacao-treino/%d/{cpReal}" % tb, body)

if __name__ == "__main__":

    main()
