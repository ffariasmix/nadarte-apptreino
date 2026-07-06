#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe v20 — onde esta a MODALIDADE por aluno? (busca por VALOR + estrutura)
Busca em /v1/cliente e /v1/contrato por QUALQUER string que contenha uma palavra
de modalidade (NATACAO/KARATE/MUAY/FITNESS/TL/HIDRO...), imprimindo caminho->valor
+ a categoria de 7 baldes. Tambem despeja as CHAVES de topo pra mapear a estrutura.
PII-safe: so imprime valores que casam modalidade (nome de pessoa nao casa); pula
chaves cpf/email/telefone/nascimento."""
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
KW = _AGUA + _LUTAS + _FIT
def _tok(t):
    t=" "+_up(t)+" "
    if any(k in t for k in _AGUA): return "agua"
    if any(k in t for k in _FIT): return "fit"
    if any(k in t for k in _LUTAS): return "lutas"
    return "outros"
def categoria7(desc):
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

BLOCK = re.compile(r"cpf|email|telefone|celular|nasc|endereco|\brg\b|cep", re.I)
def scan_values(obj, path="", out=None, depth=0):
    if out is None: out=[]
    if depth>9: return out
    if isinstance(obj,str):
        u=" "+_up(obj)+" "
        if 3<len(obj)<80 and any(k in u for k in KW):
            out.append((path, obj[:60]))
    elif isinstance(obj,dict):
        for k,v in obj.items():
            if BLOCK.search(k): continue
            scan_values(v,(path+"."+k) if path else k,out,depth+1)
    elif isinstance(obj,list):
        for v in obj[:10]:
            scan_values(v,path+"[]",out,depth+1)
    return out

def keys_of(o):
    return sorted(o.keys()) if isinstance(o,dict) else ("(lista %d)"%len(o) if isinstance(o,list) else type(o).__name__)

def sample_ativos(key, alvo=6):
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

    # A) /v1/contrato (catalogo/lista) — estrutura + valores de modalidade
    st,body=get(key,"/v1/contrato?page=0&size=5")
    c=content(body)
    print("\n[/v1/contrato] status=%s" % st, file=sys.stderr)
    itens=c if isinstance(c,list) else (c.get("content") if isinstance(c,dict) else None)
    if isinstance(itens,list) and itens:
        print("  item[0] chaves: %s" % keys_of(itens[0]), file=sys.stderr)
        hits=scan_values(itens[0])
        for p,v in hits[:10]: print("   modalidade? %-30s = '%s' -> %s" % (p[:30],v,categoria7(v)), file=sys.stderr)
    else:
        print("  (sem lista de contratos)", file=sys.stderr)

    # B) /v1/cliente por aluno — estrutura + busca por valor de modalidade
    alvos=sample_ativos(key,6)
    print("\n[/v1/cliente] amostra ATIVO: %d" % len(alvos), file=sys.stderr)
    for it in alvos:
        cid=it.get("codigoCliente") or it.get("matricula")
        cli=content(get(key,"/v1/cliente/%s"%urllib.parse.quote(str(cid)))[1])
        if not isinstance(cli,dict):
            print("  cliente %s: (sem dict)"%cid, file=sys.stderr); continue
        print("  cliente %s | chaves topo: %s" % (cid, keys_of(cli)), file=sys.stderr)
        cs=cli.get("clienteSintetico")
        if isinstance(cs,dict): print("     clienteSintetico chaves: %s" % keys_of(cs), file=sys.stderr)
        hits=scan_values(cli)
        if hits:
            for p,v in hits[:8]: print("     >> %-34s = '%s' -> %s" % (p[:34],v,categoria7(v)), file=sys.stderr)
        else:
            print("     (nenhum valor com modalidade)", file=sys.stderr)
    print("\n>> Onde aparecer 'modalidade? ...' ou '>> ...', ali esta o texto do plano por aluno.", file=sys.stderr)

if __name__=="__main__": main()
