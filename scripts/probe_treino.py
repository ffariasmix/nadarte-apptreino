#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe v21 — achar o CONTRATO/plano por aluno (ultimo elo p/ modalidade).
/v1/cliente nao tem modalidade; /v1/contrato?page&size deu 500. Testa variacoes do
endpoint de contrato (por cliente, outros params) e endpoints de plano-do-aluno.
Tambem inspeciona a estrutura de 1 item de /planos e /modalidade (pra ver se tem id
+ lista de modalidades, o que permitiria mapear plano->modalidade).
PII-safe: imprime status, chaves e valores que casam modalidade (nao nome/cpf)."""
import os, sys, json, re, unicodedata, urllib.request, urllib.error, urllib.parse
BASE = "https://apigw.pactosolucoes.com.br"
KEYS = [("716NORTE","PACTO_KEY_716NORTE"),("905SUL","PACTO_KEY_905SUL"),
        ("604NORTE","PACTO_KEY_604NORTE"),("LAGONORTE","PACTO_KEY_LAGONORTE"),
        ("LAGOSUL","PACTO_KEY_LAGOSUL"),("NATAL","PACTO_KEY_NATAL")]

def _sa(s): return "".join(c for c in unicodedata.normalize("NFD", str(s or "")) if unicodedata.category(c)!="Mn")
def _up(s): return _sa(s).upper().strip()
_AGUA=("NATAC","NATA","HIDRO","BEBE","AQUA")
_LUTAS=("KARATE","MUAY","JIU","JUDO","HAPKIDO","CAPOEIRA","BOXE","TAEKWON","KUNG","LUTA")
_FIT=("TRANSITO LIVRE"," TL ","FITNESS","MUSCULA","DANCA","PILATES","AULA COLETIVA","FUNCIONAL",
      "SPINNING","CROSS","ZUMBA","RITMO","GINASTICA","ALONGA","YOGA","TREINA")
KW=_AGUA+_LUTAS+_FIT

def get(key, path, timeout=30):
    h={"Authorization":"Bearer "+key,"Accept":"application/json","empresaId":"1"}
    try:
        with urllib.request.urlopen(urllib.request.Request(BASE+path,headers=h),timeout=timeout) as r:
            return r.status, r.read().decode("utf-8","replace")
    except urllib.error.HTTPError as e: return e.code,(e.read().decode("utf-8","replace") if e.fp else "")
    except Exception as ex: return -1,str(ex)[:120]

def content(body):
    try: j=json.loads(body); return j.get("content", j)
    except Exception: return None

def keys_of(o):
    if isinstance(o,dict): return sorted(o.keys())
    if isinstance(o,list): return "(lista %d; item0=%s)"%(len(o), sorted(o[0].keys()) if o and isinstance(o[0],dict) else "?")
    return type(o).__name__

BLOCK=re.compile(r"cpf|email|telefone|celular|nasc|endereco|\brg\b|cep", re.I)
def scan_values(obj, path="", out=None, depth=0):
    if out is None: out=[]
    if depth>9: return out
    if isinstance(obj,str):
        u=" "+_up(obj)+" "
        if 3<len(obj)<80 and any(k in u for k in KW): out.append((path,obj[:60]))
    elif isinstance(obj,dict):
        for k,v in obj.items():
            if BLOCK.search(k): continue
            scan_values(v,(path+"."+k) if path else k,out,depth+1)
    elif isinstance(obj,list):
        for v in obj[:10]: scan_values(v,path+"[]",out,depth+1)
    return out

def one_ativo(key):
    for pg in range(0,40):
        c=content(get(key,"/clientes/simples?"+urllib.parse.urlencode({"page":pg,"size":50}))[1])
        if isinstance(c,list):
            for x in c:
                if _up(x.get("situacao"))=="ATIVO": return x
    return None

def dump_ep(key, ep, label=""):
    st,body=get(key,ep)
    j=content(body) if (isinstance(st,int) and 200<=st<300) else None
    print("  [%s] %s%s" % (str(st).rjust(3), ep, ("  "+label) if label else ""), file=sys.stderr)
    if j is not None:
        print("        chaves: %s" % keys_of(j), file=sys.stderr)
        hits=scan_values(j)
        for p,v in hits[:8]:
            print("        modalidade? %-28s = '%s'" % (p[:28],v), file=sys.stderr)

def main():
    label=key=None
    for lb,env in KEYS:
        if os.environ.get(env): label,key=lb,os.environ[env]; break
    if not key: print("sem chave",file=sys.stderr); sys.exit(1)
    print("== UNIDADE %s ==" % label, file=sys.stderr)

    # estrutura de 1 item de catalogo (plano/modalidade) — tem id? tem modalidades?
    for cat in ("/planos","/modalidade"):
        st,body=get(key,cat); j=content(body)
        itens=j if isinstance(j,list) else (j.get("content") if isinstance(j,dict) else None)
        if isinstance(itens,list) and itens:
            print("\n[%s] item[0] completo:" % cat, file=sys.stderr)
            print("   %s" % json.dumps(itens[0], ensure_ascii=False)[:400], file=sys.stderr)

    cli=one_ativo(key)
    cid=cli.get("codigoCliente"); mat=cli.get("matricula")
    print("\n== testando endpoints de CONTRATO/plano (cid=%s mat=%s) ==" % (cid,mat), file=sys.stderr)
    q=urllib.parse.quote
    candidatos=[
        "/v1/contrato?page=0&size=5",
        "/v1/contrato?codigoCliente=%s&page=0&size=5"%q(str(cid)),
        "/v1/contrato?cliente=%s&page=0&size=5"%q(str(cid)),
        "/v1/contrato/%s"%q(str(cid)),
        "/v1/cliente/%s/contrato"%q(str(cid)),
        "/v1/cliente/%s/contratos"%q(str(cid)),
        "/clientes/%s/contrato"%q(str(mat)),
        "/clientes/%s/contratos"%q(str(mat)),
        "/clientes/%s/plano"%q(str(mat)),
        "/clientes/%s/planos"%q(str(mat)),
        "/v1/cliente/%s/plano"%q(str(cid)),
        "/psec/contrato?cliente=%s"%q(str(cid)),
        "/v1/contratos?codigoCliente=%s"%q(str(cid)),
    ]
    for ep in candidatos:
        dump_ep(key, ep)
    print("\n>> Onde aparecer 200 + 'modalidade? ...' (ou chaves de plano), achamos o vinculo aluno->plano.", file=sys.stderr)

if __name__=="__main__": main()
