#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe v15 — abrir /v1/cliente/{codigoCliente} e achar a MODALIDADE dentro de
`vinculos` (dados-pessoais nao tem `descricao`; a modalidade parece estar aqui).
PII-safe: imprime a estrutura de vinculos/clienteSintetico com valores, mas
REDIGE qualquer campo com cara de dado pessoal (nome/cpf/telefone/email/nascimento)."""
import os, sys, json, unicodedata, urllib.request, urllib.error, urllib.parse
BASE = "https://apigw.pactosolucoes.com.br"
KEYS = ["PACTO_KEY_716NORTE","PACTO_KEY_905SUL","PACTO_KEY_604NORTE","PACTO_KEY_LAGONORTE","PACTO_KEY_LAGOSUL","PACTO_KEY_NATAL"]
PII = ("cpf","nome","email","telefone","fone","rg","nasc","endereco","logradouro","senha","foto","genero","sexo","idade")

def up(s): return "".join(c for c in unicodedata.normalize("NFD", str(s or "")) if unicodedata.category(c)!="Mn").lower()

def get(key, path, timeout=30):
    h={"Authorization":"Bearer "+key,"Accept":"application/json","empresaId":"1"}
    try:
        with urllib.request.urlopen(urllib.request.Request(BASE+path,headers=h),timeout=timeout) as r:
            return r.status, r.read().decode("utf-8","replace")
    except urllib.error.HTTPError as e: return e.code,(e.read().decode("utf-8","replace") if e.fp else "")
    except Exception as ex: return -1,str(ex)[:100]

def content(body):
    try: j=json.loads(body); return j.get("content", j)
    except Exception: return None

def red(obj, depth=0):
    """Copia a estrutura redigindo PII (chaves com nome/cpf/etc viram ***)."""
    if depth > 5: return "..."
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            out[k] = "***" if any(p in up(k) for p in PII) else red(v, depth+1)
        return out
    if isinstance(obj, list):
        return [red(x, depth+1) for x in obj[:3]]   # so 3 itens de amostra
    if isinstance(obj, str) and len(obj) > 80:
        return obj[:80] + "…"
    return obj

def main():
    key=None
    for k in KEYS:
        if os.environ.get(k): key=os.environ[k]; break
    if not key: print("sem chave",file=sys.stderr); sys.exit(1)

    st,b=get(key,"/clientes/simples?"+urllib.parse.urlencode({"situacao":"ATIVO","page":0,"size":8}))
    c=content(b)
    if not (isinstance(c,list) and c):
        st,b=get(key,"/clientes/simples?page=0&size=8"); c=content(b)
    # tenta ate 3 alunos ATIVO (pra ver variedade de modalidade)
    alvos=[x for x in c if up(x.get("situacao"))=="ativo"][:3] if isinstance(c,list) else []
    if not alvos and isinstance(c,list): alvos=c[:3]
    print("== vou inspecionar %d aluno(s) ATIVO em /v1/cliente/{codigoCliente} ==" % len(alvos), file=sys.stderr)

    for it in alvos:
        cid=it.get("codigoCliente")
        st,b=get(key,"/v1/cliente/%s"%cid)
        cli=content(b)
        if not isinstance(cli, dict):
            print("  cliente %s -> status %s (sem objeto)"%(cid, st), file=sys.stderr); continue
        print("\n---- codigoCliente=%s ----"%cid, file=sys.stderr)
        for campo in ("vinculos","clienteSintetico"):
            if campo in cli:
                print("  [%s] = %s" % (campo, json.dumps(red(cli[campo]), ensure_ascii=False)[:900]), file=sys.stderr)
            else:
                print("  [%s] ausente" % campo, file=sys.stderr)

if __name__=="__main__": main()
