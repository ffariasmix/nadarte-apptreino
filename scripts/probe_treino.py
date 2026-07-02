#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
probe_treino.py (v2 — mirado) — descobre a familia /psec/alunos/* da API PACTO.

Estrategia: pega 1 cliente real de /clientes/simples e chama /psec/alunos/{nome}
com header empresaId + query cliente=, imprimindo os CAMPOS (chaves) de cada resposta.
PII-safe: imprime so status, chaves do JSON e contagens (nunca dados pessoais).
"""
import os, sys, json, urllib.request, urllib.error

BASE = "https://apigw.pactosolucoes.com.br"
KEYS = ["PACTO_KEY_716NORTE", "PACTO_KEY_905SUL", "PACTO_KEY_604NORTE",
        "PACTO_KEY_LAGONORTE", "PACTO_KEY_LAGOSUL", "PACTO_KEY_NATAL"]

# candidatos sob /psec/alunos/  (cobrindo os 8 indicadores)
NOMES = ["alunoApp", "ficha", "fichas", "treino", "treinos",
         "avaliacao", "avaliacoes", "avaliacao-fisica",
         "feedback", "nota", "notas", "atendimento", "interacao",
         "chat", "mensagens", "historico", "agenda", "evolucao",
         "medidas", "foto", "frequencia", "execucao"]

def get(key, path, empresa=None, timeout=20):
    h = {"Authorization": "Bearer " + key, "Accept": "application/json"}
    if empresa is not None:
        h["empresaId"] = str(empresa)
    req = urllib.request.Request(BASE + path, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, (e.read().decode("utf-8", "replace") if e.fp else "")
    except Exception as ex:
        return -1, str(ex)[:80]

def shape(body):
    try:
        j = json.loads(body)
    except Exception:
        return "(nao-JSON %d chars) %s" % (len(body), body[:160].replace("\n", " "))
    def d(x):
        if isinstance(x, dict):
            inner = " content->" + d(x["content"]) if "content" in x else ""
            return "obj{%s}%s" % (", ".join(list(x.keys())[:15]), inner)
        if isinstance(x, list):
            return "lista[%d]%s" % (len(x), (" item0=" + d(x[0]) if x else ""))
        return type(x).__name__
    return d(j)

def main():
    key = None
    for k in KEYS:
        if os.environ.get(k):
            key = os.environ[k]; break
    if not key:
        print("sem chave nos Secrets", file=sys.stderr); sys.exit(1)

    # 1) um cliente real (so para obter um codigoCliente valido)
    st, body = get(key, "/clientes/simples?page=0&size=3")
    print("clientes/simples ->", st, shape(body)[:200], file=sys.stderr)
    cid = None
    try:
        arr = json.loads(body).get("content") or []
        if arr:
            cid = arr[0].get("codigoCliente")
            print("  (codigoCliente obtido; valor omitido do log)", file=sys.stderr)
    except Exception:
        pass

    # 2) familia /psec/alunos/* com empresaId=1 + cliente
    print("\n%5s  %-22s  %s" % ("STAT", "PATH", "CAMPOS/RESPOSTA"), file=sys.stderr)
    achados = []
    for nome in NOMES:
        p = "/psec/alunos/%s?cliente=%s" % (nome, cid) if cid else "/psec/alunos/%s" % nome
        st, body = get(key, p, empresa=1)
        sh = shape(body)
        print("%5s  /psec/alunos/%-16s  %s" % (st, nome, sh[:220]), file=sys.stderr)
        if st == 200:
            achados.append({"path": "/psec/alunos/" + nome, "shape": sh})

    print("\n== RESPONDERAM 200 (usar estes) ==", file=sys.stderr)
    print(json.dumps(achados, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
