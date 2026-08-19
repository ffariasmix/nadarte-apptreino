#!/usr/bin/env node
/**
 * ux_mobile_lint.mjs — porteiro de responsividade dos painéis Nad'Arte.
 *
 * Por que existe: painéis do BI foram ao ar com número cortado na borda do card,
 * tabela de 10 colunas sumindo no celular e barra de filtros comendo um terço da
 * tela. Os testes de dados passavam; ninguém olhava o layout. Este script olha.
 *
 * Funciona no ARQUIVO-FONTE (template .html), inclusive na marcação que mora
 * dentro de template literals de JavaScript — que é como os painéis montam as
 * tabelas. Por isso é análise de texto, não de DOM: no arquivo estático o DOM
 * ainda não existe.
 *
 * Uso:
 *   node scripts/ux_mobile_lint.mjs template/index.html [outro.html ...]
 *   node scripts/ux_mobile_lint.mjs --json template/index.html
 *
 * Saída: relatório PASS/FAIL por regra. Código de saída 1 se houver ERRO.
 *
 * Orçamento de largura assumido (o pior caso real do parque de celulares):
 *   viewport 360px − .wrap(20px×2) − .panel/.tbl(18px×2) = 284px úteis.
 */

import { readFileSync } from "node:fs";
import { basename } from "node:path";

const VIEWPORT = 360;
const CHROME = 20 * 2 + 18 * 2; // padding do .wrap + padding do card
const BUDGET = VIEWPORT - CHROME; // 284px
const MAX_COLS_SEM_CARD = 4; // acima disso, tabela precisa virar card no celular

const ERRO = "ERRO";
const AVISO = "AVISO";

// ---------------------------------------------------------------- utilidades

const linhaDe = (txt, idx) => txt.slice(0, idx).split("\n").length;
const trecho = (s, n = 100) => s.replace(/\s+/g, " ").trim().slice(0, n);

/** Remove blocos @media para que as checagens vejam só o layout base (mobile-first reverso). */
function foraDeMediaQuery(css) {
  let out = "";
  let i = 0;
  while (i < css.length) {
    const m = css.indexOf("@media", i);
    if (m === -1) {
      out += css.slice(i);
      break;
    }
    out += css.slice(i, m);
    // pula o bloco balanceado
    let j = css.indexOf("{", m);
    if (j === -1) break;
    let d = 0;
    for (; j < css.length; j++) {
      if (css[j] === "{") d++;
      else if (css[j] === "}") {
        d--;
        if (d === 0) {
          j++;
          break;
        }
      }
    }
    i = j;
  }
  return out;
}

/** Acha o `<table ...>` … `</table>` a partir de um índice, tolerando marcação em string JS. */
function fatiaTabela(txt, ini) {
  const fim = txt.indexOf("</table>", ini);
  return txt.slice(ini, fim === -1 ? Math.min(ini + 6000, txt.length) : fim);
}

// ------------------------------------------------------------------- regras

const REGRAS = [];
const regra = (id, titulo, fn) => REGRAS.push({ id, titulo, fn });

