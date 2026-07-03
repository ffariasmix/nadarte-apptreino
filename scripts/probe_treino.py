#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe v12 (fase2 CRM aluno) — DECISIVO.
(1) ultima tentativa no endpoint por-indicador (parent com datas/idProfessor -> pegar
    ids de indicador; depois /alunos?indicador=X).
(2) confirma o PLANO B ja funcionando: /clientes/simples + /psec/alunos/alunoApp.
PII-safe: imprime SO status, nomes de campo e contagens. Valores de nome/cpf/email
NUNCA sao impressos. usaApp e impresso so como tipo (bool), sem vincular a pessoa."""
import os, sys, json, datetime, urllib.request, urllib.error, urllib.parse
BASE = "https://apigw.pactosolucoes.com.br"
KEYS = ["PACTO_KEY_716NORTE","PACTO_KEY_905SUL","PACTO_KEY_604NORTE","PACTO_KEY_LAGONORTE","PACTO_KEY_LAGOSUL","PACTO_KEY_NATAL"]

def get(key, path, timeout=40):
    h={"Authorization":"Bearer "+key,"Accept":"application/json","empresaId":"1"}
    try:
        with urllib.request.urlopen(urllib.request.Request(BASE+path,headers=h),timeout=timeout) as r:
            return r.status, r.read().decode("utf-8","replace")
    except urllib.error.HTTPError as e: return e.code,(e.read().decode("utf-8","replace") if e.fp else "")
    except Exception as ex: return -1,str(ex)[:120]

def keys_only(body):
    try: j=json.loads(body)
    except Exception: return "(nao-JSON len=%d)"%len(body)
    def d(x,dep=0):
        if isinstance(x,dict):
            inner=" ->"+d(x.get("content"),dep+1) if ("content" in x and dep==0) else ""
            return "obj{%s}%s"%(", ".join(list(x.keys())[:40]),inner)
        if isinstance(x,list): return "lista[%d]%s"%(len(x),(" item0="+d(x[0],dep+1) if x else ""))
        return type(x).__name__
    return d(j)

def err_msg(body):
    try:
        j=json.loads(body); m=j.get("meta", j) if isinstance(j,dict) else j
        for k in ("mensagem","message","erro","error","detalhe","detail"):
            if isinstance(m,dict) and m.get(k): return "%s=%s"%(k,str(m[k])[:200])
        return json.dumps(m, ensure_ascii=False)[:220]
    except Exception: return body[:160].replace("\n"," ")

def report(nome, st, body):
    if st==200: print("  200  %-40s  %s"%(nome, keys_only(body)[:360]), file=sys.stderr)
    else:       print("%5s  %-40s  ERRO: %s"%(st, nome, err_msg(body)), file=sys.stderr)

def q(**kw): return urllib.parse.urlencode({k:v for k,v in kw.items() if v is not None})

def content(body):
    try:
        j=json.loads(body); c=j.get("content", j)
        return c
    except Exception: return None

def main():
    key=None
    for k in KEYS:
        if os.environ.get(k): key=os.environ[k]; break
    if not key: print("sem chave",file=sys.stderr); sys.exit(1)
    now=datetime.datetime.utcnow(); df=int(now.timestamp()*1000); di=int((now-datetime.timedelta(days=365)).timestamp()*1000)

    # ---- (1) ULTIMA TENTATIVA endpoint por-indicador ----
    print("== 1) parent indicadores COM datas/idProfessor ==", file=sys.stderr)
    Ap="/psec/professores/indicadores-atividade"; Bp="/psec/professores/indicadores-carteira-professores"
    for nome,path in [
        ("atividade ?datas",           Ap+"?"+q(dataInicio=di,dataFim=df)),
        ("atividade ?datas+idProf0",   Ap+"?"+q(dataInicio=di,dataFim=df,idProfessor=0)),
        ("carteira ?datas",            Bp+"?"+q(dataInicio=di,dataFim=df)),
        ("carteira ?datas+idProf0",    Bp+"?"+q(dataInicio=di,dataFim=df,idProfessor=0)),
    ]:
        st,body=get(key,path); report(nome,st,body)

    print("== 2) /alunos com ?indicador= e datas ==", file=sys.stderr)
    Aa="/psec/professores/indicadores-atividade/alunos"
    for nome,path in [
        ("indicador=1",             Aa+"?"+q(indicador=1,page=0,size=20)),
        ("indicador=EM_DIA",        Aa+"?"+q(indicador="EM_DIA",page=0,size=20)),
        ("indicador=1+datas",       Aa+"?"+q(indicador=1,dataInicio=di,dataFim=df,page=0,size=20)),
        ("filters={}+datas+idProf", Aa+"?"+q(filters="{}",dataInicio=di,dataFim=df,idProfessor=0,page=0,size=20)),
    ]:
        st,body=get(key,path); report(nome,st,body)

    # ---- (2) PLANO B confirmado ----
    print("== 3) PLANO B: /clientes/simples ==", file=sys.stderr)
    st,body=get(key,"/clientes/simples")
    report("clientes/simples", st, body)
    prim = None
    if st==200:
        c=content(body)
        if isinstance(c,list) and c:
            print("       total na lista: %d alunos"%len(c), file=sys.stderr)
            prim = c[0].get("codigoCliente") or c[0].get("matricula")
            print("       campos do item: %s"%(", ".join(list(c[0].keys())[:40])), file=sys.stderr)

    print("== 4) PLANO B: /psec/alunos/alunoApp?cliente= (usa 1 id da lista) ==", file=sys.stderr)
    if prim is not None:
        for nome,path in [
            ("alunoApp cliente=<id>", "/psec/alunos/alunoApp?"+q(cliente=prim)),
        ]:
            st,body=get(key,path)
            report(nome, st, body)
    else:
        print("       (sem id para testar alunoApp)", file=sys.stderr)

if __name__=="__main__": main()
