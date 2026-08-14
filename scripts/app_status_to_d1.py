#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app_status_to_d1.py — grava o status de app por aluno (usaApp/treinoVencido) numa tabela D1
(apptreino_app_status) do banco da Agenda, para o Prontuario 360 (build_resumo) ler sem depender
do pages.dev (que o runner do GitHub nao consegue ler).

Le o arquivo LOCAL public/app_status.json (gerado por build_treino.py no mesmo job) e emite SQL
para stdout. O workflow executa via `wrangler d1 execute nadarte_agenda --remote --file=...`.
Uso: python scripts/app_status_to_d1.py [public/app_status.json] > app_status.sql
"""
import sys, json

SRC = sys.argv[1] if len(sys.argv) > 1 else "public/app_status.json"


def esc(s):
    return str("" if s is None else s).replace("'", "''")


def b(v):
    return 1 if v else 0


def main():
    f = json.load(open(SRC, encoding="utf-8"))
    ger = f.get("gerado", "")
    alunos = f.get("alunos", []) or []
    print("CREATE TABLE IF NOT EXISTS apptreino_app_status (unidade TEXT, matricula TEXT, usa_app INTEGER, treino_vencido INTEGER, gerado TEXT, PRIMARY KEY(unidade,matricula));")
    print("DELETE FROM apptreino_app_status;")
    rows = []
    for a in alunos:
        rows.append("('%s','%s',%d,%d,'%s')" % (
            esc(a.get("unidade")), esc(a.get("matricula")),
            b(a.get("usaApp")), b(a.get("treinoVencido")), esc(ger)))
    cols = "(unidade,matricula,usa_app,treino_vencido,gerado)"
    for i in range(0, len(rows), 100):
        print("INSERT INTO apptreino_app_status %s VALUES %s;" % (cols, ",".join(rows[i:i + 100])))
    print("-- apptreino_app_status: %d alunos - feed %s" % (len(rows), ger), file=sys.stderr)


if __name__ == "__main__":
    main()
