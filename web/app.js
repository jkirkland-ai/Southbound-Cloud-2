// Crypto Analyzer PWA.
// Loads ./data/snapshot.json (written by the GitHub Actions analyzer),
// renders a summary grid + per-asset candle charts + a recent-alerts feed.

const SNAPSHOT_URL = "./data/snapshot.json";
const POLL_MS = 60_000;

function fmtPrice(n) {
  if (n == null || isNaN(n)) return "—";
  if (n >= 1000) return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
  if (n >= 1) return n.toLocaleString(undefined, { maximumFractionDigits: 2 });
  return n.toLocaleString(undefined, { maximumFractionDigits: 6 });
}

function fmtPct(n) {
  if (n == null || isNaN(n)) return "—";
  return `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`;
}

function renderSummary(assets) {
  const host = document.getElementById("summary");
  host.innerHTML = "";
  for (const [sym, a] of Object.entries(assets)) {
    const up = (a.change_24h_pct ?? 0) >= 0;
    const el = document.createElement("div");
    el.className = "tile";
    el.innerHTML = `
      <div class="sym">${sym}</div>
      <div class="price">$${fmtPrice(a.price_usd)}</div>
      <div class="chg ${up ? "up" : "down"}">${fmtPct(a.change_24h_pct)}</div>
    `;
    host.appendChild(el);
  }
}

function renderAlerts(list) {
  const ul = document.getElementById("alerts-list");
  ul.innerHTML = "";
  if (!list || list.length === 0) {
    const li = document.createElement("li");
    li.textContent = "No alerts yet. The analyzer runs every ~10 minutes.";
    li.style.color = "var(--muted)";
    ul.appendChild(li);
    return;
  }
  for (const a of list.slice().reverse()) {
    const li = document.createElement("li");
    li.innerHTML = `
      <strong>[${a.asset}]</strong> ${a.rule} — ${a.message}
      <span class="ts">${a.ts}</span>
    `;
    ul.appendChild(li);
  }
}

const chartRegistry = new Map();

function renderCharts(assets) {
  const host = document.getElementById("charts");

  // Create cards for any new symbols.
  for (const [sym, a] of Object.entries(assets)) {
    if (!chartRegistry.has(sym)) {
      const card = document.createElement("div");
      card.className = "chart-card";
      card.innerHTML = `
        <header><h3>${sym}</h3><span class="meta"></span></header>
        <div class="chart-el"></div>
      `;
      host.appendChild(card);
      const chartEl = card.querySelector(".chart-el");
      if (!window.LightweightCharts) {
        chartEl.innerHTML = `<div style="color:var(--muted);font-size:12px;padding:8px">
          charts library unavailable</div>`;
        chartRegistry.set(sym, { card, chart: null });
        continue;
      }
      const chart = LightweightCharts.createChart(chartEl, {
        layout: {
          background: { color: "#131926" },
          textColor: "#8893a5",
        },
        grid: {
          vertLines: { color: "#1f2838" },
          horzLines: { color: "#1f2838" },
        },
        rightPriceScale: { borderColor: "#1f2838" },
        timeScale: { borderColor: "#1f2838", timeVisible: true },
      });
      const series = chart.addCandlestickSeries({
        upColor: "#26a69a",
        downColor: "#ef5350",
        wickUpColor: "#26a69a",
        wickDownColor: "#ef5350",
        borderVisible: false,
      });
      chartRegistry.set(sym, { card, chart, series });
      new ResizeObserver(() => {
        chart.applyOptions({ width: chartEl.clientWidth });
      }).observe(chartEl);
      chart.applyOptions({ width: chartEl.clientWidth });
    }

    const reg = chartRegistry.get(sym);
    const meta = reg.card.querySelector(".meta");
    const ind = a.indicators || {};
    meta.textContent = [
      a.price_usd ? `$${fmtPrice(a.price_usd)}` : null,
      ind.rsi14_1h != null ? `RSI ${ind.rsi14_1h.toFixed(1)}` : null,
    ]
      .filter(Boolean)
      .join(" · ");
    if (reg.series && Array.isArray(a.candles_1h) && a.candles_1h.length) {
      reg.series.setData(
        a.candles_1h.map((c) => ({
          time: c.t,
          open: c.o,
          high: c.h,
          low: c.l,
          close: c.c,
        }))
      );
    }
  }
}

async function refresh() {
  try {
    const r = await fetch(`${SNAPSHOT_URL}?t=${Date.now()}`, { cache: "no-store" });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const snap = await r.json();
    document.getElementById("updated").textContent =
      "updated " + (snap.generated_at || "");
    renderSummary(snap.assets || {});
    renderCharts(snap.assets || {});
    renderAlerts(snap.recent_alerts || []);
  } catch (e) {
    document.getElementById("updated").textContent = "offline (no snapshot yet)";
  }
}

refresh();
setInterval(() => {
  if (document.visibilityState === "visible") refresh();
}, POLL_MS);
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") refresh();
});

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("./sw.js").catch(() => {});
}
