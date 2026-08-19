#!/usr/bin/env node
/**
 * porteiro_responsivo.mjs — o gate de responsividade dos painéis Nad'Arte.
 * ============================================================================
 * VERSÃO: 2026.08.19-1
 *
 * ARQUIVO ÚNICO E AUTOCONTIDO, DE PROPÓSITO.
 * Ele é copiado igual dentro de cada repositório de painel. A alternativa era
 * cada workflow buscá-lo num repositório central, mas o GITHUB_TOKEN só enxerga
 * o próprio repositório — entre repositórios privados isso exige um token que
 * expira e derruba os sete gates de uma vez, sem motivo óbvio.
 *
 * O preço dessa escolha é haver cópias. Para elas não divergirem em silêncio:
 *   - o arquivo carrega uma VERSÃO no alto;
 *   - quem mexer no porteiro recopia nos sete NA MESMA LEVA;
 *   - o gate imprime a versão em toda execução, então dá para comparar entre
 *     painéis olhando o log.
 *
 * POR QUE ELE EXISTE
 * Em agosto/2026 o linter estático deu 0 erro em três painéis quebrados no
 * celular. Ele acerta no que já conhecemos; não tinha como ver um limite em
 * JavaScript, um tooltip que só aparece no hover, nem uma aba que passou da
 * borda. Quem achou os três foi MEDIR no navegador. Por isso aqui vêm as duas
 * camadas juntas, e a medição é a que manda.
 *
 * USO
 *   node scripts/porteiro_responsivo.mjs <arquivo.html>
 *   node scripts/porteiro_responsivo.mjs --so-linter <arquivo.html>   (sem navegador)
 *   node scripts/porteiro_responsivo.mjs --capturas ./capturas <arquivo.html>
 *
 * A medição precisa de playwright:  npm i --no-save playwright
 *                                   npx playwright install --with-deps chromium
 * Sem playwright instalado ele roda só o linter e AVISA que não mediu — nunca
 * finge que passou.
 *
 * Sai com código 1 se reprovar, para travar o deploy.
 */

import { readFileSync, existsSync, mkdirSync } from "node:fs";
import { resolve, basename } from "node:path";

export const VERSAO = "2026.08.19-1";

// ============================================================================
// PARTE 1 — LINTER ESTÁTICO (rápido; pega o que já conhecemos)
// ============================================================================

const CHROME = 20 * 2 + 18 * 2; // padding do .wrap + padding do card

/**
 * Os três tamanhos que a rede da Nad'Arte usa de verdade. Auditar só o celular
 * deixa passar o pior caso do parque: o iPad em retrato, onde a tabela de 842px
 * também não cabe mas nenhuma @media de 640px socorre.
 */
const TELAS = [
  { nome: "celular", viewport: 360, classe: "rtable" },
  { nome: "tablet retrato", viewport: 768, classe: "rtable-lg" },
  { nome: "tablet paisagem", viewport: 1024, classe: "rtable-lg" },
];
TELAS.forEach((t) => (t.budget = t.viewport - CHROME)); // 284 · 692 · 948

const BUDGET = TELAS[0].budget; // orçamento do celular, usado nas regras de largura fixa
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

regra("guarda-overflow", "trava de rolagem lateral em <html> E <body>", (txt, css) => {
  // A trava precisa estar NOS DOIS. Só no body não adianta: o <html> continua
  // rolando e a página anda para o lado do mesmo jeito. Isso passou despercebido
  // no Painel Digital, onde um tooltip empurrava a página 41px com o body já
  // "protegido". Regra descoberta na marra, medindo no navegador.
  // Lookbehind em vez de "começo de linha": a regra pode vir logo depois de um
  // comentário (*/), e aí não há vírgula nem chave antes dela.
  const temTrava = (sel) =>
    new RegExp(`(?<![\\w.#-])${sel}\\b[^{}]*\\{[^}]*overflow-x\\s*:\\s*(clip|hidden)`, "i").test(css);

  const achados = [];
  if (!temTrava("body"))
    achados.push({ nivel: AVISO, linha: 0, msg: "sem trava de overflow-x no <body>" });
  if (!temTrava("html"))
    achados.push({
      nivel: AVISO,
      linha: 0,
      msg: "sem trava de overflow-x no <html> — só no body NÃO impede a rolagem lateral; use `html, body { overflow-x:hidden; overflow-x:clip }`",
    });
  if (/overflow-x\s*:\s*hidden/i.test(css) && !/overflow-x\s*:\s*clip/i.test(css))
    achados.push({ nivel: AVISO, linha: 0, msg: "usa só overflow-x:hidden — quebra position:sticky nos filhos. Ponha clip depois, como par" });
  return achados;
});

