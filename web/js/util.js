// Small DOM, SVG, formatting and chart helpers shared by every section.

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
export const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
export const reduceMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export const pct = (v, d = 0) => (v == null || Number.isNaN(v) ? "–" : `${(v * 100).toFixed(d)}%`);
export const f2 = (v) => (v == null ? "–" : Number(v).toFixed(2));
export const f1 = (v) => (v == null ? "–" : Number(v).toFixed(1));
export const f3 = (v) => (v == null ? "–" : Number(v).toFixed(3));
export const int = (v) => (v == null ? "–" : Math.round(v).toLocaleString("en-US"));
export const signed = (v, digits = 2) => `${v >= 0 ? "+" : "−"}${Math.abs(v).toFixed(digits)}`;

export function esc(text) {
  return String(text).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

export function html(el, markup) {
  el.innerHTML = markup;
  return el;
}

const SVGNS = "http://www.w3.org/2000/svg";
export function s(tag, attrs = {}, parent = null) {
  const node = document.createElementNS(SVGNS, tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null) continue;
    if (k === "text") node.textContent = v;
    else node.setAttribute(k, v);
  }
  if (parent) parent.appendChild(node);
  return node;
}

export function clear(svg, width, height) {
  svg.replaceChildren();
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("height", height);
  return svg;
}

export function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

export function debounce(fn, ms) {
  let id;
  return (...args) => {
    clearTimeout(id);
    id = setTimeout(() => fn(...args), ms);
  };
}

// Scores pile up near zero, so score axes use a square-root scale: the low end,
// where the threshold lives, gets room to breathe. Ticks are labelled in real units.
export const SCORE_TICKS = [0, 0.02, 0.05, 0.1, 0.2, 0.4, 0.6, 0.8, 1];
export const scoreTicks = (width) => (width < 560 ? [0, 0.05, 0.2, 0.5, 1] : SCORE_TICKS);
export function sqrtScale(x0, x1) {
  const span = x1 - x0;
  return {
    x: (v) => x0 + Math.sqrt(clamp(v, 0, 1)) * span,
    inv: (px) => clamp((px - x0) / span, 0, 1) ** 2,
  };
}
export function linear(d0, d1, r0, r1) {
  const f = (v) => r0 + ((v - d0) / (d1 - d0)) * (r1 - r0);
  f.inv = (p) => d0 + ((p - r0) / (r1 - r0)) * (d1 - d0);
  return f;
}
export function niceTicks(max, count = 4) {
  const raw = max / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((m) => m >= raw);
  const ticks = [];
  for (let v = 0; v <= max + 1e-9; v += step) ticks.push(+v.toFixed(6));
  if (ticks[ticks.length - 1] < max) ticks.push(+(ticks[ticks.length - 1] + step).toFixed(6));
  return ticks;
}

// A horizontal bar whose data end is rounded (4px) and whose baseline end is square.
export function barPath(x0, x1, y, h, r = 4) {
  const w = Math.max(0, x1 - x0);
  const rr = Math.min(r, w, h / 2);
  return `M${x0},${y}H${x0 + w - rr}Q${x0 + w},${y} ${x0 + w},${y + rr}V${y + h - rr}Q${x0 + w},${y + h} ${x0 + w - rr},${y + h}H${x0}Z`;
}
// The same for a column growing up from a baseline at y0.
export function colPath(x, w, y0, y1, r = 4) {
  const h = Math.max(0, y0 - y1);
  const rr = Math.min(r, h, w / 2);
  return `M${x},${y0}V${y1 + rr}Q${x},${y1} ${x + rr},${y1}H${x + w - rr}Q${x + w},${y1} ${x + w},${y1 + rr}V${y0}Z`;
}

// Tooltip ------------------------------------------------------------------
const tip = () => document.getElementById("tooltip");
export function showTip(markup, clientX, clientY) {
  const t = tip();
  t.innerHTML = markup;
  t.hidden = false;
  const pad = 14;
  const { width, height } = t.getBoundingClientRect();
  let x = clientX + pad;
  let y = clientY + pad;
  if (x + width > window.innerWidth - 8) x = clientX - width - pad;
  if (y + height > window.innerHeight - 8) y = clientY - height - pad;
  t.style.left = `${Math.max(8, x)}px`;
  t.style.top = `${Math.max(8, y)}px`;
}
export function hideTip() {
  tip().hidden = true;
}
export const tipRow = (k, v) => `<div class="tt-row"><span>${esc(k)}</span><b>${esc(v)}</b></div>`;

// Table view: every chart has a plain-table twin --------------------------
export function renderTable(container, columns, rows) {
  const head = columns.map((c) => `<th scope="col">${esc(c.label)}</th>`).join("");
  const body = rows
    .map((r) => `<tr>${columns.map((c) => {
      const v = c.format ? c.format(r[c.key], r) : r[c.key];
      return `<td class="${c.num ? "num" : ""}">${esc(v ?? "–")}</td>`;
    }).join("")}</tr>`)
    .join("");
  container.innerHTML = `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
}

export function bindTableToggles(builders) {
  document.querySelectorAll("[data-table]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const key = btn.dataset.table;
      const box = document.getElementById(`table-${key}`);
      const open = box.hidden;
      if (open && builders[key]) builders[key](box);
      box.hidden = !open;
      btn.textContent = open ? "Hide table" : "Show as table";
    });
  });
}

// Count-up for headline numbers -------------------------------------------
export function countUp(el, to, format, ms = 900) {
  if (reduceMotion()) {
    el.textContent = format(to);
    return;
  }
  const start = performance.now();
  const step = (now) => {
    const k = clamp((now - start) / ms, 0, 1);
    const e = 1 - (1 - k) ** 3;
    el.textContent = format(to * e);
    if (k < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

// Re-render a chart whenever its container changes width.
export function onResize(el, fn) {
  let last = 0;
  const ro = new ResizeObserver(([entry]) => {
    const w = Math.round(entry.contentRect.width);
    if (w && w !== last) {
      last = w;
      fn(w);
    }
  });
  ro.observe(el);
}

export const ICONS = {
  flag: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 21V4m0 0h11l-2 4 2 4H5"/></svg>',
  queue: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 7h16M4 12h16M4 17h10"/></svg>',
  check: '<svg viewBox="0 0 24 24" fill="none" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10" fill="var(--good)" stroke="none"/><path d="M7.5 12.5l3 3 6-6.5" stroke="#fff"/></svg>',
  lock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg>',
  pending: '<svg viewBox="0 0 24 24" fill="none" stroke-width="2.2" stroke-linecap="round"><circle cx="12" cy="12" r="10" fill="var(--warning)" stroke="none"/><path d="M12 7v5l3 2" stroke="#0b0b0b"/></svg>',
  missed: '<svg viewBox="0 0 24 24" fill="none" stroke="var(--critical)" stroke-width="2.4" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v6M12 16.5v.5"/></svg>',
  alarm: '<svg viewBox="0 0 24 24" fill="none" stroke="var(--serious)" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l9.5 17h-19z"/><path d="M12 10v4M12 17v.5"/></svg>',
  up: "▲",
  down: "▼",
};
