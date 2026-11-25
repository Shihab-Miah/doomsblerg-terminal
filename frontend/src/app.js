const state = {
  ticker: "AAPL",
  bars: [],
  technicals: null,
  worldData: null,
};

const $ = (id) => document.getElementById(id);

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function fmtMoney(v) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return "--";
  return `$${Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function fmtNum(v, suffix = "") {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return "--";
  return `${Number(v).toFixed(2)}${suffix}`;
}

async function apiGet(path) {
  const res = await fetch(path);
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

async function apiPost(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

function switchView(viewName) {
  for (const btn of document.querySelectorAll(".tab-btn")) {
    btn.classList.toggle("active", btn.dataset.view === viewName);
  }
  for (const sec of document.querySelectorAll(".view-grid")) {
    sec.classList.toggle("active", sec.id === `view-${viewName}`);
  }
}

function renderKV(container, items) {
  container.replaceChildren();
  for (const [label, val, cls] of items) {
    const card = el("div", "kv-item");
    card.appendChild(el("span", "", label));
    card.appendChild(el("strong", cls || "", val ?? "--"));
    container.appendChild(card);
  }
}

/* ── Candlestick & Technical Canvas Chart ── */
function drawPriceChart(bars, technicals) {
  const canvas = $("price-canvas");
  const ctx = canvas.getContext("2d");
  const W = canvas.width;
  const H = canvas.height;
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = "#070b11";
  ctx.fillRect(0, 0, W, H);

  if (!bars || bars.length === 0) {
    ctx.fillStyle = "#98abc4";
    ctx.fillText("No historical bars available.", 20, 40);
    return;
  }

  const pad = { top: 20, right: 64, bottom: 26, left: 16 };
  const plotW = W - pad.left - pad.right;
  const plotH = H - pad.top - pad.bottom;

  let minPx = Infinity;
  let maxPx = -Infinity;
  for (const b of bars) {
    const lo = b.low ?? b.close;
    const hi = b.high ?? b.close;
    if (lo < minPx) minPx = lo;
    if (hi > maxPx) maxPx = hi;
  }
  if (technicals?.suggested_atr_stop_loss) minPx = Math.min(minPx, technicals.suggested_atr_stop_loss);
  if (technicals?.suggested_atr_target) maxPx = Math.max(maxPx, technicals.suggested_atr_target);
  const span = Math.max(maxPx - minPx, 0.01);
  minPx -= span * 0.06;
  maxPx += span * 0.06;

  const yOf = (px) => pad.top + ((maxPx - px) / (maxPx - minPx)) * plotH;
  const stepX = plotW / bars.length;

  // Grid lines
  ctx.strokeStyle = "#192434";
  ctx.lineWidth = 1;
  ctx.font = "11px ui-monospace, monospace";
  for (let i = 0; i <= 4; i++) {
    const px = minPx + ((maxPx - minPx) * i) / 4;
    const y = yOf(px);
    ctx.beginPath();
    ctx.moveTo(pad.left, y);
    ctx.lineTo(W - pad.right, y);
    ctx.stroke();
    ctx.fillStyle = "#8aa0bd";
    ctx.fillText(px.toFixed(2), W - pad.right + 6, y + 4);
  }

  // Candles
  const bodyW = Math.max(2, Math.min(12, stepX * 0.65));
  bars.forEach((b, idx) => {
    const x = pad.left + idx * stepX + stepX * 0.5;
    const o = b.open ?? b.close;
    const c = b.close;
    const h = b.high ?? Math.max(o, c);
    const l = b.low ?? Math.min(o, c);
    const up = c >= o;
    ctx.strokeStyle = up ? "#22c55e" : "#ef4444";
    ctx.fillStyle = up ? "#22c55e" : "#ef4444";

    ctx.beginPath();
    ctx.moveTo(x, yOf(h));
    ctx.lineTo(x, yOf(l));
    ctx.stroke();

    const yTop = yOf(Math.max(o, c));
    const yBot = yOf(Math.min(o, c));
    ctx.fillRect(x - bodyW / 2, yTop, bodyW, Math.max(1.5, yBot - yTop));
  });

  // ATR Stop & Target reference lines
  const drawLevel = (px, color, label) => {
    if (!px) return;
    const y = yOf(px);
    ctx.save();
    ctx.setLineDash([5, 4]);
    ctx.strokeStyle = color;
    ctx.beginPath();
    ctx.moveTo(pad.left, y);
    ctx.lineTo(W - pad.right, y);
    ctx.stroke();
    ctx.fillStyle = color;
    ctx.fillText(`${label} $${Number(px).toFixed(2)}`, pad.left + 6, y - 4);
    ctx.restore();
  };
  drawLevel(technicals?.suggested_atr_stop_loss, "#f59e0b", "ATR Stop");
  drawLevel(technicals?.suggested_atr_target, "#38bdf8", "Target");
}

function attachChartHover() {
  const canvas = $("price-canvas");
  canvas.addEventListener("mousemove", (e) => {
    if (!state.bars.length) return;
    const rect = canvas.getBoundingClientRect();
    const relX = ((e.clientX - rect.left) / rect.width) * canvas.width;
    const plotW = canvas.width - 80;
    const idx = Math.floor(((relX - 16) / plotW) * state.bars.length);
    const b = state.bars[Math.max(0, Math.min(state.bars.length - 1, idx))];
    if (b) {
      $("chart-readout").textContent = `${b.date} | O ${b.open} H ${b.high} L ${b.low} C ${b.close} Vol ${Number(b.volume || 0).toLocaleString()}`;
    }
  });
}

/* ── Load Stock Workspace ── */
async function loadStock(ticker, range = "3mo") {
  state.ticker = ticker.toUpperCase().trim() || "AAPL";
  $("ticker-input").value = state.ticker;
  $("bt-ticker").value = state.ticker;
  $("ord-symbol").value = state.ticker;
  $("kpi-ticker").textContent = state.ticker;

  try {
    const [quote, over, hist, scoreData] = await Promise.all([
      apiGet(`/api/stock/${state.ticker}/quote`),
      apiGet(`/api/stock/${state.ticker}/overview`),
      apiGet(`/api/stock/${state.ticker}/history?range=${encodeURIComponent(range)}`),
      apiGet(`/api/stock/${state.ticker}/score`),
    ]);

    const dossier = scoreData.compact_ai_dossier || {};
    const fund = scoreData.details?.fundamentals || {};
    const tech = scoreData.details?.technicals || {};
    state.bars = hist.history || [];
    state.technicals = tech;

    $("kpi-name").textContent = over.name ? `${over.name} (${over.sector || "Equity"})` : state.ticker;
    $("kpi-price").textContent = fmtMoney(quote.price);
    $("kpi-sources").textContent = `${quote.sources_agreed || 1} feeds (${quote.confidence || "live"})`;
    $("kpi-quant").textContent = `${dossier.quant_score_100 ?? "--"} / 100`;
    $("kpi-signal").textContent = dossier.quant_signal || "--";
    $("kpi-dcf").textContent = fmtMoney(dossier.dcf_fair_value);
    const gap = dossier.dcf_upside_pct;
    $("kpi-dcf-gap").textContent = gap !== undefined && gap !== null ? `${gap > 0 ? "+" : ""}${gap}% vs Price` : "N/A";
    $("kpi-levels").textContent = `${fmtMoney(dossier.stop_loss)} / ${fmtMoney(dossier.target_price)}`;
    $("kpi-trend").textContent = `${tech.trend || "--"} · RSI ${tech.rsi_14 ?? "--"}`;

    $("chart-title").textContent = `${state.ticker} Daily Candlesticks (${range.toUpperCase()})`;
    drawPriceChart(state.bars, tech);

    renderKV($("fundamentals-body"), [
      ["Market Cap", over.market_cap ? `$${(Number(over.market_cap) / 1e9).toFixed(1)}B` : "--"],
      ["WACC Discount", `${dossier.wacc_pct ?? "--"}%`],
      ["Piotroski F-Score", `${dossier.piotroski_f ?? "--"} / 9`, (dossier.piotroski_f || 0) >= 7 ? "bull" : ""],
      ["Altman Z-Score", `${dossier.altman_z ?? "--"} (${dossier.altman_zone || ""})`],
      ["Sharpe Ratio", `${dossier.sharpe ?? "--"}`],
      ["Max Drawdown 1Y", `${dossier.max_drawdown_pct ?? "--"}%`, "bear"],
      ["Beta vs SPY", `${dossier.beta ?? "--"}`],
      ["MACD Trend", `${tech.macd?.trend ?? "--"}`],
    ]);

    const sentBox = $("sentiment-body");
    sentBox.replaceChildren();
    const topCard = el("div", "list-card");
    topCard.appendChild(el("strong", "", `News Sentiment: ${dossier.news_sentiment ?? 0} | Insider Signal: ${dossier.insider_signal || "neutral"}`));
    const rec = dossier.analyst_ratings;
    if (rec) {
      topCard.appendChild(el("small", "muted", `Wall St Ratings — StrongBuy: ${rec.strongBuy ?? 0}, Buy: ${rec.buy ?? 0}, Hold: ${rec.hold ?? 0}, Sell: ${(rec.sell || 0) + (rec.strongSell || 0)}`));
    }
    sentBox.appendChild(topCard);
    for (const h of dossier.top_headlines || []) {
      const item = el("div", "list-card");
      item.appendChild(el("span", "", h));
      sentBox.appendChild(item);
    }
  } catch (err) {
    $("kpi-name").textContent = `Error: ${err.message}`;
  }
}

/* ── 8-Agent AI Council ── */
async function runDebate() {
  switchView("council");
  const banner = $("verdict-banner");
  const grid = $("agents-grid");
  banner.replaceChildren(el("p", "muted", `Convening 8 agents across Google, Groq, OpenRouter & Kilo for ${state.ticker}... (takes ~10-18s)`));
  grid.replaceChildren();
  try {
    const res = await apiGet(`/api/stock/${state.ticker}/debate`);
    const v = res.verdict || {};
    const action = String(v.action || "HOLD").toUpperCase();
    const cls = action.includes("BUY") ? "badge-buy" : (action.includes("SELL") ? "badge-sell" : "badge-hold");

    banner.replaceChildren();
    const row = el("div", "panel-actions");
    row.appendChild(el("span", `verdict-badge ${cls}`, `${res.ticker}: ${action} (${v.confidence_pct ?? "--"}% confidence)`));
    row.appendChild(el("span", "pill pill-ok", `Entry ${fmtMoney(v.computed_entry_price)} | Stop ${fmtMoney(v.computed_stop_loss)} | Target ${fmtMoney(v.computed_target_price)}`));
    banner.appendChild(row);
    banner.appendChild(el("p", "", v.plain_english_verdict || ""));
    if (v.biggest_risk) banner.appendChild(el("small", "warn", `Biggest Risk: ${v.biggest_risk}`));

    const labels = [
      ["3_fundamental_auditor", "Fundamental SEC Auditor", "note"],
      ["4_macro_economist", "Macro Economist", "note"],
      ["5_sentiment_scout", "Sentiment & Insider Scout", "note"],
      ["6_bull_advocate", "Bull Case Advocate", "case"],
      ["7_bear_advocate", "Bear Case Advocate", "case"],
    ];
    for (const [key, title, field] of labels) {
      const ag = res.agents?.[key];
      if (!ag) continue;
      const card = el("div", "list-card");
      card.appendChild(el("strong", "", title));
      card.appendChild(el("small", "muted", ag.provider || ""));
      card.appendChild(el("p", "", ag[field] || ""));
      grid.appendChild(card);
    }
    const geoCard = el("div", "list-card");
    geoCard.appendChild(el("strong", "", "Geospatial Physical-World Scout"));
    const geoSigs = res.agents?.["2_geospatial_scout_python"]?.physical_world_signals || [];
    geoCard.appendChild(el("p", "", geoSigs.join(" · ") || "No elevated physical-world risk."));
    grid.appendChild(geoCard);
  } catch (err) {
    banner.replaceChildren(el("p", "bear", `Council failed: ${err.message}`));
  }
}

async function runSecAudit() {
  switchView("council");
  const banner = $("verdict-banner");
  banner.replaceChildren(el("p", "muted", `Auditing latest SEC 10-K / 10-Q for ${state.ticker}...`));
  try {
    const res = await apiGet(`/api/stock/${state.ticker}/audit`);
    const a = res.audit || {};
    banner.replaceChildren();
    banner.appendChild(el("strong", "", `SEC ${res.form} (${res.filing_date}) — Overall Risk: ${String(a.overall_risk_level || "").toUpperCase()} (${res.provider_used})`));
    banner.appendChild(el("p", "", a.plain_english_summary || ""));
    for (const flag of a.red_flags || []) {
      banner.appendChild(el("small", "bear", `Red Flag: ${flag}`));
    }
    for (const cat of a.key_strengths_or_catalysts || []) {
      banner.appendChild(el("small", "bull", `Catalyst: ${cat}`));
    }
  } catch (err) {
    banner.replaceChildren(el("p", "bear", `Audit failed: ${err.message}`));
  }
}

/* ── God's Eye Map Canvas ── */
function drawWorldMap(data) {
  const canvas = $("world-canvas");
  const ctx = canvas.getContext("2d");
  const W = canvas.width;
  const H = canvas.height;
  ctx.fillStyle = "#060b12";
  ctx.fillRect(0, 0, W, H);

  const proj = (lon, lat) => [((Number(lon) + 180) / 360) * W, ((90 - Number(lat)) / 180) * H];

  // Lat/Lon graticule
  ctx.strokeStyle = "#121f30";
  ctx.lineWidth = 1;
  for (let lon = -150; lon <= 150; lon += 30) {
    const [x] = proj(lon, 0);
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, H);
    ctx.stroke();
  }
  for (let lat = -60; lat <= 60; lat += 30) {
    const [, y] = proj(0, lat);
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(W, y);
    ctx.stroke();
  }

  // Lightweight continent bounding outlines for clean zero-CDN orientation
  const continents = [
    [[-168, 66], [-140, 70], [-85, 62], [-55, 50], [-80, 25], [-105, 18], [-125, 38], [-168, 66]],
    [[-80, 12], [-35, -6], [-40, -23], [-68, -54], [-76, -42], [-80, 12]],
    [[-10, 36], [38, 36], [42, 68], [-10, 62], [-10, 36]],
    [[-17, 35], [35, 32], [51, 12], [35, -25], [19, -35], [-17, 15], [-17, 35]],
    [[35, 38], [65, 70], [170, 66], [140, 35], [105, 2], [75, 8], [45, 14], [35, 38]],
    [[113, -12], [154, -26], [145, -39], [115, -34], [113, -12]],
  ];
  ctx.fillStyle = "#101c2c";
  ctx.strokeStyle = "#253952";
  for (const poly of continents) {
    ctx.beginPath();
    poly.forEach(([lon, lat], i) => {
      const [x, y] = proj(lon, lat);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
  }

  // Chokepoints
  for (const cp of data.maritime?.chokepoint_markers || []) {
    const [x, y] = proj(cp.longitude, cp.latitude);
    ctx.fillStyle = "#22d3ee";
    ctx.fillRect(x - 3, y - 3, 6, 6);
  }
  // Wildfires
  for (const f of data.wildfires?.points || []) {
    const [x, y] = proj(f.longitude, f.latitude);
    ctx.fillStyle = "rgba(249, 115, 22, 0.85)";
    ctx.beginPath();
    ctx.arc(x, y, 3, 0, Math.PI * 2);
    ctx.fill();
  }
  // Earthquakes
  for (const q of data.earthquakes?.points || []) {
    const [x, y] = proj(q.longitude, q.latitude);
    const r = Math.max(3, (Number(q.magnitude) || 4.5) * 1.4);
    ctx.strokeStyle = "#ef4444";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.stroke();
  }
  // Aviation aircraft points
  for (const ac of data.aviation?.points || []) {
    if (ac.lat == null || ac.lon == null) continue;
    const [x, y] = proj(ac.lon, ac.lat);
    ctx.fillStyle = "#4ade80";
    ctx.beginPath();
    ctx.arc(x, y, 2.2, 0, Math.PI * 2);
    ctx.fill();
  }
}

async function loadGodsEye() {
  const hub = $("geo-hub-select").value;
  const list = $("geo-triggers");
  list.replaceChildren(el("p", "muted", "Scanning satellite fires, earthquakes, flights, and energy inventories..."));
  try {
    const data = await apiGet(`/api/gods-eye?region=${encodeURIComponent(hub)}&ais=false`);
    state.worldData = data;
    drawWorldMap(data);
    list.replaceChildren();
    for (const trig of data.trading_signal_triggers || []) {
      const card = el("div", "list-card");
      card.appendChild(el("strong", trig.severity === "high" ? "bear" : "warn", `[${String(trig.severity || "low").toUpperCase()}] ${trig.signal}`));
      card.appendChild(el("small", "muted", trig.market_implication));
      if (trig.watch_tickers?.length) {
        const chips = el("div", "chip-row");
        for (const sym of trig.watch_tickers) {
          const b = el("button", "chip", sym);
          b.type = "button";
          b.addEventListener("click", () => {
            switchView("stock");
            loadStock(sym);
          });
          chips.appendChild(b);
        }
        card.appendChild(chips);
      }
      list.appendChild(card);
    }
  } catch (err) {
    list.replaceChildren(el("p", "bear", `Geo scan error: ${err.message}`));
  }
}

/* ── Macro, Yield Curve, FX & Commodities ── */
async function loadMacroFx() {
  try {
    const [macro, yc, fx, coms] = await Promise.all([
      apiGet("/api/macro?q=dashboard"),
      apiGet("/api/yield-curve"),
      apiGet("/api/fx?base=USD"),
      apiGet("/api/commodities"),
    ]);

    // Yield curve plot
    const canvas = $("curve-canvas");
    const ctx = canvas.getContext("2d");
    const W = canvas.width;
    const H = canvas.height;
    ctx.fillStyle = "#070b11";
    ctx.fillRect(0, 0, W, H);
    const entries = Object.entries(yc.yields_pct || {}).filter(([, v]) => typeof v === "number");
    if (entries.length) {
      const vals = entries.map(([, v]) => v);
      const lo = Math.min(...vals) - 0.3;
      const hi = Math.max(...vals) + 0.3;
      const pad = 28;
      ctx.strokeStyle = yc.curve_inverted ? "#ef4444" : "#38bdf8";
      ctx.lineWidth = 2.5;
      ctx.font = "10px ui-monospace, monospace";
      ctx.beginPath();
      entries.forEach(([tenor, val], i) => {
        const x = pad + (i / Math.max(1, entries.length - 1)) * (W - pad * 2);
        const y = H - pad - ((val - lo) / Math.max(0.01, hi - lo)) * (H - pad * 2);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
        ctx.fillStyle = "#98abc4";
        ctx.fillText(tenor, x - 12, H - 8);
      });
      ctx.stroke();
      ctx.fillStyle = yc.curve_inverted ? "#ef4444" : "#22c55e";
      ctx.fillText(`10Y-2Y: ${yc.spread_10y_minus_2y ?? "--"}% (${yc.curve_inverted ? "INVERTED" : "Normal"})`, 14, 18);
    }

    renderKV($("macro-grid"), [
      ["Fed Funds Rate", `${macro["interest rate"]?.value ?? "--"}%`],
      ["SOFR Overnight", `${macro.sofr?.value ?? "--"}%`],
      ["Unemployment", `${macro.unemployment?.value ?? "--"}%`],
      ["VIX Fear Index", `${macro.vix?.value ?? "--"}`],
      ["HY Credit Spread", `${macro["high yield spread"]?.value ?? "--"}%`],
      ["10Y - 3M Spread", `${yc.spread_10y_minus_3m ?? "--"}%`, yc.curve_inverted ? "bear" : "bull"],
    ]);

    renderKV($("fx-box"), Object.entries(fx.rates || {}).map(([ccy, rate]) => [`USD / ${ccy}`, `${rate}`]));

    const tbody = $("commodities-tbody");
    tbody.replaceChildren();
    for (const c of coms.commodities || []) {
      const tr = document.createElement("tr");
      tr.appendChild(Object.assign(el("td", "", c.name), { dataset: { label: "Commodity" } }));
      tr.appendChild(Object.assign(el("td", "", c.price ?? "--"), { dataset: { label: "Price" } }));
      const chg = c.change_pct;
      const chgTd = el("td", chg >= 0 ? "bull" : "bear", chg !== null && chg !== undefined ? `${chg > 0 ? "+" : ""}${chg}%` : "--");
      chgTd.dataset.label = "Day Chg";
      tr.appendChild(chgTd);
      tr.appendChild(Object.assign(el("td", "", c.unit || ""), { dataset: { label: "Unit" } }));
      tbody.appendChild(tr);
    }
  } catch (err) {
    renderKV($("macro-grid"), [["Error", err.message, "bear"]]);
  }
}

/* ── Backtester & Alpaca Paper Broker ── */
function drawBacktestChart(curve) {
  const canvas = $("backtest-canvas");
  const ctx = canvas.getContext("2d");
  const W = canvas.width;
  const H = canvas.height;
  ctx.fillStyle = "#070b11";
  ctx.fillRect(0, 0, W, H);
  if (!curve || curve.length < 2) return;

  const eqs = curve.map((p) => p.equity);
  const lo = Math.min(...eqs);
  const hi = Math.max(...eqs);
  const pad = 22;
  ctx.strokeStyle = "#22c55e";
  ctx.lineWidth = 2;
  ctx.beginPath();
  curve.forEach((p, i) => {
    const x = pad + (i / (curve.length - 1)) * (W - pad * 2);
    const y = H - pad - ((p.equity - lo) / Math.max(1, hi - lo)) * (H - pad * 2);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();
  ctx.fillStyle = "#98abc4";
  ctx.font = "11px ui-monospace, monospace";
  ctx.fillText(`End Equity: ${fmtMoney(eqs[eqs.length - 1])}`, 14, 16);
}

async function runBacktestForm(e) {
  if (e) e.preventDefault();
  const sym = $("bt-ticker").value.trim().toUpperCase() || "AAPL";
  const strat = $("bt-strategy").value;
  const range = $("bt-range").value;
  renderKV($("backtest-summary"), [["Status", "Running simulation..."]]);
  try {
    const res = await apiGet(`/api/backtest?ticker=${encodeURIComponent(sym)}&strategy=${encodeURIComponent(strat)}&range=${encodeURIComponent(range)}`);
    drawBacktestChart(res.equity_curve);
    renderKV($("backtest-summary"), [
      ["Strategy Return", `${res.total_return_pct > 0 ? "+" : ""}${res.total_return_pct}%`, res.total_return_pct >= 0 ? "bull" : "bear"],
      ["Buy & Hold", `${res.buy_and_hold_return_pct > 0 ? "+" : ""}${res.buy_and_hold_return_pct}%`],
      ["Win Rate", `${res.win_rate_pct}%`],
      ["Profit Factor", `${res.profit_factor}`],
      ["Sharpe", `${res.sharpe_ratio ?? "--"}`],
      ["Max Drawdown", `${res.max_drawdown_pct ?? "--"}%`, "bear"],
    ]);
    const tbody = $("bt-trades-tbody");
    tbody.replaceChildren();
    for (const t of res.recent_trades || []) {
      const tr = document.createElement("tr");
      tr.appendChild(Object.assign(el("td", "", `${t.entry_date} @ ${t.entry_price}`), { dataset: { label: "Entry" } }));
      tr.appendChild(Object.assign(el("td", "", `${t.exit_date} @ ${t.exit_price}`), { dataset: { label: "Exit" } }));
      const rTd = el("td", t.return_pct >= 0 ? "bull" : "bear", `${t.return_pct > 0 ? "+" : ""}${t.return_pct}%`);
      rTd.dataset.label = "Return";
      tr.appendChild(rTd);
      tr.appendChild(Object.assign(el("td", "", t.exit_reason), { dataset: { label: "Reason" } }));
      tbody.appendChild(tr);
    }
  } catch (err) {
    renderKV($("backtest-summary"), [["Error", err.message, "bear"]]);
  }
}

async function syncPaperPortfolio() {
  try {
    const [acct, pos, orders, risk] = await Promise.all([
      apiGet("/api/paper/account"),
      apiGet("/api/paper/positions"),
      apiGet("/api/paper/orders?limit=8"),
      apiGet("/api/paper/risk"),
    ]);
    renderKV($("paper-account-box"), [
      ["Paper Equity", fmtMoney(acct.equity)],
      ["Cash", fmtMoney(acct.cash)],
      ["Buying Power", fmtMoney(acct.buying_power)],
      ["Day P&L", `${fmtMoney(acct.day_pnl)} (${acct.day_pnl_pct}%)`, acct.day_pnl >= 0 ? "bull" : "bear"],
      ["Weighted Beta", `${risk.weighted_beta}`],
    ]);

    const sBox = $("paper-stress-box");
    sBox.replaceChildren();
    const card = el("div", "list-card");
    card.appendChild(el("strong", "", risk.plain_english_summary || "Stress test ready"));
    const sc = risk.stress_scenarios || {};
    card.appendChild(el("small", "muted", `Crash (-15% SPY): ${fmtMoney(sc.market_crash_spy_minus_15pct?.estimated_pnl)} | Rate Shock (+100bps): ${fmtMoney(sc.rate_hike_100bps_shock?.estimated_pnl)}`));
    sBox.appendChild(card);

    const tbody = $("paper-positions-tbody");
    tbody.replaceChildren();
    for (const p of pos.positions || []) {
      const tr = document.createElement("tr");
      tr.appendChild(Object.assign(el("td", "", p.symbol), { dataset: { label: "Symbol" } }));
      tr.appendChild(Object.assign(el("td", "", p.qty), { dataset: { label: "Qty" } }));
      tr.appendChild(Object.assign(el("td", "", fmtMoney(p.market_value)), { dataset: { label: "Value" } }));
      const pl = el("td", p.unrealized_pl >= 0 ? "bull" : "bear", `${fmtMoney(p.unrealized_pl)} (${p.unrealized_pl_pct}%)`);
      pl.dataset.label = "P&L";
      tr.appendChild(pl);
      tbody.appendChild(tr);
    }
    for (const o of orders.orders || []) {
      const tr = document.createElement("tr");
      tr.appendChild(Object.assign(el("td", "", `${o.side.toUpperCase()} ${o.symbol}`), { dataset: { label: "Symbol" } }));
      tr.appendChild(Object.assign(el("td", "", o.qty), { dataset: { label: "Qty" } }));
      tr.appendChild(Object.assign(el("td", "", o.status), { dataset: { label: "Status" } }));
      const td = el("td", "");
      td.dataset.label = "Action";
      if (["new", "accepted", "pending_new", "partially_filled"].includes(String(o.status).toLowerCase())) {
        const cBtn = el("button", "btn btn-secondary", "Cancel");
        cBtn.type = "button";
        cBtn.addEventListener("click", async () => {
          await apiPost("/api/paper/cancel", { order_id: o.id });
          await syncPaperPortfolio();
        });
        td.appendChild(cBtn);
      } else {
        td.textContent = o.filled_avg_price ? `@ $${o.filled_avg_price}` : o.status;
      }
      tr.appendChild(td);
      tbody.appendChild(tr);
    }
  } catch (err) {
    renderKV($("paper-account-box"), [["Error", err.message, "bear"]]);
  }
}

/* ── Safe Modal Paper Order Confirmation (Per Modern-Web-Guidance Dialog Spec) ── */
function setupDialogFallback() {
  if (!("closedBy" in HTMLDialogElement.prototype)) {
    const outside = (e, d) => {
      const r = d.getBoundingClientRect();
      return e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom;
    };
    for (const d of document.querySelectorAll('dialog[closedby="any"]')) {
      let pressedOutside = false;
      d.addEventListener("pointerdown", (e) => { pressedOutside = outside(e, d); });
      d.addEventListener("pointerup", (e) => { if (pressedOutside && outside(e, d)) d.close(); });
    }
  }
}

async function handlePaperPreview(e) {
  e.preventDefault();
  const payload = {
    symbol: $("ord-symbol").value.trim().toUpperCase(),
    qty: Number($("ord-qty").value),
    side: $("ord-side").value,
    type: "market",
    confirm: false,
  };
  try {
    const preview = await apiPost("/api/paper/order", payload);
    const dialog = $("order-confirm-dialog");
    const body = $("order-dialog-body");
    body.replaceChildren();
    body.appendChild(el("p", "", `${payload.side.toUpperCase()} ${payload.qty} share(s) of ${payload.symbol} (~${fmtMoney(preview.estimated_order_value)})`));
    body.appendChild(el("small", "muted", `Portfolio Weight: ${preview.portfolio_weight_pct}% | ATR Stop Hint: ${fmtMoney(preview.suggested_atr_stop_loss)}`));
    if (preview.warning) body.appendChild(el("p", "warn", preview.warning));

    dialog.onclose = async () => {
      const choice = dialog.returnValue;
      dialog.returnValue = "";
      if (choice === "confirm") {
        await apiPost("/api/paper/order", { ...payload, confirm: true });
        await syncPaperPortfolio();
      }
    };
    dialog.showModal();
  } catch (err) {
    alert(`Order preview failed: ${err.message}`);
  }
}

/* ── Command Palette Runner ── */
async function executeNaturalCommand(query) {
  $("command-input").value = query;
  switchView("console");
  $("console-meta").textContent = `Running: "${query}"...`;
  $("console-output").textContent = "Querying DoomsBlerg backend...";
  try {
    const res = await apiPost("/api/ask", { query });
    $("console-meta").textContent = `Intent: ${res.intent} (${res.match_mode}) — ${res.plain_english_hint || ""}`;
    $("console-output").textContent = JSON.stringify(res, null, 2);
  } catch (err) {
    $("console-meta").textContent = "Command failed";
    $("console-output").textContent = err.message;
  }
}

/* ── Bootstrap ── */
async function init() {
  setupDialogFallback();
  attachChartHover();

  try {
    const health = await apiGet("/health");
    $("pill-api").textContent = `API: ${health.status.toUpperCase()}`;
    $("pill-api").className = "pill pill-ok";
  } catch {
    $("pill-api").textContent = "API: Offline";
    $("pill-api").className = "pill pill-err";
  }

  for (const btn of document.querySelectorAll(".tab-btn")) {
    btn.addEventListener("click", () => {
      const v = btn.dataset.view;
      switchView(v);
      if (v === "gods-eye" && !state.worldData) loadGodsEye();
      if (v === "macro") loadMacroFx();
      if (v === "trading") syncPaperPortfolio();
    });
  }

  $("command-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const q = $("command-input").value.trim();
    if (q) executeNaturalCommand(q);
  });

  $("quick-chips").addEventListener("click", (e) => {
    const btn = e.target.closest("button");
    if (!btn) return;
    if (btn.dataset.ticker) {
      switchView("stock");
      loadStock(btn.dataset.ticker, $("range-select").value);
    } else if (btn.dataset.query) {
      executeNaturalCommand(btn.dataset.query);
    }
  });

  $("btn-load-stock").addEventListener("click", () => loadStock($("ticker-input").value, $("range-select").value));
  $("ticker-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      loadStock($("ticker-input").value, $("range-select").value);
    }
  });
  $("btn-run-debate-fast").addEventListener("click", runDebate);
  $("btn-run-debate").addEventListener("click", runDebate);
  $("btn-run-audit").addEventListener("click", runSecAudit);
  $("btn-run-briefing").addEventListener("click", () => executeNaturalCommand("morning briefing"));
  $("btn-refresh-geo").addEventListener("click", loadGodsEye);
  $("btn-refresh-macro").addEventListener("click", loadMacroFx);
  $("backtest-form").addEventListener("submit", runBacktestForm);
  $("btn-refresh-paper").addEventListener("click", syncPaperPortfolio);
  $("paper-order-form").addEventListener("submit", handlePaperPreview);
  $("btn-ai-health").addEventListener("click", async () => {
    switchView("console");
    const h = await apiGet("/api/ai/health");
    $("console-output").textContent = JSON.stringify(h, null, 2);
  });

  await loadStock("AAPL", "3mo");
}

init();
