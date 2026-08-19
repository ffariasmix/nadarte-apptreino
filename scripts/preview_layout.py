#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
preview_layout.py — gera uma previa do painel com dados SINTETICOS, so para
conferir layout em varias larguras sem depender da coleta.

Por que existe: o build de verdade passa por um GATE que exige coleta real.
Quando a mudanca e so de layout, esperar uma coleta de horas para descobrir
que um numero ficou cortado e caro. Esta previa injeta um retrato plausivel
(6 unidades, professores com carteira, alunos com nome e e-mail longos) e
grava um HTML abrivel no navegador.

Os dados sao INVENTADOS. Nunca use esta saida para decidir nada de negocio,
e nunca publique este arquivo.

Uso: python3 scripts/preview_layout.py [saida.html]
"""
import json, random, sys, os, datetime

TEMPLATE = "template/index.html"
MARKER = "/*__DATA__*/null"
SAIDA = sys.argv[1] if len(sys.argv) > 1 else "preview-layout.html"

random.seed(42)  # previa reproduzivel: mesma rodada, mesmo desenho

UNIDADES = [
    ("604-norte", "604 Norte"), ("716-norte", "716 Norte"), ("905-sul", "905 Sul"),
    ("lago-norte", "Lago Norte"), ("lago-sul", "Lago Sul"), ("natal-rn", "Natal/RN"),
]
# nomes longos de proposito: nome curto esconde o bug de estouro
NOMES = [
    "Maria Fernanda Albuquerque Cavalcanti", "Rodrigo Rocha Mendonça",
    "Bibiana Ribeiro Portella Nunes", "Carmencita Romana Weiprecht",
    "João Pedro", "Ana", "Gustavo Marcos Valadão Sobrinho",
    "Isadora Lordello Marar", "Rubens Foizer Filho", "Adaise Cristina do Nascimento",
]
MODALIDADES = ["Fitness", "Ambos · Água+Fitness", "Ambos · Fitness+Luta",
               "Ambos · Água+Fitness+Luta", "Água", "Luta", "Outros"]
FAIXAS = ["engajado", "morno", "risco", "semdado"]


def aluno(i, uid, unome, prof):
    dias = random.choice([-15, -1, 3, 12, 45, 200, None])
    return {
        "unit": uid, "unitNome": unome,
        "matricula": str(10000 + i),
        "nome": random.choice(NOMES),
        "email": f"nome.sobrenome.comprido{i}@umprovedordeemaillongo.com.br",
        "telefone": "(61) 99999-0000",
        "professor": prof,
        "professorId": prof and f"p-{uid}-{abs(hash(prof)) % 5}",
        "modalidade": random.choice(MODALIDADES),
        "usaApp": random.choice([True, False, None]),
        "fazTreino": random.choice([True, False]),
        "treinoStatus": random.choice(["emdia", "vencido", None]),
        "recenciaDias": random.choice([2, 9, 20, 40, 90, None]),
        "presencaDias": random.choice([1, 10, 35, None]),
        "diasContrato": dias,
        "faixa": random.choice(FAIXAS),
        "situacao": "ATIVO",
        "foto": None,
    }


def main():
    if not os.path.exists(TEMPLATE):
        sys.exit(f"template nao encontrado: {TEMPLATE} (rode a partir da raiz do repo)")

    unidades, professores, alunos = [], [], []
    n = 0
    for uid, unome in UNIDADES:
        unidades.append({
            "id": uid, "nome": unome,
            "totalAlunos": random.randint(600, 1200),
            "totalAlunosAtivos": random.randint(400, 900),
            "percUtilizamApp": round(random.uniform(14, 67), 1),
            "percentualEmDia": round(random.uniform(38, 89), 1),
            "totalTreinosEmDia": random.randint(80, 400),
            "totalTreinosVencidos": random.randint(10, 200),
            "totalTreinosRenovar": random.randint(5, 60),
            "avaliacoesRealizadas": random.randint(20, 300),
            "avaliacoesAtrasadas": random.randint(0, 90),
            "acompanhamentoEm": random.randint(10, 200),
            "tempoMedioPermanenciaTreino": random.randint(45, 120),
            "notaMedia": round(random.uniform(4.2, 5.0), 2),
            "notaTotal": random.randint(50, 900),
        })
        for k in range(5):
            pnome = random.choice(NOMES)
            pid = f"p-{uid}-{k}"
            professores.append({
                "id": pid, "nome": pnome, "unit": uid,
                "carteiraReal": random.randint(8, 90),
                "comTreino": random.randint(5, 80),
                "emDia": random.randint(2, 60), "vencidos": random.randint(0, 40),
                "pctEmDia": round(random.uniform(20, 98), 1),
                "notaMedia": round(random.uniform(4.0, 5.0), 2),
                "notaTotal": random.randint(0, 400),
                "indice": random.randint(20, 99),
            })
            for _ in range(random.randint(6, 14)):
                alunos.append(aluno(n, uid, unome, pnome)); n += 1
        # alguns alunos sem professor, para exercitar o "—"
        for _ in range(4):
            alunos.append(aluno(n, uid, unome, None)); n += 1

    data = {
        "gerado_em": datetime.datetime.utcnow().isoformat() + "Z",
        "PREVIA_SINTETICA": True,
        "unidades": unidades, "professores": professores, "alunos": alunos,
    }

    html = open(TEMPLATE, encoding="utf-8").read()
    if MARKER not in html:
        sys.exit(f"marcador {MARKER} nao encontrado no template")
    html = html.replace(MARKER, json.dumps(data, ensure_ascii=False), 1)
    aviso = ('<div style="background:#7A1F1F;color:#fff;padding:10px 16px;font:600 13px '
             'system-ui;text-align:center">PRÉVIA DE LAYOUT · DADOS INVENTADOS · '
             'não use para decidir nada</div>')
    html = html.replace("<body>", "<body>" + aviso, 1)

    open(SAIDA, "w", encoding="utf-8").write(html)
    print(f"previa gravada em {SAIDA}")
    print(f"  {len(unidades)} unidades · {len(professores)} professores · {len(alunos)} alunos")
    print("  abra no navegador e estreite a janela ate 360px")


if __name__ == "__main__":
    main()
