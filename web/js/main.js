// Boot: load the frozen results, then wire every section to the shared state.
import { initComposer } from "./composer.js";
import { initLab } from "./lab.js";
import { initSections, renderChecks } from "./sections.js";
import { set, setThreshold, state } from "./state.js";
import { initStream } from "./stream.js";
import { $, $$, bindTableToggles, esc, reduceMotion } from "./util.js";
import { initVault } from "./vault.js";

const MOON = '<path d="M12 3a9 9 0 1 0 9 9 7 7 0 0 1-9-9z"/>';
const SUN = '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>';

function effectiveTheme() {
  const t = document.documentElement.dataset.theme;
  if (t) return t;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function setupTheme(stream) {
  const btn = $("#theme-btn");
  const paint = () => { btn.querySelector("svg").innerHTML = effectiveTheme() === "dark" ? SUN : MOON; };
  btn.addEventListener("click", () => {
    const next = effectiveTheme() === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("triage-theme", next); } catch (e) { /* storage unavailable: theme lasts this visit */ }
    paint();
    stream.refreshColors();
  });
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { paint(); stream.refreshColors(); });
  paint();
}

function setupNav() {
  const links = $$(".sections a");
  const pill = $(".nav-pill");
  const move = (a) => {
    links.forEach((l) => l.classList.toggle("active", l === a));
    if (!a) { pill.style.width = "0"; return; }
    pill.style.width = `${a.offsetWidth}px`;
    pill.style.transform = `translateX(${a.offsetLeft}px)`;
    const nav = $(".sections");
    if (a.offsetLeft < nav.scrollLeft || a.offsetLeft + a.offsetWidth > nav.scrollLeft + nav.clientWidth) {
      nav.scrollTo({ left: a.offsetLeft - 24, behavior: reduceMotion() ? "auto" : "smooth" });
    }
  };
  const io = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (e.isIntersecting) move(links.find((l) => l.getAttribute("href") === `#${e.target.id}`));
    }
  }, { rootMargin: "-45% 0px -50% 0px" });
  $$("main > section").forEach((sec) => io.observe(sec));
}

function setupReveal() {
  const io = new IntersectionObserver((entries) => {
    for (const e of entries) if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
  }, { rootMargin: "0px 0px -8% 0px" });
  $$(".reveal").forEach((el) => io.observe(el));
}

function setupSpotlight() {
  document.addEventListener("pointermove", (e) => {
    const card = e.target.closest?.(".card");
    if (!card) return;
    const r = card.getBoundingClientRect();
    card.style.setProperty("--mx", `${e.clientX - r.left}px`);
    card.style.setProperty("--my", `${e.clientY - r.top}px`);
  }, { passive: true });
}

function setupPalette(stream) {
  const box = $("#palette");
  const input = $("#palette-input");
  const list = $("#palette-list");
  const go = (id) => () => document.getElementById(id).scrollIntoView({ behavior: reduceMotion() ? "auto" : "smooth" });
  const items = [
    ...$$(".sections a").map((a) => ({ label: a.textContent, hint: "section", run: go(a.getAttribute("href").slice(1)) })),
    { label: "Acceptance checks", hint: "section", run: go("checks") },
    { label: "Reset threshold to frozen", hint: "action", run: () => setThreshold(state.frozen) },
    { label: "Toggle theme", hint: "action", run: () => $("#theme-btn").click() },
    { label: "Play / pause the live replay", hint: "action", run: () => stream.toggle() },
    { label: "Open the model card", hint: "report", run: () => window.open("/reports/model_card.md", "_blank", "noopener") },
    { label: "Open the decision note", hint: "report", run: () => window.open("/reports/decision_note.md", "_blank", "noopener") },
  ];
  let shown = items, sel = 0;
  const render = () => {
    const q = input.value.trim().toLowerCase();
    shown = items.filter((i) => i.label.toLowerCase().includes(q));
    sel = Math.min(sel, Math.max(0, shown.length - 1));
    list.innerHTML = shown.map((i, n) => `<li role="option" aria-selected="${n === sel}" class="${n === sel ? "sel" : ""}" data-n="${n}">${esc(i.label)}<span>${i.hint}</span></li>`).join("");
  };
  const open = () => { box.hidden = false; input.value = ""; sel = 0; render(); input.focus(); };
  const close = () => { box.hidden = true; };
  const run = (i) => { close(); i?.run(); };
  $("#palette-btn").addEventListener("click", open);
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); box.hidden ? open() : close(); }
    else if (!box.hidden && e.key === "Escape") close();
  });
  input.addEventListener("input", () => { sel = 0; render(); });
  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") { sel = Math.min(shown.length - 1, sel + 1); render(); e.preventDefault(); }
    if (e.key === "ArrowUp") { sel = Math.max(0, sel - 1); render(); e.preventDefault(); }
    if (e.key === "Enter") run(shown[sel]);
  });
  list.addEventListener("click", (e) => { const li = e.target.closest("li"); if (li) run(shown[Number(li.dataset.n)]); });
  box.addEventListener("click", (e) => { if (e.target === box) close(); });
}

async function boot() {
  const res = await fetch("/api/dashboard");
  if (!res.ok) throw new Error(`The server answered ${res.status}.`);
  const data = await res.json();
  set({ data, threshold: data.meta.threshold, frozen: data.meta.threshold, costFn: data.meta.costs.fn, costFp: data.meta.costs.fp });

  const stream = initStream(data.tickets);
  initComposer(data);
  const lab = initLab(data);
  const builders = initSections(data);
  builders.lab = lab.table;
  bindTableToggles(builders);
  initVault(data, (test) => { data.test = test; renderChecks(data); });
  setupTheme(stream);
  setupNav();
  setupReveal();
  setupSpotlight();
  setupPalette(stream);
  $("#boot").classList.add("gone");
  setTimeout(() => $("#boot")?.remove(), 600);
}

boot().catch((err) => {
  $("#boot").innerHTML = `<p><b>Could not load the dashboard.</b><br>${esc(err.message)}<br>Is <code>python -m triage serve</code> running?</p>`;
});
