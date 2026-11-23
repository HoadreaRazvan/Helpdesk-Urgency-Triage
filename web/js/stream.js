// Hero: the validation window replayed in time. Each ticket enters on the right
// at the height of its urgency score and drifts left. Tickets above the line are
// flagged. Drag anywhere on the canvas to move the threshold for every view.
import { state, on, setThreshold } from "./state.js";
import { $, clamp, cssVar, esc, f2, reduceMotion, showTip, hideTip, tipRow } from "./util.js";

const TRAVEL_S = 11;          // seconds a ticket takes to cross the canvas
const DAY_S = [2.2, 0.7];      // seconds of replay per calendar day, at 1× and 4×
const PAD = { l: 44, r: 16, t: 16, b: 24 };

export function initStream(tickets) {
  const canvas = $("#stream");
  const ctx = canvas.getContext("2d");
  const ordered = [...tickets].sort((a, b) => (a.t < b.t ? -1 : 1));
  const first = Date.parse(ordered[0].t.replace(" ", "T"));
  const times = ordered.map((k) => (Date.parse(k.t.replace(" ", "T")) - first) / 86400000);
  let W = 0, H = 0, dpr = 1, colors = {};
  let playing = !reduceMotion();
  let speed = 0;
  let clock = 0;          // replay time in days since the first ticket
  let cursor = 0;         // next ticket to spawn
  let live = [];          // particles on screen
  let last = performance.now();
  let dragging = false;
  let hover = null;

  const yOf = (score) => PAD.t + (1 - Math.sqrt(clamp(score, 0, 1))) * (H - PAD.t - PAD.b);
  const scoreOf = (y) => clamp(1 - (y - PAD.t) / (H - PAD.t - PAD.b), 0, 1) ** 2;

  function readColors() {
    colors = { surface: cssVar("--surface"), ink: cssVar("--ink"), ink2: cssVar("--ink-2"), muted: cssVar("--muted"),
               grid: cssVar("--grid"), urgent: cssVar("--urgent"), calm: cssVar("--calm"), accent: cssVar("--accent") };
  }

  function resize() {
    const rect = canvas.getBoundingClientRect();
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    W = rect.width; H = rect.height;
    canvas.width = Math.round(W * dpr);
    canvas.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    if (!playing) draw();
  }

  function spawn() {
    while (cursor < ordered.length && times[cursor] <= clock) {
      const k = ordered[cursor];
      live.push({ k, born: clock, x: W - PAD.r, flaggedAtBirth: k.s >= state.threshold });
      cursor++;
    }
    if (cursor >= ordered.length && live.length === 0) {  // loop the replay
      clock = 0; cursor = 0;
    }
  }

  function step(dt) {
    clock += dt / DAY_S[speed];
    spawn();
    const v = (W - PAD.l - PAD.r) / TRAVEL_S;
    for (const p of live) p.x -= v * dt;
    live = live.filter((p) => p.x > PAD.l - 6);
  }

  function counters() {
    let caught = 0, missed = 0, alarms = 0;
    for (const p of live) {
      const flag = p.k.s >= state.threshold;
      if (p.k.y && flag) caught++;
      else if (p.k.y) missed++;
      else if (flag) alarms++;
    }
    const day = ordered[Math.max(0, cursor - 1)].t.slice(0, 10);
    $("#stream-clock").textContent = new Date(`${day}T12:00:00`).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "long", year: "numeric" });
    $("#stream-counters").innerHTML =
      `<span>On screen: <b>${caught}</b> caught</span><span><b>${missed}</b> missed</span><span><b>${alarms}</b> false alarms</span>`;
  }

  function draw() {
    ctx.clearRect(0, 0, W, H);
    const ty = yOf(state.threshold);
    // flagged zone
    ctx.fillStyle = colors.accent;
    ctx.globalAlpha = 0.07;
    ctx.fillRect(PAD.l, PAD.t, W - PAD.l - PAD.r, ty - PAD.t);
    ctx.globalAlpha = 1;
    // grid + score ticks
    ctx.font = "11px system-ui, sans-serif";
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    for (const v of [0, 0.05, 0.2, 0.5, 1]) {
      const y = yOf(v);
      ctx.strokeStyle = colors.grid;
      ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(PAD.l, Math.round(y) + 0.5); ctx.lineTo(W - PAD.r, Math.round(y) + 0.5); ctx.stroke();
      ctx.fillStyle = colors.muted;
      ctx.fillText(v === 0 ? "0" : String(v), PAD.l - 8, y);
    }
    ctx.save();
    ctx.translate(12, (H - PAD.b + PAD.t) / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.textAlign = "center";
    ctx.fillText("urgency score", 0, 0);
    ctx.restore();
    // zone labels
    ctx.textAlign = "left";
    ctx.font = "600 11px ui-monospace, monospace";
    ctx.fillStyle = colors.ink2;
    if (ty - PAD.t > 22) ctx.fillText("URGENT REVIEW", PAD.l + 10, PAD.t + 12);
    if (H - PAD.b - ty > 22) ctx.fillText("NORMAL QUEUE", PAD.l + 10, H - PAD.b - 10);
    // particles
    for (const p of live) {
      const y = yOf(p.k.s);
      const flag = p.k.s >= state.threshold;
      const fade = clamp((p.x - PAD.l) / 60, 0, 1);
      const age = (clock - p.born) * DAY_S[speed];
      ctx.globalAlpha = fade;
      if (flag && age < 0.9) {  // a pulse ring when a flagged ticket arrives
        ctx.strokeStyle = p.k.y ? colors.urgent : colors.calm;
        ctx.globalAlpha = fade * (1 - age / 0.9);
        ctx.lineWidth = 2;
        ctx.beginPath(); ctx.arc(p.x, y, 5 + age * 18, 0, Math.PI * 2); ctx.stroke();
        ctx.globalAlpha = fade;
      }
      ctx.fillStyle = colors.surface;
      ctx.beginPath(); ctx.arc(p.x, y, 6, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = p.k.y ? colors.urgent : colors.calm;
      ctx.beginPath(); ctx.arc(p.x, y, 4.2, 0, Math.PI * 2); ctx.fill();
      if (hover === p) {
        ctx.strokeStyle = colors.ink; ctx.lineWidth = 2;
        ctx.beginPath(); ctx.arc(p.x, y, 7, 0, Math.PI * 2); ctx.stroke();
      }
    }
    ctx.globalAlpha = 1;
    // threshold line + handle
    ctx.strokeStyle = colors.ink;
    ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(PAD.l, ty); ctx.lineTo(W - PAD.r, ty); ctx.stroke();
    const label = `threshold ${f2(state.threshold)}${state.threshold === state.frozen ? " · frozen" : ""}`;
    ctx.font = "600 12px system-ui, sans-serif";
    const tw = ctx.measureText(label).width + 20;
    const hx = W - PAD.r - tw;
    const hy = clamp(ty - 13, 2, H - 28);
    ctx.fillStyle = colors.ink;
    ctx.beginPath(); ctx.roundRect(hx, hy, tw, 26, 13); ctx.fill();
    ctx.fillStyle = colors.surface;
    ctx.textAlign = "center";
    ctx.fillText(label, hx + tw / 2, hy + 13.5);
  }

  function frame(now) {
    const dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    if (playing) { step(dt); counters(); }
    draw();
    requestAnimationFrame(frame);
  }

  // interaction: drag the threshold, hover a ticket
  function pointerScore(e) {
    const rect = canvas.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  }
  canvas.addEventListener("pointerdown", (e) => {
    dragging = true;
    canvas.setPointerCapture(e.pointerId);
    setThreshold(scoreOf(pointerScore(e).y));
  });
  canvas.addEventListener("pointermove", (e) => {
    const p = pointerScore(e);
    if (dragging) { setThreshold(scoreOf(p.y)); hideTip(); return; }
    let best = null, bestD = 14;
    for (const q of live) {
      const d = Math.hypot(q.x - p.x, yOf(q.k.s) - p.y);
      if (d < bestD) { best = q; bestD = d; }
    }
    hover = best;
    if (best) {
      const k = best.k;
      showTip(`<div class="tt-head"><i class="dot ${k.y ? "urgent" : "calm"}"></i>${esc(k.id)} · ${k.y ? "urgent" : "not urgent"}</div>` +
        tipRow("Score", f2(k.s)) + tipRow("Flagged", k.s >= state.threshold ? "yes" : "no") +
        `<div class="tt-text">${esc(k.text.slice(0, 160))}${k.text.length > 160 ? "…" : ""}</div>`, e.clientX, e.clientY);
    } else hideTip();
  });
  const end = () => { dragging = false; };
  canvas.addEventListener("pointerup", end);
  canvas.addEventListener("pointercancel", end);
  canvas.addEventListener("pointerleave", () => { hover = null; hideTip(); });

  const playBtn = $("#stream-play");
  const syncPlay = () => {
    playBtn.textContent = playing ? "❚❚" : "▶";
    playBtn.setAttribute("aria-label", playing ? "Pause replay" : "Play replay");
  };
  playBtn.addEventListener("click", () => { playing = !playing; syncPlay(); });
  $("#stream-speed").addEventListener("click", (e) => {
    speed = 1 - speed;
    e.currentTarget.textContent = speed ? "4×" : "1×";
  });
  syncPlay();

  readColors();
  new ResizeObserver(resize).observe(canvas);
  resize();
  if (!playing) {  // reduced motion: show a static snapshot of the first days
    clock = 5; spawn();
    const v = (W - PAD.l - PAD.r) / TRAVEL_S;
    for (const p of live) p.x = W - PAD.r - (clock - times[ordered.indexOf(p.k)]) * DAY_S[0] * v;
    live = live.filter((p) => p.x > PAD.l);
    counters();
  }
  requestAnimationFrame(frame);
  on(() => { if (!playing) counters(); });
  return {
    refreshColors: () => { readColors(); draw(); },
    toggle: () => { playing = !playing; syncPlay(); },
  };
}
