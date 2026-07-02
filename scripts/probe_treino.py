#!/usr/bin/env python3

# -*- coding: utf-8 -*-

"""

probe_treino.py (v5) — achar o parametro UNIT-LEVEL para os agregados de treino.

Imprime os VALORES (agregados, sem PII) para comparar idProfessor=0/1 e datas.

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

def vals(body):

    try:

        c = json.loads(body).get("content", {})

    except Exception:

        return "(nao-JSON %d)" % len(body)

    if isinstance(c, dict):

        keep = {k: v for k, v in c.items() if isinstance(v, (int, float, bool))}

        return json.dumps(keep, ensure_ascii=False)[:300]

    return str(type(c).__name__)

def main():

    key = None

    for k in KEYS:

        if os.environ.get(k):

            key = os.environ[k]; break

    if not key:

        print("sem chave", file=sys.stderr); sys.exit(1)

    now = datetime.datetime.utcnow()

    df = int(now.timestamp() * 1000)

    di = int((now - datetime.timedelta(days=365)).timestamp() * 1000)

    testes = [

        ("dados?idProfessor=0", "/psec/treino-bi/dados?idProfessor=0"),

        ("dados?idProfessor=1", "/psec/treino-bi/dados?idProfessor=1"),

        ("dados (sem idProfessor)", "/psec/treino-bi/dados"),

        ("carteira", "/psec/treino-bi/carteira"),

        ("gerados-executados", "/psec/treino-bi/gerados-executados"),

        ("gerados-executados?datas", "/psec/treino-bi/gerados-executados?dataInicio=%d&dataFim=%d" % (di, df)),

        ("gerados-executados?idProf=0", "/psec/treino-bi/gerados-executados?idProfessor=0"),

        ("resumo-execucoes/0", "/psec/treino-bi/resumo-execucoes-periodo/0"),

        ("resumo-execucoes/1", "/psec/treino-bi/resumo-execucoes-periodo/1"),

    ]

    for nome, path in testes:

        st, body = get(key, path)

        print("%5s  %-28s  %s" % (st, nome, vals(body)), file=sys.stderr)

if __name__ == "__main__":

    main()
