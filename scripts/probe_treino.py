#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe v28 — diagnostico do CRUZAMENTO treino-em-dia por aluno.
Descobre por que treinoStatus veio null p/ todos: mapa vazio? ou mismatch de formato de matricula?
  1) alunos-treino-em-dia/0 (varias paginas) -> quantas matriculas? formato (tipo/zero a esquerda)?
  2) carteira -> formato da matricula do aluno.
  3) interseccao bruta vs interseccao normalizada (int).
PII-safe: mascara o miolo das matriculas."""
import os, sys, json, urllib.request, urllib.error
BASE = "https://apigw.pactosolucoes.com.br"
KEYS = [("716NORTE","PACTO_KEY_716NORTE"),("905SUL","PACTO_KEY_905SUL"),
        ("604NORTE","PACTO_KEY_604NORTE"),("LAGONORTE","PACTO_KEY_LAGONORTE"),
        ("LAGOSUL","PACTO_KEY_LAGOSUL"),("NATAL","PACTO_KEY_NATAL")]
def get(key, path, timeout=40):
    h={"Authorization":"Bearer "+key,"Accept":"application/json","empresaId":"1"}
    try:
        with urllib.request.urlopen(urllib.request.Request(BASE+path,headers=h),timeout=timeout) as r:
            return r.status, r.read().decode("utf-8","replace")
    except urllib.error.HTTPError as e: return e.code,(e.read().decode("utf-8","replace") if e.fp else "")
    except Exception as ex: return -1,str(ex)[:120]
def cont(b):
    try: j=json.loads(b); return j.get("content", j)
    except: return None
def mask(m):
    s=str(m);
    return s if len(s)<=4 else s[:2]+("*"*(len(s)-4))+s[-2:]
def fmt(m):
    s=str(m)
    return "tipo=%s len=%d zero_esq=%s ex=%s" % (type(m).__name__, len(s), s[:1]=="0", mask(m))

def fetch_all(key, ep):
    got=[]; seen=-1
    for page in range(1,21):
        lst=cont(get(key,"/psec/treino-bi/%s/0?page=%d&size=1000"%(ep,page))[1])
        items=lst if isinstance(lst,list) else (lst.get("content") if isinstance(lst,dict) else None)
        if not items: break
        got+=items
        if len(items)<1000 or len(got)==seen: break
        seen=len(got)
    return got

def main():
    label=key=None
    for lb,env in KEYS:
        if os.environ.get(env): label,key=lb,os.environ[env]; break
    if not key: print("sem chave",file=sys.stderr); sys.exit(1)
    print("== UNIDADE %s ==" % label, file=sys.stderr)

    emdia=fetch_all(key,"alunos-treino-em-dia")
    venc =fetch_all(key,"alunos-treino-vencido")
    print("\n[listas] em dia=%d | vencido=%d" % (len(emdia), len(venc)), file=sys.stderr)
    if emdia:
        m0=emdia[0].get("matricula")
        print("  matricula da lista treino: %s" % fmt(m0), file=sys.stderr)
        print("  chaves item: %s" % list(emdia[0].keys()), file=sys.stderr)

    # carteira (mesma fonte que o coletor usa p/ os alunos)
    cart=cont(get(key,"/psec/treino-bi/carteira?page=1&size=5")[1])
    citems=cart if isinstance(cart,list) else (cart.get("content") if isinstance(cart,dict) else None)
    if isinstance(citems,list) and citems:
        cm=citems[0].get("matricula")
        print("\n[carteira] matricula do aluno: %s" % fmt(cm), file=sys.stderr)
        print("  chaves item: %s" % list(citems[0].keys())[:12], file=sys.stderr)

    # interseccao bruta (str) vs normalizada (int)
    set_treino_raw=set(str(x.get("matricula")) for x in (emdia+venc) if x.get("matricula") is not None)
    def norm(m):
        try: return str(int(str(m)))
        except: return str(m)
    set_treino_norm=set(norm(x.get("matricula")) for x in (emdia+venc) if x.get("matricula") is not None)
    cart_all=cont(get(key,"/psec/treino-bi/carteira")[1])
    caitems=cart_all if isinstance(cart_all,list) else (cart_all.get("content") if isinstance(cart_all,dict) else None)
    cmats=[x.get("matricula") for x in (caitems or []) if x.get("matricula") is not None]
    raw_hit=sum(1 for m in cmats if str(m) in set_treino_raw)
    norm_hit=sum(1 for m in cmats if norm(m) in set_treino_norm)
    print("\n[cruzamento] carteira=%d | match BRUTO(str)=%d | match NORMALIZADO(int)=%d"
          % (len(cmats), raw_hit, norm_hit), file=sys.stderr)
    print(">> Se NORMALIZADO >> BRUTO, o bug e zero-a-esquerda: normalizar matricula resolve.", file=sys.stderr)
    print(">> Se ambos ~0 com listas>0, a matricula da lista != matricula da carteira (outra chave).", file=sys.stderr)

if __name__=="__main__": main()
