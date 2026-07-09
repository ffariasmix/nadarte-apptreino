#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe v29 — confirma paginacao 0-indexed de alunos-treino-em-dia/vencido.
Testa page=0 vs page=1 (size=1000) e imprime formato da matricula retornada.
PII-safe: mascara o miolo da matricula."""
import os, sys, json, urllib.request, urllib.error
BASE = "https://apigw.pactosolucoes.com.br"
KEYS = [("716NORTE","PACTO_KEY_716NORTE"),("905SUL","PACTO_KEY_905SUL"),
        ("604NORTE","PACTO_KEY_604NORTE"),("LAGONORTE","PACTO_KEY_LAGONORTE"),
        ("LAGOSUL","PACTO_KEY_LAGOSUL"),("NATAL","PACTO_KEY_NATAL")]
def get(key, path, timeout=40):
    h={"Authorization":"Bearer "+key,"Accept":"application/json","empresaId":"1"}
    try:
        with urllib.request.urlopen(urllib.request.Request(BASE+path,headers=h),timeout=timeout) as r:
            return r.status, r.read().decode("utf-8","replace")
    except urllib.error.HTTPError as e: return e.code,(e.read().decode("utf-8","replace") if e.fp else "")
    except Exception as ex: return -1,str(ex)[:120]
def cont(b):
    try: j=json.loads(b); return j.get("content", j)
    except: return None
def items_of(x):
    return x if isinstance(x,list) else (x.get("content") if isinstance(x,dict) else None)
def mask(m):
    s=str(m); return s if len(s)<=4 else s[:2]+("*"*(len(s)-4))+s[-2:]

def main():
    label=key=None
    for lb,env in KEYS:
        if os.environ.get(env): label,key=lb,os.environ[env]; break
    if not key: print("sem chave",file=sys.stderr); sys.exit(1)
    print("== UNIDADE %s ==" % label, file=sys.stderr)
    for ep in ("alunos-treino-em-dia","alunos-treino-vencido"):
        for page in (0,1,2):
            it=items_of(cont(get(key,"/psec/treino-bi/%s/0?page=%d&size=1000"%(ep,page))[1]))
            n=len(it) if isinstance(it,list) else -1
            print("[%s page=%d] itens=%s" % (ep, page, n), file=sys.stderr)
        # formato da matricula na page=0
        it0=items_of(cont(get(key,"/psec/treino-bi/%s/0?page=0&size=5"%ep)[1]))
        if isinstance(it0,list) and it0:
            m=it0[0].get("matricula")
            print("   matricula ex: tipo=%s len=%d zero_esq=%s val=%s" % (
                type(m).__name__, len(str(m)), str(m)[:1]=="0", mask(m)), file=sys.stderr)
            print("   chaves: %s" % list(it0[0].keys()), file=sys.stderr)
    print(">> Esperado: page=0 com centenas, page>=1 vazio => 0-indexed confirmado.", file=sys.stderr)

if __name__=="__main__": main()
