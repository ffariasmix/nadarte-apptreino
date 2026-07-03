#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe v11 (fase2 CRM aluno) — revelar a MENSAGEM DE ERRO (envelope meta) das
duas rotas por-aluno que existem, e testar mais formatos de filters.
Alvos: /psec/professores/indicadores-atividade/alunos
       /psec/professores/indicadores-carteira-professores/alunos
PII-safe: em 500/400 imprime o texto do ERRO (nao tem dado de aluno). Se algum
retornar 200, imprime SO as chaves (nomes de campo), nunca valores."""
import os, sys, json, datetime, urllib.request, urllib.error, urllib.parse
BASE = "https://apigw.pactosolucoes.com.br"
KEYS = ["PACTO_KEY_716NORTE","PACTO_KEY_905SUL","PACTO_KEY_604NORTE","PACTO_KEY_LAGONORTE","PACTO_KEY_LAGOSUL","PACTO_KEY_NATAL"]

def get(key, path, timeout=30):
    h={"Authorization":"Bearer "+key,"Accept":"application/json","empresaId":"1"}
    try:
        with urllib.request.urlopen(urllib.request.Request(BASE+path,headers=h),timeout=timeout) as r:
            return r.status, r.read().decode("utf-8","replace")
    except urllib.error.HTTPError as e: return e.code,(e.read().decode("utf-8","replace") if e.fp else "")
    except Exception as ex: return -1,str(ex)[:120]

def keys_only(body):
    """Se 200: so nomes de chave (sem valores). Item0 tambem so chaves."""
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
    """Extrai o texto de erro do envelope meta (seguro: nao tem PII)."""
    try:
        j=json.loads(body)
        m=j.get("meta", j) if isinstance(j,dict) else j
        for k in ("mensagem","message","erro","error","detalhe","detail","exception","descricao"):
            if isinstance(m,dict) and m.get(k): return "%s=%s"%(k,str(m[k])[:260])
        return json.dumps(m, ensure_ascii=False)[:300]
    except Exception:
        return body[:200].replace("\n"," ")

def report(nome, st, body):
    if st==200: print("  200  %-42s  %s"%(nome, keys_only(body)[:340]), file=sys.stderr)
    else:       print("%5s  %-42s  ERRO: %s"%(st, nome, err_msg(body)), file=sys.stderr)

def q(**kw):
    return urllib.parse.urlencode({k:v for k,v in kw.items() if v is not None})

def main():
    key=None
    for k in KEYS:
        if os.environ.get(k): key=os.environ[k]; break
    if not key: print("sem chave",file=sys.stderr); sys.exit(1)
    now=datetime.datetime.utcnow(); df=int(now.timestamp()*1000); di=int((now-datetime.timedelta(days=365)).timestamp()*1000)

    A="/psec/professores/indicadores-atividade/alunos"
    B="/psec/professores/indicadores-carteira-professores/alunos"

    print("== 1) mensagem de erro atual (pra saber o que falta) ==", file=sys.stderr)
    for nome,path in [("atividade filters={}", A+"?"+q(filters="{}",page=0,size=20)),
                      ("carteira  filters={}", B+"?"+q(filters="{}",page=0,size=20))]:
        st,body=get(key,path); report(nome,st,body)

    print("== 2) filters como ARRAY de objetos ==", file=sys.stderr)
    arrs = [
        ('[]',                                  "[]"),
        ('[{"campo":"situacao","valor":"A"}]',  '[{"campo":"situacao","valor":"A"}]'),
        ('[{"field":"situacao","value":"A"}]',  '[{"field":"situacao","value":"A"}]'),
        ('[{"id":"situacao","value":"ATIVO"}]', '[{"id":"situacao","value":"ATIVO"}]'),
    ]
    for label,f in arrs:
        st,body=get(key,A+"?"+q(filters=f,page=0,size=20)); report("atividade "+label,st,body)

    print("== 3) com datas / idProfessor fora do filters ==", file=sys.stderr)
    for nome,path in [
        ("atividade +datas",        A+"?"+q(filters="{}",page=0,size=20,dataInicio=di,dataFim=df)),
        ("atividade idProfessor=0", A+"?"+q(filters="{}",page=0,size=20,idProfessor=0)),
        ("carteira +datas",         B+"?"+q(filters="{}",page=0,size=20,dataInicio=di,dataFim=df)),
        ("carteira idProfessor=0",  B+"?"+q(filters="{}",page=0,size=20,idProfessor=0)),
    ]:
        st,body=get(key,path); report(nome,st,body)

    print("== 4) endpoints-pai (sem /alunos) pra confirmar que respondem ==", file=sys.stderr)
    for nome,path in [
        ("indicadores-atividade",             "/psec/professores/indicadores-atividade"),
        ("indicadores-carteira-professores",  "/psec/professores/indicadores-carteira-professores"),
    ]:
        st,body=get(key,path); report(nome,st,body)

if __name__=="__main__": main()
