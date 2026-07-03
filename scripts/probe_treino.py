#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe v9 — campos internos de bi-professores-vinculos (por professor). PII-safe: so caminhos de chave, sem valores."""
import os, sys, json, urllib.request, urllib.error
BASE="https://apigw.pactosolucoes.com.br"
KEYS=["PACTO_KEY_716NORTE","PACTO_KEY_905SUL","PACTO_KEY_604NORTE","PACTO_KEY_LAGONORTE","PACTO_KEY_LAGOSUL","PACTO_KEY_NATAL"]
def get(key,path,timeout=25):
    h={"Authorization":"Bearer "+key,"Accept":"application/json","empresaId":"1"}
    try:
        with urllib.request.urlopen(urllib.request.Request(BASE+path,headers=h),timeout=timeout) as r:
            return r.status,r.read().decode("utf-8","replace")
    except urllib.error.HTTPError as e: return e.code,(e.read().decode("utf-8","replace") if e.fp else "")
    except Exception as ex: return -1,str(ex)[:80]
def paths(x,pre="",out=None):
    if out is None: out=[]
    if isinstance(x,dict):
        for k,v in x.items(): paths(v,pre+k+".",out)
    elif isinstance(x,list):
        if x: paths(x[0],pre+"[].",out)
    else:
        out.append(pre[:-1])
    return out
def item0(body):
    try:
        c=json.loads(body).get("content",{})
        it=c[0] if isinstance(c,list) and c else c
        return " | ".join(paths(it)[:60])
    except Exception: return "(erro)"
def main():
    key=None
    for k in KEYS:
        if os.environ.get(k): key=os.environ[k]; break
    for nome,p in [
        ("bi-professores-vinculos", "/psec/colaboradores/bi-professores-vinculos"),
        ("professores-ativos", "/colaboradores/professores-ativos"),
        ("indic-atividades-acumuladas", "/psec/professores/indicadores-atividades-acumuladas"),
    ]:
        st,body=get(key,p)
        print("== %s (%s) ==" % (nome,st), file=sys.stderr)
        print("   "+item0(body), file=sys.stderr)
if __name__=="__main__": main()
