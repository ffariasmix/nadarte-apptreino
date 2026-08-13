#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
crm_to_d1.py — grava o feed de CRM (App Treino) numa tabela D1 (apptreino_crm) do banco da Agenda.

Motivo: o runner do GitHub (edge US) NÃO consegue ler public/agenda_treino.json em
nadarte-apptreino.pages.dev (o edge devolve HTML "Deployment Not Found"). Então a Agenda Tática
passa a ler os candidatos de Coordenação/Treino do D1 (100% acessível do runner via wrangler),
e esta etapa mantém o D1 fresco a cada coleta. Sem PII no git (fica só no D1, como o resto da agenda).

Lê o arquivo LOCAL public/agenda_treino.json (gerado por build_treino.py no mesmo job) e emite SQL
para stdout. O workflow executa via `wrangler d1 execute nadarte_agenda --remote --file=...`.
Uso: python scripts/crm_to_d1.py [public/agenda_treino.json] > crm.sql
"""
import sys, json

SRC = sys.argv[1] if len(sys.argv) > 1 else "public/agenda_treino.json"


def esc(s):
    return str("" if s is None else s).replace("'", "''")


def b(v):
    return 1 if v else 0


def nn(v):
    try:
        if v is None or v == "":
            return "NULL"
        return int(v)
    except Exception:
        return "NULL"


def main():
    f = json.load(open(SRC, encoding="utf-8"))
    ger = f.get("gerado", "")
    crm = f.get("crm", []) or []
    print("CREATE TABLE IF NOT EXISTS apptreino_crm (unidade TEXT, matricula TEXT, nome TEXT, cat TEXT, foto TEXT, faixa TEXT, usa_app INTEGER, treino_vencido INTEGER, app_parado INTEGER, recencia_dias INTEGER, presenca_cai INTEGER, gerado TEXT, PRIMARY KEY(unidade,matricula));")
    print("DELETE FROM apptreino_crm;")
    rows = []
    for c in crm:
        rows.append("('%s','%s','%s','%s','%s','%s',%d,%d,%d,%s,%d,'%s')" % (
            esc(c.get("unidade")), esc(c.get("matricula")), esc(c.get("nome")), esc(c.get("cat")),
            esc(c.get("foto", "")), esc(c.get("faixa", "")),
            b(c.get("usaApp")), b(c.get("treinoVencido")), b(c.get("appParado")),
            nn(c.get("recenciaDias")), b(c.get("presencaCai")), esc(ger)))
    cols = "(unidade,matricula,nome,cat,foto,faixa,usa_app,treino_vencido,app_parado,recencia_dias,presenca_cai,gerado)"
    for i in range(0, len(rows), 50):
        print("INSERT INTO apptreino_crm %s VALUES %s;" % (cols, ",".join(rows[i:i + 50])))
    print("-- apptreino_crm: %d candidatos · feed %s" % (len(rows), ger), file=sys.stderr)


if __name__ == "__main__":
    main()
