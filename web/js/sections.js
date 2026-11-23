// The static sections: KPIs, ladder, experiments, tone, calibration, errors,
// shifts, subgroups, data and acceptance checks.
import { CATEGORY_NAMES, CHANNEL_NAMES, sentencesHTML } from "./composer.js";
import { $, clear, colPath, barPath, countUp, esc, f1, f2, f3, hideTip, html, ICONS, int, linear,
         niceTicks, onResize, pct, renderTable, s, showTip, signed, tipRow } from "./util.js";

const pretty = (slice, v) => slice === "initial_channel" ? CHANNEL_NAMES[v] ?? v
  : slice === "category" ? CATEGORY_NAMES[v] ?? v
  : slice === "requester_type" ? String(v).replace("_", " ") : v;

// Horizontal bars with the label above each bar (works at phone width too).
function hbars(svg, w, rows, { max, min = 0, format, refs = [], valueW = 70 }) {
  const ROW = 38, HEAD = 26, BAR = 14;
  let y = 6;
  const layout = rows.map((r) => {
    const item = { ...r, y };
    y += r.header ? HEAD : ROW;
    return item;
  });
  const H = y + 22;
  clear(svg, w, H);
  const x = linear(min, max, 0, w - valueW);
  const ticks = niceTicks(max - min, 4).map((v) => v + min).filter((v) => v <= max + 1e-9);
  ticks.forEach((v) => {
    s("line", { x1: x(v), x2: x(v), y1: 0, y2: H - 22, class: "grid" }, svg);
    s("text", { x: x(v), y: H - 6, "text-anchor": "middle", text: format(v, true) }, svg);
  });
  // Reference lines go under the bars and labels, so they never strike through text.
  for (const ref of refs) {
    s("line", { x1: x(ref.value), x2: x(ref.value), y1: 0, y2: H - 22, style: "stroke:var(--ink-2)", "stroke-width": 1.5, "stroke-dasharray": "4 3" }, svg);
    s("text", { x: x(ref.value) + 5, y: 10, class: "lbl", style: "font-weight:600;font-size:11px", text: ref.label }, svg);
  }
  for (const r of layout) {
    if (r.header) {
      s("text", { x: 0, y: r.y + 16, style: "fill:var(--muted);font:600 11px ui-monospace,monospace;letter-spacing:.08em", text: r.header.toUpperCase() }, svg);
      continue;
    }
    s("text", { x: 0, y: r.y + 12, class: "lbl", text: r.label }, svg);
    if (r.note) s("text", { x: w - valueW + 8, y: r.y + 12, "text-anchor": "start", text: r.note }, svg);
    if (r.value == null) {
      s("text", { x: 0, y: r.y + 29, text: r.missing ?? "not enough data" }, svg);
    } else {
      s("path", { d: barPath(x(min), x(Math.max(min, r.value)), r.y + 18, BAR), class: r.cls ?? "m-calm" }, svg);
      s("text", { x: x(Math.max(min, r.value)) + 6, y: r.y + 29, class: "val", text: format(r.value) }, svg);
    }
    const hit = s("rect", { x: 0, y: r.y, width: w, height: ROW, fill: "transparent" }, svg);
    if (r.tip) {
      hit.addEventListener("pointermove", (e) => showTip(r.tip, e.clientX, e.clientY));
      hit.addEventListener("pointerleave", hideTip);
    }
  }
}

