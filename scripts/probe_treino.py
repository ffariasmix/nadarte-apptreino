#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe v19 — LIGAR aluno -> plano/modalidade.
Ja sabemos: catalogo em GET /modalidade e GET /planos; o NOME do plano carrega a
modalidade. Falta achar de qual campo sai o plano/modalidade DE CADA ALUNO.
Estrategia: para uma amostra de ATIVOS, busca /v1/cliente/{cid} e VARRE recursivamente
por campos cujo nome bate plano|modalidad|contrato|produto|servico, imprimindo
caminho->valor (texto de plano, nao PII) e a categoria de 6 baldes.
PII-safe: so imprime campos de plano/modalidade (nunca nome/cpf/nascimento)."""
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
def _tok(t):
    t=" "+_up(t)+" "
    if any(k in t for k in _AGUA): return "agua"
    if any(k in t for k in _FIT): return "fit"
    if any(k in t for k in _LUTAS): return "lutas"
    return "outros"

def categoria6(desc):
    """6 baldes pedidos + 'Luta' (so luta) + 'Outros' (nao mapeado)."""
    toks=[t for t in re.split(r"[;,+/]", str(desc or "")) if t.strip()]
    b=set(_tok(t) for t in toks)
    b.discard("outros")
    A,F,L = "agua" in b, "fit" in b, "lutas" in b
    if A and F and L: return "Ambos (Agua+Fitness+Luta)"
    if A and F:       return "Ambos (Agua+Fitness)"
    if A and L:       return "Ambos (Agua+Luta)"
    if F and L:       return "Ambos (Fitness+Luta)"
    if A:             return "Agua"
    if F:             return "Fitness"
    if L:             return "Luta"
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

RX = re.compile(r"plano|modalidad|contrato|produto|servico", re.I)
BLOCK = re.compile(r"cpf|nome|nasc|email|telefone|endereco|rg|pessoa", re.I)  # nunca imprimir

def find_fields(obj, path="", out=None, depth=0):
    if out is None: out=[]
    if depth>7: return out
    if isinstance(obj, dict):
        for k,v in obj.items():
            p=(path+"."+k) if path else k
            if isinstance(v,(str,int,float)) and RX.search(k) and not BLOCK.search(k) and str(v).strip():
                out.append((p, str(v)[:60]))
            find_fields(v, p, out, depth+1)
    elif isinstance(obj, list):
        for v in obj[:6]:
            find_fields(v, path+"[]", out, depth+1)
    return out

def sample_ativos(key, alvo=8):
    out=[]
    for pg in range(0,40):
        if len(out)>=alvo: break
        c=content(get(key,"/clientes/simples?"+urllib.parse.urlencode({"page":pg,"size":50}))[1])
        if not isinstance(c,list): continue
        for x in c:
            if _up(x.get("situacao"))=="ATIVO":
                out.append(x);
                if len(out)>=alvo: break
    return out

def main():
    label=key=None
    for lb,env in KEYS:
        if os.environ.get(env): label,key=lb,os.environ[env]; break
    if not key: print("sem chave",file=sys.stderr); sys.exit(1)
    print("== UNIDADE %s ==" % label, file=sys.stderr)
    alvos=sample_ativos(key,8)
    print("amostra ATIVO: %d" % len(alvos), file=sys.stderr)
    campos_freq={}   # quais paths carregam texto de plano
    for it in alvos:
        cid=it.get("codigoCliente") or it.get("matricula")
        cli=content(get(key,"/v1/cliente/%s"%urllib.parse.quote(str(cid)))[1])
        achados=find_fields(cli)
        # mostra so paths com valor "texto de plano" (>3 chars, tem letra)
        vistos=[(p,v) for p,v in achados if isinstance(v,str) and len(v.strip())>3 and re.search(r"[A-Za-z]",v)]
        for p,v in vistos:
            campos_freq[p]=campos_freq.get(p,0)+1
        if vistos:
            print("  cliente %s:" % cid, file=sys.stderr)
            for p,v in vistos[:8]:
                print("     %-38s = '%s'  -> %s" % (p[:38], v, categoria6(v)), file=sys.stderr)
        else:
            print("  cliente %s: (nenhum campo plano/modalidade com texto)" % cid, file=sys.stderr)
    print("\n== PATHS que carregaram texto de plano (freq na amostra) ==", file=sys.stderr)
    for p,n in sorted(campos_freq.items(), key=lambda x:-x[1]):
        print("   %-40s %d/%d" % (p, n, len(alvos)), file=sys.stderr)
    print("\n>> Se algum path aparece consistente, e a fonte da modalidade por aluno.", file=sys.stderr)

if __name__=="__main__": main()
