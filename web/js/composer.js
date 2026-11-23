// "Try a ticket": a live form scored by the frozen model, with a sentence-by-sentence explanation.
import { state, on } from "./state.js";
import { $, clamp, debounce, esc, f2, ICONS, s, signed, sqrtScale } from "./util.js";

export const CATEGORY_NAMES = {
  account_access: "Account access", billing: "Billing", data_request: "Data request",
  email_calendar: "Email & calendar", general_inquiry: "General inquiry", hardware: "Hardware",
  network: "Network", software: "Software",
};
export const CHANNEL_NAMES = {
  web_form: "Web form", email: "Email", phone: "Phone", chat: "Chat", walk_in: "Walk-in",
  mobile_app: "Mobile app", unknown: "Unknown",
};
const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const FIELD_NAMES = { category: "Category", initial_channel: "Channel", submitted_at: "Time", attachments_count: "Attachments" };

// Colour each sentence by how much it moves the score: orange raises, blue lowers.
export function sentencesHTML(sentences) {
  return sentences.map((x) => {
    const strength = clamp(Math.abs(x.effect) / 0.3, 0, 1);
    const mix = Math.round(8 + strength * 42);
    const hue = x.effect >= 0 ? "--urgent" : "--calm";
    const bg = Math.abs(x.effect) < 0.005 ? "transparent" : `color-mix(in srgb, var(${hue}) ${mix}%, transparent)`;
    return `<span class="sent" style="background:${bg}">${esc(x.text)}<sup>${signed(x.effect)}</sup></span>`;
  }).join(" ");
}