export function initSections(data) {
  const v = data.validation;
  const meta = data.meta;
  const base = Object.fromEntries(v.baselines.map((b) => [b.id, b]));
  const chosen = data.finalists[meta.selection.chosen];
  const other = data.finalists[meta.selection.chosen === "A" ? "B" : "A"];
  const builders = {};

  // KPIs ------------------------------------------------------------------
  const kpis = [
    { label: "Urgent tickets caught", value: v.recall, fmt: (x) => pct(x), sub: `Keyword rule: ${pct(base.keyword_rule.recall)}` },
    { label: "Cost per 100 tickets", value: v.cost_per_100, fmt: (x) => f1(x), sub: `Rule ${f1(base.keyword_rule.cost_per_100)} · do nothing ${f1(base.majority.cost_per_100)}` },
    { label: "Tickets ahead of an urgent one", value: v.queue.urgent_ahead_flagged, fmt: (x) => f1(x), sub: `${f1(v.queue.urgent_ahead_fifo)} without the flag` },
  ];
  $("#kpis").innerHTML = kpis.map((k, i) => `<div class="kpi"><div class="label">${k.label}</div><div class="value" id="kpi-${i}">–</div><div class="sub">${k.sub}</div></div>`).join("");
  kpis.forEach((k, i) => countUp($(`#kpi-${i}`), k.value, k.fmt));

  // Ladder ---------------------------------------------------------------
  const ladderRows = [
    { ...base.majority, short: "Baseline 1 · majority class" },
    { ...base.shouting_rule, short: "Naive rule · “urgent” / “ASAP”" },
    { ...base.keyword_rule, short: "Baseline 2 · keyword rule" },
    { ...other, short: other.name, threshold: other.threshold },
    { ...chosen, short: `${chosen.name} ✔`, threshold: chosen.threshold, selected: true },
  ];
  onResize($("#ladder-chart").parentElement, (w) => hbars($("#ladder-chart"), w, ladderRows.map((r) => ({
    label: r.short, value: r.cost_per_100, cls: r.selected ? "m-calm" : "m-muted",
    tip: `<div class="tt-head">${esc(r.short)}</div>` + tipRow("Cost per 100", f1(r.cost_per_100)) + tipRow("Recall", pct(r.recall)) +
         tipRow("Precision", pct(r.precision)) + tipRow("Flagged", pct(r.flag_rate)) + (r.threshold ? tipRow("Threshold", f2(r.threshold)) : ""),
  })), { max: 100, format: (x, tick) => (tick ? String(x) : f1(x)), valueW: 52 }));
  builders.ladder = (box) => renderTable(box, [
    { key: "short", label: "Model" }, { key: "recall", label: "Recall", num: true, format: (x) => pct(x, 1) },
    { key: "precision", label: "Precision", num: true, format: (x) => pct(x, 1) }, { key: "flag_rate", label: "Flagged", num: true, format: (x) => pct(x, 1) },
    { key: "tp", label: "TP", num: true }, { key: "fn", label: "FN", num: true }, { key: "fp", label: "FP", num: true }, { key: "tn", label: "TN", num: true },
    { key: "cost_per_100", label: "Cost / 100", num: true, format: f1 },
  ], ladderRows);

  // Experiments dot plot ----------------------------------------------------
  function drawExperiments(w) {
    const svg = $("#exp-chart");
    const ROW = 34;
    const rows = data.experiments;
    const H = rows.length * ROW + 30;
    clear(svg, w, H);
    const x = linear(0.3, 1.0, 4, w - 50);
    for (const t of [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]) {
      s("line", { x1: x(t), x2: x(t), y1: 0, y2: H - 22, class: "grid" }, svg);
      s("text", { x: x(t), y: H - 6, "text-anchor": "middle", text: t.toFixed(1) }, svg);
    }
    rows.forEach((e, i) => {
      const y = i * ROW + 6;
      const leak = !e.allowed;
      const cls = leak ? "critical" : e.selected ? "calm" : "muted";
      const label = leak ? `${e.id} · excluded: uses post-submission columns` : `${e.id}${e.selected ? " · selected" : ""}`;
      s("text", { x: 0, y: y + 11, class: "lbl", style: "font-family:ui-monospace,monospace;font-size:11px", text: label }, svg);
      const m = e.cv_average_precision, sd = e.cv_average_precision_std;
      s("line", { x1: x(Math.max(0.3, m - sd)), x2: x(Math.min(1, m + sd)), y1: y + 22, y2: y + 22, class: `s-${cls}`, "stroke-width": 2, "stroke-linecap": "round" }, svg);
      s("circle", { cx: x(m), cy: y + 22, r: 5, class: `m-${cls}`, style: "stroke:var(--surface)", "stroke-width": 2 }, svg);
      s("text", { x: x(Math.min(1, m + sd)) + 8, y: y + 26, class: "val", text: f3(m) }, svg);
      const hit = s("rect", { x: 0, y, width: w, height: ROW, fill: "transparent" }, svg);
      hit.addEventListener("pointermove", (ev) => showTip(`<div class="tt-head">${esc(e.id)}</div>` +
        tipRow("Family", e.name) + tipRow("Settings", e.params) + tipRow("CV average precision", `${f3(m)} ± ${f3(sd)}`) +
        tipRow("CV ROC AUC", f3(e.cv_roc_auc)) + tipRow("CV Brier", f3(e.cv_brier)) + (e.note ? `<div class="tt-text">${esc(e.note)}</div>` : ""), ev.clientX, ev.clientY));
      hit.addEventListener("pointerleave", hideTip);
    });
  }
  onResize($("#exp-chart").parentElement, drawExperiments);
  builders.exp = (box) => renderTable(box, [
    { key: "id", label: "Experiment" }, { key: "params", label: "Settings" },
    { key: "cv_average_precision", label: "CV AP", num: true, format: f3 }, { key: "cv_average_precision_std", label: "± std", num: true, format: f3 },
    { key: "cv_roc_auc", label: "CV AUC", num: true, format: f3 }, { key: "cv_brier", label: "Brier", num: true, format: f3 },
    { key: "allowed", label: "Allowed", format: (x) => (x ? "yes" : "no: leakage") },
  ], data.experiments);

  // Tone -------------------------------------------------------------------
  const styles = { "calm request": "Calm request", shouting: "Shouting", negation: "Negation" };
  const toneRows = [];
  for (const key of Object.keys(styles)) {
    toneRows.push({ header: styles[key] });
    data.tone.filter((t) => t.style === key).forEach((t) => toneRows.push({
      label: `“${t.phrase}”`, value: t.urgent_rate, cls: "m-urgent",
      tip: `<div class="tt-head">“${esc(t.phrase)}”</div>` + tipRow("Training tickets", t.tickets) + tipRow("Urgent", pct(t.urgent_rate)),
    }));
  }
  onResize($("#tone-chart").parentElement, (w) => hbars($("#tone-chart"), w, toneRows, {
    max: 1, format: (x, tick) => pct(x), refs: [{ value: data.audit.train_prevalence, label: `average ${pct(data.audit.train_prevalence, 1)}` }], valueW: 48,
  }));
  builders.tone = (box) => renderTable(box, [
    { key: "style", label: "Style" }, { key: "phrase", label: "Phrase" }, { key: "tickets", label: "Tickets", num: true },
    { key: "urgent_rate", label: "Urgent", num: true, format: (x) => pct(x, 1) },
  ], data.tone);
  const find = (p) => data.tone.find((t) => t.phrase === p);
  const withText = data.experiments.find((e) => e.id === "logreg_C1");
  const noText = data.experiments.find((e) => e.id === "logreg_C1_no_text");
  $("#insight-cards").innerHTML = [
    { big: pct(find("Please treat as urgent.")?.urgent_rate), text: "of training tickets that say “Please treat as urgent.” are urgent. Calm and explicit beats loud." },
    { big: pct(find("URGENT!!!")?.urgent_rate), text: `of tickets shouting “URGENT!!!” are urgent, below the ${pct(data.audit.train_prevalence)} average. The panel does not reward volume.` },
    { big: `${f2(withText.cv_average_precision)} → ${f2(noText.cv_average_precision)}`, text: "Average precision with and without the ticket text. The description carries most of the signal." },
    { big: pct(base.shouting_rule.recall), text: "of urgent tickets caught by a rule on the words “urgent” and “ASAP”. The keyword rule on impact and deadlines catches " + pct(base.keyword_rule.recall) + "." },
  ].map((c) => `<div class="card insight"><div class="big">${c.big}</div><p>${c.text}</p></div>`).join("");

  // Calibration ---------------------------------------------------------------
  function drawCalibration(w) {
    const svg = $("#calib-chart");
    const size = Math.min(w, 360);
    const P = { l: 40, r: 12, t: 12, b: 34 };
    clear(svg, w, size);
    const x = linear(0, 1, P.l, size - P.r);
    const y = linear(0, 1, size - P.b, P.t);
    for (const t of [0, 0.2, 0.4, 0.6, 0.8, 1]) {
      s("line", { x1: x(t), x2: x(t), y1: P.t, y2: size - P.b, class: "grid" }, svg);
      s("line", { x1: P.l, x2: size - P.r, y1: y(t), y2: y(t), class: "grid" }, svg);
      s("text", { x: x(t), y: size - P.b + 15, "text-anchor": "middle", text: String(t) }, svg);
      s("text", { x: P.l - 6, y: y(t) + 4, "text-anchor": "end", text: String(t) }, svg);
    }
    s("text", { x: (P.l + size - P.r) / 2, y: size - 4, "text-anchor": "middle", text: "mean score in bin" }, svg);
    s("text", { x: 12, y: (P.t + size - P.b) / 2, transform: `rotate(-90 12 ${(P.t + size - P.b) / 2})`, "text-anchor": "middle", text: "actually urgent" }, svg);
    s("line", { x1: x(0), y1: y(0), x2: x(1), y2: y(1), style: "stroke:var(--axis)", "stroke-width": 1.5 }, svg);
    const bins = v.calibration.bins;
    s("path", { d: bins.map((b, i) => `${i ? "L" : "M"}${x(b.mean_score)},${y(b.urgent_rate)}`).join(""), fill: "none", class: "s-calm", "stroke-width": 2, "stroke-linejoin": "round" }, svg);
    const maxN = Math.max(...bins.map((b) => b.count));
    for (const b of bins) {
      const c = s("circle", { cx: x(b.mean_score), cy: y(b.urgent_rate), r: 4 + 7 * Math.sqrt(b.count / maxN), class: "m-calm", style: "stroke:var(--surface)", "stroke-width": 2 }, svg);
      c.addEventListener("pointermove", (e) => showTip(`<div class="tt-head">Scores ${f1(b.low)}–${f1(b.high)}</div>` +
        tipRow("Tickets", b.count) + tipRow("Mean score", f3(b.mean_score)) + tipRow("Actually urgent", pct(b.urgent_rate, 1)), e.clientX, e.clientY));
      c.addEventListener("pointerleave", hideTip);
    }
  }
  onResize($("#calib-chart").parentElement, drawCalibration);
  builders.calib = (box) => renderTable(box, [
    { key: "low", label: "From", num: true, format: f1 }, { key: "high", label: "To", num: true, format: f1 },
    { key: "count", label: "Tickets", num: true }, { key: "mean_score", label: "Mean score", num: true, format: f3 },
    { key: "urgent_rate", label: "Urgent", num: true, format: (x) => pct(x, 1) },
  ], v.calibration.bins);
  $("#calib-metrics").innerHTML = [["Expected calibration error", f3(v.calibration.ece)], ["Brier score", f3(v.brier)],
    ["Mean score vs. urgent rate", `${f3(v.calibration.mean_score)} vs ${f3(v.calibration.urgent_rate)}`]]
    .map(([k, x]) => `<dt>${k}</dt><dd>${x}</dd>`).join("");

  // Errors ---------------------------------------------------------------------
  function drawErrors(kind) {
    const list = v.errors.filter((e) => kind === "all" || e.kind === kind);
    $("#error-grid").innerHTML = list.map((e) => `
      <article class="card err">
        <div class="top"><span class="kind">${e.kind === "missed" ? ICONS.missed + "Missed urgent" : ICONS.alarm + "False alarm"}</span>
          <span class="score-pill">score ${f3(e.score)}</span></div>
        <div class="meta">${esc(e.ticket_id)} · ${esc(e.submitted_at.slice(0, 16))} · ${esc(CATEGORY_NAMES[e.category] ?? e.category)} · ${esc(CHANNEL_NAMES[e.initial_channel] ?? e.initial_channel)}</div>
        <p class="highlighted">${sentencesHTML(e.sentences)}</p>
        <p class="hyp"><b>Hypothesis.</b> ${esc(e.hypothesis)}</p>
      </article>`).join("");
  }
  document.querySelectorAll("[data-kind]").forEach((b) => b.addEventListener("click", () => {
    document.querySelectorAll("[data-kind]").forEach((x) => x.classList.toggle("on", x === b));
    drawErrors(b.dataset.kind);
  }));
  drawErrors("all");

  // Shifts -------------------------------------------------------------------
  const ref = v.shifts.find((x) => x.id === "baseline");
  const delta = (val, refVal, higherIsBetter, digits, asPct) => {
    const d = val - refVal;
    const shown = asPct ? `${d >= 0 ? "+" : "−"}${Math.abs(d * 100).toFixed(0)} pts` : signed(d, digits);
    if (Math.abs(d) < (asPct ? 0.005 : 0.05)) return `<span class="delta flat">≈ 0</span>`;
    if (higherIsBetter === null) return `<span class="delta flat">${shown}</span>`;
    const good = higherIsBetter ? d > 0 : d < 0;
    return `<span class="delta ${good ? "good" : "bad"}">${d > 0 ? ICONS.up : ICONS.down} ${shown}<span class="sr">${good ? " better" : " worse"}</span></span>`;
  };
  $("#shift-grid").innerHTML = v.shifts.filter((x) => x.id !== "baseline").map((x) => `
    <article class="card shift">
      <span class="tag">${x.kind}</span>
      <h3>${esc(x.name)}</h3>
      <p>${esc(x.note)}</p>
      <dl class="deltas">
        <dt>Recall</dt><dd class="v">${pct(x.recall)}</dd><dd>${delta(x.recall, ref.recall, true, 2, true)}</dd>
        <dt>Precision</dt><dd class="v">${pct(x.precision)}</dd><dd>${delta(x.precision, ref.precision, true, 2, true)}</dd>
        <dt>Flagged</dt><dd class="v">${pct(x.flag_rate)}</dd><dd>${delta(x.flag_rate, ref.flag_rate, null, 2, true)}</dd>
        <dt>Cost / 100</dt><dd class="v">${f1(x.cost_per_100)}</dd><dd>${delta(x.cost_per_100, ref.cost_per_100, false, 1, false)}</dd>
      </dl>
    </article>`).join("");

  // Slices ---------------------------------------------------------------------
  const groupsOrder = [["requester_type", "Requester type (not a model input)"], ["initial_channel", "Channel"], ["month", "Month"]];
  const sliceRows = [];
  for (const [key, title] of groupsOrder) {
    sliceRows.push({ header: title });
    v.slices.filter((x) => x.slice === key).forEach((x) => sliceRows.push({
      label: `${pretty(key, x.value)} · ${x.tickets} tickets, ${x.urgent} urgent`,
      value: x.enough_data ? x.recall : null,
      missing: `too few urgent tickets to report a recall (${x.urgent})`,
      cls: "m-calm",
      tip: `<div class="tt-head">${esc(pretty(key, x.value))}</div>` + tipRow("Tickets", x.tickets) + tipRow("Urgent", x.urgent) +
           tipRow("Recall", x.enough_data ? pct(x.recall) : "too few") + tipRow("Precision", x.enough_data ? pct(x.precision) : "too few") + tipRow("Flagged", pct(x.flag_rate)),
    }));
  }
  onResize($("#slice-chart").parentElement, (w) => hbars($("#slice-chart"), w, sliceRows, {
    max: 1, format: (x) => pct(x), refs: [{ value: v.recall, label: `overall ${pct(v.recall)}` }], valueW: 48,
  }));
  builders.slices = (box) => renderTable(box, [
    { key: "slice", label: "Slice" }, { key: "value", label: "Value", format: (x, r) => pretty(r.slice, x) },
    { key: "tickets", label: "Tickets", num: true }, { key: "urgent", label: "Urgent", num: true },
    { key: "recall", label: "Recall", num: true, format: (x) => (x == null ? "too few" : pct(x, 1)) },
    { key: "precision", label: "Precision", num: true, format: (x) => (x == null ? "too few" : pct(x, 1)) },
    { key: "flag_rate", label: "Flagged", num: true, format: (x) => pct(x, 1) },
  ], v.slices);

  // Timeline -------------------------------------------------------------------
  const months = data.audit.drift.monthly;
  function drawTimeline(w) {
    const svg = $("#timeline");
    const H = 250, P = { l: 36, r: 8, t: 46, b: 30 };
    clear(svg, w, H);
    const max = Math.max(...months.map((m) => m.tickets));
    const ticks = niceTicks(max, 4);
    const y = linear(0, ticks[ticks.length - 1], H - P.b, P.t);
    const slot = (w - P.l - P.r) / months.length;
    const cw = Math.min(24, slot * 0.6);
    const windows = [["train", "Train"], ["val", "Validation"], ["test", "Test · labels sealed"]];
    for (const [key, label] of windows) {
      const idx = months.map((m, i) => (m.window === key ? i : -1)).filter((i) => i >= 0);
      const x0 = P.l + idx[0] * slot, x1 = P.l + (idx[idx.length - 1] + 1) * slot;
      s("rect", { x: x0 + 2, y: 6, width: x1 - x0 - 4, height: H - P.b - 6, rx: 10, style: `fill:var(--${key === "test" ? "accent" : "ink"});opacity:${key === "test" ? 0.08 : key === "val" ? 0.05 : 0.025}` }, svg);
      s("text", { x: x0 + 12, y: 24, class: "lbl", style: "font-weight:600", text: label }, svg);
      s("text", { x: x0 + 12, y: 38, text: `${int(data.audit.windows[key])} tickets` }, svg);
    }
    ticks.forEach((t) => {
      s("line", { x1: P.l, x2: w - P.r, y1: y(t), y2: y(t), class: "grid" }, svg);
      s("text", { x: P.l - 6, y: y(t) + 4, "text-anchor": "end", text: String(t) }, svg);
    });
    months.forEach((m, i) => {
      const cx = P.l + i * slot + slot / 2;
      s("path", { d: colPath(cx - cw / 2, cw, y(0), y(m.tickets)), class: m.window === "test" ? "m-muted" : "m-calm" }, svg);
      const d = new Date(`${m.month}-01T12:00:00`);
      s("text", { x: cx, y: H - P.b + 16, "text-anchor": "middle", text: d.toLocaleDateString("en-US", { month: "short" }) + (d.getMonth() === 0 || i === 0 ? ` ${String(d.getFullYear()).slice(2)}` : "") }, svg);
      if (m.tickets === max) s("text", { x: cx, y: y(m.tickets) - 6, "text-anchor": "middle", class: "val", text: String(m.tickets) }, svg);
      if (i > 0 && !months[i - 1].ch_mobile_app && m.ch_mobile_app) {
        s("text", { x: cx, y: y(m.tickets) - 20, "text-anchor": "middle", class: "lbl", text: "mobile_app appears" }, svg);
      }
      const hit = s("rect", { x: P.l + i * slot, y: P.t, width: slot, height: H - P.t - P.b, fill: "transparent" }, svg);
      hit.addEventListener("pointermove", (e) => showTip(`<div class="tt-head">${m.month} · ${m.window}</div>` +
        tipRow("Tickets", m.tickets) + tipRow("account_access", m.cat_account_access ?? 0) + tipRow("mobile_app", m.ch_mobile_app ?? 0) +
        tipRow("Urgent rate", m.urgent_rate == null ? (m.window === "test" ? "sealed" : "not shown") : pct(m.urgent_rate, 1)), e.clientX, e.clientY));
      hit.addEventListener("pointerleave", hideTip);
    });
  }
  onResize($("#timeline").parentElement, drawTimeline);
  builders.timeline = (box) => renderTable(box, [
    { key: "month", label: "Month" }, { key: "window", label: "Window" }, { key: "tickets", label: "Tickets", num: true },
    { key: "cat_account_access", label: "account_access", num: true }, { key: "ch_mobile_app", label: "mobile_app", num: true, format: (x) => x ?? 0 },
    { key: "urgent_rate", label: "Urgent rate (train only)", num: true, format: (x) => (x == null ? "–" : pct(x, 1)) },
  ], months);

  // Cleaning, leakage, requesters ------------------------------------------------
  $("#cleaning").innerHTML = data.audit.cleaning.map((c) => `<li><b>${c.rows}</b><span>${esc(c.step)}</span></li>`).join("") +
    `<li><b>${int(data.audit.rows_clean)}</b><span>clean tickets from ${int(data.audit.rows_raw)} raw rows</span></li>`;
  onResize($("#leak-chart").parentElement, (w) => hbars($("#leak-chart"), w, data.audit.leak_scan.map((l) => ({
    label: `${l.column}${l.available_at_submission ? "" : " · excluded"}`, value: l.auc,
    cls: l.available_at_submission ? "m-calm" : "m-critical",
    tip: `<div class="tt-head">${esc(l.column)}</div>` + tipRow("AUC alone", f3(l.auc)) + tipRow("Known at submission", l.available_at_submission ? "yes" : "no") + tipRow("Verdict", l.verdict),
  })), { min: 0.5, max: 1, format: (x) => f2(x), refs: [{ value: 0.85, label: "0.85" }], valueW: 44 }));
  const r = data.audit.requesters;
  $("#requesters").innerHTML = `
    <div class="req-stat"><b>${int(r.requesters)}</b><span>requesters, median ${r.median_tickets} tickets each, up to ${r.max_tickets}</span></div>
    <div class="req-stat"><b>${pct(r.share_later_from_known)}</b><span>of validation and test tickets come from people already seen in training</span></div>
    <div class="req-stat"><b>${pct(r.purge_would_drop / r.train_rows)}</b><span>of training would be deleted by a strict requester purge</span></div>
    <p class="req-note">Urgency varies across frequent requesters by ${f3(r.urgent_rate_spread)}, against ${f3(r.spread_expected_by_chance)} expected by chance:
      people carry no urgency of their own. So: split by time, group CV folds by requester, and never use the ID as a feature.</p>`;

  // Checks and reports -----------------------------------------------------------
  renderChecks(data);
  $("#report-links").innerHTML = [["model_card", "Model card"], ["decision_note", "Decision note"], ["experiments", "Experiment table"],
    ["validation_report", "Validation report"], ["error_analysis", "Error analysis"], ["audit", "Data audit"]]
    .map(([k, label]) => `<a class="btn small ghost" href="/reports/${k}.md" target="_blank" rel="noopener">${label} ↗</a>`).join("");
  const vs = meta.versions;
  $("#versions").textContent = `Model ${meta.model.id} · threshold ${f2(meta.threshold)} · frozen ${meta.frozen_at.slice(0, 10)} · Python ${vs.python} · scikit-learn ${vs["scikit-learn"]}`;

  return builders;
}

