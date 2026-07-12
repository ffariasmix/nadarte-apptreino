#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe v34 — (1) EXECUCOES REAIS de treino e (2) AVALIACOES UNICAS por usuario.
  1) Disseca /psec/treino-bi/treinamento por completo: mediaExecucao (avaliados?) vs
     acessoExecucoesZW (serie diaria real?) e quaisquer outros campos de execucao.
  2) Procura fonte de avaliacoes/notas POR USUARIO (p/ distinguir total x usuarios unicos).
PII-safe: tipos, contagem, chaves; sem valores sensiveis."""
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
def descr(v, depth=0):
    if isinstance(v,list): return "LISTA(%d)%s" % (len(v), (" item0keys="+str(list(v[0].keys())) if v and isinstance(v[0],dict) else (" item0="+str(v[0])[:30] if v else "")))
    if isinstance(v,dict): return "dict{%s}" % ", ".join(list(v.keys())[:12])
    return "%s=%r" % (type(v).__name__, str(v)[:24])
def items_of(x):
    if isinstance(x,list): return x
    if isinstance(x,dict):
        for k in ("content","lista","clientes","alunos","dados","itens","avaliacoes"):
            if isinstance(x.get(k),list): return x[k]
    return None

def main():
    label=key=None
    for lb,env in KEYS:
        if os.environ.get(env): label,key=lb,os.environ[env]; break
    if not key: print("sem chave",file=sys.stderr); sys.exit(1)
    print("== UNIDADE %s ==" % label, file=sys.stderr)

    # 1) treinamento — TODOS os campos de topo
    print("\n[1] /psec/treino-bi/treinamento — campos de topo:", file=sys.stderr)
    d=cont(get(key,"/psec/treino-bi/treinamento")[1])
    if isinstance(d,dict):
        for k in d.keys():
            print("   %s -> %s" % (k, descr(d[k])), file=sys.stderr)
        # foca em acessoExecucoesZW e mediaExecucao
        for k in ("acessoExecucoesZW","mediaExecucao","execucoes","totalExecucoes","gerados","executados"):
            if k in d: print("   >>> %s detalhe: %s" % (k, json.dumps(d[k])[:300]), file=sys.stderr)
    else:
        print("   (nao-dict) %s" % descr(d), file=sys.stderr)

    # 2) execucao real — candidatos
    print("\n[2] candidatos de EXECUCAO REAL (treinos realizados):", file=sys.stderr)
    for p in ["/psec/treino-bi/gerados-executados","/psec/treino-bi/execucoes",
              "/psec/treino-bi/treinos-realizados","/psec/treino-bi/execucao-treino"]:
        st,body=get(key,p); dd=cont(body)
        print("   [%s] status=%s -> %s" % (p, st, descr(dd) if st==200 else ""), file=sys.stderr)

    # 3) avaliacoes/notas POR USUARIO
    print("\n[3] candidatos de AVALIACOES por usuario (total x unicos):", file=sys.stderr)
    for p in ["/psec/treino-bi/avaliacoes?page=0&size=3","/psec/treino-bi/avaliacoes-treino?page=0&size=3",
              "/psec/treino-bi/notas?page=0&size=3","/psec/treino-bi/alunos-avaliaram?page=0&size=3",
              "/psec/treino-bi/avaliacao-treino?page=0&size=3"]:
        st,body=get(key,p); it=items_of(cont(body))
        n=len(it) if isinstance(it,list) else -1
        ks=list(it[0].keys()) if isinstance(it,list) and it and isinstance(it[0],dict) else None
        print("   [%s] status=%s itens=%s %s" % (p.split("?")[0], st, n, ("chaves="+str(ks)) if ks else ""), file=sys.stderr)

    print("\n>> Quero: (a) campo de execucao REAL (todos treinos feitos) e (b) lista de avaliacoes por usuario.", file=sys.stderr)

if __name__=="__main__": main()
