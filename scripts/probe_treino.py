#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe v16 — confirmar o JOIN aluno->professor de treino.
Compara os CODIGOS de colaborador em /v1/cliente/{id}.vinculos com os IDs dos
professores de treino (bi-professores-vinculos). Se houver overlap, o modelo
'faz treino = vinculado a professor de treino' funciona.
PII-safe: imprime SO codigos e contagens (nunca nomes)."""
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

def main():
    key=None
    for k in KEYS:
        if os.environ.get(k): key=os.environ[k]; break
    if not key: print("sem chave",file=sys.stderr); sys.exit(1)

    # 1) professores de treino (id) desta unidade
    profs = content(get(key,"/psec/colaboradores/bi-professores-vinculos")[1])
    prof_ids = set()
    if isinstance(profs, list):
        for p in profs:
            pid = (p.get("professor") or {}).get("id")
            if pid is not None: prof_ids.add(str(pid))
    print("== professores de treino: %d | ids(amostra): %s" % (
        len(prof_ids), sorted(prof_ids)[:15]), file=sys.stderr)

    # 2) amostra ROBUSTA de 12 alunos ATIVO (varre paginas; pagina 0 pode vir vazia)
    alvos=[]
    for pg in range(0, 30):
        if len(alvos) >= 12: break
        c=content(get(key,"/clientes/simples?"+urllib.parse.urlencode({"page":pg,"size":50}))[1])
        if not isinstance(c, list): continue
        for x in c:
            if up(x.get("situacao"))=="ativo":
                alvos.append(x)
                if len(alvos) >= 12: break
    print("== amostra coletada: %d alunos ATIVO" % len(alvos), file=sys.stderr)

    tipos = {}
    com_prof_treino = 0
    codes_vistos = set()
    for it in alvos:
        cid=it.get("codigoCliente")
        cli=content(get(key,"/v1/cliente/%s"%cid)[1])
        vinc = cli.get("vinculos") if isinstance(cli,dict) else None
        cods, tps = [], []
        if isinstance(vinc, list):
            for v in vinc:
                cod = str((v.get("colaborador") or {}).get("codigo"))
                tp  = v.get("tipoVinculo")
                cods.append(cod); tps.append(tp)
                codes_vistos.add(cod)
                tipos[tp] = tipos.get(tp, 0) + 1
        bate = [x for x in cods if x in prof_ids]
        if bate: com_prof_treino += 1
        print("  cliente=%s vinculos=%s tipos=%s -> bate treino? %s" % (
            cid, cods, tps, bool(bate)), file=sys.stderr)

    print("== RESUMO ==", file=sys.stderr)
    print("  tipos de vinculo vistos:", tipos, file=sys.stderr)
    print("  alunos (de %d) com vinculo a professor de treino: %d" % (len(alvos), com_prof_treino), file=sys.stderr)
    print("  overlap de codigos (colaborador ∩ professores treino): %d" % len(codes_vistos & prof_ids), file=sys.stderr)
    print("  >> se overlap>0 e 'bate treino' aparece True, o JOIN funciona.", file=sys.stderr)

if __name__=="__main__": main()
