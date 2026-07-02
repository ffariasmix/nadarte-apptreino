#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
probe_treino.py — explorador de endpoints (referencia da descoberta).
Confere rapidamente os endpoints unit-level usados pelo coletor.
"""
import os, sys, json, datetime, urllib.request, urllib.error

BASE = "https://apigw.pactosolucoes.com.br"
KEYS = ["PACTO_KEY_716NORTE", "PACTO_KEY_905SUL", "PACTO_KEY_604NORTE",
        "PACTO_KEY_LAGONORTE", "PACTO_KEY_LAGOSUL", "PACTO_KEY_NATAL"]

def get(key, path):
    h = {"Authorization": "Bearer " + key, "Accept": "application/json", "empresaId": "1"}
    try:
        with urllib.request.urlopen(urllib.request.Request(BASE + path, headers=h), timeout=25) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, (e.read().decode("utf-8", "replace") if e.fp else "")
    except Exception as ex:
        return -1, str(ex)[:80]

def keys_of(body):
    try:
        c = json.loads(body).get("content", {})
        if isinstance(c, dict):
            return ", ".join(list(c.keys())[:25])
        return type(c).__name__
    except Exception:
        return "(nao-JSON %d)" % len(body)

def main():
    key = None
    for k in KEYS:
        if os.environ.get(k):
            key = os.environ[k]; break
    if not key:
        print("sem chave", file=sys.stderr); sys.exit(1)
    now = datetime.datetime.utcnow()
    df = int(now.timestamp() * 1000); di = int((now - datetime.timedelta(days=365)).timestamp() * 1000)
    for path in [
        "/psec/treino-bi/dados?idProfessor=0",
        "/psec/treino-bi/carteira",
        "/psec/treino-bi/contagem-treinos-aprovar",
        "/psec/avaliacao-fisica-bi?dataInicio=%d&dataFim=%d" % (di, df),
    ]:
        st, body = get(key, path)
        print("%5s  %-46s  %s" % (st, path[:46], keys_of(body)[:200]), file=sys.stderr)

if __name__ == "__main__":
    main()
