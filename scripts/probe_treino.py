#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe v17 — a MODALIDADE (Fitness/Ambos/Agua/Lutas) esta disponivel na API?
Testa as duas fontes que a base de conhecimento do dashboard de Frequencia aponta:
  1) campo `categoria` em /clientes/simples (ja sabemos que veio vazio — reconfirma)
  2) campo `descricao` em /clientes/{matricula}/dados-pessoais  (o que falta cravar)
Aplica o MESMO classify_grupo do dashboard de Frequencia e reporta a distribuicao.
PII-safe: imprime SO contagens, o TEXTO DE MODALIDADE (plano, nao e dado pessoal)
e a categoria resultante. NUNCA imprime cpf, nome, nascimento."""
import os, sys, json, unicodedata, urllib.request, urllib.error, urllib.parse
BASE = "https://apigw.pactosolucoes.com.br"
KEYS = [("716NORTE","PACTO_KEY_716NORTE"),("905SUL","PACTO_KEY_905SUL"),
        ("604NORTE","PACTO_KEY_604NORTE"),("LAGONORTE","PACTO_KEY_LAGONORTE"),
        ("LAGOSUL","PACTO_KEY_LAGOSUL"),("NATAL","PACTO_KEY_NATAL")]

# ---- classify_grupo (identico ao coletor / dashboard de Frequencia) ----
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

def content(body):
    try: j=json.loads(body); return j.get("content", j)
    except Exception: return None

def sample_ativos(key, alvo=12):
    """Amostra robusta de ATIVOS (varre paginas; pagina 0 pode vir vazia)."""
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

def probe_unidade(label, key):
    print("\n================ UNIDADE %s ================" % label, file=sys.stderr)
    alvos=sample_ativos(key, 12)
    print("amostra ATIVO: %d" % len(alvos), file=sys.stderr)
    cat_simples_ok=0
    desc_ok=0; desc_dist={}; exemplos=[]
    keys_vistos=set()   # nomes de campo do dados-pessoais (sem valores)
    for it in alvos:
        mat=it.get("matricula") or it.get("codigoCliente")
        if str(it.get("categoria") or "").strip(): cat_simples_ok+=1
        st,body=get(key,"/clientes/%s/dados-pessoais"%urllib.parse.quote(str(mat)))
        dp=content(body)
        if isinstance(dp,dict):
            for k in dp.keys(): keys_vistos.add(k)
            desc=dp.get("descricao")
            if str(desc or "").strip():
                desc_ok+=1
                cat=classify_grupo(desc)
                desc_dist[cat]=desc_dist.get(cat,0)+1
                if len(exemplos)<8: exemplos.append((str(desc)[:60], cat))  # modalidade = plano, nao PII
        else:
            print("  dados-pessoais status=%s (sem content dict)" % st, file=sys.stderr)
    print("campos vistos em dados-pessoais: %s" % sorted(keys_vistos), file=sys.stderr)
    print("categoria (em /clientes/simples) preenchida: %d/%d" % (cat_simples_ok,len(alvos)), file=sys.stderr)
    print("descricao (em dados-pessoais) preenchida:    %d/%d" % (desc_ok,len(alvos)), file=sys.stderr)
    if exemplos:
        print("exemplos (modalidade -> categoria):", file=sys.stderr)
        for d,c in exemplos: print("   '%s' -> %s" % (d,c), file=sys.stderr)
    if desc_dist:
        print("distribuicao de categoria na amostra: %s" % desc_dist, file=sys.stderr)

def main():
    feitas=0
    for label,env in KEYS:      # roda em ate 2 unidades pra ser rapido
        k=os.environ.get(env)
        if not k: continue
        probe_unidade(label,k)
        feitas+=1
        if feitas>=2: break
    if not feitas:
        print("sem chave", file=sys.stderr); sys.exit(1)
    print("\n>> CONCLUSAO: se 'descricao preenchida' > 0, dá pra classificar Fitness/Ambos/Agua/Lutas.", file=sys.stderr)

if __name__=="__main__": main()
