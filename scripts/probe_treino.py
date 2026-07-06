#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe v18 — CATALOGO de modalidades/planos/categorias.
Em vez de olhar aluno a aluno, varre endpoints candidatos de catalogo e lista os
NOMES de modalidades/planos disponiveis no sistema (com a categoria Fitness/Agua/
Ambos/Lutas que o classify_grupo atribuiria a cada nome).
PII-safe: catalogo (nomes de plano/modalidade) nao e dado pessoal."""
import os, sys, json, unicodedata, urllib.request, urllib.error, urllib.parse
BASE = "https://apigw.pactosolucoes.com.br"
KEYS = [("716NORTE","PACTO_KEY_716NORTE"),("905SUL","PACTO_KEY_905SUL"),
        ("604NORTE","PACTO_KEY_604NORTE"),("LAGONORTE","PACTO_KEY_LAGONORTE"),
        ("LAGOSUL","PACTO_KEY_LAGOSUL"),("NATAL","PACTO_KEY_NATAL")]

def _sa(s): return "".join(c for c in unicodedata.normalize("NFD", str(s or "")) if unicodedata.category(c)!="Mn")
def _up(s): return _sa(s).upper().strip()
_AGUA=("NATAC","NATA","HIDRO","BEBE","AQUA")
_LUTAS=("KARATE","MUAY","JIU","JUDO","HAPKIDO","CAPOEIRA","BOXE","TAEKWON","KUNG","LUTA")
_FIT=("TRANSITO LIVRE","FITNESS","MUSCULA","DANCA","PILATES","AULA COLETIVA","FUNCIONAL",
      "SPINNING","CROSS","ZUMBA","RITMO","GINASTICA","ALONGA","YOGA","TREINA")
def _tok(t):
    t=_up(t)
    if any(k in t for k in _AGUA): return "agua"
    if any(k in t for k in _FIT): return "fit"
    if any(k in t for k in _LUTAS): return "lutas"
    return "outros"
def classify_grupo(desc):
    toks=[t for t in str(desc or "").replace(";",",").split(",") if t.strip()]
    b=set(_tok(t) for t in toks)
    if not b: return "Fitness"
    if "agua" in b and ("fit" in b or "lutas" in b): return "Ambos"
    if "agua" in b: return "Agua"
    if "fit" in b: return "Fitness"
    return "Lutas e Outros"

def get(key, path, timeout=30):
    h={"Authorization":"Bearer "+key,"Accept":"application/json","empresaId":"1"}
    try:
        with urllib.request.urlopen(urllib.request.Request(BASE+path,headers=h),timeout=timeout) as r:
            return r.status, r.read().decode("utf-8","replace")
    except urllib.error.HTTPError as e: return e.code,(e.read().decode("utf-8","replace") if e.fp else "")
    except Exception as ex: return -1,str(ex)[:120]

def as_json(body):
    try: return json.loads(body)
    except Exception: return None

def listify(j):
    """Extrai a lista de itens de varias formas de resposta {content:[...]}, [...], {content:{content:[...]}}"""
    if isinstance(j, list): return j
    if isinstance(j, dict):
        c=j.get("content", j)
        if isinstance(c, list): return c
        if isinstance(c, dict) and isinstance(c.get("content"), list): return c["content"]
    return None

NAME_FIELDS=("nome","descricao","modalidade","titulo","descricaoModalidade","nomeModalidade",
             "nomePlano","descricaoPlano","name","label")

def name_of(it):
    if not isinstance(it, dict): return str(it)[:50]
    for f in NAME_FIELDS:
        v=it.get(f)
        if str(v or "").strip(): return str(v).strip()
    # senao, mostra as chaves pra debug
    return "{keys:"+",".join(list(it.keys())[:6])+"}"

CANDIDATOS=[
    "/modalidades","/modalidade","/v1/modalidade","/v1/modalidades","/psec/modalidades",
    "/psec/modalidade","/planos","/plano","/v1/plano","/v1/planos","/psec/planos",
    "/categorias","/categoria","/v1/categoria","/psec/categorias",
    "/v1/modalidade/listar","/modalidades/listar",
    "/produtos","/produto","/v1/produto","/servicos","/v1/servico",
    "/plano/listar","/v1/plano/listar",
    "/v1/contrato?page=0&size=30",
]

def probe_catalogo(label, key):
    print("\n================ UNIDADE %s ================" % label, file=sys.stderr)
    achou=False
    for ep in CANDIDATOS:
        st,body=get(key,ep)
        j=as_json(body) if (isinstance(st,int) and 200<=st<300) else None
        itens=listify(j) if j is not None else None
        if itens is None:
            print("  [%s] %s -> (sem lista)" % (str(st).rjust(3), ep), file=sys.stderr)
            continue
        achou=True
        nomes=[]
        for it in itens:
            n=name_of(it)
            if n and n not in nomes: nomes.append(n)
        print("  [%s] %s -> %d item(ns)" % (str(st).rjust(3), ep, len(itens)), file=sys.stderr)
        for n in nomes[:40]:
            print("        - %-42s | %s" % (n[:42], classify_grupo(n)), file=sys.stderr)
        if len(nomes)>40:
            print("        ... (+%d)" % (len(nomes)-40), file=sys.stderr)
    if not achou:
        print("  (nenhum endpoint de catalogo respondeu com lista)", file=sys.stderr)

def main():
    for label,env in KEYS:      # 1 unidade basta pro catalogo
        k=os.environ.get(env)
        if not k: continue
        probe_catalogo(label,k)
        break
    else:
        print("sem chave", file=sys.stderr); sys.exit(1)
    print("\n>> Se algum endpoint listou modalidades/planos, temos o CATALOGO disponivel.", file=sys.stderr)

if __name__=="__main__": main()
