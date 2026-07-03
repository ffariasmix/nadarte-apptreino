#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pacto_fetch_treino.py — COLETOR REAL (App Treino, agregados por unidade)

Para cada unidade (1 ApiKey), chama os endpoints de BI confirmados e monta
data/treino.json com os indicadores AGREGADOS por unidade. Sem varrer aluno.

Endpoints (empresaId=1, idProfessor=0 = total da unidade):
  /psec/treino-bi/dados?idProfessor=0        -> alunos, percUtilizamApp, percentualEmDia, treinos vencidos/em dia
  /psec/treino-bi/carteira                   -> acompanhamento/renovacao (KPI8)
  /psec/treino-bi/contagem-treinos-aprovar   -> treinos a aprovar
  /psec/avaliacao-fisica-bi?dataInicio&dataFim -> avaliacoes realizadas/atrasadas (KPI4/5)
(treinos executados removido: nao alimentado pelos alunos; nota do treino: endpoint 500 na Pacto)
"""
import os, sys, json, time, random, datetime, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

BASE = "https://apigw.pactosolucoes.com.br"
UNITS = [
    ("716Norte", "716 Norte", "PACTO_KEY_716NORTE"),
    ("905Sul",   "905 Sul",   "PACTO_KEY_905SUL"),
    ("604Norte", "604 Norte", "PACTO_KEY_604NORTE"),
    ("LagoNorte","Lago Norte","PACTO_KEY_LAGONORTE"),
    ("LagoSul",  "Lago Sul",  "PACTO_KEY_LAGOSUL"),
    ("Natal",    "Natal/RN",  "PACTO_KEY_NATAL"),
]

def http_get(key, path, tries=4, timeout=30):
    for i in range(tries):
        req = urllib.request.Request(BASE + path, headers={
            "Authorization": "Bearer " + key, "Accept": "application/json", "empresaId": "1"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and i < tries - 1:
                time.sleep(min(10, 0.8 * (2 ** i)) + random.random()); continue
            return e.code, ""
        except Exception:
            if i < tries - 1:
                time.sleep(1 + i); continue
            return -1, ""
    return -1, ""

def content(key, path):
    st, body = http_get(key, path)
    if st != 200:
        print("  [warn] %s -> %s" % (path, st), file=sys.stderr)
        return {}
    try:
        j = json.loads(body)
        c = j.get("content", j)
        return c if isinstance(c, (dict, list)) else {"valor": c}
    except Exception:
        return {}

def num(d, *keys):
    for k in keys:
        if isinstance(d, dict) and d.get(k) is not None:
            try:
                return float(d[k])
            except Exception:
                return d[k]
    return None

def coleta_unidade(uk, ulabel, key):
    print("[coleta] %s..." % ulabel, file=sys.stderr)
    now = datetime.datetime.utcnow()
    df = int(now.timestamp() * 1000)
    di = int((now - datetime.timedelta(days=365)).timestamp() * 1000)

    dados = content(key, "/psec/treino-bi/dados?idProfessor=0")  # 0 = TOTAL da unidade (1 = professor 1)
    cart  = content(key, "/psec/treino-bi/carteira")
    aprov = content(key, "/psec/treino-bi/contagem-treinos-aprovar")
    avf   = content(key, "/psec/avaliacao-fisica-bi?dataInicio=%d&dataFim=%d" % (di, df))

    # Professores 360: um chamado -> lista de professores com indicadores de treino
    profs = []
    raw = content(key, "/psec/colaboradores/bi-professores-vinculos")
    if isinstance(raw, list):
        for p in raw:
            pr = p.get("professor", {}) or {}
            bi = p.get("biTreinoTreinamentoDTO", {}) or {}
            tp = bi.get("tempoPermanenciaPrograma") or {}
            profs.append({
                "unit": uk, "unitNome": ulabel,
                "id": pr.get("id"), "nome": pr.get("nome"),
                "comTreino": num(bi, "alunosAtivosComTreino"),
                "semTreino": num(bi, "alunosAtivosSemTreino"),
                "emDia": num(bi, "alunosAtivosProgramaEmDia"),
                "vencidos": num(bi, "alunosProgramaVencidos"),
                "renovar": num(bi, "alunosProgramaRenovar"),
                "pctEmDia": num(bi, "porcentagemTreinosEmDia"),
                "renovar30": num(bi, "treinosRenovarEm30Dias"),
                "tempoMedio": num(tp, "medio") if isinstance(tp, dict) else None,
            })

    unidade = {
        "id": uk, "nome": ulabel,
        "totalAlunos": num(dados, "totalAlunos"),
        "totalAlunosAtivos": num(dados, "totalAlunosAtivos"),
        "totalAlunosComTreino": num(dados, "totalAlunosComTreino"),
        "totalAlunosSemTreino": num(dados, "totalAlunosSemTreino"),
        "percUtilizamApp": num(dados, "percUtilizamApp"),
        "percentualEmDia": num(dados, "percentualEmDia"),
        "totalTreinosVencidos": num(dados, "totalTreinosVencidos"),
        "totalTreinosEmDia": num(dados, "totalTreinosEmdia", "totalTreinosEmDia"),
        "totalTreinosRenovar": num(dados, "totalTreinosRenovar"),
        "tempoMedioPermanenciaTreino": num(dados, "tempoMedioPermanenciaTreino"),
        "agendamentos": num(dados, "agendamentos"),
        "compareceram": num(dados, "compareceram"),
        "acompanhamentoEm": num(cart, "totalAlunosEmAcompanhamento"),
        "acompanhamentoSem": num(cart, "totalAlunosSemAcompanhamento"),
        "taxaRenovacao": num(cart, "taxaRenovacaoZW", "taxaRenovacao"),
        "treinosAprovar": num(aprov, "valor") if isinstance(aprov, dict) else aprov,
        "avaliacoesRealizadas": num(avf, "realizadas"),
        "avaliacoesAtrasadas": num(avf, "atrasadas"),
        "avaliacoesReavaliacoes": num(avf, "reavaliacoes"),
        "avaliacoesPrevistas": num(avf, "previstas"),
        "avaliacoesSem": num(avf, "semAvaliacao"),
    }
    return {"unit": unidade, "profs": profs}

def main():
    resultados = {}
    def run(u):
        uk, ulabel, env = u
        key = os.environ.get(env)
        if not key:
            print("[skip] %s: sem %s" % (ulabel, env), file=sys.stderr); return
        try:
            resultados[uk] = coleta_unidade(uk, ulabel, key)
        except Exception as ex:
            print("[erro] %s: %s" % (ulabel, ex), file=sys.stderr)
    with ThreadPoolExecutor(max_workers=len(UNITS)) as ex:
        list(ex.map(run, UNITS))
    os.makedirs("data", exist_ok=True)
    unidades, professores = [], []
    for k in sorted(resultados):
        r = resultados[k]
        unidades.append(r["unit"])
        professores.extend(r.get("profs", []))
    out = {"gerado_em": datetime.datetime.utcnow().isoformat() + "Z",
           "unidades": unidades, "professores": professores}
    with open("data/treino.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("OK -> data/treino.json (%d unidades, %d professores)" % (len(unidades), len(professores)), file=sys.stderr)

if __name__ == "__main__":
    main()
