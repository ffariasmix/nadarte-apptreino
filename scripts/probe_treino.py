#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe v31 — fonte de AVALIACAO por aluno (p/ % sobre publico-alvo).
Testa:
  A) /psec/treino-bi/alunos-avaliacao-em-dia/0 e -vencida/0 (analogo ao treino, 0-indexed)
  B) /psec/avaliacao-fisica-bi (ja usado p/ agregados) — tem lista por aluno?
  C) /v1/cliente/{cid} — tem data/flag de avaliacao? (procura chave 'avali')
PII-safe: so contagem, chaves e matricula mascarada."""
import os, sys, json, urllib.request, urllib.error
BASE = "https://apigw.pactosolucoes.com.br"
KEYS = [("716NORTE","PACTO_KEY_716NORTE"),("905SUL","PACTO_KEY_905SUL"),
        ("604NORTE","PACTO_KEY_604NORTE"),("LAGONORTE","PACTO_KEY_LAGONORTE"),
        ("LAGOSUL","PACTO_KEY_LAGOSUL"),("NATAL","PACTO_KEY_NATAL")]
def get(key, path, timeout=35):
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
def find_key(obj, target, path=""):
    out=[]
    if isinstance(obj, dict):
        for k,v in obj.items():
            p=path+"."+k
            if target in k.lower(): out.append((p, type(v).__name__))
            out+=find_key(v, target, p)
    elif isinstance(obj, list) and obj:
        out+=find_key(obj[0], target, path+"[0]")
    return out

def main():
    label=key=None
    for lb,env in KEYS:
        if os.environ.get(env): label,key=lb,os.environ[env]; break
    if not key: print("sem chave",file=sys.stderr); sys.exit(1)
    print("== UNIDADE %s ==" % label, file=sys.stderr)

    # A) listas por aluno (analogo ao treino)
    for ep in ("alunos-avaliacao-em-dia","alunos-avaliacao-vencida","alunos-avaliacao-vencido"):
        st,body=get(key,"/psec/treino-bi/%s/0?page=0&size=5"%ep)
        it=items_of(cont(body))
        n=len(it) if isinstance(it,list) else -1
        ks=list(it[0].keys()) if isinstance(it,list) and it and isinstance(it[0],dict) else None
        print("[A %s] status=%s itens=%s chaves=%s" % (ep, st, n, ks), file=sys.stderr)

    # B) avaliacao-fisica-bi — ver estrutura (tem lista?)
    st,body=get(key,"/psec/avaliacao-fisica-bi")
    d=cont(body)
    print("\n[B] /psec/avaliacao-fisica-bi status=%s tipo=%s chaves=%s"
          % (st, type(d).__name__, (list(d.keys())[:15] if isinstance(d,dict) else None)), file=sys.stderr)

    # C) /v1/cliente/{cid} tem chave 'avali'?
    c=cont(get(key,"/clientes/simples?page=0&size=5&situacao=ATIVO")[1])
    lst=c if isinstance(c,list) else (c.get("lista") or c.get("content") or [] if isinstance(c,dict) else [])
    cid=(lst[0].get("codigoCliente") or lst[0].get("matricula")) if lst else None
    if cid is not None:
        d=cont(get(key,"/v1/cliente/%s"%cid)[1])
        hits=find_key(d,"avali") if isinstance(d,(dict,list)) else []
        print("\n[C] /v1/cliente/{cid}: chaves com 'avali' = %s" % (hits or "nenhuma"), file=sys.stderr)

    print("\n>> Melhor caso: [A] com listas nao-vazias (mesmo padrao do treino) -> % avaliacao por publico-alvo exato.", file=sys.stderr)

if __name__=="__main__": main()
