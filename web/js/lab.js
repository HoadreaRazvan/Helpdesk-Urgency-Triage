// Threshold lab: every validation ticket as a dot, the cost curve on the same
// x-axis, and the confusion matrix, all driven by one draggable line.
import { cheapest, confusionAt, groupDays, on, queueAt, set, setThreshold, state, sweep } from "./state.js";
import { $, $$, clear, esc, f1, f2, hideTip, int, linear, niceTicks, onResize, pct, renderTable, s,
         scoreTicks, showTip, sqrtScale, tipRow } from "./util.js";

const PAD_L = 108, PAD_R = 18, R = 4;

export function initLab(data) {
  const tickets = data.tickets;
  const days = groupDays(tickets);
  const swarm = $("#swarm");
  const curve = $("#costcurve");
  let width = 0, scale = null, dots = [], rows = sweep(tickets, state.costFn, state.costFp);

  function layoutSwarm(w) {
    width = w;
    scale = sqrtScale(PAD_L, w - PAD_R);
    const groups = [tickets.filter((k) => k.y === 1), tickets.filter((k) => k.y === 0)];
    const placed = [[], []];
    const maxOff = [0, 0];
    const gap = 2 * R + 1;
    const cap = [56, 80];  // beyond this half-height, dots may overlap rather than grow the chart
    groups.forEach((g, gi) => {
      const sorted = [...g].sort((a, b) => a.s - b.s);
      const list = placed[gi];
      sorted.forEach((k, idx) => {
        const x = scale.x(k.s);
        const near = [];
        for (let j = list.length - 1; j >= 0 && x - list[j].x < gap; j--) near.push(list[j].off);
        let off = null;
        for (let i = 0; ; i++) {
          const o = (i % 2 ? 1 : -1) * Math.ceil(i / 2) * (R * 0.9);
          if (Math.abs(o) > cap[gi]) break;
          if (!near.some((n) => Math.abs(n - o) < gap)) { off = o; break; }
        }
        if (off === null) off = (((idx * 7919) % 1000) / 1000 - 0.5) * 2 * cap[gi];  // deterministic scatter
        list.push({ k, x, off });
        maxOff[gi] = Math.max(maxOff[gi], Math.abs(off));
      });
    });
    const band = maxOff.map((m) => Math.max(34, m + R + 6));
    const top = 28;
    const centers = [top + band[0], top + 2 * band[0] + 18 + band[1]];
    const height = centers[1] + band[1] + 28;
    return { placed, centers, band, height, top };
  }

  let geo = null;
  function drawSwarm(w) {
    geo = layoutSwarm(w);
    clear(swarm, w, geo.height);
    swarm.zone = s("rect", { y: geo.top - 8, height: geo.height - geo.top - 20, style: "fill:var(--accent);opacity:.07" }, swarm);
    const labels = [`Urgent · ${int(geo.placed[0].length)}`, `Not urgent · ${int(geo.placed[1].length)}`];
    geo.centers.forEach((cy, i) => {
      s("line", { x1: PAD_L, x2: w - PAD_R, y1: cy, y2: cy, class: "grid" }, swarm);
      s("text", { x: 0, y: cy + 4, class: "lbl", text: labels[i] }, swarm);
    });
    const axisY = geo.height - 18;
    s("line", { x1: PAD_L, x2: w - PAD_R, y1: axisY, y2: axisY, class: "axis" }, swarm);
    for (const t of scoreTicks(w)) {
      const x = scale.x(t);
      s("line", { x1: x, x2: x, y1: axisY, y2: axisY + 4, class: "axis" }, swarm);
      s("text", { x, y: axisY + 15, "text-anchor": "middle", text: String(t) }, swarm);
    }
    s("text", { x: w - PAD_R, y: geo.top - 12, "text-anchor": "end", text: "urgency score (square-root scale) →" }, swarm);
    dots = [];
    geo.placed.forEach((list, gi) => {
      for (const p of list) {
        const c = s("circle", { cx: p.x, cy: geo.centers[gi] + p.off, r: R, class: p.k.y ? "m-urgent" : "m-calm",
                                style: "stroke:var(--surface)", "stroke-width": 1 }, swarm);
        dots.push({ c, k: p.k, x: p.x, y: geo.centers[gi] + p.off });
      }
    });
    swarm.frozen = s("path", { class: "m-ink" }, swarm);
    swarm.line = s("line", { y1: geo.top - 8, y2: geo.height - 20, style: "stroke:var(--ink)", "stroke-width": 2 }, swarm);
    swarm.chip = s("g", {}, swarm);
    swarm.hit = s("rect", { x: 0, y: 0, width: w, height: geo.height, fill: "transparent", style: "cursor:ew-resize;touch-action:none" }, swarm);
    bindDrag(swarm, (e) => hoverSwarm(e));
    updateSwarm();
  }

  function updateSwarm() {
    if (!geo) return;
    const t = state.threshold;
    const x = scale.x(t);
    swarm.zone.setAttribute("x", x);
    swarm.zone.setAttribute("width", Math.max(0, width - PAD_R - x));
    swarm.line.setAttribute("x1", x);
    swarm.line.setAttribute("x2", x);
    for (const d of dots) {
      const wrong = d.k.y ? d.k.s < t : d.k.s >= t;
      d.c.style.opacity = wrong ? 1 : 0.32;
    }
    const fx = scale.x(state.frozen);
    swarm.frozen.setAttribute("d", `M${fx - 6},${geo.top - 22} h12 l-6,8 z`);
    swarm.chip.replaceChildren();
    const label = `${f2(t)} · drag`;
    const tw = label.length * 6.6 + 16;
    const cx = Math.min(Math.max(x - tw / 2, PAD_L), width - PAD_R - tw);
    s("rect", { x: cx, y: geo.height - 16, width: tw, height: 16, rx: 8, class: "m-ink" }, swarm.chip);
    s("text", { x: cx + tw / 2, y: geo.height - 4.5, "text-anchor": "middle", style: "fill:var(--surface);font:600 11px system-ui", text: label }, swarm.chip);
  }

  function hoverSwarm(e) {
    const rect = swarm.getBoundingClientRect();
    const px = ((e.clientX - rect.left) / rect.width) * width;
    const py = ((e.clientY - rect.top) / rect.height) * geo.height;
    let best = null, bestD = 12;
    for (const d of dots) {
      const dist = Math.hypot(d.x - px, d.y - py);
      if (dist < bestD) { best = d; bestD = dist; }
    }
    if (!best) return hideTip();
    const k = best.k;
    const flag = k.s >= state.threshold;
    const outcome = k.y ? (flag ? "caught" : "missed") : (flag ? "false alarm" : "correctly left");
    showTip(`<div class="tt-head"><i class="dot ${k.y ? "urgent" : "calm"}"></i>${esc(k.id)} · ${outcome}</div>` +
      tipRow("Score", f2(k.s)) + tipRow("Submitted", k.t) + tipRow("Category", k.cat) + tipRow("Channel", k.ch) +
      `<div class="tt-text">${esc(k.text.slice(0, 180))}${k.text.length > 180 ? "…" : ""}</div>`, e.clientX, e.clientY);
  }

  // drag behaviour shared by the swarm and the cost curve
  function bindDrag(svg, onHover) {
    let dragging = false;
    const toT = (e) => {
      const rect = svg.getBoundingClientRect();
      return scale.inv(((e.clientX - rect.left) / rect.width) * width);
    };
    svg.hit.addEventListener("pointerdown", (e) => { dragging = true; svg.hit.setPointerCapture(e.pointerId); setThreshold(toT(e)); hideTip(); });
    svg.hit.addEventListener("pointermove", (e) => { if (dragging) setThreshold(toT(e)); else onHover(e); });
    svg.hit.addEventListener("pointerup", () => { dragging = false; });
    svg.hit.addEventListener("pointercancel", () => { dragging = false; });
    svg.hit.addEventListener("pointerleave", hideTip);
  }

  // cost curve ----------------------------------------------------------------
  let cgeo = null;
  function drawCurve(w) {
    const H = 190, top = 14, bottom = 26;
    const maxCost = Math.max(...rows.map((r) => r.per100));
    const ticks = niceTicks(maxCost, 3);
    const y = linear(0, ticks[ticks.length - 1], H - bottom, top);
    cgeo = { H, y, top, bottom };
    clear(curve, w, H);
    ticks.forEach((v) => {
      s("line", { x1: PAD_L, x2: w - PAD_R, y1: y(v), y2: y(v), class: "grid" }, curve);
      s("text", { x: PAD_L - 8, y: y(v) + 4, "text-anchor": "end", text: String(v) }, curve);
    });
    s("text", { x: 0, y: top + 4, class: "lbl", text: "Cost per 100" }, curve);
    s("text", { x: 0, y: top + 20, text: `FN ${state.costFn} · FP ${state.costFp}` }, curve);
    s("line", { x1: PAD_L, x2: w - PAD_R, y1: H - bottom, y2: H - bottom, class: "axis" }, curve);
    for (const t of scoreTicks(w)) {
      s("text", { x: scale.x(t), y: H - bottom + 15, "text-anchor": "middle", text: String(t) }, curve);
    }
    const path = (key) => rows.map((r, i) => `${i ? "L" : "M"}${scale.x(r.t).toFixed(1)},${y(r[key]).toFixed(1)}`).join("");
    s("path", { d: path("per100"), fill: "none", style: "stroke:var(--muted);opacity:.7", "stroke-width": 1.5, "stroke-linejoin": "round" }, curve);
    s("path", { d: path("smoothed"), fill: "none", class: "s-calm", "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }, curve);
    const best = cheapest(rows);
    s("path", { d: `M${scale.x(best.t)},${y(best.smoothed) - 7} l6,7 l-6,7 l-6,-7 z`, class: "m-calm",
                style: "stroke:var(--surface)", "stroke-width": 2 }, curve);
    s("text", { x: scale.x(best.t) + 9, y: y(best.smoothed) - 9, class: "lbl", text: `cheapest ${f2(best.t)}` }, curve);
    curve.cursor = s("line", { y1: top, y2: H - bottom, style: "stroke:var(--ink)", "stroke-width": 2 }, curve);
    curve.dot = s("circle", { r: 5, class: "m-calm", style: "stroke:var(--surface)", "stroke-width": 2 }, curve);
    curve.hit = s("rect", { x: 0, y: 0, width: w, height: H, fill: "transparent", style: "cursor:ew-resize;touch-action:none" }, curve);
    bindDrag(curve, (e) => {
      const rect = curve.getBoundingClientRect();
      const t = Math.round(scale.inv(((e.clientX - rect.left) / rect.width) * width) * 100) / 100;
      const r = rows[Math.min(98, Math.max(0, Math.round(t * 100) - 1))];
      showTip(`<div class="tt-head">Threshold ${f2(r.t)}</div>` + tipRow("Cost per 100", f1(r.per100)) +
        tipRow("Smoothed", f1(r.smoothed)) + tipRow("Recall", pct(r.recall)) + tipRow("Precision", pct(r.precision)) +
        tipRow("Flagged", pct(r.flagRate)), e.clientX, e.clientY);
    });
    updateCurve();
  }

  function updateCurve() {
    if (!cgeo) return;
    const x = scale.x(state.threshold);
    const r = rows[Math.round(state.threshold * 100) - 1];
    curve.cursor.setAttribute("x1", x);
    curve.cursor.setAttribute("x2", x);
    curve.dot.setAttribute("cx", x);
    curve.dot.setAttribute("cy", cgeo.y(r.smoothed));
  }

  // side panel ----------------------------------------------------------------
  function updateSide() {
    const t = state.threshold;
    const cm = confusionAt(tickets, t);
    const r = rows[Math.round(t * 100) - 1];
    const q = queueAt(days, t);
    $("#t-value").textContent = f2(t);
    $("#t-range").value = Math.round(t * 100);
    $("#cm").innerHTML = [
      ["good", cm.tp, "Caught · TP"], ["bad", cm.fn, "Missed · FN"],
      ["bad", cm.fp, "False alarms · FP"], ["good", cm.tn, "Left in queue · TN"],
    ].map(([cls, n, k]) => `<div class="cell ${cls}"><div class="n">${n}</div><div class="k">${k}</div></div>`).join("");
    $("#lab-metrics").innerHTML = [
      ["Recall (urgent caught)", pct(cm.recall)], ["Precision (flags that were right)", pct(cm.precision)],
      ["Flagged", `${pct(cm.flagRate)} · ${f1(q.flagsPerDay)}/day`], ["Accuracy", pct((cm.tp + cm.tn) / cm.n)],
      ["Cost per 100 tickets", f1(r.per100)],
    ].map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("");
    $("#lab-queue").innerHTML = `An urgent ticket waits behind<strong>${f1(q.aheadFlagged)} tickets</strong>instead of ${f1(q.aheadFifo)} in first-come order (${f1(q.perDay)} tickets a day).`;
  }

  $("#t-range").addEventListener("input", (e) => setThreshold(Number(e.target.value) / 100));
  $("#t-reset").addEventListener("click", () => setThreshold(state.frozen));
  $("#t-optimal").addEventListener("click", () => setThreshold(cheapest(rows).t));
  $$("[data-cost]").forEach((b) => b.addEventListener("click", () => {
    const key = b.dataset.cost === "fn" ? "costFn" : "costFp";
    const v = Math.min(20, Math.max(1, state[key] + Number(b.dataset.d)));
    set({ [key]: v });
  }));

  on((patch) => {
    if ("costFn" in patch || "costFp" in patch) {
      rows = sweep(tickets, state.costFn, state.costFp);
      $("#cost-fn").textContent = state.costFn;
      $("#cost-fp").textContent = state.costFp;
      if (width) drawCurve(width);
    }
    updateSwarm();
    updateCurve();
    updateSide();
  });

  onResize($(".lab-plots"), (w) => { drawSwarm(w); drawCurve(w); });
  updateSide();

  return {
    table: (box) => renderTable(box, [
      { key: "t", label: "Threshold", num: true, format: f2 }, { key: "recall", label: "Recall", num: true, format: (v) => pct(v, 1) },
      { key: "precision", label: "Precision", num: true, format: (v) => pct(v, 1) }, { key: "flagRate", label: "Flagged", num: true, format: (v) => pct(v, 1) },
      { key: "fn", label: "FN", num: true }, { key: "fp", label: "FP", num: true },
      { key: "per100", label: "Cost / 100", num: true, format: f1 }, { key: "smoothed", label: "Smoothed", num: true, format: f1 },
    ], rows),
  };
}
