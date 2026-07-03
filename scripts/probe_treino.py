#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe v10 (fase2 CRM aluno) — achar a combinacao certa do feed POR ALUNO.
Alvo: /psec/professores/indicadores-atividade/alunos?filters=<json>&page=&size=
PII-safe: imprime SO status, chaves (nomes de campo) e contagens. NUNCA valores
(nome/cpf/email nao aparecem — logs de repo publico sao visiveis)."""
import os, sys, json, datetime, urllib.request, urllib.error, urllib.parse
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
    """Descreve a ESTRUTURA (so nomes de chave e tamanhos), nunca valores."""
    try: j=json.loads(body)
    except Exception: return "(nao-JSON len=%d) %s"%(len(body), body[:120])
    def d(x,dep=0):
        if isinstance(x,dict):
            inner=" ->"+d(x.get("content"),dep+1) if ("content" in x and dep==0) else ""
            return "obj{%s}%s"%(", ".join(list(x.keys())[:30]),inner)
        if isinstance(x,list): return "lista[%d]%s"%(len(x),(" item0="+d(x[0],dep+1) if x else ""))
        return type(x).__name__
    return d(j)

def q(**kw):
    return urllib.parse.urlencode({k:v for k,v in kw.items() if v is not None})

def main():
    key=None
    for k in KEYS:
        if os.environ.get(k): key=os.environ[k]; break
    if not key: print("sem chave",file=sys.stderr); sys.exit(1)

    P="/psec/professores/indicadores-atividade/alunos"
    # varios formatos de filters ate um responder 200 com lista
    filtros = [
        ("sem filters",        None),
        ("filters={}",         "{}"),
        ("filters=[]",         "[]"),
        ('filters={"situacao":"ATIVO"}', '{"situacao":"ATIVO"}'),
        ('filters={"situacao":1}',       '{"situacao":1}'),
        ('filters={"nivel":"TODOS"}',    '{"nivel":"TODOS"}'),
        ('filters={"idProfessor":0}',    '{"idProfessor":0}'),
        ('filters={"todos":true}',       '{"todos":true}'),
    ]
    print("== A) %s  (variando filters, page=0 size=20) =="%P, file=sys.stderr)
    for nome,f in filtros:
        path = P + "?" + q(filters=f, page=0, size=20)
        st,body = get(key,path)
        print("%5s  %-34s  %s"%(st,nome,shape(body)[:320]), file=sys.stderr)

    # B) sem 'size', com page (alguns endpoints ignoram size)
    print("== B) variacoes de paginacao ==", file=sys.stderr)
    for nome,path in [
        ("page=0",              P+"?"+q(filters="{}", page=0)),
        ("page=0&size=100",     P+"?"+q(filters="{}", page=0, size=100)),
        ("pagina=0 (pt)",       P+"?"+q(filters="{}", pagina=0)),
        ("sem page",            P+"?"+q(filters="{}")),
    ]:
        st,body=get(key,path); print("%5s  %-20s  %s"%(st,nome,shape(body)[:320]), file=sys.stderr)

    # C) rotas irmas candidatas (caso a de cima nao sirva)
    print("== C) rotas irmas ==", file=sys.stderr)
    irmas = [
        ("carteira-professores/alunos", "/psec/professores/indicadores-carteira-professores/alunos?"+q(filters="{}",page=0,size=20)),
        ("treino-bi/alunos",            "/psec/treino-bi/alunos?"+q(page=0,size=20)),
        ("treino-bi/carteira/alunos",   "/psec/treino-bi/carteira/alunos?"+q(page=0,size=20)),
        ("atividades-acumuladas/alunos","/psec/professores/indicadores-atividades-acumuladas/alunos?"+q(filters="{}",page=0)),
    ]
    for nome,path in irmas:
        st,body=get(key,path); print("%5s  %-30s  %s"%(st,nome,shape(body)[:320]), file=sys.stderr)

if __name__=="__main__": main()
