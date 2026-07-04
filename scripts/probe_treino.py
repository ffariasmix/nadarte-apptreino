#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe v14 — achar ONDE a MODALIDADE do aluno vive na API (o `descricao` de
dados-pessoais veio vazio -> publico-alvo saiu 100% Fitness). Testa candidatos e
mostra as CHAVES + o valor de campos com cara de modalidade/plano.
PII-safe: imprime chaves e valores SO de campos de modalidade/plano (nunca nome/cpf)."""
import os, sys, json, unicodedata, urllib.request, urllib.error, urllib.parse
BASE = "https://apigw.pactosolucoes.com.br"
KEYS = ["PACTO_KEY_716NORTE","PACTO_KEY_905SUL","PACTO_KEY_604NORTE","PACTO_KEY_LAGONORTE","PACTO_KEY_LAGOSUL","PACTO_KEY_NATAL"]

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

# campos que interessam (modalidade/plano) — so estes tem valor impresso; PII (nome/cpf) NUNCA
CAND = ("descric","plano","planos","modalidad","categoria","produto","servic","contrato","turma","atividade")
PII  = ("cpf","nome","email","telefone","rg","nasc","endereco","senha")

def dump(nome, st, body):
    if st != 200:
        print("%5s  %-38s  (sem 200)"%(st, nome), file=sys.stderr); return
    c = content(body)
    if isinstance(c, list): c0 = c[0] if c else {}
    else: c0 = c
    if not isinstance(c0, dict):
        print("  200  %-38s  tipo=%s"%(nome, type(c0).__name__), file=sys.stderr); return
    chaves = [k for k in c0.keys()]
    vals = []
    for k, v in c0.items():
        kl = up(k)
        if any(p in kl for p in PII):  # nunca imprime PII
            continue
        if any(t in kl for t in CAND) and isinstance(v, (str, int, float)) and str(v).strip():
            vals.append("%s=%s" % (k, str(v)[:70]))
    print("  200  %-38s  CHAVES: %s"%(nome, ", ".join(str(k) for k in chaves)[:220]), file=sys.stderr)
    if vals:
        print("            >> modalidade/plano: %s"%(" | ".join(vals)[:280]), file=sys.stderr)
    else:
        print("            >> nenhum campo de modalidade com valor aqui", file=sys.stderr)

def main():
    key=None
    for k in KEYS:
        if os.environ.get(k): key=os.environ[k]; break
    if not key: print("sem chave",file=sys.stderr); sys.exit(1)

    # pega 1 aluno ATIVO real (matricula + codigoCliente)
    st,b=get(key,"/clientes/simples?"+urllib.parse.urlencode({"situacao":"ATIVO","page":0,"size":5}))
    c=content(b);
    if not (isinstance(c,list) and c):
        st,b=get(key,"/clientes/simples?page=0&size=5"); c=content(b)
    it = next((x for x in c if up(x.get("situacao"))=="ativo"), c[0]) if isinstance(c,list) and c else {}
    MAT=it.get("matricula"); CID=it.get("codigoCliente")
    print("== ids: matricula=%s codigoCliente=%s | chaves de clientes/simples: %s"%(
        MAT, CID, ", ".join(it.keys())), file=sys.stderr)

    print("== (A) dados-pessoais (esperavamos 'descricao' com a modalidade) ==", file=sys.stderr)
    dump("clientes/%s/dados-pessoais"%MAT, *get(key,"/clientes/%s/dados-pessoais"%MAT))

    print("== (B) detalhe do cliente (/v1/cliente/{codigoCliente}) ==", file=sys.stderr)
    dump("v1/cliente/%s"%CID, *get(key,"/v1/cliente/%s"%CID))

    print("== (C) contratos em bulk (/v1/contrato) — ideal p/ juntar por cliente ==", file=sys.stderr)
    dump("v1/contrato?size=3", *get(key,"/v1/contrato?page=0&size=3"))

    print("== (D) outros caminhos de plano/modalidade por aluno ==", file=sys.stderr)
    for nome,path in [
        ("clientes/{mat}/contratos", "/clientes/%s/contratos"%MAT),
        ("clientes/{mat}/plano",     "/clientes/%s/plano"%MAT),
        ("clientes/{mat}/modalidades","/clientes/%s/modalidades"%MAT),
        ("clientes/{mat}/contrato",  "/clientes/%s/contrato"%MAT),
        ("v1/contrato/cliente/{cid}","/v1/contrato/cliente/%s"%CID),
        ("clientes/{cid}/detalhe",   "/clientes/%s/detalhe"%CID),
    ]:
        dump(nome, *get(key,path))

if __name__=="__main__": main()