export function renderChecks(data) {
  const used = data.test.used;
  const v = data.validation;
  const checks = [
    ["No future information in features", "Whitelist column policy plus a guard that refuses post-submission sources. Excluded: assigned_priority, handling_team, resolution_hours.", true],
    ["Reproducible split", "Time-based windows frozen in a manifest with SHA-256 fingerprints of the data and of each window's IDs.", true],
    ["At least two meaningful baselines", "Majority class and a hand-written keyword rule, both beaten on cost.", true],
    ["Complete confusion matrix", `TP ${v.tp} · FN ${v.fn} · FP ${v.fp} · TN ${v.tn} on validation, and the same for every model and slice.`, true],
    ["Threshold not chosen on the test set", "Swept on validation only. A test re-runs the pipeline with every test label flipped and gets the same threshold.", true],
    ["At least ten inspected errors", `${v.errors.length} mistakes with explanations and hypotheses in the error analysis.`, true],
    ["Intended and prohibited use", "Written in the model card: re-order the queue, never refuse or delay a ticket.", true],
    ["Test set used once", used ? `Opened on ${data.test.lock.opened_at.slice(0, 10)}. A second opening is refused.` : "Still sealed, ready for L8. The lock is written before any score is computed.", used],
  ];
  $("#check-list").innerHTML = checks.map(([title, proof, ok]) =>
    `<div class="card check">${ok ? ICONS.check : ICONS.pending}<div><h3>${title}</h3><p>${proof}</p></div></div>`).join("");
}
