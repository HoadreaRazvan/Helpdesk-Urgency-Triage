// L8 vault: the sealed test set, opened once with a deliberate press-and-hold.
import { $, esc, f1, f2, f3, ICONS, int, pct, reduceMotion, s, signed } from "./util.js";

const HOLD_MS = 2400;
const CIRC = 2 * Math.PI * 100;

function drawDoor(svg) {
  svg.replaceChildren();
  const defs = s("defs", {}, svg);
  const grad = s("radialGradient", { id: "vault-glow" }, defs);
  s("stop", { offset: "0%", style: "stop-color:var(--accent);stop-opacity:.55" }, grad);
  s("stop", { offset: "100%", style: "stop-color:var(--accent);stop-opacity:0" }, grad);
  s("circle", { cx: 110, cy: 110, r: 104, class: "glow" }, svg);
  s("circle", { cx: 110, cy: 110, r: 100, class: "ring" }, svg);
  svg.progress = s("circle", { cx: 110, cy: 110, r: 100, class: "progress", "stroke-dasharray": CIRC, "stroke-dashoffset": CIRC }, svg);
  const door = s("g", { class: "door" }, svg);
  s("circle", { cx: 110, cy: 110, r: 84, class: "door" }, door);
  s("circle", { cx: 110, cy: 110, r: 70, class: "ring2" }, door);
  const spokes = s("g", { class: "spokes" }, door);
  for (const a of [0, 60, 120]) {
    const r = (a * Math.PI) / 180;
    s("line", { x1: 110 - 46 * Math.cos(r), y1: 110 - 46 * Math.sin(r), x2: 110 + 46 * Math.cos(r), y2: 110 + 46 * Math.sin(r) }, spokes);
  }
  s("circle", { cx: 110, cy: 110, r: 16, class: "hub" }, door);
  for (let i = 0; i < 8; i++) {
    const a = (i * Math.PI) / 4;
    s("rect", { x: 110 + 90 * Math.cos(a) - 5, y: 110 + 90 * Math.sin(a) - 3, width: 10, height: 6, rx: 2, class: "bolt",
                transform: `rotate(${(i * 45)} ${110 + 90 * Math.cos(a)} ${110 + 90 * Math.sin(a)})` }, svg);
  }
}

function resultsHTML(data, t) {
  const v = data.finalists[data.meta.selection.chosen];
  const rows = [
    ["Recall", v.recall, t.recall, (x) => pct(x), true],
    ["Precision", v.precision, t.precision, (x) => pct(x), true],
    ["Flagged", v.flag_rate, t.flag_rate, (x) => pct(x), null],
    ["Cost per 100", v.cost_per_100, t.cost_per_100, f1, false],
    ["Average precision", v.average_precision, t.average_precision, f3, true],
  ];
  const rule = t.baselines.find((b) => b.id === "keyword_rule");
  const major = t.baselines.find((b) => b.id === "majority");
  return `
    <p class="eyebrow">Opened ${esc(t.opened_at.slice(0, 10))} · final</p>
    <h3>${int(t.tickets)} test tickets, scored once.</h3>
    <div class="compare">
      <span class="h"></span><span class="h n">Validation</span><span class="h n">Test</span><span class="h n">Change</span>
      ${rows.map(([k, a, b, fmt]) => `<span>${k}</span><span class="n">${fmt(a)}</span><span class="n">${fmt(b)}</span><span class="n muted">${signed(b - a, k === "Cost per 100" ? 1 : 2)}</span>`).join("")}
    </div>
    <div class="cm" style="margin-top:16px">
      <div class="cell good"><div class="n">${t.tp}</div><div class="k">Caught · TP</div></div>
      <div class="cell bad"><div class="n">${t.fn}</div><div class="k">Missed · FN</div></div>
      <div class="cell bad"><div class="n">${t.fp}</div><div class="k">False alarms · FP</div></div>
      <div class="cell good"><div class="n">${t.tn}</div><div class="k">Left in queue · TN</div></div>
    </div>
    <p style="margin-top:14px">On the same test tickets, the keyword rule costs ${f1(rule.cost_per_100)} per 100 (recall ${pct(rule.recall)})
      and doing nothing costs ${f1(major.cost_per_100)}. The model card now reports these numbers. Nothing may be tuned from here on.</p>`;
}

