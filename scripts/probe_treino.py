#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe v13 — caçar 3 alvos travados, usando IDs reais:
  (A) Professor -> LISTA de alunos da carteira (o vinculo existe: quem prescreve o treino)
  (B) Nota / NPS do treino (irmaos do avaliacao-treino)
  (C) Ficha/avaliacao POR ALUNO (indicadores -> lista, e ficha por codigoPessoa)
PII-safe: imprime SO status, nomes de campo e a mensagem de ERRO (sem valores)."""
import os, sys, json, urllib.request, urllib.error, urllib.parse
BASE = "https://apigw.pactosolucoes.com.br"
KEYS = ["PACTO_KEY_716NORTE","PACTO_KEY_905SUL","PACTO_KEY_604NORTE","PACTO_KEY_LAGONORTE","PACTO_KEY_LAGOSUL","PACTO_KEY_NATAL"]

def get(key, path, timeout=30):
    h={"Authorization":"Bearer "+key,"Accept":"application/json","empresaId":"1"}
    try:
        with urllib.request.urlopen(urllib.request.Request(BASE+path,headers=h),timeout=timeout) as r:
            return r.status, r.read().decode("utf-8","replace")
    except urllib.error.HTTPError as e: return e.code,(e.read().decode("utf-8","replace") if e.fp else "")
    except Exception as ex: return -1,str(ex)[:100]

def shape(body):
    try: j=json.loads(body)
    except Exception: return "(nao-JSON len=%d)"%len(body)
    def d(x,dep=0):
        if isinstance(x,dict):
            inner=" ->"+d(x.get("content"),dep+1) if ("content" in x and dep==0) else ""
            return "obj{%s}%s"%(", ".join(list(x.keys())[:30]),inner)
        if isinstance(x,list): return "lista[%d]%s"%(len(x),(" item0="+d(x[0],dep+1) if x else ""))
        return type(x).__name__
    return d(j)

def err(body):
    try:
        j=json.loads(body); m=j.get("meta",j) if isinstance(j,dict) else j
        for k in ("mensagem","message","erro","error","detalhe","detail"):
            if isinstance(m,dict) and m.get(k): return "%s=%s"%(k,str(m[k])[:160])
        return json.dumps(m,ensure_ascii=False)[:180]
    except Exception: return body[:120].replace("\n"," ")

def rep(nome, st, body):
    if st==200: print("  200  %-40s  %s"%(nome, shape(body)[:340]), file=sys.stderr)
    else:       print("%5s  %-40s  ERRO: %s"%(st, nome, err(body)), file=sys.stderr)

def content(body):
    try: j=json.loads(body); return j.get("content", j)
    except Exception: return None

def main():
    key=None
    for k in KEYS:
        if os.environ.get(k): key=os.environ[k]; break
    if not key: print("sem chave",file=sys.stderr); sys.exit(1)

    # ---- IDs reais ----
    PID=None
    st,b=get(key,"/psec/colaboradores/bi-professores-vinculos")
    c=content(b)
    if isinstance(c,list) and c:
        print("== [0] bi-professores-vinculos: chaves de UM professor (procurar lista de alunos) ==",file=sys.stderr)
        print("   item0=",shape(json.dumps(c[0]))[:400],file=sys.stderr)
        PID=(c[0].get("professor") or {}).get("id")
    CID=MAT=CP=None
    st,b=get(key,"/clientes/simples?page=0&size=5")
    c=content(b)
    if isinstance(c,list) and c:
        CID=c[0].get("codigoCliente"); MAT=c[0].get("matricula")
    if MAT is not None:
        st,b=get(key,"/clientes/%s/dados-pessoais"%MAT)
        cc=content(b)
        if isinstance(cc,dict): CP=cc.get("codigoPessoa")
    print("   IDs -> professor=%s cliente=%s matricula=%s codigoPessoa=%s"%(PID,CID,MAT,CP),file=sys.stderr)
    P=str(PID); C=str(CP); CL=str(CID)

    print("== (A) PROFESSOR -> LISTA DE ALUNOS ==",file=sys.stderr)
    for nome,path in [
        ("professores/{id}/alunos", "/psec/professores/%s/alunos"%P),
        ("colaboradores/{id}/alunos","/psec/colaboradores/%s/alunos"%P),
        ("treino-bi/alunos?idProfessor","/psec/treino-bi/alunos?idProfessor=%s"%P),
        ("treino/alunos?idProfessor","/psec/treino/alunos?idProfessor=%s"%P),
        ("treino-bi/carteira?idProfessor","/psec/treino-bi/carteira?idProfessor=%s"%P),
        ("professores/{id}/carteira","/psec/professores/%s/carteira"%P),
        ("colaboradores/{id}/carteira","/psec/colaboradores/%s/carteira"%P),
    ]:
        s2,b2=get(key,path); rep(nome,s2,b2)

    print("== (B) NOTA / NPS DO TREINO ==",file=sys.stderr)
    for nome,path in [
        ("avaliacao-treino/0","/psec/treino-bi/avaliacao-treino/0"),
        ("avaliacao-treino/0/{cp}","/psec/treino-bi/avaliacao-treino/0/%s"%C),
        ("treino-bi/nps","/psec/treino-bi/nps"),
        ("treino-bi/satisfacao","/psec/treino-bi/satisfacao"),
        ("treino-bi/avaliacoes","/psec/treino-bi/avaliacoes"),
        ("treino-bi/feedback","/psec/treino-bi/feedback"),
    ]:
        s2,b2=get(key,path); rep(nome,s2,b2)

    print("== (C) FICHA / INDICADOR POR ALUNO ==",file=sys.stderr)
    for nome,path in [
        ("indicadores-atividade (lista)","/psec/professores/indicadores-atividade"),
        ("indicadores (lista alt)","/psec/professores/indicadores"),
        ("treino/ficha/{cp}","/psec/treino/ficha/%s"%C),
        ("treino-bi/ficha/{cp}","/psec/treino-bi/ficha/%s"%C),
        ("alunos/{cp}/treino","/psec/alunos/%s/treino"%C),
        ("treino-bi/aluno/{cp}","/psec/treino-bi/aluno/%s"%C),
        ("treino/aluno/{cliente}","/psec/treino/aluno/%s"%CL),
    ]:
        s2,b2=get(key,path); rep(nome,s2,b2)

if __name__=="__main__": main()