regra("balao-de-largura-fixa", "tooltip e balão de ajuda não estouram a tela", (txt, css) => {
  const base = foraDeMediaQuery(css);
  const achados = [];
  // Elemento posicionado com largura fixa em px é a causa mais comum de
  // vazamento invisível: só aparece no hover, então ninguém vê testando — mas
  // empurra a página o tempo todo.
  for (const m of base.matchAll(/([^{}]+)\{([^}]*position:\s*absolute[^}]*)\}/g)) {
    const [, sel, corpo] = m;
    const w = corpo.match(/(?<!max-)width:\s*(\d+)px/);
    if (!w || +w[1] < 150) continue;
    if (/max-width/.test(corpo)) continue;
    // O max-width pode estar numa regra separada, mais adiante no arquivo.
    // Sem isto o linter acusa algo que já está resolvido — e aviso falso ensina
    // a ignorar aviso.
    const ultimaParte = sel.trim().split(/[\s>+~,]/).filter(Boolean).pop();
    if (ultimaParte && new RegExp(`${ultimaParte.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}[^{}]*\\{[^}]*max-width`, "i").test(css)) continue;
    achados.push({
      nivel: AVISO,
      linha: 0,
      msg: `${sel.trim().slice(0, 44)} é absoluto com width:${w[1]}px e sem max-width — perto da borda ele empurra a página. Acrescente max-width:calc(100vw - 32px)`,
    });
  }
  return achados;
});

regra("barra-de-abas-sem-rolagem", "barra de abas/filtros rola em vez de esconder botão", (txt, css) => {
  const achados = [];
  // O pior defeito que apareceu nesta auditoria: no Conversas, a aba
  // "Aquisição & Campanhas" ficava fora da tela. Antes da trava de overflow dava
  // para rolar até ela; DEPOIS da trava ela virou um botão que simplesmente não
  // existe para quem está no celular. A trava transformou um incômodo em perda
  // de função — por isso toda tira horizontal de botões precisa de rolagem
  // própria, ou de quebra de linha.
  for (const m of css.matchAll(/([^{}]+)\{([^}]*display:\s*flex[^}]*)\}/g)) {
    const [, sel, corpo] = m;
    const nome = sel.trim().split(/[\s,]/).filter(Boolean).pop();
    if (!nome || !/^[.#]?[\w-]+$/.test(nome)) continue;
    if (!/tabs?\b|filtro|filters?\b|chips?\b|toggle|segment/i.test(nome)) continue;
    if (/flex-wrap:\s*wrap/.test(corpo)) continue;          // quebra linha: ok
    if (/overflow-x:\s*(auto|scroll)/.test(corpo)) continue; // rola: ok
    // Só interessa o CONTÊINER, não o botão solto. Um botão também é flex (para
    // alinhar ícone e texto) e acusá-lo é ruído — e aviso falso ensina a ignorar
    // aviso. O sinal de contêiner é ter regra de filho/descendente no CSS.
    const esc = nome.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const ehContainer = new RegExp(`${esc}\\s*(>|\\s)\\s*[.\\w\\[]`).test(css);
    if (!ehContainer) continue;
    achados.push({
      nivel: AVISO,
      linha: 0,
      msg: `${nome} é uma tira horizontal sem flex-wrap nem overflow-x — o último botão pode ficar fora da tela e, com a trava de overflow, inalcançável. Dê overflow-x:auto (com \`> * { flex:0 0 auto }\`) ou flex-wrap:wrap`,
    });
  }
  return achados;
});

