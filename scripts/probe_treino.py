#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe v30 — BLOCO 02: de onde sai o campo `objecao` (motivo 'Sem Professor') e se esta populado.
  A) /v1/cliente/{cid}                -> objecao ja vem aqui? (seria DE GRACA, ja chamamos)
  B) /clientes/{matricula}/dados-pessoais -> objecao aqui?
Conta quantos populados numa amostra e mostra preview MASCARADO (sem PII)."""
import os, sys, json, urllib.request, urllib.error
BASE = "https://apigw.pactosolucoes.com.br"
KEYS = [("716NORTE","PACTO_KEY_716NORTE"),("905SUL","PACTO_KEY_905SUL"),
        ("604NORTE","PACTO_KEY_604NORTE"),("LAGONORTE","PACTO_KEY_LAGONORTE"),
        ("LAGOSUL","PACTO_KEY_LAGOSUL"),("NATAL","PACTO_KEY_NATAL")]
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
def find_key(obj, target, path=""):
    """Procura recursivamente uma chave (case-insensitive contendo target). Retorna [(caminho, valor)]."""
    out=[]
    if isinstance(obj, dict):
        for k,v in obj.items():
            p=path+"."+k
            if target in k.lower(): out.append((p, v))
            out+=find_key(v, target, p)
    elif isinstance(obj, list) and obj:
        out+=find_key(obj[0], target, path+"[0]")
    return out
def mask(v):
    if v is None: return "None"
    s=str(v).strip()
    if s=="": return "(vazio)"
    return "len=%d preview=%r" % (len(s), (s[:8]+"..."+s[-4:]) if len(s)>16 else s[:3]+"***")

def main():
    label=key=None
    for lb,env in KEYS:
        if os.environ.get(env): label,key=lb,os.environ[env]; break
    if not key: print("sem chave",file=sys.stderr); sys.exit(1)
    print("== UNIDADE %s ==" % label, file=sys.stderr)
    # amostra de ativos
    c=cont(get(key,"/clientes/simples?page=0&size=40&situacao=ATIVO")[1])
    lst=c if isinstance(c,list) else (c.get("lista") or c.get("content") or [] if isinstance(c,dict) else [])
    amostra=[(x.get("codigoCliente") or x.get("matricula"), x.get("matricula")) for x in lst[:20] if x]
    print("amostra: %d alunos" % len(amostra), file=sys.stderr)

    # A) /v1/cliente/{cid}
    a_hits=a_pop=0; a_paths=set(); a_ex=[]
    for cid,mat in amostra:
        d=cont(get(key,"/v1/cliente/%s"%cid)[1])
        hits=find_key(d,"objec") if isinstance(d,(dict,list)) else []
        if hits:
            a_hits+=1
            for p,v in hits:
                a_paths.add(p.split("[0]")[-1] if "[0]" in p else p)
                if v not in (None,"",0): a_pop+=1;
                if len(a_ex)<3 and v not in (None,""): a_ex.append((p,mask(v)))
    print("\n[A] /v1/cliente/{cid}: com chave objecao=%d/%d | populados=%d | caminhos=%s"
          % (a_hits, len(amostra), a_pop, sorted(a_paths)), file=sys.stderr)
    for p,m in a_ex: print("     ex %s -> %s" % (p, m), file=sys.stderr)

    # B) /clientes/{matricula}/dados-pessoais
    b_hits=b_pop=0; b_paths=set(); b_ex=[]
    for cid,mat in amostra[:10]:
        d=cont(get(key,"/clientes/%s/dados-pessoais"%mat)[1])
        hits=find_key(d,"objec") if isinstance(d,(dict,list)) else []
        if hits:
            b_hits+=1
            for p,v in hits:
                b_paths.add(p);
                if v not in (None,"",0): b_pop+=1
                if len(b_ex)<3 and v not in (None,""): b_ex.append((p,mask(v)))
    print("\n[B] /clientes/{mat}/dados-pessoais: com chave objecao=%d/10 | populados=%d | caminhos=%s"
          % (b_hits, b_pop, sorted(b_paths)), file=sys.stderr)
    for p,m in b_ex: print("     ex %s -> %s" % (p, m), file=sys.stderr)

    print("\n>> Se [A] tiver objecao, e DE GRACA (ja chamamos /v1/cliente). Senao usamos [B].", file=sys.stderr)
    print(">> 'populados' baixo e esperado agora (equipe ainda nao registrou) — importa a CHAVE existir.", file=sys.stderr)

if __name__=="__main__": main()
