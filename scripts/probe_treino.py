#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe v8 (fase2 professores) — achar o endpoint que da indicadores POR PROFESSOR.
PII-safe: imprime so status, chaves e contagens (nunca nomes)."""
import os, sys, json, datetime, urllib.request, urllib.error, urllib.parse
BASE = "https://apigw.pactosolucoes.com.br"
KEYS = ["PACTO_KEY_716NORTE","PACTO_KEY_905SUL","PACTO_KEY_604NORTE","PACTO_KEY_LAGONORTE","PACTO_KEY_LAGOSUL","PACTO_KEY_NATAL"]

def get(key, path, timeout=25):
    h={"Authorization":"Bearer "+key,"Accept":"application/json","empresaId":"1"}
    try:
        with urllib.request.urlopen(urllib.request.Request(BASE+path,headers=h),timeout=timeout) as r:
            return r.status, r.read().decode("utf-8","replace")
    except urllib.error.HTTPError as e: return e.code,(e.read().decode("utf-8","replace") if e.fp else "")
    except Exception as ex: return -1,str(ex)[:80]

def shape(body):
    try: j=json.loads(body)
    except Exception: return "(nao-JSON %d)"%len(body)
    def d(x,dep=0):
        if isinstance(x,dict):
            inner=" ->"+d(x["content"],dep+1) if ("content" in x and dep==0) else ""
            return "obj{%s}%s"%(", ".join(list(x.keys())[:22]),inner)
        if isinstance(x,list): return "lista[%d]%s"%(len(x),(" item0="+d(x[0],dep+1) if x else ""))
        return type(x).__name__
    return d(j)

def main():
    key=None
    for k in KEYS:
        if os.environ.get(k): key=os.environ[k]; break
    if not key: print("sem chave",file=sys.stderr); sys.exit(1)
    now=datetime.datetime.utcnow(); df=int(now.timestamp()*1000); di=int((now-datetime.timedelta(days=365)).timestamp()*1000)
    dts="dataInicio=%d&dataFim=%d"%(di,df)
    testes=[
        ("indicadores-carteira-professores", "/psec/professores/indicadores-carteira-professores"),
        ("indicadores-carteira-professores?dts", "/psec/professores/indicadores-carteira-professores?%s"%dts),
        ("indicadores-atividade", "/psec/professores/indicadores-atividade"),
        ("indicadores-atividade?dts", "/psec/professores/indicadores-atividade?%s"%dts),
        ("indicadores-atividades-acumuladas", "/psec/professores/indicadores-atividades-acumuladas"),
        ("ranking/podium", "/psec/professores/ranking/podium"),
        ("colaboradores/professores-ativos", "/colaboradores/professores-ativos"),
        ("colaboradores/bi-professores-vinculos", "/psec/colaboradores/bi-professores-vinculos"),
        ("colaboradores/all-simple", "/psec/colaboradores/all-simple?page=0&size=5"),
    ]
    for nome,path in testes:
        st,body=get(key,path)
        print("%5s  %-40s  %s"%(st,nome,shape(body)[:300]),file=sys.stderr)

if __name__=="__main__": main()
