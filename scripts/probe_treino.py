#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
probe_treino.py — EXPLORADOR de endpoints do App Treino na API PACTO (ZillyonWeb)

Objetivo: descobrir QUAIS endereços da API entregam os dados que faltam
(ficha, execução de treino, avaliação física, nota/feedback, atendimento).
Roda no GitHub Actions, onde as chaves ficam nos Secrets — você não manuseia credencial.

SEGURANÇA (regras da base de conhecimento):
- NUNCA imprime PII (nome, CPF): só STATUS, CHAVES do JSON e CONTAGENS.
- Usa as chaves via variáveis de ambiente (Secrets), nunca hardcoded.

Como rodar: via workflow (.github/workflows/probe.yml) OU localmente:
    PACTO_KEY_716NORTE=xxxx python scripts/probe_treino.py
"""
import os, sys, json, time, random, urllib.request, urllib.error

BASE = "https://apigw.pactosolucoes.com.br"

# 1 chave por unidade (Secrets do GitHub). Basta 1 para o probe.
UNITS = [
    ("716Norte", "PACTO_KEY_716NORTE"),
    ("905Sul",   "PACTO_KEY_905SUL"),
    ("604Norte", "PACTO_KEY_604NORTE"),
    ("LagoNorte","PACTO_KEY_LAGONORTE"),
    ("LagoSul",  "PACTO_KEY_LAGOSUL"),
]

# Caminhos CANDIDATOS a testar (chutes iniciais — confirme pela resposta, não pela doc).
# Marque aqui novos caminhos conforme forem aparecendo na documentação.
CANDIDATOS = [
    # já confirmado (serve de sanity-check de autenticação):
    "/psec/alunos/alunoApp",
    # ficha / prescrição de treino:
    "/treino", "/treinos", "/ficha", "/fichas", "/prescricao", "/programa",
    "/v1/treino", "/v1/ficha", "/v1/fichas", "/psec/treino", "/psec/ficha",
    "/psec/alunos/ficha", "/psec/alunos/treino", "/aluno/treino", "/aluno/ficha",
    # execução de treino (treino realizado):
    "/execucao-treino", "/treino/execucao", "/ficha/execucao", "/psec/execucao-treino",
    # avaliação física:
    "/avaliacao", "/avaliacoes", "/avaliacao-fisica", "/v1/avaliacao",
    "/psec/avaliacao", "/psec/alunos/avaliacao",
    # nota / feedback do treino:
    "/feedback", "/avaliacao-treino", "/treino/nota", "/nota-treino",
    # atendimento / chat professor->aluno:
    "/atendimento", "/interacao", "/chat", "/mensagens", "/psec/atendimento",
    # engajamento / gamificação:
    "/engajamento", "/gamificacao",
]

def http_get(key, path, tries=4, timeout=25):
    """GET com Bearer + backoff. Retorna (status, body_str)."""
    url = BASE + path
    for i in range(tries):
        req = urllib.request.Request(url, headers={
            "Authorization": "Bearer " + key,
            "Accept": "application/json",
        })
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and i < tries - 1:
                time.sleep(min(12, 0.8 * (2 ** i)) + random.random())
                continue
            return e.code, (e.read().decode("utf-8", "replace") if e.fp else "")
        except Exception as ex:
            if i < tries - 1:
                time.sleep(1 + i)
                continue
            return -1, str(ex)
    return -1, "sem resposta"

def shape(body):
    """Descreve a resposta SEM vazar PII: só tipo, chaves e contagens."""
    try:
        j = json.loads(body)
    except Exception:
        return "(não-JSON, %d chars)" % len(body)
    def desc(x, depth=0):
        if isinstance(x, dict):
            ks = list(x.keys())
            inner = ""
            if "content" in x and depth == 0:
                inner = " content->" + desc(x["content"], depth + 1)
            return "obj{%s}%s" % (", ".join(ks[:12]), inner)
        if isinstance(x, list):
            return "lista[%d]%s" % (len(x), (" item0=" + desc(x[0], depth + 1)) if x else "")
        return type(x).__name__
    return desc(j)

def main():
    # usa a primeira chave disponível nos Secrets
    key = None; unit = None
    for u, env in UNITS:
        v = os.environ.get(env)
        if v:
            key, unit = v, u
            break
    if not key:
        print("ERRO: nenhuma PACTO_KEY_* encontrada no ambiente (Secrets).", file=sys.stderr)
        sys.exit(1)

    print("== PROBE App Treino — unidade de teste:", unit, "==", file=sys.stderr)
    print(f"{'STATUS':>6}  {'PATH':<34}  FORMATO", file=sys.stderr)
    achados = []
    for path in CANDIDATOS:
        st, body = http_get(key, path)
        fmt = shape(body) if st == 200 else ("" if st in (404, 401, 403) else shape(body))
        print(f"{st:>6}  {path:<34}  {fmt}", file=sys.stderr)
        if st == 200:
            achados.append({"path": path, "shape": fmt})
        time.sleep(0.5)  # gentil com o rate-limit

    print("\n== ENDPOINTS QUE RESPONDERAM 200 ==", file=sys.stderr)
    print(json.dumps(achados, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
