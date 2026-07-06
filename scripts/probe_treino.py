#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe v22 — achar o campo de FOTO (aluno e professor) e se vem preenchido.
Aluno: procura foto em /v1/cliente (JA chamamos por aluno -> de graca) e no
       /clientes/{matricula}/dados-pessoais (urlFoto).
Professor: inspeciona /psec/colaboradores/bi-professores-vinculos.
PII-safe: NAO imprime a URL completa (so scheme://host + extensao + tamanho),
nem nome/cpf. Foto e' dado pessoal -> so confirmamos que o campo existe/preenche."""
import os, sys, json, re, unicodedata, urllib.request, urllib.error, urllib.parse
BASE = "https://apigw.pactosolucoes.com.br"
KEYS = [("716NORTE","PACTO_KEY_716NORTE"),("905SUL","PACTO_KEY_905SUL"),
        ("604NORTE","PACTO_KEY_604NORTE"),("LAGONORTE","PACTO_KEY_LAGONORTE"),
        ("LAGOSUL","PACTO_KEY_LAGOSUL"),("NATAL","PACTO_KEY_NATAL")]

def _up(s): return "".join(c for c in unicodedata.normalize("NFD",str(s or "")) if unicodedata.category(c)!="Mn").upper()

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

FOTO_RX = re.compile(r"foto|imagem|avatar|urlfoto|fotokey|photo|picture|image", re.I)

def safe_url(v):
    """resumo PII-safe de uma URL/base64: scheme://host + extensao + tamanho."""
    v=str(v)
    if v.startswith("data:"): return "data-uri(base64) len=%d" % len(v)
    try:
        p=urllib.parse.urlparse(v)
        ext=""
        m=re.search(r"\.(jpg|jpeg|png|webp|gif)(\?|$)", v, re.I)
        if m: ext=" ."+m.group(1).lower()
        if p.scheme and p.netloc: return "%s://%s%s len=%d" % (p.scheme,p.netloc,ext,len(v))
    except Exception: pass
    return "(nao-url) len=%d '%s...'" % (len(v), v[:12])

def find_foto(obj, path="", out=None, depth=0):
    if out is None: out=[]
    if depth>8: return out
    if isinstance(obj,dict):
        for k,v in obj.items():
            p=(path+"."+k) if path else k
            if isinstance(v,str) and FOTO_RX.search(k):
                out.append((p, bool(v.strip()), safe_url(v) if v.strip() else "(vazio)"))
            find_foto(v,p,out,depth+1)
    elif isinstance(obj,list):
        for v in obj[:5]: find_foto(v,path+"[]",out,depth+1)
    return out

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

    # ---- PROFESSOR: bi-professores-vinculos ----
    print("\n[PROFESSOR] /psec/colaboradores/bi-professores-vinculos", file=sys.stderr)
    profs=content(get(key,"/psec/colaboradores/bi-professores-vinculos")[1])
    if isinstance(profs,list) and profs:
        print("  chaves item[0]: %s" % sorted(profs[0].keys()), file=sys.stderr)
        pp=profs[0].get("professor")
        if isinstance(pp,dict): print("  chaves professor: %s" % sorted(pp.keys()), file=sys.stderr)
        n_ok=0; ex=[]
        for it in profs[:20]:
            hits=find_foto(it)
            preench=[h for h in hits if h[1]]
            if preench: n_ok+=1
            for p,ok,resumo in hits:
                if (p,resumo) not in [(a,b) for a,b,_ in ex]:
                    ex.append((p,resumo,ok))
        print("  campos de foto encontrados:", file=sys.stderr)
        seen=set()
        for p,resumo,ok in ex:
            if p in seen: continue
            seen.add(p)
            print("     %-26s preenchido=%s  %s" % (p, ok, resumo), file=sys.stderr)
        print("  professores (dos 20) com foto preenchida: %d" % n_ok, file=sys.stderr)
    else:
        print("  (sem lista de professores)", file=sys.stderr)

    # ---- ALUNO: /v1/cliente (de graca) + dados-pessoais.urlFoto ----
    alvos=sample_ativos(key,6)
    print("\n[ALUNO] amostra ATIVO: %d" % len(alvos), file=sys.stderr)
    cli_ok=dp_ok=0; campos_cli={}
    for it in alvos:
        cid=it.get("codigoCliente") or it.get("matricula")
        mat=it.get("matricula") or cid
        cli=content(get(key,"/v1/cliente/%s"%urllib.parse.quote(str(cid)))[1])
        for p,ok,resumo in (find_foto(cli) if isinstance(cli,dict) else []):
            campos_cli[p]=campos_cli.get(p,[0,""]);
            if ok: campos_cli[p][0]+=1; campos_cli[p][1]=resumo
            if ok: cli_ok+=1
        dp=content(get(key,"/clientes/%s/dados-pessoais"%urllib.parse.quote(str(mat)))[1])
        uf = dp.get("urlFoto") if isinstance(dp,dict) else None
        if str(uf or "").strip(): dp_ok+=1
    print("  /v1/cliente -> campos de foto vistos:", file=sys.stderr)
    for p,(n,resumo) in sorted(campos_cli.items(), key=lambda x:-x[1][0]):
        print("     %-28s preenchido em %d/%d  %s" % (p, n, len(alvos), resumo), file=sys.stderr)
    if not campos_cli: print("     (nenhum campo de foto no /v1/cliente)", file=sys.stderr)
    print("  /clientes/{matricula}/dados-pessoais.urlFoto preenchido: %d/%d" % (dp_ok,len(alvos)), file=sys.stderr)
    print("\n>> Onde 'preenchido' > 0, ali esta a foto pronta pra exibir.", file=sys.stderr)

if __name__=="__main__": main()
