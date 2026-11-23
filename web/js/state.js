// One shared threshold and cost setting, so the live replay, the lab and the
// composer always agree. Every view subscribes and redraws on change.
import { clamp } from "./util.js";

export const state = { data: null, threshold: 0.1, frozen: 0.1, costFn: 5, costFp: 1 };
const listeners = new Set();

export function on(fn) {
  listeners.add(fn);
}

export function set(patch) {
  Object.assign(state, patch);
  listeners.forEach((fn) => fn(patch));
}

export function setThreshold(t) {
  const v = Math.round(clamp(t, 0.01, 0.99) * 100) / 100;
  if (v !== state.threshold) set({ threshold: v });
}

// --- metrics computed in the browser from the 660 validation scores -------
export function confusionAt(tickets, t) {
  let tp = 0, fn = 0, fp = 0, tn = 0;
  for (const k of tickets) {
    const flag = k.s >= t;
    if (k.y) flag ? tp++ : fn++;
    else flag ? fp++ : tn++;
  }
  const n = tp + fn + fp + tn;
  const precision = tp + fp ? tp / (tp + fp) : 0;
  const recall = tp + fn ? tp / (tp + fn) : 0;
  return { tp, fn, fp, tn, n, precision, recall, flagRate: (tp + fp) / n,
           f1: precision + recall ? (2 * precision * recall) / (precision + recall) : 0 };
}

// Same rule as the Python pipeline: lowest cost averaged over ±0.02, ties to the lower threshold.
export function sweep(tickets, costFn, costFp) {
  const rows = [];
  for (let i = 1; i <= 99; i++) {
    const t = i / 100;
    const cm = confusionAt(tickets, t);
    const cost = cm.fn * costFn + cm.fp * costFp;
    rows.push({ t, ...cm, cost, per100: (100 * cost) / cm.n });
  }
  const k = 2;
  rows.forEach((r, i) => {
    let sum = 0;
    for (let j = i - k; j <= i + k; j++) sum += rows[clamp(j, 0, rows.length - 1)].per100;
    r.smoothed = sum / (2 * k + 1);
  });
  return rows;
}

export function cheapest(rows) {
  return rows.reduce((best, r) => (r.smoothed < best.smoothed - 1e-9 ? r : best), rows[0]);
}

// How many tickets are ahead of an urgent ticket in its day's queue.
export function groupDays(tickets) {
  const days = new Map();
  for (const k of tickets) {
    const d = k.t.slice(0, 10);
    if (!days.has(d)) days.set(d, []);
    days.get(d).push(k);
  }
  return [...days.values()].map((list) => list.sort((a, b) => (a.t < b.t ? -1 : 1)));
}

export function queueAt(days, t) {
  let fifo = 0, flagged = 0, urgent = 0, flags = 0;
  for (const day of days) {
    const nFlag = day.filter((k) => k.s >= t).length;
    flags += nFlag;
    let flagBefore = 0, plainBefore = 0;
    day.forEach((k, i) => {
      const flag = k.s >= t;
      if (k.y) {
        urgent++;
        fifo += i;
        flagged += flag ? flagBefore : nFlag + plainBefore;
      }
      flag ? flagBefore++ : plainBefore++;
    });
  }
  return { aheadFifo: fifo / urgent, aheadFlagged: flagged / urgent, flagsPerDay: flags / days.length,
           perDay: days.reduce((a, d) => a + d.length, 0) / days.length };
}
