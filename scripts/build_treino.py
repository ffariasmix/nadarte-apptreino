#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_treino.py — MOTOR + GATE + INJEÇÃO

1. Lê data/treino_raw.json (saída do coletor)
2. GATE: valida volumes mínimos e consistência. Se falhar, NÃO publica (mantém o último bom).
3. Monta o objeto DATA no contrato que o dashboard consome
4. Injeta no template (template/index.html) e escreve public/index.html

Uso:
    python scripts/build_treino.py            # valida + gera public/
    python scripts/build_treino.py --check    # só valida (gate), não escreve public/
"""
import os, sys, json, datetime

RAW = "data/treino_raw.json"
TEMPLATE = "template/index.html"
OUT_DIR = "public"
MARKER = "/*__DATA__*/null"   # âncora no template (ver README, passo de wiring)

# Limiares do GATE (ajustáveis)
MIN_ATIVOS_REDE = 2000        # a rede tem ~4,5k ativos; abaixo disso algo quebrou
MIN_UNIDADES = 3

def gate(raw):
    problemas = []
    unis = raw.get("unidades", {})
    if len(unis) < MIN_UNIDADES:
        problemas.append(f"poucas unidades coletadas: {len(unis)}")
    tot_ativos = sum(u.get("ativos", 0) for u in unis.values())
    if tot_ativos < MIN_ATIVOS_REDE:
        problemas.append(f"ativos na rede abaixo do mínimo: {tot_ativos} < {MIN_ATIVOS_REDE}")
    for uk, u in unis.items():
        if u.get("ativos", 0) <= 0:
            problemas.append(f"unidade {uk} sem ativos")
    return problemas

def build_data(raw):
    """Contrato consumido pelo dashboard (window.DATA)."""
    unidades = []
    alunos = []
    for uk, u in raw.get("unidades", {}).items():
        unidades.append({"id": uk, "nome": u.get("label", uk), "ativos": u.get("ativos", 0)})
        for a in u.get("alunos", []):
            alunos.append(a)  # já pseudonimizado no coletor (sem PII)
    return {
        "gerado_em": datetime.datetime.utcnow().isoformat() + "Z",
        "janela": raw.get("janela", ""),
        "unidades": unidades,
        "alunos": alunos,
        # elegíveis (Fitness+Ambos) — o dashboard aplica o corte; aqui só sinalizamos
        "publico_elegivel": ["Fitness", "Ambos"],
    }

def main():
    check_only = "--check" in sys.argv
    if not os.path.exists(RAW):
        print(f"ERRO: {RAW} não existe (rode o coletor antes).", file=sys.stderr); sys.exit(2)
    raw = json.load(open(RAW, encoding="utf-8"))

    problemas = gate(raw)
    if problemas:
        print("GATE REPROVOU — publicação bloqueada (último dado bom mantido):", file=sys.stderr)
        for p in problemas:
            print("  -", p, file=sys.stderr)
        sys.exit(3)
    print("GATE OK.", file=sys.stderr)
    if check_only:
        return

    data = build_data(raw)
    tpl = open(TEMPLATE, encoding="utf-8").read()
    if MARKER not in tpl:
        print(f"ERRO: âncora {MARKER!r} não encontrada no template. "
              f"Ver README (passo de wiring do window.DATA).", file=sys.stderr)
        sys.exit(4)
    injected = tpl.replace(MARKER, json.dumps(data, ensure_ascii=False))
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(injected)
    print(f"OK -> {OUT_DIR}/index.html  ({len(data['alunos'])} alunos, "
          f"{len(data['unidades'])} unidades)", file=sys.stderr)

if __name__ == "__main__":
    main()
