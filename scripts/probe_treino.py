#!/usr/bin/env python3

# -*- coding: utf-8 -*-

"""

probe_treino.py (v3.1) — confirma a ESTRUTURA real dos endpoints de BI Treino.

empresaId = 1 (a ApiKey ja escopa a unidade). PII-safe: so status/chaves/contagens.

"""

import os, sys, json, urllib.request, urllib.error, urllib.parse

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

            return "obj{%s}%s" % (", ".join(list(x.keys())[:25]), inner)

        if isinstance(x, list):

            return "lista[%d]%s" % (len(x), (" item0=" + d(x[0], depth + 1) if x else ""))

        return type(x).__name__

    return d(j)

def line(st, name, body):

    print("%5s  %-46s  %s" % (st, name, shape(body)[:260]), file=sys.stderr)

def main():

    key = None

    for k in KEYS:

        if os.environ.get(k):

            key = os.environ[k]; break

    if not key:

        print("sem chave", file=sys.stderr); sys.exit(1)

    st, body = get(key, "/clientes/simples?page=0&size=3")

    line(st, "clientes/simples", body)

    cid = mat = empresa = None

    try:

        c = (json.loads(body).get("content") or [])[0]

        cid, mat, empresa = c.get("codigoCliente"), c.get("matricula"), c.get("empresa")

        print("  empresa(nome)=%s (cid/mat omitidos)" % empresa, file=sys.stderr)

    except Exception:

        pass

    emp = 1  # empresaId (header e path) e SEMPRE 1 — a ApiKey ja escopa a unidade

    cp = None

    if mat is not None:

        st, body = get(key, "/clientes/%s/dados-pessoais" % mat)

        line(st, "clientes/{matricula}/dados-pessoais", body)

        try:

            cp = json.loads(body).get("content", {}).get("codigoPessoa")

        except Exception:

            pass

    filtros = urllib.parse.quote(json.dumps({"dataInicio": 1704067200000, "dataFim": 1735689599000}))

    cfg = urllib.parse.quote(json.dumps({"incluirProfessorInativo": False}))

    st, body = get(key, "/psec/professores/indicadores-atividade/alunos?filters=%s&configs=%s&page=1" % (filtros, cfg))

    line(st, "professores/indicadores-atividade/alunos", body)

    P = cp if cp is not None else 1

    testes = [

        ("treino-bi/dados?idProfessor=1", "/psec/treino-bi/dados?idProfessor=1"),

        ("treino-bi/resumo-execucoes-periodo/1", "/psec/treino-bi/resumo-execucoes-periodo/1"),

        ("treino-bi/alunos-acessos", "/psec/treino-bi/alunos-acessos"),

        ("treino-bi/contagem-treinos-aprovar", "/psec/treino-bi/contagem-treinos-aprovar"),

        ("treino-bi/gerados-executados", "/psec/treino-bi/gerados-executados"),

        ("treino-bi/carteira", "/psec/treino-bi/carteira"),

        ("treino-bi/avaliacao-treino/1/{cp}", "/psec/treino-bi/avaliacao-treino/1/%s" % P),

        ("treino-bi/alunos-treino-vencido/{cp}", "/psec/treino-bi/alunos-treino-vencido/%s" % P),

        ("treino-bi/alunos-treino-em-dia/{cp}", "/psec/treino-bi/alunos-treino-em-dia/%s" % P),

        ("treino-bi/alunos-em-acompanhamento/{cp}", "/psec/treino-bi/alunos-em-acompanhamento/%s" % P),

    ]

    print("\n%5s  %-46s  %s" % ("STAT", "ENDPOINT", "CAMPOS/RESPOSTA"), file=sys.stderr)

    for nome, path in testes:

        st, body = get(key, path, empresa=emp)

        line(st, nome, body)

if __name__ == "__main__":

    main()
