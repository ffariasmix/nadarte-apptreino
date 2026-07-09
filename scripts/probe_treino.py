#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe v33 — fechar a fonte de AVALIACAO por aluno.
Pistas da v32: /psec/alunos/avaliacao* deram 400 (existem!); mesma familia de /psec/alunos/alunoApp?cliente=.
  1) /psec/alunos/avaliacao?cliente={cid} e variacoes (forma query, como alunoApp).
  2) Disseca avaliacao-fisica-bi (com datas): 'avaliacoes','atrasadas','semAvaliacao','grafico' sao listas?
PII-safe: so tipos, contagem, chaves; matricula/valores mascarados."""
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
def descr(v):
    if isinstance(v,list): return "LISTA(%d)%s" % (len(v), (" item0keys="+str(list(v[0].keys())) if v and isinstance(v[0],dict) else ""))
    if isinstance(v,dict): return "dict(chaves=%s)" % list(v.keys())[:10]
    return "%s=%r" % (type(v).__name__, (str(v)[:20]))

def main():
    label=key=None
    for lb,env in KEYS:
        if os.environ.get(env): label,key=lb,os.environ[env]; break
    if not key: print("sem chave",file=sys.stderr); sys.exit(1)
    print("== UNIDADE %s ==" % label, file=sys.stderr)

    # um cliente ativo de amostra
    c=cont(get(key,"/clientes/simples?page=0&size=5&situacao=ATIVO")[1])
    lst=c if isinstance(c,list) else (c.get("lista") or c.get("content") or [] if isinstance(c,dict) else [])
    cid=(lst[0].get("codigoCliente") or lst[0].get("matricula")) if lst else None
    mat=lst[0].get("matricula") if lst else None
    print("amostra cid=%s" % cid, file=sys.stderr)

    print("\n[1] /psec/alunos/avaliacao* nas formas query/caminho:", file=sys.stderr)
    variacoes = [
      "/psec/alunos/avaliacao?cliente=%s" % cid,
      "/psec/alunos/avaliacao-vencida?cliente=%s" % cid,
      "/psec/alunos/avaliacaofisica?cliente=%s" % cid,
      "/psec/alunos/avaliacao-fisica?cliente=%s" % cid,
      "/psec/alunos/avaliacao/%s" % cid,
      "/psec/alunos/avaliacao-vencida/%s" % cid,
      "/psec/alunos/avaliacao?matricula=%s" % mat,
    ]
    for p in variacoes:
        st,body=get(key,p)
        d=cont(body)
        shown=p.split("?")[0]+("?"+p.split("?")[1].split("=")[0]+"=..." if "?" in p else "")
        print("  [%s] status=%s -> %s" % (shown, st, (descr(d) if st==200 else "")), file=sys.stderr)

    print("\n[2] avaliacao-fisica-bi COM datas — disseca cada chave:", file=sys.stderr)
    df=int(datetime.datetime.now().timestamp()*1000)
    di=int((datetime.datetime.now()-datetime.timedelta(days=365)).timestamp()*1000)
    d=cont(get(key,"/psec/avaliacao-fisica-bi?dataInicio=%d&dataFim=%d"%(di,df))[1])
    if isinstance(d,dict):
        for k in ("avaliacoes","atrasadas","semAvaliacao","ativosAtrasada","futuras","previstas","grafico","alunosParq"):
            if k in d: print("   %s -> %s" % (k, descr(d[k])), file=sys.stderr)

    print("\n>> Alvo: forma que volte 200 com LISTA de alunos (matricula + status/vencimento de avaliacao).", file=sys.stderr)

if __name__=="__main__": main()
