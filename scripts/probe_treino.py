#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe v26 — ADERENCIA (gerados x executados) veio 0; achar o parametro certo.
Testa gerados-executados com/sem periodo, treinamento.mediaExecucao e resumo por periodo.
PII-safe: so numeros."""
import os, sys, json, datetime, urllib.request, urllib.error, urllib.parse
BASE = "https://apigw.pactosolucoes.com.br"
KEYS = [("716NORTE","PACTO_KEY_716NORTE"),("905SUL","PACTO_KEY_905SUL"),
        ("604NORTE","PACTO_KEY_604NORTE"),("LAGONORTE","PACTO_KEY_LAGONORTE"),
        ("LAGOSUL","PACTO_KEY_LAGOSUL"),("NATAL","PACTO_KEY_NATAL")]
def get(key, path, timeout=30):
    h={"Authorization":"Bearer "+key,"Accept":"application/json","empresaId":"1"}
    try:
        with urllib.request.urlopen(urllib.request.Request(BASE+path,headers=h),timeout=timeout) as r:
            return r.status, r.read().decode("utf-8","replace")
    except urllib.error.HTTPError as e: return e.code,(e.read().decode("utf-8","replace") if e.fp else "")
    except Exception as ex: return -1,str(ex)[:120]
def cont(b):
    try: j=json.loads(b); return j.get("content", j)
    except: return None
def nums(o):
    """so os campos numericos de um dict (PII-safe)."""
    if isinstance(o,dict):
        return {k:v for k,v in o.items() if isinstance(v,(int,float))}
    return o

def main():
    label=key=None
    for lb,env in KEYS:
        if os.environ.get(env): label,key=lb,os.environ[env]; break
    if not key: print("sem chave",file=sys.stderr); sys.exit(1)
    print("== UNIDADE %s ==" % label, file=sys.stderr)
    now=int(datetime.datetime.utcnow().timestamp()*1000)
    d30=int((datetime.datetime.utcnow()-datetime.timedelta(days=30)).timestamp()*1000)
    d365=int((datetime.datetime.utcnow()-datetime.timedelta(days=365)).timestamp()*1000)

    print("\n[gerados-executados] variacoes:", file=sys.stderr)
    for ep in ["/psec/treino-bi/gerados-executados",
               "/psec/treino-bi/gerados-executados?dataInicio=%d&dataFim=%d"%(d30,now),
               "/psec/treino-bi/gerados-executados?dataInicio=%d&dataFim=%d"%(d365,now),
               "/psec/treino-bi/gerados-executados?empresaId=1",
               "/psec/treino-bi/gerado-executado-completo?dataInicio=%d&dataFim=%d"%(d365,now)]:
        st,body=get(key,ep); c=cont(body)
        print("  %s %s -> %s" % (str(st).rjust(3), ep.split("?")[1] if "?" in ep else "(sem periodo)", nums(c)), file=sys.stderr)

    print("\n[treinamento.mediaExecucao / acessoExecucoesZW]", file=sys.stderr)
    st,body=get(key,"/psec/treino-bi/treinamento"); c=cont(body)
    if isinstance(c,dict):
        print("  status=%s | mediaExecucao=%s | acessoExecucoesZW=%s" % (st, c.get("mediaExecucao"), c.get("acessoExecucoesZW")), file=sys.stderr)

    print("\n[resumo-execucoes-periodo/1] (execucoes por dia)", file=sys.stderr)
    st,body=get(key,"/psec/treino-bi/resumo-execucoes-periodo/1"); c=cont(body)
    print("  status=%s | %s" % (st, nums(c)), file=sys.stderr)

    print("\n>> onde aparecer numeros > 0 em gerados/executados, esse e o formato certo.", file=sys.stderr)

if __name__=="__main__": main()
