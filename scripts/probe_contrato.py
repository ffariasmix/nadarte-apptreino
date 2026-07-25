#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
probe_contrato.py — SÓ INSPECIONA (não altera nada).
Descobre, no endpoint /v1/contrato/matricula/{mat}, qual é o campo de DATA DE FIM
e como a renovação antecipada aparece (múltiplos contratos com fim diferente).
Imprime no log as chaves e os campos de data de alguns alunos perto de vencer.
Uso (via workflow): python scripts/probe_contrato.py
"""
import os, sys, json, datetime, urllib.request, urllib.error

BASE = "https://apigw.pactosolucoes.com.br"
UNITS = [("716Norte", "PACTO_KEY_716NORTE"), ("905Sul", "PACTO_KEY_905SUL"),
         ("604Norte", "PACTO_KEY_604NORTE"), ("LagoNorte", "PACTO_KEY_LAGONORTE"),
         ("LagoSul", "PACTO_KEY_LAGOSUL"), ("Natal", "PACTO_KEY_NATAL")]
NOW_MS = int(datetime.datetime.utcnow().timestamp() * 1000)

def http_get(key, path, timeout=30):
    req = urllib.request.Request(BASE + path, headers={
        "Authorization": "Bearer " + key, "Accept": "application/json", "empresaId": "1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return -1, str(e)

def parse_ms(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v).strip()
    if s.isdigit():
        return int(s)
    for f in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return int(datetime.datetime.strptime(s[:19], f).timestamp() * 1000)
        except Exception:
            pass
    return None

def dias(ms):
    return None if ms is None else round((ms - NOW_MS) / 86400000.0)

def main():
    want = (os.environ.get("PROBE_UNIT") or "").strip()
    unit = key = None
    for uk, env in UNITS:
        k = os.environ.get(env)
        if k and (not want or want == uk):
            unit, key = uk, k
            break
    if not key:
        print("Nenhuma PACTO_KEY encontrada no ambiente (ou PROBE_UNIT sem chave).")
        sys.exit(1)
    print("== Probe contrato · unidade %s ==" % unit)
    st, body = http_get(key, "/clientes/simples?page=0&size=200&situacao=ATIVO")
    print("clientes/simples -> HTTP %s" % st)
    if st != 200:
        sys.exit(1)
    j = json.loads(body); c = j.get("content", j)
    lst = c if isinstance(c, list) else (c.get("content") if isinstance(c, dict) else [])
    print("clientes na página: %d" % len(lst))
    rows = []
    for it in lst:
        mat = it.get("matricula") or it.get("codigoCliente")
        fm = parse_ms(it.get("fimContrato"))
        rows.append((mat, fm, dias(fm)))
    perto = [r for r in rows if r[2] is not None and r[2] <= 10]     # <=10 dias ou vencido
    longe = [r for r in rows if r[2] is not None and r[2] > 90]
    amostra = perto[:5] + longe[:2]
    print("perto de vencer (<=10d/vencido): %d · amostrando %d" % (len(perto), len(amostra)))
    for mat, fm, dd in amostra:
        print("\n---- matrícula %s · fimContrato(lista)=%s (%s dias) ----" % (mat, fm, dd))
        st2, body2 = http_get(key, "/v1/contrato/matricula/%s" % mat)
        print("  /v1/contrato/matricula -> HTTP %s" % st2)
        if st2 != 200:
            continue
        try:
            jj = json.loads(body2); cc = jj.get("content", jj)
            itens = cc if isinstance(cc, list) else (cc.get("content") if isinstance(cc, dict) else [cc])
            if not isinstance(itens, list):
                itens = [itens]
            print("  contratos retornados: %d" % len(itens))
            for idx, x in enumerate(itens):
                if not isinstance(x, dict):
                    continue
                datish = {k: v for k, v in x.items()
                          if any(t in str(k).lower() for t in ("data", "fim", "inic", "venc", "term", "vig"))}
                print("   contrato[%d] chaves = %s" % (idx, list(x.keys())))
                print("   contrato[%d] datas  = %s" % (idx, json.dumps(datish, ensure_ascii=False, default=str)))
        except Exception as e:
            print("  erro ao parsear: %s" % e)

if __name__ == "__main__":
    main()
