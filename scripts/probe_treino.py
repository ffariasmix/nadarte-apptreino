#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe v23 — CONTRATO por matricula -> modalidade (7 baldes).
Endpoint achado na doc: GET /v1/contrato/matricula/{matricula} (escopo
adm:cadastros:contrato:modelos-de-contrato:consultar). Confirma se NOSSA chave
tem o escopo (status 200 x 403/500), mostra a ESTRUTURA do item e classifica a
descricao do plano nos 7 baldes. PII-safe: descricao de plano nao e dado pessoal."""
import os, sys, json, re, unicodedata, urllib.request, urllib.error, urllib.parse
BASE = "https://apigw.pactosolucoes.com.br"
KEYS = [("716NORTE","PACTO_KEY_716NORTE"),("905SUL","PACTO_KEY_905SUL"),
        ("604NORTE","PACTO_KEY_604NORTE"),("LAGONORTE","PACTO_KEY_LAGONORTE"),
        ("LAGOSUL","PACTO_KEY_LAGOSUL"),("NATAL","PACTO_KEY_NATAL")]

def _up(s): return "".join(c for c in unicodedata.normalize("NFD",str(s or "")) if unicodedata.category(c)!="Mn").upper().strip()
_AGUA=("NATAC","NATA","HIDRO","BEBE","AQUA")
_LUTAS=("KARATE","MUAY","JIU","JUDO","HAPKIDO","CAPOEIRA","BOXE","TAEKWON","KUNG","LUTA")
_FIT=("TRANSITO LIVRE"," TL ","FITNESS","MUSCULA","DANCA","PILATES","AULA COLETIVA","FUNCIONAL",
      "SPINNING","CROSS","ZUMBA","RITMO","GINASTICA","ALONGA","YOGA","TREINA","LIVRE ACESSO")
def _tok(t):
    t=" "+_up(t)+" "
    if any(k in t for k in _AGUA): return "agua"
    if any(k in t for k in _FIT): return "fit"
    if any(k in t for k in _LUTAS): return "lutas"
    return "outros"
def categoria7(desc):
    u=_up(desc)
    if "TODAS AS MODALIDADES" in u or "TODAS MODALIDADES" in u: return "Ambos(A+F+L)"  # plano completo
    toks=[t for t in re.split(r"[;,+/]", str(desc or "")) if t.strip()]
    b=set(_tok(t) for t in toks); b.discard("outros")
    A,F,L="agua" in b,"fit" in b,"lutas" in b
    if A and F and L: return "Ambos(A+F+L)"
    if A and F: return "Ambos(A+F)"
    if A and L: return "Ambos(A+L)"
    if F and L: return "Ambos(F+L)"
    if A: return "Agua"
    if F: return "Fitness"
    if L: return "Luta"
    return "Outros"

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

def sample_ativos(key, alvo=12):
    out=[]
    for pg in range(0,40):
        if len(out)>=alvo: break
        c=content(get(key,"/clientes/simples?"+urllib.parse.urlencode({"page":pg,"size":50}))[1])
        if not isinstance(c,list): continue
        for x in c:
            if _up(x.get("situacao"))=="ATIVO":
                out.append(x)
                if len(out)>=alvo: break
    return out

def main():
    label=key=None
    for lb,env in KEYS:
        if os.environ.get(env): label,key=lb,os.environ[env]; break
    if not key: print("sem chave",file=sys.stderr); sys.exit(1)
    print("== UNIDADE %s ==" % label, file=sys.stderr)
    alvos=sample_ativos(key,12)
    print("amostra ATIVO: %d\n" % len(alvos), file=sys.stderr)

    status_cont={}; dist={}; estrutura_mostrada=False; sem_contrato=0
    for it in alvos:
        mat=it.get("matricula") or it.get("codigoCliente")
        st,body=get(key,"/v1/contrato/matricula/%s"%urllib.parse.quote(str(mat)))
        status_cont[st]=status_cont.get(st,0)+1
        c=content(body) if (isinstance(st,int) and 200<=st<300) else None
        itens=c if isinstance(c,list) else (c.get("content") if isinstance(c,dict) else None)
        if not isinstance(itens,list) or not itens:
            if st!=200: print("  matricula=%s -> HTTP %s" % (mat,st), file=sys.stderr)
            else: sem_contrato+=1
            continue
        if not estrutura_mostrada:
            print("  [estrutura] chaves do contrato: %s" % sorted(itens[0].keys()), file=sys.stderr)
            print("  [estrutura] item[0]: %s\n" % json.dumps(itens[0], ensure_ascii=False)[:300], file=sys.stderr)
            estrutura_mostrada=True
        # classifica a descricao de cada contrato do aluno (normalmente pega o vigente)
        descs=[str(x.get("descricao") or "") for x in itens if str(x.get("descricao") or "").strip()]
        cat=categoria7(" , ".join(descs)) if descs else "Outros"
        dist[cat]=dist.get(cat,0)+1
        print("  matricula=%s | %d contrato(s): %s -> %s" % (mat, len(itens), descs[:2], cat), file=sys.stderr)

    print("\n== RESUMO ==", file=sys.stderr)
    print("  status HTTP do endpoint contrato: %s" % status_cont, file=sys.stderr)
    print("  sem contrato (200 vazio): %d" % sem_contrato, file=sys.stderr)
    print("  distribuicao 7 baldes (amostra): %s" % dist, file=sys.stderr)
    print("\n>> status 200 => nossa chave TEM o escopo; ai eu ligo a modalidade no coletor.", file=sys.stderr)

if __name__=="__main__": main()
