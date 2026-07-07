#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe v24 — NOTA do treino (estrelas) + EXECUCOES por periodo.
Endpoints (grupo BI Treino):
  GET /psec/treino-bi/avaliacao-treino/{tipoBusca}/{codigoPessoa}
      tipoBusca: 0=Todas, 1..5 = nº de estrelas ; le quantidadeTotalElementos p/ montar o histograma
  GET /psec/treino-bi/resumo-execucoes-periodo/{empresaId}
Confirma escopo (200 x 403), descobre o codigoPessoa certo (0=rede?) e a estrutura real.
PII-safe: imprime SO status, contagens, chaves de campo e a nota media derivada.
NUNCA imprime nomes nem o texto de comentarios (se existir campo comentario, so cita o nome dele)."""
import os, sys, json, urllib.request, urllib.error, urllib.parse
BASE = "https://apigw.pactosolucoes.com.br"
KEYS = [("716NORTE","PACTO_KEY_716NORTE"),("905SUL","PACTO_KEY_905SUL"),
        ("604NORTE","PACTO_KEY_604NORTE"),("LAGONORTE","PACTO_KEY_LAGONORTE"),
        ("LAGOSUL","PACTO_KEY_LAGOSUL"),("NATAL","PACTO_KEY_NATAL")]
PII_KEYS = ("nome","comentario","comment","obs","observacao","cpf","email","telefone","aluno","cliente")

def get(key, path, timeout=30):
    h={"Authorization":"Bearer "+key,"Accept":"application/json","empresaId":"1"}
    try:
        with urllib.request.urlopen(urllib.request.Request(BASE+path,headers=h),timeout=timeout) as r:
            return r.status, r.read().decode("utf-8","replace")
    except urllib.error.HTTPError as e: return e.code,(e.read().decode("utf-8","replace") if e.fp else "")
    except Exception as ex: return -1,str(ex)[:120]

def asj(body):
    try: return json.loads(body)
    except Exception: return None

def keys_safe(obj):
    """chaves de um item + indicacao [PII] nos campos sensiveis (sem valores)."""
    if isinstance(obj, list) and obj: obj=obj[0]
    if not isinstance(obj, dict): return type(obj).__name__
    out=[]
    for k in obj.keys():
        tag="[PII]" if any(p in k.lower() for p in PII_KEYS) else ""
        out.append(k+tag)
    return out

def dist_estrelas(key, cp):
    """Le quantidadeTotalElementos por tipoBusca (0..5). Devolve {tipo:(status,total)}."""
    d={}
    for tipo in range(0,6):
        st,body=get(key,"/psec/treino-bi/avaliacao-treino/%d/%s?page=1&size=1"%(tipo, urllib.parse.quote(str(cp))))
        j=asj(body)
        qt=j.get("quantidadeTotalElementos") if isinstance(j,dict) else None
        d[tipo]=(st,qt)
    return d, j  # j = ultimo json (tipo=5) so p/ debug

def main():
    label=key=None
    for lb,env in KEYS:
        if os.environ.get(env): label,key=lb,os.environ[env]; break
    if not key: print("sem chave",file=sys.stderr); sys.exit(1)
    print("== UNIDADE %s ==" % label, file=sys.stderr)

    # pega um codigoPessoa de professor (do bi-professores-vinculos)
    prof_cp=None
    pj=asj(get(key,"/psec/colaboradores/bi-professores-vinculos")[1])
    profs = pj if isinstance(pj,list) else (pj.get("content") if isinstance(pj,dict) else None)
    if isinstance(profs,list) and profs:
        prof_cp=(profs[0].get("professor") or {}).get("codigoPessoa")
    print("codigoPessoa de professor (amostra): %s" % prof_cp, file=sys.stderr)

    # ---- AVALIACAO-TREINO: histograma de estrelas p/ codigoPessoa candidatos ----
    for cp in [0, prof_cp]:
        if cp is None: continue
        print("\n[avaliacao-treino] codigoPessoa=%s" % cp, file=sys.stderr)
        d,_=dist_estrelas(key, cp)
        print("  status/qtd por tipoBusca: %s" % {t:d[t] for t in d}, file=sys.stderr)
        counts={t:(d[t][1] or 0) for t in range(1,6) if d[t][0]==200}
        tot=sum(counts.values())
        if tot>0:
            media=sum(t*counts.get(t,0) for t in range(1,6))/tot
            print("  DISTRIBUICAO estrelas (1..5): %s" % counts, file=sys.stderr)
            print("  >>> NOTA MEDIA: %.2f (de %d avaliacoes)" % (media, tot), file=sys.stderr)
        # estrutura do content (tipo=0=todas), PII-safe
        st,body=get(key,"/psec/treino-bi/avaliacao-treino/0/%s?page=1&size=2"%urllib.parse.quote(str(cp)))
        j=asj(body)
        if isinstance(j,dict) and isinstance(j.get("content"),list) and j["content"]:
            print("  chaves de uma avaliacao: %s" % keys_safe(j["content"]), file=sys.stderr)

    # ---- RESUMO-EXECUCOES-PERIODO (empresaId=1) ----
    print("\n[resumo-execucoes-periodo/1]", file=sys.stderr)
    st,body=get(key,"/psec/treino-bi/resumo-execucoes-periodo/1?page=0&size=3")
    j=asj(body)
    print("  status=%s" % st, file=sys.stderr)
    if isinstance(j,dict):
        print("  chaves topo: %s" % sorted(j.keys()), file=sys.stderr)
        print("  totalElements: %s" % j.get("totalElements"), file=sys.stderr)
        print("  chaves do content: %s" % keys_safe(j.get("content")), file=sys.stderr)

    # ---- GERADOS x EXECUTADOS (aderencia) ----
    print("\n[gerados-executados]", file=sys.stderr)
    st,body=get(key,"/psec/treino-bi/gerados-executados")
    j=asj(body)
    print("  status=%s | chaves: %s" % (st, keys_safe(j.get("content") if isinstance(j,dict) and "content" in j else j)), file=sys.stderr)

    print("\n>> status 200 => temos escopo; a NOTA MEDIA acima ja e o KPI7.", file=sys.stderr)

if __name__=="__main__": main()