export function initVault(data, onOpened) {
  const card = $("#vault-card");
  const body = $("#vault-body");
  const door = $("#vault-door");
  drawDoor(door);
  const m = data.meta;

  if (data.test.used && data.test.results) {
    card.classList.add("open");
    body.innerHTML = resultsHTML(data, data.test.results);
    return;
  }

  body.innerHTML = `
    <p class="eyebrow"><span style="display:inline-flex;width:14px;vertical-align:-2px">${ICONS.lock}</span> Sealed</p>
    <h3>Test window · ${esc(m.windows.test.first.slice(0, 10))} to ${esc(m.windows.test.last.slice(0, 10))}</h3>
    <p>${int(m.windows.test.rows)} tickets whose labels nobody has looked at. Opening them runs the frozen model once and writes a lock first,
      so even an interrupted run counts. Normally done in L8, in front of the team.</p>
    <dl class="frozen-list">
      <dt>Model</dt><dd>${esc(m.model.id)}</dd>
      <dt>Threshold</dt><dd>${f2(m.threshold)}</dd>
      <dt>Costs</dt><dd>miss ${m.costs.fn} · false alarm ${m.costs.fp}</dd>
      <dt>Frozen</dt><dd>${esc(m.frozen_at.replace("T", " ").slice(0, 16))} UTC</dd>
      <dt>Test IDs</dt><dd>sha256 ${esc(m.windows.test.ids_sha256.slice(0, 16))}…</dd>
    </dl>
    <label class="confirm"><input type="checkbox" id="vault-ok"><span>${esc(m.confirmation)}. After this, the model, threshold and costs cannot change.</span></label>
    <button class="hold" id="vault-hold" disabled><span class="fill"></span><span id="vault-label">Hold to open the test set</span></button>
    <p class="vault-msg" id="vault-msg" role="status"></p>`;

  const ok = $("#vault-ok");
  const hold = $("#vault-hold");
  const fill = hold.querySelector(".fill");
  ok.addEventListener("change", () => { hold.disabled = !ok.checked; });

  let start = 0, raf = 0, done = false;
  const paint = (p) => {
    fill.style.transform = `scaleX(${p})`;
    door.progress.setAttribute("stroke-dashoffset", CIRC * (1 - p));
  };
  const tick = (now) => {
    const p = Math.min(1, (now - start) / HOLD_MS);
    paint(p);
    if (p >= 1) return open();
    raf = requestAnimationFrame(tick);
  };
  const begin = (e) => {
    if (hold.disabled || done) return;
    e.preventDefault();
    start = performance.now();
    cancelAnimationFrame(raf);
    raf = requestAnimationFrame(tick);
  };
  const cancel = () => {
    if (done) return;
    cancelAnimationFrame(raf);
    paint(0);
  };
  hold.addEventListener("pointerdown", begin);
  hold.addEventListener("pointerup", cancel);
  hold.addEventListener("pointerleave", cancel);
  hold.addEventListener("keydown", (e) => { if ((e.key === " " || e.key === "Enter") && !e.repeat) begin(e); });
  hold.addEventListener("keyup", (e) => { if (e.key === " " || e.key === "Enter") cancel(); });

  async function open() {
    done = true;
    hold.disabled = true;
    ok.disabled = true;
    $("#vault-label").textContent = "Opening…";
    try {
      const res = await fetch("/api/test/unseal", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirmation: m.confirmation }),
      });
      const out = await res.json();
      if (!res.ok) throw new Error(out.error || "The test set could not be opened.");
      card.classList.add("open");
      setTimeout(() => {
        body.innerHTML = resultsHTML(data, out.results);
        body.classList.add("results-in");
      }, reduceMotion() ? 0 : 900);
      onOpened(out.test);
    } catch (err) {
      $("#vault-msg").textContent = err.message;
      $("#vault-label").textContent = "Could not open";
      paint(0);
    }
  }
}