regra("grade-de-muitas-colunas", "grade com 10+ colunas cabe ou rola dentro do card", (txt, css) => {
  const achados = [];
  // Mapa de calor de 24 horas, calendário, matriz. Com a trava de overflow no
  // html, uma grade dessas não empurra mais a página — ela simplesmente some
  // pela borda. Dado invisível é PIOR que dado rolável: ninguém procura o que
  // não sabe que existe. Foi o que aconteceu no Painel Digital, onde as horas
  // 16 a 23 do mapa de calor ficaram fora da tela.
  for (const m of css.matchAll(/([^{}]+)\{([^}]*grid-template-columns:[^;}]*repeat\((\d+)\s*,[^)]*\)[^;}]*)/g)) {
    const [, sel, corpo, n] = m;
    if (+n < 10) continue;
    // O casamento pode pegar o cabeçalho de uma @media em vez do seletor, porque
    // o corpo permite chaves. Nesse caso o "nome" viria como "640px)" e quebraria
    // a expressão montada abaixo. Descarta.
    if (/@|\(/.test(sel)) continue;
    const nome = sel.trim().split(/[\s,]/).filter(Boolean).pop();
    if (!nome || !/^[.#]?[\w-]+$/.test(nome)) continue;
    // Aceita se as colunas encolhem de verdade (minmax(0,...)) ou se o próprio
    // seletor ganha rolagem contida em alguma @media de celular.
    if (/minmax\(\s*0/.test(corpo)) continue;
    // `1fr` encolhe sozinho — a não ser que algum filho tenha tamanho mínimo
    // (aspect-ratio, min-width, min-height). Foi isso que travou o mapa de calor
    // do Digital. Sem essa checagem a regra acusa grade que cabe tranquila.
    const escN = nome.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const filhoTravado = new RegExp(`${escN}\\s[^{}]*\\{[^}]*(aspect-ratio|min-width:\\s*\\d|min-height:\\s*\\d)`, "i").test(css);
    if (/repeat\(\d+\s*,\s*1fr\)/.test(corpo) && !filhoTravado) continue;
    const rolaNoCelular = new RegExp(
      `@media[^{]*max-width:\\s*[3-6]\\d\\dpx[\\s\\S]{0,900}?${nome.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}[^{}]*\\{[^}]*overflow-x\\s*:\\s*(auto|scroll)`,
      "i",
    ).test(css);
    if (rolaNoCelular) continue;
    achados.push({
      nivel: AVISO,
      linha: 0,
      msg: `${nome} é uma grade de ${n} colunas sem encolher nem rolar — no celular as últimas colunas somem pela borda. Use minmax(0,1fr) ou dê overflow-x:auto ao próprio contêiner numa @media de celular`,
    });
  }
  return achados;
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

regra("tabela-estoura", `tabela cabe em celular (${TELAS[0].budget}px), tablet retrato (${TELAS[1].budget}px) e paisagem (${TELAS[2].budget}px)`, (txt) => {
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
    const temRtableLg = /class=(["'`])[^"'`]*\brtable-lg\b[^"'`]*\1/.test(antes);
    const emModal = /pmodalc|modalc|Drawer|drawer/.test(txt.slice(Math.max(0, m.index - 2500), m.index));

    // Em qual tela ela ainda não cabe, considerando a proteção que já tem?
    const quebra = TELAS.filter((t) => {
      if (larguraMin <= t.budget) return false;
      if (t.classe === "rtable" && temRtable) return false;
      if (t.classe === "rtable-lg" && temRtableLg) return false;
      return true;
    });

    if (quebra.length) {
      const precisa = quebra.some((t) => t.classe === "rtable-lg") ? "rtable-lg" : "rtable";
      achados.push({
        nivel: ERRO,
        linha: linhaDe(txt, m.index),
        msg: `${cols} colunas ≈ ${larguraMin}px mínimos — estoura em ${quebra.map((t) => t.nome).join(", ")}${emModal ? " (dentro de modal, ainda mais estreito)" : ""}. Falta a classe "${precisa}" no contêiner`,
      });
    } else if (cols > MAX_COLS_SEM_CARD && !temRtable && !temRtableLg) {
      achados.push({
        nivel: AVISO,
        linha: linhaDe(txt, m.index),
        msg: `${cols} colunas sem modo card — cabe hoje (${larguraMin}px), mas qualquer conteúdo mais longo estoura`,
      });
    }
  }
  return achados;
});

regra("card-sem-rotulo", "toda célula do modo card tem data-label", (txt) => {
  const achados = [];
  const re = /class=(["'`])[^"'`]*\brtable(-lg)?\b[^"'`]*\1/g;
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


// ============================================================================
// PARTE 2 — MEDIÇÃO NO NAVEGADOR (é esta que pega o que o linter não vê)
// ============================================================================

function medirNaPagina(largura) {
  const CLICAVEL = 'button, a[href], [role="button"], [role="tab"], input, select, summary';
  const DADO = "th, td, .cell, .kpi .v, .metric, [data-label]";

  // Está dentro de algo que rola de propósito? Então não é defeito.
  const dentroDeRolagemDeliberada = (el) => {
    let p = el.parentElement;
    for (let i = 0; i < 6 && p; i++, p = p.parentElement) {
      const ox = getComputedStyle(p).overflowX;
      if (ox === "auto" || ox === "scroll") return true;
    }
    return false;
  };

  const invisivel = (el) => {
    const s = getComputedStyle(el);
    return s.display === "none" || s.visibility === "hidden" || +s.opacity === 0;
  };

  const descreve = (el) => {
    const r = el.getBoundingClientRect();
    const cls = typeof el.className === "string" && el.className ? "." + el.className.trim().split(/\s+/)[0] : "";
    return {
      seletor: el.tagName + (el.id ? "#" + el.id : "") + cls,
      texto: (el.textContent || "").replace(/\s+/g, " ").trim().slice(0, 44),
      esquerda: Math.round(r.left),
      direita: Math.round(r.right),
      largura: Math.round(r.width),
    };
  };

  const forasDe = (seletores) =>
    [...document.querySelectorAll(seletores)]
      .filter((el) => {
        const r = el.getBoundingClientRect();
        if (r.width === 0 || r.height === 0) return false;
        if (invisivel(el)) return false;
        // O skip-link fica escondido fora da tela de propósito, é padrão de acessibilidade.
        if (/skip-link/.test(el.className || "")) return false;
        if (dentroDeRolagemDeliberada(el)) return false;
        return r.right > largura + 2 || r.left < -2;
      })
      .map(descreve);

  return {
    scrollWidth: document.documentElement.scrollWidth,
    rolaPagina: document.documentElement.scrollWidth > largura + 1,
    clicaveisFora: forasDe(CLICAVEL),
    dadosFora: forasDe(DADO),
  };
}


/** Páginas de mentira com veredito conhecido. Testam o testador. */
const CASOS = [
  { nome: "página que cabe", esperado: "aprova",
    html: `<!doctype html><meta name=viewport content="width=device-width,initial-scale=1"><style>html,body{margin:0;overflow-x:hidden;overflow-x:clip;font:14px system-ui}.c{padding:12px}button{display:block;width:100%;margin:6px 0;padding:10px}</style><div class=c><button>Um</button><button>Dois</button><table><tr><td>Alpha</td></tr></table></div>` },
  { nome: "aba fora da tela (defeito real do Conversas)", esperado: "reprova",
    html: `<!doctype html><meta name=viewport content="width=device-width,initial-scale=1"><style>html,body{margin:0;overflow-x:hidden;overflow-x:clip;font:14px system-ui}.tabs{display:flex;gap:6px;white-space:nowrap}.tabs button{flex:0 0 auto;padding:10px 14px}</style><div class=tabs><button>Visao geral</button><button>Atendimento</button><button>Aquisicao e Campanhas</button></div>` },
  { nome: "rola dentro do card de propósito (mapa de calor do Digital)", esperado: "aprova",
    html: `<!doctype html><meta name=viewport content="width=device-width,initial-scale=1"><style>html,body{margin:0;overflow-x:hidden;overflow-x:clip}.heat{display:grid;grid-template-columns:repeat(24,15px);gap:2px;overflow-x:auto}.heat i{display:block;height:15px;background:#ccc}</style><div class=heat>${"<i></i>".repeat(24)}</div>` },
  { nome: "página inteira anda para o lado", esperado: "reprova",
    html: `<!doctype html><meta name=viewport content="width=device-width,initial-scale=1"><style>html,body{margin:0;font:14px system-ui}.larga{width:900px;height:40px;background:#eee}</style><div class=larga>bloco mais largo que a tela</div>` },
];

const reprovou = (r) => r.rolaPagina || r.clicaveisFora.length > 0 || r.dadosFora.length > 0;

/** Gate quebrado ou solta tudo ou trava tudo, e nenhum dos dois é visível. */
async function conferirOMedidor(navegador) {
  let falhas = 0;
  for (const c of CASOS) {
    const ctx = await navegador.newContext({ viewport: { width: 390, height: 700 } });
    const pag = await ctx.newPage();
    await pag.setContent(c.html, { waitUntil: "load" });
    await pag.waitForTimeout(200);
    const r = await pag.evaluate(medirNaPagina, 390);
    const veredito = reprovou(r) ? "reprova" : "aprova";
    const ok = veredito === c.esperado;
    if (!ok) falhas++;
    console.log(`  ${ok ? "PASS" : "FALHOU"} autoteste: ${c.nome} -> ${veredito}`);
    await ctx.close();
  }
  return falhas;
}

// ============================================================================
// MOTOR
// ============================================================================

const args = process.argv.slice(2);
const opt = (f, p) => { const i = args.indexOf(f); return i === -1 ? p : args[i + 1]; };
const SO_LINTER = args.includes("--so-linter");
const CAPTURAS = opt("--capturas", null);
const LARGURAS = opt("--larguras", "390,768,1024").split(",").map(Number);
const ALVOS = args.filter((a, i) => !a.startsWith("--") && !["--capturas", "--larguras"].includes(args[i - 1]));

if (!ALVOS.length) {
  console.error("uso: node scripts/porteiro_responsivo.mjs [--so-linter] [--capturas PASTA] <arquivo.html>");
  process.exit(2);
}
if (CAPTURAS && !existsSync(CAPTURAS)) mkdirSync(CAPTURAS, { recursive: true });

console.log(`porteiro de responsividade · versão ${VERSAO}`);
let houveErro = false;

// ---- camada 1: linter ------------------------------------------------------
for (const arq of ALVOS) {
  const txt = readFileSync(arq, "utf8");
  const css = [...txt.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)].map((m) => m[1]).join("\n");
  console.log(`\n═══ linter · ${basename(arq)}`);
  for (const r of REGRAS) {
    const achados = r.fn(txt, css);
    const e = achados.filter((a) => a.nivel === ERRO).length;
    const av = achados.filter((a) => a.nivel === AVISO).length;
    if (e) houveErro = true;
    console.log(`  [${e ? "FAIL" : av ? "AVISO" : "PASS"}] ${r.id}`);
    for (const a of achados) console.log(`         ${a.nivel} ${a.linha ? "linha " + a.linha : ""} · ${a.msg}`);
  }
}

// ---- camada 2: medição -----------------------------------------------------
if (SO_LINTER) {
  console.log("\n--so-linter: NÃO medi no navegador. Isto NÃO é um gate completo.");
} else {
  let chromium;
  try { ({ chromium } = await import("playwright")); }
  catch {
    console.error("\nERRO: playwright não instalado — a medição não rodou.");
    console.error("      Instale (`npm i --no-save playwright && npx playwright install --with-deps chromium`)");
    console.error("      ou rode com --so-linter assumindo que o gate fica incompleto.");
    process.exit(1);
  }

  const navegador = await chromium.launch();
  console.log("\n═══ conferindo se o medidor está confiável");
  if (await conferirOMedidor(navegador)) {
    console.error("O MEDIDOR NÃO ESTÁ CONFIÁVEL — não use como gate.");
    await navegador.close();
    process.exit(1);
  }

  for (const arq of ALVOS) {
    const url = /^https?:/.test(arq) ? arq : "file://" + resolve(arq);
    console.log(`\n═══ medindo · ${basename(arq)}`);
    for (const largura of LARGURAS) {
      const ctx = await navegador.newContext({ viewport: { width: largura, height: 900 } });
      const pag = await ctx.newPage();
      try { await pag.goto(url, { waitUntil: "networkidle", timeout: 60000 }); }
      catch { await pag.goto(url, { waitUntil: "load", timeout: 60000 }); }
      await pag.waitForTimeout(2500);

      const r = await pag.evaluate(medirNaPagina, largura);
      const problemas = [
        ...(r.rolaPagina ? [{ tipo: "a página rola para o lado", d: { seletor: "<html>", texto: "", esquerda: 0, direita: r.scrollWidth } }] : []),
        ...r.clicaveisFora.map((d) => ({ tipo: "clicável fora da tela", d })),
        ...r.dadosFora.map((d) => ({ tipo: "dado fora da tela", d })),
      ];

      if (!problemas.length) console.log(`  PASS  ${largura}px`);
      else {
        houveErro = true;
        console.log(`  FALHOU  ${largura}px — ${problemas.length} problema(s)`);
        for (const p of problemas.slice(0, 8))
          console.log(`          ${p.tipo}: ${p.d.seletor}${p.d.texto ? ` "${p.d.texto}"` : ""} — de ${p.d.esquerda}px a ${p.d.direita}px (tela tem ${largura}px)`);
        if (problemas.length > 8) console.log(`          … e mais ${problemas.length - 8}`);
        if (CAPTURAS) {
          await pag.evaluate((sels) => {
            for (const s of sels) { try { const el = document.querySelector(s); if (el) { el.style.outline = "3px solid #E8521A"; el.style.outlineOffset = "2px"; } } catch {} }
          }, problemas.map((p) => p.d.seletor).slice(0, 5)).catch(() => {});
          const f = `${CAPTURAS}/${basename(ALVOS[0], ".html")}-${largura}px.png`;
          await pag.screenshot({ path: f });
          console.log(`          captura: ${f}`);
        }
      }
      await ctx.close();
    }
  }
  await navegador.close();
}

console.log(houveErro ? "\nRESULTADO: REPROVOU — não publique" : "\nRESULTADO: passou");
process.exit(houveErro ? 1 : 0);