export function initComposer(data) {
  const form = {
    description: "", category: "network", initial_channel: "phone",
    attachments_count: 0, minutes: 9 * 60 + 40, weekday: 1,
  };
  const text = $("#c-text");

  // presets
  const presets = $("#presets");
  data.presets.forEach((p, i) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "chip";
    b.textContent = p.name;
    b.addEventListener("click", () => load(p, b));
    presets.appendChild(b);
    if (i === 0) setTimeout(() => load(p, b));
  });

  function load(p, button) {
    presets.querySelectorAll(".chip").forEach((c) => c.classList.toggle("on", c === button));
    const [h, m] = p.time.split(":").map(Number);
    Object.assign(form, { description: p.description, category: p.category, initial_channel: p.initial_channel,
                          attachments_count: p.attachments_count, minutes: h * 60 + m, weekday: p.weekday });
    text.value = form.description;
    syncAll();
    request();
  }

  function chipGroup(el, options, key, names) {
    el.replaceChildren();
    for (const value of options) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "chip";
      b.setAttribute("role", "radio");
      b.dataset.value = String(value);
      b.textContent = names ? names[value] ?? value : value;
      if (key === "initial_channel" && value === "mobile_app") b.title = "First seen in May 2026: never in training";
      b.addEventListener("click", () => {
        form[key] = typeof form[key] === "number" ? Number(value) : value;
        syncAll();
        request();
      });
      el.appendChild(b);
    }
  }
  chipGroup($("#c-category"), data.options.categories, "category", CATEGORY_NAMES);
  chipGroup($("#c-channel"), data.options.channels, "initial_channel", CHANNEL_NAMES);
  chipGroup($("#c-weekday"), [0, 1, 2, 3, 4, 5, 6], "weekday", WEEKDAYS);

  function syncChips(el, value) {
    el.querySelectorAll(".chip").forEach((c) => {
      const on = c.dataset.value === String(value);
      c.classList.toggle("on", on);
      c.setAttribute("aria-checked", on);
    });
  }

  text.addEventListener("input", () => {
    form.description = text.value;
    presets.querySelectorAll(".chip").forEach((c) => c.classList.remove("on"));
    $("#char-count").textContent = `${text.value.length} characters`;
    request();
  });
  $("#att-minus").addEventListener("click", () => { form.attachments_count = Math.max(0, form.attachments_count - 1); syncAll(); request(); });
  $("#att-plus").addEventListener("click", () => { form.attachments_count = Math.min(5, form.attachments_count + 1); syncAll(); request(); });
  $("#c-time").addEventListener("change", (e) => {
    const [h, m] = (e.target.value || "09:00").split(":").map(Number);
    form.minutes = h * 60 + m;
    syncAll();
    request();
  });

  // 24-hour dial ---------------------------------------------------------
  const dial = $("#dial");
  const C = 90, R = 62;
  const angleOf = (min) => (min / 1440) * 2 * Math.PI - Math.PI / 2;
  function buildDial() {
    dial.replaceChildren();
    s("circle", { cx: C, cy: C, r: R, fill: "none", style: "stroke:var(--grid)", "stroke-width": 12 }, dial);
    const a0 = angleOf(8 * 60), a1 = angleOf(18 * 60);
    s("path", { d: `M${C + R * Math.cos(a0)},${C + R * Math.sin(a0)} A${R},${R} 0 0 1 ${C + R * Math.cos(a1)},${C + R * Math.sin(a1)}`,
                fill: "none", style: "stroke:var(--accent);opacity:.28", "stroke-width": 12, "stroke-linecap": "round" }, dial);
    for (let h = 0; h < 24; h++) {
      const a = angleOf(h * 60), major = h % 6 === 0;
      s("line", { x1: C + (R - 12) * Math.cos(a), y1: C + (R - 12) * Math.sin(a), x2: C + (R - (major ? 20 : 16)) * Math.cos(a),
                  y2: C + (R - (major ? 20 : 16)) * Math.sin(a), style: "stroke:var(--muted)", "stroke-width": major ? 2 : 1 }, dial);
      if (major) s("text", { x: C + (R + 18) * Math.cos(a), y: C + (R + 18) * Math.sin(a) + 4, "text-anchor": "middle",
                             style: "fill:var(--muted);font:11px system-ui", text: String(h) }, dial);
    }
    dial.timeText = s("text", { x: C, y: C + 2, "text-anchor": "middle", style: "fill:var(--ink);font:700 22px system-ui" }, dial);
    dial.subText = s("text", { x: C, y: C + 20, "text-anchor": "middle", style: "fill:var(--muted);font:11px system-ui" }, dial);
    dial.handle = s("circle", { r: 9, style: "fill:var(--ink);stroke:var(--surface)", "stroke-width": 3 }, dial);
  }
  buildDial();
  const minutesFromEvent = (e) => {
    const rect = dial.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 180 - C;
    const y = ((e.clientY - rect.top) / rect.height) * 180 - C;
    let a = Math.atan2(y, x) + Math.PI / 2;
    if (a < 0) a += 2 * Math.PI;
    return (Math.round(((a / (2 * Math.PI)) * 1440) / 5) * 5) % 1440;
  };
  let turning = false;
  dial.addEventListener("pointerdown", (e) => { turning = true; dial.setPointerCapture(e.pointerId); form.minutes = minutesFromEvent(e); syncAll(); request(); });
  dial.addEventListener("pointermove", (e) => { if (turning) { form.minutes = minutesFromEvent(e); syncAll(); request(); } });
  dial.addEventListener("pointerup", () => { turning = false; });
  dial.addEventListener("pointercancel", () => { turning = false; });
  dial.addEventListener("keydown", (e) => {
    const step = e.shiftKey ? 60 : 5;
    if (["ArrowRight", "ArrowUp"].includes(e.key)) form.minutes = (form.minutes + step) % 1440;
    else if (["ArrowLeft", "ArrowDown"].includes(e.key)) form.minutes = (form.minutes - step + 1440) % 1440;
    else return;
    e.preventDefault();
    syncAll();
    request();
  });

  const hhmm = () => `${String(Math.floor(form.minutes / 60)).padStart(2, "0")}:${String(form.minutes % 60).padStart(2, "0")}`;
  function syncAll() {
    syncChips($("#c-category"), form.category);
    syncChips($("#c-channel"), form.initial_channel);
    syncChips($("#c-weekday"), form.weekday);
    $("#c-att").textContent = form.attachments_count;
    $("#c-time").value = hhmm();
    $("#char-count").textContent = `${text.value.length} characters`;
    const a = angleOf(form.minutes);
    dial.handle.setAttribute("cx", C + R * Math.cos(a));
    dial.handle.setAttribute("cy", C + R * Math.sin(a));
    dial.timeText.textContent = hhmm();
    const h = form.minutes / 60;
    dial.subText.textContent = form.weekday >= 5 || h < 8 || h >= 18 ? "after hours" : "business hours";
    dial.setAttribute("aria-valuenow", form.minutes);
    dial.setAttribute("aria-valuetext", `${hhmm()}, ${WEEKDAYS[form.weekday]}`);
  }

  // scoring ---------------------------------------------------------------
  let lastResult = null;
  let seq = 0;
  const request = debounce(async () => {
    if (!form.description.trim()) return;
    const id = ++seq;
    $("#result").classList.add("busy");
    try {
      const res = await fetch("/api/predict", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ description: form.description, category: form.category, initial_channel: form.initial_channel,
                               attachments_count: form.attachments_count, submitted_at: `2026-03-0${2 + form.weekday} ${hhmm()}` }),
      });
      const body = await res.json();
      if (id !== seq) return;
      if (!res.ok) throw new Error(body.error || "Request failed");
      lastResult = body;
      render();
    } catch (err) {
      $("#verdict").innerHTML = `<p>${esc(err.message)}</p>`;
    } finally {
      if (id === seq) $("#result").classList.remove("busy");
    }
  }, 180);

  const gauge = $("#gauge");
  const GC = { x: 120, y: 122, r: 96 };
  const g = sqrtScale(0, 1);
  const arcPoint = (v) => {
    const a = Math.PI + g.x(v) * Math.PI;
    return [GC.x + GC.r * Math.cos(a), GC.y + GC.r * Math.sin(a)];
  };
  const arc = (v0, v1) => {
    const [x0, y0] = arcPoint(v0), [x1, y1] = arcPoint(v1);
    return `M${x0},${y0} A${GC.r},${GC.r} 0 0 1 ${x1},${y1}`;
  };
  function drawGauge(score, threshold, flagged) {
    gauge.replaceChildren();
    s("path", { d: arc(0, 1), fill: "none", style: "stroke:var(--grid)", "stroke-width": 16, "stroke-linecap": "round" }, gauge);
    if (score > 0.0005) {
      s("path", { d: arc(0, score), fill: "none", style: `stroke:var(${flagged ? "--urgent" : "--calm"})`,
                  "stroke-width": 16, "stroke-linecap": "round" }, gauge);
    }
    const [tx, ty] = arcPoint(threshold);
    const a = Math.PI + g.x(threshold) * Math.PI;
    s("line", { x1: GC.x + (GC.r - 14) * Math.cos(a), y1: GC.y + (GC.r - 14) * Math.sin(a), x2: GC.x + (GC.r + 14) * Math.cos(a),
                y2: GC.y + (GC.r + 14) * Math.sin(a), style: "stroke:var(--ink)", "stroke-width": 2.5, "stroke-linecap": "round" }, gauge);
    s("text", { x: tx - 6, y: ty - 18, "text-anchor": "end", style: "fill:var(--ink-2);font:600 11px system-ui", text: `flag ≥ ${f2(threshold)}` }, gauge);
    for (const v of [0, 0.5, 1]) {
      const [x, y] = arcPoint(v);
      s("text", { x: v === 0 ? x : v === 1 ? x : x, y: y + (v === 0.5 ? -14 : 18), "text-anchor": "middle",
                  style: "fill:var(--muted);font:11px system-ui", text: String(v) }, gauge);
    }
  }

  function render() {
    if (!lastResult) return;
    const r = lastResult;
    const t = state.threshold;
    const flagged = r.score >= t;
    drawGauge(r.score, t, flagged);
    $("#g-score").textContent = f2(r.score);
    $("#verdict").innerHTML = flagged
      ? `<span class="badge" style="color:var(--ink)"><span style="color:var(--serious)">${ICONS.flag}</span>Suggest urgent review</span><p>A suggestion to read this ticket first. Staff decide.</p>`
      : `<span class="badge">${ICONS.queue}Normal queue</span><p>Handled in its usual turn, exactly as without the model.</p>`;
    $("#explained").innerHTML = sentencesHTML(r.sentences);
    $("#field-effects").innerHTML = r.fields.map((f) => {
      const w = clamp(Math.abs(f.effect) / 0.5, 0, 1) * 50;
      const left = f.effect >= 0 ? 50 : 50 - w;
      const name = f.field === "category" ? CATEGORY_NAMES[f.value] : f.field === "initial_channel" ? CHANNEL_NAMES[f.value] : f.value;
      return `<span class="fe-label">${FIELD_NAMES[f.field]} · <b>${esc(name)}</b></span>
        <span class="fe-bar"><i style="left:${left}%;width:${Math.max(w, 0.6)}%;background:var(${f.effect >= 0 ? "--urgent" : "--calm"})"></i></span>
        <span class="fe-val">${signed(f.effect)}</span>`;
    }).join("");
  }

  syncAll();
  on((patch) => { if ("threshold" in patch) render(); });
  return { rerender: render };
}
