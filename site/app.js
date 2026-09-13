(function () {
  const CHART_COLORS = {
    accent: '#22d3ee',
    accent2: '#38bdf8',
    call: '#3b82f6',
    put: '#fb7185',
    positive: '#34d399',
    negative: '#f87171',
    warning: '#fbbf24',
    purple: '#a78bfa',
    grid: 'rgba(139,149,167,0.12)',
    text: '#8b95a7',
  };

  Chart.defaults.color = CHART_COLORS.text;
  Chart.defaults.font.family = "'Inter', sans-serif";
  Chart.defaults.borderColor = CHART_COLORS.grid;

  const charts = {};
  let currentData = null;

  function fmt(n, decimals = 2) {
    if (n === null || n === undefined || Number.isNaN(n)) return '—';
    return Number(n).toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
  }

  function fmtPct(n, decimals = 2) {
    if (n === null || n === undefined || Number.isNaN(n)) return '—';
    const sign = n > 0 ? '+' : '';
    return `${sign}${fmt(n, decimals)}%`;
  }

  function fmtMoney(n, decimals = 2) {
    if (n === null || n === undefined || Number.isNaN(n)) return '—';
    return `$${fmt(n, decimals)}`;
  }

  function fmtCompact(n) {
    if (n === null || n === undefined || Number.isNaN(n)) return '—';
    return Number(n).toLocaleString('en-US', { notation: 'compact', maximumFractionDigits: 2 });
  }

  function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  }

  function setClass(id, cls) {
    const el = document.getElementById(id);
    if (!el) return;
    el.className = el.className.split(' ')[0] + (cls ? ' ' + cls : '');
  }

  function destroyChart(key) {
    if (charts[key]) {
      charts[key].destroy();
      delete charts[key];
    }
  }

  // ---------------- Tabs ----------------
  function initTabs() {
    document.querySelectorAll('.tab-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach((b) => b.classList.remove('active'));
        document.querySelectorAll('.tab-panel').forEach((p) => p.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
      });
    });
  }

  // ---------------- Rendering ----------------
  function renderSpotStrip(meta, technicals) {
    setText('spotTicker', meta.ticker || '—');
    setText('spotPrice', meta.spot != null ? fmtMoney(meta.spot) : '—');
    const change = technicals ? technicals.day_change_pct : null;
    const changeEl = document.getElementById('spotChange');
    if (change != null) {
      changeEl.textContent = fmtPct(change);
      changeEl.className = 'spot-change ' + (change >= 0 ? 'positive' : 'negative');
    } else {
      changeEl.textContent = '—';
      changeEl.className = 'spot-change';
    }
    const tagsEl = document.getElementById('spotTags');
    tagsEl.innerHTML = '';
    const tags = [];
    if (meta.company_name) tags.push(meta.company_name);
    if (meta.sector) tags.push(meta.sector);
    if (meta.market_cap) tags.push('Mkt Cap ' + fmtCompact(meta.market_cap));
    if (meta.as_of_date) tags.push('As of ' + meta.as_of_date);
    tags.forEach((t) => {
      const span = document.createElement('span');
      span.className = 'spot-tag';
      span.textContent = t;
      tagsEl.appendChild(span);
    });
    setText('asOfLabel', meta.as_of_date ? 'as of ' + meta.as_of_date : 'no data');
    setText('updatedAt', meta.generated_at_utc ? 'Last refreshed: ' + new Date(meta.generated_at_utc).toLocaleString() : 'Last refreshed: —');
  }

  function renderVolatility(v) {
    if (!v) return;
    setText('v-atmIv', v.atm_iv_pct != null ? fmtPct(v.atm_iv_pct, 1).replace('+', '') : '—');
    setText('v-ivRichness', v.iv_richness_label ? `${v.iv_richness_label} vs HV20 (${fmtPct(v.iv_minus_hv20_pts, 1)} pts)` : '—');
    setClass('v-atmIv', v.iv_richness_label === 'Rich' ? 'kpi-value warning' : v.iv_richness_label === 'Cheap' ? 'kpi-value positive' : 'kpi-value accent');

    setText('v-skew', v.skew_pct_pts != null ? `${fmt(v.skew_pct_pts, 2)} pts` : '—');
    setClass('v-skew', v.skew_pct_pts > 0 ? 'kpi-value warning' : 'kpi-value');

    setText('v-expMove', v.expected_move_dollars != null ? fmtMoney(v.expected_move_dollars) : '—');
    setText('v-expMovePct', v.expected_move_pct != null ? `${fmtPct(v.expected_move_pct, 2).replace('+', '±')} by primary expiry` : '—');

    setText('v-term', v.term_structure_label || '—');
    setClass('v-term', v.term_structure_label && v.term_structure_label.includes('calm') ? 'kpi-value positive' : 'kpi-value warning');
    setText('v-termDetail', v.secondary_atm_iv_pct != null ? `Front ${fmt(v.atm_iv_pct, 1)}% vs Back ${fmt(v.secondary_atm_iv_pct, 1)}%` : '—');

    setText('v-primaryExp', v.primary_expiration || '—');
    setText('v-secondaryExp', v.secondary_expiration || '—');
    setText('v-hvPercentile', v.realized_vol_20d_percentile_1y != null ? `${fmt(v.realized_vol_20d_percentile_1y, 0)}th percentile` : '—');

    // IV vs HV chart
    destroyChart('ivHv');
    const ctx1 = document.getElementById('chartIvHv').getContext('2d');
    charts.ivHv = new Chart(ctx1, {
      type: 'bar',
      data: {
        labels: ['ATM IV (front)', 'ATM IV (back)', 'HV20', 'HV30'],
        datasets: [{
          label: 'Annualized Vol %',
          data: [v.atm_iv_pct, v.secondary_atm_iv_pct, v.realized_vol_20d_pct, v.realized_vol_30d_pct],
          backgroundColor: [CHART_COLORS.accent, CHART_COLORS.accent2, CHART_COLORS.purple, CHART_COLORS.purple + 'aa'],
          borderRadius: 6,
        }],
      },
      options: baseBarOptions('%'),
    });

    // Realized vol windows chart
    destroyChart('rv');
    const ctx2 = document.getElementById('chartRv').getContext('2d');
    charts.rv = new Chart(ctx2, {
      type: 'bar',
      data: {
        labels: ['10d', '20d', '30d', '60d'],
        datasets: [{
          label: 'Realized Vol %',
          data: [v.realized_vol_10d_pct, v.realized_vol_20d_pct, v.realized_vol_30d_pct, v.realized_vol_60d_pct],
          backgroundColor: CHART_COLORS.accent2,
          borderRadius: 6,
        }],
      },
      options: baseBarOptions('%'),
    });
  }

  function renderTechnicals(t) {
    if (!t) return;
    setText('t-trend', t.trend_label || '—');
    setClass('t-trend', t.trend_label === 'Uptrend' ? 'kpi-value positive' : t.trend_label === 'Downtrend' ? 'kpi-value negative' : 'kpi-value warning');
    setText('t-trendDetail', `vs SMA50 ${fmtPct(t.pct_vs_sma50)} · vs SMA200 ${fmtPct(t.pct_vs_sma200)}`);

    setText('t-rsi', t.rsi14 != null ? fmt(t.rsi14, 1) : '—');
    setText('t-rsiLabel', t.rsi_label || '—');
    setClass('t-rsi', t.rsi_label === 'Overbought' ? 'kpi-value warning' : t.rsi_label === 'Oversold' ? 'kpi-value positive' : 'kpi-value');

    setText('t-macdCross', t.macd_cross || '—');
    setClass('t-macdCross', t.macd_cross === 'Bullish' ? 'kpi-value positive' : t.macd_cross === 'Bearish' ? 'kpi-value negative' : 'kpi-value');
    setText('t-macdDetail', t.macd != null ? `MACD ${fmt(t.macd, 2)} · Signal ${fmt(t.macd_signal, 2)} · Hist ${fmt(t.macd_hist, 2)}` : '—');

    setText('t-atr', t.atr14 != null ? fmtMoney(t.atr14) : '—');
    setText('t-atrPct', t.atr_pct != null ? `${fmt(t.atr_pct, 2)}% of spot` : '—');

    setText('t-percentB', t.percent_b != null ? fmt(t.percent_b, 2) : '—');
    setText('t-volRatio', t.volume_ratio != null ? `${fmt(t.volume_ratio, 2)}x` : '—');
    setText('t-52wRange', t.low_52w != null ? `${fmtMoney(t.low_52w, 0)} – ${fmtMoney(t.high_52w, 0)}` : '—');

    destroyChart('price');
    destroyChart('volume');
    destroyChart('rsi');
    const series = t.price_series || [];
    const labels = series.map((p) => p.date);
    const closes = series.map((p) => p.close);
    const bbUpper = series.map((p) => p.bollinger_upper);
    const bbLower = series.map((p) => p.bollinger_lower);
    const volumes = series.map((p) => p.volume);
    const rsiSeries = series.map((p) => p.rsi);
    const sma20Line = closes.map(() => t.sma20);
    const sma50Line = closes.map(() => t.sma50);
    const sma200Line = closes.map(() => t.sma200);

    // Trend line: a sparse two-point overlay connected via spanGaps.
    let trendLineData = null;
    if (t.trend_line) {
      trendLineData = new Array(labels.length).fill(null);
      let startIdx = labels.indexOf(t.trend_line.start_date);
      let endIdx = labels.indexOf(t.trend_line.end_date);
      if (startIdx === -1) startIdx = Math.max(0, labels.length - t.trend_line.window_days);
      if (endIdx === -1) endIdx = labels.length - 1;
      trendLineData[startIdx] = t.trend_line.start_value;
      trendLineData[endIdx] = t.trend_line.end_value;
    }

    const srDatasets = [];
    (t.resistance_levels || []).forEach((r, i) => {
      srDatasets.push({
        label: `Resistance ${fmtMoney(r.level, 0)}`,
        data: new Array(labels.length).fill(r.level),
        borderColor: CHART_COLORS.put,
        borderDash: [2, 3],
        borderWidth: i === 0 ? 1.5 : 1,
        pointRadius: 0,
        fill: false,
      });
    });
    (t.support_levels || []).forEach((s, i) => {
      srDatasets.push({
        label: `Support ${fmtMoney(s.level, 0)}`,
        data: new Array(labels.length).fill(s.level),
        borderColor: CHART_COLORS.positive,
        borderDash: [2, 3],
        borderWidth: i === 0 ? 1.5 : 1,
        pointRadius: 0,
        fill: false,
      });
    });

    const ctx = document.getElementById('chartPrice').getContext('2d');
    charts.price = new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [
          { label: 'BB Upper', data: bbUpper, borderColor: 'rgba(167,139,250,0.35)', backgroundColor: 'rgba(167,139,250,0.08)', pointRadius: 0, borderWidth: 1, fill: '+1' },
          { label: 'BB Lower', data: bbLower, borderColor: 'rgba(167,139,250,0.35)', backgroundColor: 'transparent', pointRadius: 0, borderWidth: 1, fill: false },
          { label: 'Close', data: closes, borderColor: CHART_COLORS.accent, backgroundColor: 'transparent', pointRadius: 0, borderWidth: 2.2, tension: 0.15 },
          { label: 'SMA20 (current)', data: sma20Line, borderColor: CHART_COLORS.positive, borderDash: [4, 4], pointRadius: 0, borderWidth: 1 },
          { label: 'SMA50 (current)', data: sma50Line, borderColor: CHART_COLORS.warning, borderDash: [4, 4], pointRadius: 0, borderWidth: 1 },
          { label: 'SMA200 (current)', data: sma200Line, borderColor: CHART_COLORS.put, borderDash: [4, 4], pointRadius: 0, borderWidth: 1 },
          ...(trendLineData ? [{ label: 'Trend line (60d)', data: trendLineData, borderColor: CHART_COLORS.warning, borderWidth: 2, pointRadius: 0, spanGaps: true }] : []),
          ...srDatasets,
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: { legend: { display: true, labels: { boxWidth: 10, font: { size: 10 }, filter: (item) => !item.text.startsWith('BB ') } } },
        scales: {
          x: { ticks: { maxTicksLimit: 8, font: { size: 10 } }, grid: { display: false } },
          y: { ticks: { font: { size: 10 }, callback: (v) => fmtMoney(v, 0) }, grid: { color: CHART_COLORS.grid } },
        },
      },
    });

    const upDownColors = closes.map((c, i) => {
      if (i === 0 || c == null || closes[i - 1] == null) return CHART_COLORS.text;
      return c >= closes[i - 1] ? 'rgba(52,211,153,0.6)' : 'rgba(248,113,113,0.6)';
    });
    const ctxVol = document.getElementById('chartVolume').getContext('2d');
    charts.volume = new Chart(ctxVol, {
      type: 'bar',
      data: {
        labels,
        datasets: [{ label: 'Volume', data: volumes, backgroundColor: upDownColors, barPercentage: 1.0, categoryPercentage: 1.0 }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: { legend: { display: false } },
        scales: {
          x: { display: false },
          y: { ticks: { font: { size: 9 }, maxTicksLimit: 3, callback: (v) => fmtCompact(v) }, grid: { color: CHART_COLORS.grid } },
        },
      },
    });

    const ctxRsi = document.getElementById('chartRsi').getContext('2d');
    charts.rsi = new Chart(ctxRsi, {
      type: 'line',
      data: {
        labels,
        datasets: [
          { label: 'Overbought (70)', data: new Array(labels.length).fill(70), borderColor: 'rgba(248,113,113,0.4)', borderDash: [3, 3], pointRadius: 0, borderWidth: 1 },
          { label: 'Oversold (30)', data: new Array(labels.length).fill(30), borderColor: 'rgba(52,211,153,0.4)', borderDash: [3, 3], pointRadius: 0, borderWidth: 1 },
          { label: 'RSI (14)', data: rsiSeries, borderColor: CHART_COLORS.accent2, backgroundColor: 'transparent', pointRadius: 0, borderWidth: 1.8, tension: 0.15 },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: { legend: { display: true, labels: { boxWidth: 10, font: { size: 10 } } } },
        scales: {
          x: { ticks: { maxTicksLimit: 8, font: { size: 10 } }, grid: { display: false } },
          y: { min: 0, max: 100, ticks: { font: { size: 10 }, stepSize: 25 }, grid: { color: CHART_COLORS.grid } },
        },
      },
    });

    // Support & resistance card
    const srEl = document.getElementById('srDisplay');
    srEl.innerHTML = '';
    const resistances = (t.resistance_levels || []).slice(0, 3);
    const supports = (t.support_levels || []).slice(0, 3);
    if (!resistances.length && !supports.length) {
      srEl.innerHTML = '<div class="kpi-sub">Not enough swing history to detect clear levels.</div>';
    } else {
      resistances.forEach((r) => {
        const div = document.createElement('div');
        div.className = 'wall-row put';
        div.innerHTML = `<div><div class="wall-label">Resistance</div><div class="wall-oi">${r.touches} touch${r.touches > 1 ? 'es' : ''}</div></div><div class="wall-value">${fmtMoney(r.level, 0)}</div>`;
        srEl.appendChild(div);
      });
      supports.forEach((s) => {
        const div = document.createElement('div');
        div.className = 'wall-row call';
        div.innerHTML = `<div><div class="wall-label">Support</div><div class="wall-oi">${s.touches} touch${s.touches > 1 ? 'es' : ''}</div></div><div class="wall-value">${fmtMoney(s.level, 0)}</div>`;
        srEl.appendChild(div);
      });
    }

    // Trend line KPI
    if (t.trend_line) {
      setText('t-trendLineDir', t.trend_line.direction);
      setClass('t-trendLineDir', t.trend_line.direction === 'Uptrend' ? 'kpi-value positive' : t.trend_line.direction === 'Downtrend' ? 'kpi-value negative' : 'kpi-value warning');
      setText('t-trendLineDetail', `${fmtPct(t.trend_line.pct_change_over_window, 1)} over ${t.trend_line.window_days}d (${t.trend_line.start_date} \u2192 ${t.trend_line.end_date})`);
    } else {
      setText('t-trendLineDir', '\u2014');
      setText('t-trendLineDetail', 'Not enough history');
    }
  }

  function renderLiquidity(l) {
    if (!l) return;
    setText('l-pcOi', l.put_call_oi_ratio != null ? fmt(l.put_call_oi_ratio, 2) : '—');
    setClass('l-pcOi', l.put_call_oi_ratio > 1 ? 'kpi-value warning' : 'kpi-value');
    setText('l-oiTotals', `Calls ${fmtCompact(l.total_call_oi)} · Puts ${fmtCompact(l.total_put_oi)}`);

    setText('l-pcVol', l.put_call_volume_ratio != null ? fmt(l.put_call_volume_ratio, 2) : '—');
    setClass('l-pcVol', l.put_call_volume_ratio > 1 ? 'kpi-value warning' : 'kpi-value');
    setText('l-volTotals', `Calls ${fmtCompact(l.total_call_volume)} · Puts ${fmtCompact(l.total_put_volume)}`);

    setText('l-spread', l.avg_atm_spread_pct != null ? `${fmt(l.avg_atm_spread_pct, 2)}%` : '—');
    setClass('l-spread', l.avg_atm_spread_pct > 8 ? 'kpi-value negative' : l.avg_atm_spread_pct > 4 ? 'kpi-value warning' : 'kpi-value positive');

    setText('l-shortFloat', l.short_percent_of_float_pct != null ? `${fmt(l.short_percent_of_float_pct, 2)}%` : '—');
    setText('l-daysToCover', l.short_ratio_days_to_cover != null ? `${fmt(l.short_ratio_days_to_cover, 1)} days to cover` : 'n/a');

    destroyChart('oi');
    const ctx = document.getElementById('chartOi').getContext('2d');
    charts.oi = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: ['Open Interest', 'Volume'],
        datasets: [
          { label: 'Calls', data: [l.total_call_oi, l.total_call_volume], backgroundColor: CHART_COLORS.call, borderRadius: 6 },
          { label: 'Puts', data: [l.total_put_oi, l.total_put_volume], backgroundColor: CHART_COLORS.put, borderRadius: 6 },
        ],
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: true, labels: { boxWidth: 12, font: { size: 11 } } } },
        scales: {
          x: { ticks: { font: { size: 10 }, callback: (v) => fmtCompact(v) }, grid: { color: CHART_COLORS.grid } },
          y: { ticks: { font: { size: 11 } }, grid: { display: false } },
        },
      },
    });

    const wallEl = document.getElementById('wallDisplay');
    wallEl.innerHTML = '';
    const rows = [
      { cls: 'call', label: 'Call Wall', strike: l.top_call_oi_strike, oi: l.top_call_oi },
      { cls: 'put', label: 'Put Wall', strike: l.top_put_oi_strike, oi: l.top_put_oi },
    ];
    rows.forEach((r) => {
      const div = document.createElement('div');
      div.className = 'wall-row ' + r.cls;
      div.innerHTML = `
        <div>
          <div class="wall-label">${r.label}</div>
          <div class="wall-oi">${fmtCompact(r.oi)} OI</div>
        </div>
        <div class="wall-value">${r.strike != null ? fmtMoney(r.strike, 0) : '—'}</div>
      `;
      wallEl.appendChild(div);
    });

    setText('l-avgVolume', l.avg_daily_volume_30d != null ? fmtCompact(l.avg_daily_volume_30d) : '—');
    setText('l-expirations', (l.near_term_expirations_used || []).join(' · ') || '—');
  }

  function renderEvents(e) {
    if (!e) return;
    if (e.next_earnings && e.next_earnings.date) {
      setText('e-earningsDate', e.next_earnings.date);
      setText('e-earningsDetail', `${e.next_earnings.days_until} days away${e.next_earnings.eps_estimate != null ? ' · EPS est ' + fmt(e.next_earnings.eps_estimate, 2) : ''}${e.earnings_inside_primary_expiration ? ' · inside primary expiry' : ''}`);
      setClass('e-earningsDate', e.earnings_inside_primary_expiration ? 'kpi-value warning' : 'kpi-value');
    } else {
      setText('e-earningsDate', '—');
      setText('e-earningsDetail', 'No upcoming date found');
    }

    setText('e-exDiv', e.estimated_next_ex_dividend_date || '—');
    setText('e-divYield', e.days_to_next_ex_dividend != null
      ? `${e.days_to_next_ex_dividend} days away · yield ${fmt(e.dividend_yield_pct, 2)}%`
      : (e.dividend_yield_pct != null ? `yield ${fmt(e.dividend_yield_pct, 2)}%` : 'No dividend history'));

    const nextFomc = (e.upcoming_fomc_meetings || [])[0];
    if (nextFomc) {
      setText('e-fomc', nextFomc.range);
      setText('e-fomcDetail', `${nextFomc.days_until} days away${nextFomc.has_sep ? ' · has SEP/dot plot' : ''}`);
    } else {
      setText('e-fomc', '—');
      setText('e-fomcDetail', '—');
    }

    destroyChart('earnings');
    const moves = (e.past_earnings_moves || []).slice().reverse();
    const ctx = document.getElementById('chartEarnings').getContext('2d');
    charts.earnings = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: moves.map((m) => m.date),
        datasets: [{
          label: 'Next-day move %',
          data: moves.map((m) => m.move_pct),
          backgroundColor: moves.map((m) => (m.move_pct >= 0 ? CHART_COLORS.positive : CHART_COLORS.negative)),
          borderRadius: 6,
        }],
      },
      options: baseBarOptions('%'),
    });

    const fomcListEl = document.getElementById('fomcList');
    fomcListEl.innerHTML = '';
    (e.upcoming_fomc_meetings || []).forEach((m) => {
      const div = document.createElement('div');
      div.className = 'event-row';
      div.innerHTML = `
        <div>
          <div class="event-date">${m.range}</div>
          <div class="event-days">${m.days_until} days away</div>
        </div>
        ${m.has_sep ? '<span class="event-tag">SEP + dot plot</span>' : ''}
      `;
      fomcListEl.appendChild(div);
    });
  }

  function renderRegime(r) {
    if (!r) return;
    setText('r-vix', r.vix_level != null ? fmt(r.vix_level, 2) : '—');
    setText('r-vixPercentile', r.vix_1y_percentile != null ? `${fmt(r.vix_1y_percentile, 0)}th percentile (1y)` : '—');
    setClass('r-vix', r.vix_level > 25 ? 'kpi-value negative' : r.vix_level > 18 ? 'kpi-value warning' : 'kpi-value positive');

    setText('r-vixTerm', r.vix_term_structure_label || '—');
    setClass('r-vixTerm', r.vix_term_structure_label && r.vix_term_structure_label.includes('stressed') ? 'kpi-value negative' : 'kpi-value positive');
    setText('r-vix3m', r.vix3m_level != null ? `VIX3M ${fmt(r.vix3m_level, 2)}` : '—');

    setText('r-marketTrend', r.market_trend_label || '—');
    setClass('r-marketTrend', r.market_trend_label && r.market_trend_label.toLowerCase().includes('up') ? 'kpi-value positive' : r.market_trend_label && r.market_trend_label.toLowerCase().includes('down') ? 'kpi-value negative' : 'kpi-value warning');
    setText('r-spyDetail', r.spy_price != null ? `SPY ${fmtMoney(r.spy_price)} · SMA50 ${fmtMoney(r.spy_sma50, 0)} · SMA200 ${fmtMoney(r.spy_sma200, 0)}` : '—');

    setText('r-beta', r.beta != null ? fmt(r.beta, 2) : '—');
    setText('r-corr', r.correlation_to_spy_60d != null ? `60d corr to SPY: ${fmt(r.correlation_to_spy_60d, 2)}${r.beta_source ? ' · beta ' + r.beta_source : ''}` : '—');

    destroyChart('sector');
    const ctx = document.getElementById('chartSector').getContext('2d');
    charts.sector = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: [`${r.sector_etf || 'Sector'} 1M`, `${r.sector_etf || 'Sector'} 3M`, 'vs SPY 1M', 'vs SPY 3M'],
        datasets: [{
          label: 'Return %',
          data: [r.sector_return_1m_pct, r.sector_return_3m_pct, r.sector_vs_spy_1m_pct, r.sector_vs_spy_3m_pct],
          backgroundColor: [CHART_COLORS.accent, CHART_COLORS.accent2, CHART_COLORS.positive, CHART_COLORS.purple].map((c, i) => {
            const val = [r.sector_return_1m_pct, r.sector_return_3m_pct, r.sector_vs_spy_1m_pct, r.sector_vs_spy_3m_pct][i];
            return val >= 0 ? CHART_COLORS.positive : CHART_COLORS.negative;
          }),
          borderRadius: 6,
        }],
      },
      options: baseBarOptions('%'),
    });
  }

  function baseBarOptions(unitSuffix) {
    return {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { font: { size: 10 } }, grid: { display: false } },
        y: { ticks: { font: { size: 10 }, callback: (v) => `${v}${unitSuffix}` }, grid: { color: CHART_COLORS.grid } },
      },
    };
  }

  function renderAll(data) {
    currentData = data;
    renderSpotStrip(data.meta || {}, data.technicals);
    renderVolatility(data.volatility);
    renderTechnicals(data.technicals);
    renderLiquidity(data.liquidity);
    renderEvents(data.events);
    renderRegime(data.regime);
  }

  // ---------------- Data loading ----------------
  async function loadTicker(ticker) {
    const errEl = document.getElementById('loadError');
    errEl.classList.add('hidden');
    const btn = document.getElementById('loadTickerBtn');
    btn.disabled = true;
    btn.textContent = 'Loading…';
    try {
      const resp = await fetch(`data/${ticker.toUpperCase()}.json?t=${Date.now()}`, { cache: 'no-store' });
      if (!resp.ok) throw new Error(`No data file found for ${ticker.toUpperCase()}. Run the script for this ticker first.`);
      const data = await resp.json();
      renderAll(data);
      document.getElementById('tickerInput').value = ticker.toUpperCase();
      history.replaceState(null, '', `?ticker=${ticker.toUpperCase()}`);
    } catch (err) {
      errEl.textContent = err.message || 'Failed to load ticker data.';
      errEl.classList.remove('hidden');
    } finally {
      btn.disabled = false;
      btn.textContent = 'Load';
    }
  }

  async function init() {
    initTabs();
    document.getElementById('loadTickerBtn').addEventListener('click', () => {
      const val = document.getElementById('tickerInput').value.trim();
      if (val) loadTicker(val);
    });
    document.getElementById('tickerInput').addEventListener('keydown', (ev) => {
      if (ev.key === 'Enter') document.getElementById('loadTickerBtn').click();
    });

    const params = new URLSearchParams(window.location.search);
    let initialTicker = params.get('ticker');
    if (!initialTicker) {
      try {
        const resp = await fetch(`data/last_ticker.json?t=${Date.now()}`, { cache: 'no-store' });
        if (resp.ok) {
          const j = await resp.json();
          initialTicker = j.ticker;
        }
      } catch (e) { /* ignore */ }
    }
    if (initialTicker) {
      loadTicker(initialTicker);
    } else {
      document.getElementById('loadError').textContent = 'No ticker loaded yet. Enter a ticker above.';
      document.getElementById('loadError').classList.remove('hidden');
    }
  }

  init();
})();
