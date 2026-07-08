#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe v27 — Bloco 01: NOTA por professor + TREINO EM DIA por aluno.
  A) /psec/treino-bi/dados?idProfessor={profId}  -> por professor: nr*estrelas (nota) + treinos em dia?
  B) /psec/treino-bi/alunos-treino-em-dia/{codigoPessoa}   -> estrutura (lista por aluno?)
  C) /psec/treino-bi/alunos-treino-vencido/{codigoPessoa}
PII-safe: status, chaves e numeros. Se as listas trouxerem nomes, imprime SO as chaves e a contagem."""
import os, sys, json, urllib.request, urllib.error, urllib.parse
BASE = "https://apigw.pactosolucoes.com.br"
KEYS = [("716NORTE","PACTO_KEY_716NORTE"),("905SUL","PACTO_KEY_905SUL"),
        ("604NORTE","PACTO_KEY_604NORTE"),("LAGONORTE","PACTO_KEY_LAGONORTE"),
        ("LAGOSUL","PACTO_KEY_LAGOSUL"),("NATAL","PACTO_KEY_NATAL")]
PII=("nome","cpf","email","telefone","aluno","cliente")
def get(key, path, timeout=30):
    h={"Authorization":"Bearer "+key,"Accept":"application/json","empresaId":"1"}
    try:
        with urllib.request.urlopen(urllib.request.Request(BASE+path,headers=h),timeout=timeout) as r:
            return r.status, r.read().decode("utf-8","replace")
    except urllib.error.HTTPError as e: return e.code,(e.read().decode("utf-8","replace") if e.fp else "")
    except Exception as ex: return -1,str(ex)[:120]
def cont(b):
    try: j=json.loads(b); return j.get("content", j)
    except: return None
def keys_safe(o):
    if isinstance(o,list): return "(lista %d; item0=%s)"%(len(o), keys_safe(o[0]) if o else "?")
    if isinstance(o,dict): return [k+("[PII]" if any(p in k.lower() for p in PII) else "") for k in o.keys()]
    return type(o).__name__

def main():
    label=key=None
    for lb,env in KEYS:
        if os.environ.get(env): label,key=lb,os.environ[env]; break
    if not key: print("sem chave",file=sys.stderr); sys.exit(1)
    print("== UNIDADE %s ==" % label, file=sys.stderr)
    # pega um professor (id + codigoPessoa)
    pj=cont(get(key,"/psec/colaboradores/bi-professores-vinculos")[1])
    profs=pj if isinstance(pj,list) else (pj.get("content") if isinstance(pj,dict) else None)
    pid=pcp=None
    if isinstance(profs,list) and profs:
        pr=profs[0].get("professor") or {}
        pid, pcp = pr.get("id"), pr.get("codigoPessoa")
    print("professor amostra: id=%s codigoPessoa=%s" % (pid,pcp), file=sys.stderr)

    # A) dados?idProfessor={pid} -> nota + treino em dia POR PROFESSOR?
    print("\n[A] /psec/treino-bi/dados?idProfessor=%s" % pid, file=sys.stderr)
    st,body=get(key,"/psec/treino-bi/dados?idProfessor=%s"%urllib.parse.quote(str(pid)))
    d=cont(body)
    if isinstance(d,dict):
        interesse={k:d.get(k) for k in ("totalAlunos","totalTreinosEmdia","percentualEmDia","totalTreinosVencidos",
                    "nr1estrelas","nr2estrelas","nr3estrelas","nr4estrelas","nr5estrelas","percentualAvaliacoes") if k in d}
        print("  status=%s | por-professor: %s" % (st, interesse), file=sys.stderr)
    else:
        print("  status=%s (sem dict)" % st, file=sys.stderr)

    # B/C) treino em dia / vencido por aluno
    for ep,lb in [("alunos-treino-em-dia","em dia"),("alunos-treino-vencido","vencido")]:
        for cp in [0, pcp]:
            if cp is None: continue
            st,body=get(key,"/psec/treino-bi/%s/%s?page=1&size=2"%(ep, urllib.parse.quote(str(cp))))
            j=cont(body)
            n=(j.get("quantidadeTotalElementos") if isinstance(j,dict) else None)
            itens=j.get("content") if isinstance(j,dict) else (j if isinstance(j,list) else None)
            print("\n[%s cp=%s] status=%s | qtd=%s | chaves=%s" % (lb, cp, str(st).rjust(3), n, keys_safe(itens)), file=sys.stderr)

    print("\n>> Se [A] trouxer nr*estrelas e treinos em dia por professor, resolve NOTA-por-prof + base do treino.", file=sys.stderr)
    print(">> Se [B] trouxer lista por aluno com flag de em-dia, resolve TREINO-EM-DIA por aluno.", file=sys.stderr)

if __name__=="__main__": main()
