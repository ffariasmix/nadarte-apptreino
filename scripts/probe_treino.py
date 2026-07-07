#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe v25 — NOTA do treino, 2a tentativa.
avaliacao-treino deu 500 com codigoPessoa=0 e =professor. Testa:
  (a) /psec/treino-bi/dash            -> pode trazer a NOTA MEDIA agregada pronta
  (b) /psec/treino-bi/treinamento     -> idem
  (c) avaliacao-treino/{tipo}/{cp}    -> com codigoPessoa de ALUNO real (+ professorId)
  (d) avaliacao-treino-ia/{tipo}/{cp}
PII-safe: status, chaves de campo e a nota media derivada. Sem nomes/comentarios."""
import os, sys, json, urllib.request, urllib.error, urllib.parse
BASE = "https://apigw.pactosolucoes.com.br"
KEYS = [("716NORTE","PACTO_KEY_716NORTE"),("905SUL","PACTO_KEY_905SUL"),
        ("604NORTE","PACTO_KEY_604NORTE"),("LAGONORTE","PACTO_KEY_LAGONORTE"),
        ("LAGOSUL","PACTO_KEY_LAGOSUL"),("NATAL","PACTO_KEY_NATAL")]
PII = ("nome","comentario","comment","obs","observ","cpf","email","telefone")
def up(s):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD",str(s or "")) if unicodedata.category(c)!="Mn").upper()

def get(key, path, timeout=30):
    h={"Authorization":"Bearer "+key,"Accept":"application/json","empresaId":"1"}
    try:
        with urllib.request.urlopen(urllib.request.Request(BASE+path,headers=h),timeout=timeout) as r:
            return r.status, r.read().decode("utf-8","replace")
    except urllib.error.HTTPError as e: return e.code,(e.read().decode("utf-8","replace") if e.fp else "")
    except Exception as ex: return -1,str(ex)[:120]
def asj(b):
    try: return json.loads(b)
    except: return None

def find_nota(obj, path="", out=None, depth=0):
    """procura recursivamente campos que parecem NOTA/AVALIACAO/MEDIA/ESTRELA e imprime path=valor(numerico)."""
    if out is None: out=[]
    if depth>6: return out
    if isinstance(obj,dict):
        for k,v in obj.items():
            p=(path+"."+k) if path else k
            ku=up(k)
            if isinstance(v,(int,float)) and any(t in ku for t in ("NOTA","AVALIA","MEDIA","ESTRELA","RATING","SATISF")):
                out.append((p,v))
            find_nota(v,p,out,depth+1)
    elif isinstance(obj,list):
        for v in obj[:3]: find_nota(v,path+"[]",out,depth+1)
    return out
def keys_safe(o):
    if isinstance(o,list) and o: o=o[0]
    if not isinstance(o,dict): return type(o).__name__
    return [k+("[PII]" if any(p in k.lower() for p in PII) else "") for k in o.keys()]

def aluno_codigoPessoa(key):
    """acha o codigoPessoa de 1 aluno ATIVO (via /clientes/simples -> dados-pessoais)."""
    for pg in range(0,20):
        c=asj(get(key,"/clientes/simples?"+urllib.parse.urlencode({"page":pg,"size":50}))[1])
        c=c.get("content",c) if isinstance(c,dict) else c
        if not isinstance(c,list): continue
        for x in c:
            if up(x.get("situacao"))=="ATIVO":
                mat=x.get("matricula") or x.get("codigoCliente")
                dp=asj(get(key,"/clientes/%s/dados-pessoais"%urllib.parse.quote(str(mat)))[1])
                dp=dp.get("content",dp) if isinstance(dp,dict) else dp
                cp=(dp or {}).get("codigoPessoa") if isinstance(dp,dict) else None
                if cp: return cp
    return None

def dump(key, ep, label):
    st,body=get(key,ep); j=asj(body)
    print("  [%s] %s -> %s" % (label, str(st).rjust(3), ep), file=sys.stderr)
    if isinstance(st,int) and 200<=st<300 and isinstance(j,dict):
        c=j.get("content",j)
        print("     chaves: %s" % keys_safe(c), file=sys.stderr)
        nt=find_nota(j)
        for p,v in nt[:10]: print("     NOTA? %-40s = %s" % (p[:40],v), file=sys.stderr)

def main():
    label=key=None
    for lb,env in KEYS:
        if os.environ.get(env): label,key=lb,os.environ[env]; break
    if not key: print("sem chave",file=sys.stderr); sys.exit(1)
    print("== UNIDADE %s ==" % label, file=sys.stderr)

    # (a)(b) dashboards agregados — podem ter a nota pronta
    print("\n[DASH/TREINAMENTO agregados]", file=sys.stderr)
    for ep,lb in [("/psec/treino-bi/dash","dash"),("/psec/treino-bi/treinamento","treinamento"),
                  ("/psec/treino-bi/dados?idProfessor=0","dados")]:
        dump(key, ep, lb)

    # (c)(d) avaliacao-treino com codigoPessoa de ALUNO real
    acp=aluno_codigoPessoa(key)
    print("\n[avaliacao-treino] codigoPessoa de ALUNO real = %s" % acp, file=sys.stderr)
    if acp:
        for ep in ["/psec/treino-bi/avaliacao-treino/0/%s?page=1&size=2"%acp,
                   "/psec/treino-bi/avaliacao-treino/0/%s?professorId=0&page=1&size=2"%acp,
                   "/psec/treino-bi/avaliacao-treino-ia/0/%s?page=1&size=2"%acp]:
            st,body=get(key,ep); j=asj(body)
            print("  %s -> %s" % (str(st).rjust(3), ep.split("?")[0]), file=sys.stderr)
            if isinstance(st,int) and 200<=st<300 and isinstance(j,dict):
                print("     qtd=%s chaves=%s" % (j.get("quantidadeTotalElementos"), keys_safe(j.get("content"))), file=sys.stderr)
    print("\n>> Onde aparecer 'NOTA?' ou 200 no avaliacao-treino, achamos a nota.", file=sys.stderr)

if __name__=="__main__": main()