regra("viewport", "meta viewport declarada", (txt) => {
  const m = txt.match(/<meta[^>]+name=["']viewport["'][^>]*>/i);
  if (!m) return [{ nivel: ERRO, linha: 1, msg: "sem <meta name=viewport> — o celular renderiza como desktop e encolhe tudo" }];
  if (!/width\s*=\s*device-width/i.test(m[0]))
    return [{ nivel: ERRO, linha: linhaDe(txt, m.index), msg: "viewport sem width=device-width: " + trecho(m[0]) }];
  return [];
});

regra("guarda-overflow", "trava de rolagem lateral no <body>", (txt, css) => {
  // overflow-x:clip trava o vazamento SEM quebrar position:sticky (hidden quebra).
  if (/body[^{]*\{[^}]*overflow-x\s*:\s*(clip|hidden)/i.test(css)) {
    if (/body[^{]*\{[^}]*overflow-x\s*:\s*hidden/i.test(css) && !/overflow-x\s*:\s*clip/i.test(css))
      return [{ nivel: AVISO, linha: 0, msg: "usa overflow-x:hidden no body — quebra position:sticky. Prefira clip (com hidden antes, como fallback)" }];
    return [];
  }
  return [{ nivel: AVISO, linha: 0, msg: "sem trava de overflow-x no body: qualquer elemento que estoure gera rolagem lateral na página inteira" }];
});

/**
 * Largura mínima confortável de uma célula, pelo que ela carrega dentro.
 * Contar colunas não basta: 4 colunas com avatar + e-mail + 3 etiquetas já
 * estouram, e 10 colunas de número inteiro também. O que decide é a soma.
 */
function larguraDaCelula(td) {
  if (/aluno-cell|\bav\b|avatar\(/.test(td)) return 200; // avatar + nome + e-mail
  if (/class="[^"]*\bbar\b|<svg|stack/.test(td)) return 110; // barra/gráfico embutido
  if (/\bpill\b|c-red|c-green|c-amber|Pill\(/.test(td)) return 90; // etiqueta colorida
  if (/white-space:\s*nowrap/.test(td)) return 90;
  return 62; // número ou texto curto
}

regra("tabela-estoura-no-celular", `tabela cabe em ${BUDGET}px ou vira card`, (txt) => {
  const achados = [];
  const re = /<table[\s>]/g;
  let m;
  while ((m = re.exec(txt))) {
    const corpo = fatiaTabela(txt, m.index);

    // As colunas quase sempre nascem de um .map() dentro de template literal,
    // então o cabeçalho tem 1 <th> literal e a LINHA tem os <td> de verdade.
    const tbody = corpo.slice(corpo.indexOf("<tbody"));
    const primeiraLinha = tbody.slice(tbody.indexOf("<tr"), tbody.indexOf("</tr>") + 5);
    const tds = [...primeiraLinha.matchAll(/<td[^>]*>[\s\S]*?(?=<td|<\/tr>|$)/g)].map((x) => x[0]);
    const ths = (corpo.slice(0, corpo.indexOf("<tbody")).match(/<th[\s>]/g) || []).length;
    const cols = Math.max(tds.length, ths);
    if (cols < 2) continue;

    const larguraMin = tds.length ? tds.reduce((s, td) => s + larguraDaCelula(td), 0) : cols * 62;
    const antes = txt.slice(Math.max(0, m.index - 600), m.index);
    const temRtable = /class=(["'`])[^"'`]*\brtable\b[^"'`]*\1/.test(antes);
    const emModal = /pmodalc|modalc|Drawer|drawer/.test(txt.slice(Math.max(0, m.index - 2500), m.index));

    if (temRtable) continue;

    if (larguraMin > BUDGET)
      achados.push({
        nivel: ERRO,
        linha: linhaDe(txt, m.index),
        msg: `${cols} colunas ≈ ${larguraMin}px mínimos em ${BUDGET}px úteis${emModal ? " (dentro de modal, ainda mais estreito)" : ""} — falta "rtable" no contêiner; as colunas da direita saem da tela`,
      });
    else if (cols > MAX_COLS_SEM_CARD)
      achados.push({
        nivel: AVISO,
        linha: linhaDe(txt, m.index),
        msg: `${cols} colunas sem "rtable" — cabe hoje (${larguraMin}px), mas qualquer conteúdo mais longo estoura`,
      });
  }
  return achados;
});

regra("card-sem-rotulo", "toda célula do modo card tem data-label", (txt) => {
  const achados = [];
  const re = /class=(["'`])[^"'`]*\brtable\b[^"'`]*\1/g;
  let m;
  while ((m = re.exec(txt))) {
    const t = txt.indexOf("<table", m.index);
    if (t === -1 || t - m.index > 600) continue;
    const corpo = fatiaTabela(txt, t);
    const tbody = corpo.slice(corpo.indexOf("<tbody"));
    const tds = tbody.match(/<td[^>]*>/g) || [];
    // a 1ª célula de cada linha é o "título" do card e dispensa rótulo
    const semRotulo = tds.filter((td, i) => i > 0 && !/data-label=/.test(td) && !/colspan=/.test(td));
    if (semRotulo.length)
      achados.push({
        nivel: ERRO,
        linha: linhaDe(txt, t),
        msg: `${semRotulo.length} célula(s) sem data-label — no modo card o valor aparece solto, sem dizer do que é: ${trecho(semRotulo[0], 60)}`,
      });
  }
  return achados;
});

regra("largura-fixa-estoura", `linha flex com larguras fixas somando mais que ${BUDGET}px`, (txt) => {
  const achados = [];
  // pega blocos que abrem uma linha flex inline e olha as larguras fixas dos filhos
  const re = /style="[^"]*display:\s*flex[^"]*"/g;
  let m;
  while ((m = re.exec(txt))) {
    if (/flex-wrap:\s*wrap/.test(m[0])) continue; // quebra linha, não estoura
    const bloco = txt.slice(m.index, m.index + 900);
    const mins = [...bloco.matchAll(/min-width:\s*(\d+)px/g)].map((x) => +x[1]);
    if (mins.length < 2) continue;
    const gap = +(bloco.match(/gap:\s*(\d+)px/)?.[1] || 0);
    const soma = mins.reduce((a, b) => a + b, 0) + gap * (mins.length - 1);
    if (soma > BUDGET)
      achados.push({
        nivel: ERRO,
        linha: linhaDe(txt, m.index),
        msg: `soma de min-width = ${soma}px em ${BUDGET}px úteis (${mins.join("+")} + gaps) — a coluna da direita é cortada`,
      });
  }
  return achados;
});

/** A regra foi aliviada em alguma @media de celular? (evita apontar largura de desktop). */
function aliviadaNoCelular(css, seletorParcial) {
  const alvo = seletorParcial.trim().split(/\s+/).pop(); // ex.: ".ct" de ".aluno-cell .contacts .ct"
  const re = new RegExp(`@media[^{]*max-width:\\s*[3-6]\\d\\dpx[\\s\\S]{0,4000}?\\${alvo}[^{;]*\\{[^}]*max-width:\\s*(100%|none)`, "");
  return re.test(css);
}

regra("largura-fixa-texto", "contêiner de texto sem largura fixa em px", (txt, css) => {
  const base = foraDeMediaQuery(css);
  const achados = [];
  for (const m of base.matchAll(/([.#][\w-]+(?:\s+[.\w-]+)*)\s*\{[^}]*max-width:\s*(\d+)px[^}]*\}/g)) {
    const px = +m[2];
    const sel = m[1].trim();
    if (px >= 200 && px <= 400 && /nm|cell|contact|texto|nome/i.test(sel) && !aliviadaNoCelular(css, sel))
      achados.push({ nivel: AVISO, linha: 0, msg: `${sel} tem max-width:${px}px fixo e não é liberado em @media de celular — corta o texto em vez de acompanhar o card` });
  }
  return achados;
});

regra("sticky-come-tela", "barra fixa não pode ocupar o alto da tela no celular", (txt, css) => {
  const achados = [];
  for (const m of css.matchAll(/([.#][\w-]+)\s*\{[^}]*position:\s*sticky[^}]*\}/g)) {
    const sel = m[1];
    // aliviada em media query de celular? procura o seletor dentro de @media max-width
    const aliviada = new RegExp(
      `@media[^{]*max-width:\\s*(?:4\\d\\d|5\\d\\d|6\\d\\d)px[^{]*\\{(?:[^{}]|\\{[^{}]*\\})*\\${sel}\\s*\\{[^}]*position:\\s*(static|relative)`,
      "s"
    ).test(css);
    if (!aliviada)
      achados.push({
        nivel: AVISO,
        linha: 0,
        msg: `${sel} é sticky e não é liberada em nenhuma @media de celular — se o conteúdo quebrar em várias linhas ela come a tela e "some" com os dados`,
      });
  }
  return achados;
});

regra("alvo-de-toque", "botão/chip com área de toque de no mínimo 32px", (txt, css) => {
  const base = foraDeMediaQuery(css);
  const achados = [];
  for (const m of base.matchAll(/([.#][\w-]+)\s*\{([^}]*)\}/g)) {
    const [, sel, corpo] = m;
    if (!/(chip|btn|tab|pill)/i.test(sel)) continue;
    if (/cursor:\s*pointer/.test(corpo) === false) continue;
    const pad = corpo.match(/padding:\s*(\d+(?:\.\d+)?)px/);
    const fs = corpo.match(/font-size:\s*(\d+(?:\.\d+)?)px/);
    if (!pad || !fs) continue;
    const altura = +pad[1] * 2 + +fs[1] * 1.45;
    if (altura < 32) achados.push({ nivel: AVISO, linha: 0, msg: `${sel} tem ~${altura.toFixed(0)}px de altura — abaixo dos 32px confortáveis para o dedo` });
  }
  return achados;
});

// -------------------------------------------------------------------- motor

function auditar(arquivo) {
  const txt = readFileSync(arquivo, "utf8");
  const css = [...txt.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)].map((m) => m[1]).join("\n");
  return REGRAS.map((r) => ({ ...r, achados: r.fn(txt, css) }));
}

const args = process.argv.slice(2);
const json = args.includes("--json");
const arquivos = args.filter((a) => !a.startsWith("--"));

if (!arquivos.length) {
  console.error("uso: node scripts/ux_mobile_lint.mjs [--json] arquivo.html ...");
  process.exit(2);
}

let erros = 0;
let avisos = 0;
const relatorio = [];

for (const arq of arquivos) {
  const res = auditar(arq);
  relatorio.push({ arquivo: arq, regras: res });
  if (json) continue;
  console.log(`\n═══ ${basename(arq)}  (orçamento mobile: ${BUDGET}px úteis em viewport de ${VIEWPORT}px)`);
  for (const r of res) {
    const e = r.achados.filter((a) => a.nivel === ERRO).length;
    const a = r.achados.filter((x) => x.nivel === AVISO).length;
    erros += e;
    avisos += a;
    const marca = e ? "FAIL" : a ? "AVISO" : "PASS";
    console.log(`  [${marca}] ${r.id} — ${r.titulo}`);
    for (const ac of r.achados) console.log(`         ${ac.nivel} ${ac.linha ? "linha " + ac.linha : ""} · ${ac.msg}`);
  }
}

if (json) {
  console.log(JSON.stringify(relatorio, null, 2));
  const todos = relatorio.flatMap((r) => r.regras.flatMap((x) => x.achados));
  process.exit(todos.some((a) => a.nivel === ERRO) ? 1 : 0);
}

console.log(`\n──────── ${erros} erro(s), ${avisos} aviso(s)`);
process.exit(erros ? 1 : 0);
