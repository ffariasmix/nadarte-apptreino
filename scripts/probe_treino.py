#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe v32 — CACA AMPLA da avaliacao POR ALUNO (o dado existe: a academia sabe quem renovar).
  1) Testa uma bateria de endpoints candidatos (lista por aluno c/ data de avaliacao/vencimento).
  2) Dump COMPLETO das chaves de /v1/cliente/{cid} (achar campo de avaliacao com outro nome).
  3) avaliacao-fisica-bi COM datas: ve se traz lista de clientes embutida.
PII-safe: matricula mascarada; imprime nomes de CHAVES, nao valores sensiveis."""
import os, sys, json, urllib.request, urllib.error, datetime
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
    if isinstance(x,list): return x
    if isinstance(x,dict):
        for k in ("content","lista","clientes","alunos","dados","itens"):
            if isinstance(x.get(k),list): return x[k]
    return None
def all_keys(obj, prefix="", depth=0, acc=None):
    if acc is None: acc=set()
    if depth>3: return acc
    if isinstance(obj,dict):
        for k,v in obj.items():
            acc.add(prefix+k)
            all_keys(v, prefix+k+".", depth+1, acc)
    elif isinstance(obj,list) and obj:
        all_keys(obj[0], prefix, depth+1, acc)
    return acc

def try_list(key, path):
    st,body=get(key,path)
    it=items_of(cont(body))
    n=len(it) if isinstance(it,list) else -1
    ks=None
    if isinstance(it,list) and it and isinstance(it[0],dict): ks=list(it[0].keys())
    print("  [%s] status=%s itens=%s %s" % (path[:64], st, n, ("chaves="+str(ks)) if ks else ""), file=sys.stderr)
    return (st, n, ks)

def main():
    label=key=None
    for lb,env in KEYS:
        if os.environ.get(env): label,key=lb,os.environ[env]; break
    if not key: print("sem chave",file=sys.stderr); sys.exit(1)
    print("== UNIDADE %s ==" % label, file=sys.stderr)

    print("\n[1] Endpoints candidatos (lista por aluno):", file=sys.stderr)
    cands = [
      "/psec/avaliacao-fisica-bi/alunos?page=0&size=5",
      "/psec/avaliacao-fisica-bi/clientes?page=0&size=5",
      "/psec/avaliacao-fisica-bi/vencidas?page=0&size=5",
      "/psec/avaliacao-fisica-bi/atrasadas?page=0&size=5",
      "/psec/avaliacao-fisica-bi/detalhado?page=0&size=5",
      "/psec/avaliacao-fisica-bi/lista?page=0&size=5",
      "/psec/avaliacao-fisica/vencidas?page=0&size=5",
      "/psec/avaliacao-fisica/agenda?page=0&size=5",
      "/psec/avaliacao-fisica/clientes?page=0&size=5",
      "/psec/alunos/avaliacao-vencida/0?page=0&size=5",
      "/psec/alunos/avaliacao/0?page=0&size=5",
      "/psec/treino-bi/alunos-avaliacao-fisica-vencida/0?page=0&size=5",
      "/psec/treino-bi/alunos-reavaliacao/0?page=0&size=5",
      "/psec/treino-bi/carteira-avaliacao/0?page=0&size=5",
    ]
    for p in cands: try_list(key, p)

    print("\n[2] avaliacao-fisica-bi COM datas (lista embutida?):", file=sys.stderr)
    df=int(datetime.datetime.now().timestamp()*1000)
    di=int((datetime.datetime.now()-datetime.timedelta(days=365)).timestamp()*1000)
    st,body=get(key,"/psec/avaliacao-fisica-bi?dataInicio=%d&dataFim=%d"%(di,df))
    d=cont(body)
    print("  status=%s tipo=%s chaves=%s" % (st, type(d).__name__, (list(d.keys()) if isinstance(d,dict) else None)), file=sys.stderr)

    print("\n[3] /v1/cliente/{cid} — TODAS as chaves (achar avaliacao com outro nome):", file=sys.stderr)
    c=cont(get(key,"/clientes/simples?page=0&size=5&situacao=ATIVO")[1])
    lst=c if isinstance(c,list) else (c.get("lista") or c.get("content") or [] if isinstance(c,dict) else [])
    cid=(lst[0].get("codigoCliente") or lst[0].get("matricula")) if lst else None
    if cid is not None:
        d=cont(get(key,"/v1/cliente/%s"%cid)[1])
        ks=sorted(all_keys(d))
        # foca nas chaves que cheiram a data/avaliacao/ficha/vencimento
        quentes=[k for k in ks if any(t in k.lower() for t in ("avali","reavali","ficha","venciment","data","validade","proxim"))]
        print("  total de chaves: %d" % len(ks), file=sys.stderr)
        print("  CHAVES QUENTES (data/avaliacao/ficha/vencimento): %s" % quentes, file=sys.stderr)

    print("\n>> Quero uma lista por aluno com matricula + data/vencimento de avaliacao. Marca a que voltar 200 com itens>0.", file=sys.stderr)

if __name__=="__main__": main()
