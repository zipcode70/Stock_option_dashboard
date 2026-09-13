# Handover Notes — Options Indicators Dashboard

This file exists so you (a future session of this AI, or a different AI tool)
can pick up work on this project without re-deriving the design from scratch.
Written for a non-coder owner, so it favors plain explanations over jargon.

## What this project is, in one paragraph

A static site (`site/`) plus a Python data pipeline (`scripts/compute_indicators.py`)
that, given any single ticker, computes a five-category "pre-trade checklist"
for options trading — volatility, price/technicals, liquidity/positioning,
events, and market regime — and renders it as a 5-tab dashboard. It is
**on-demand only**: the owner types a ticker into the dashboard (or the agent
runs the script) right before making a trading decision. There is no
schedule, no automation, and nothing is pushed to GitHub — this project lives
only in the Perplexity Computer workspace and is deployed via `deploy_website`
for preview/sharing.

## Relationship to the other dashboards in this workspace

This is a **standalone sibling project** — it shares no code or data with:
- `gex_dashboard/` — SPY/QQQ daily gamma exposure tracker (GitHub-hosted, `zipcode70/JW-dashboard1`)
- `ticker_gex_dashboard/` — on-demand gamma exposure dashboard for any ticker (GitHub-hosted, `zipcode70/Ticker_dashboard_gamma`)

**Important:** this dashboard does **not** compute gamma exposure, call wall,
put wall, max pain, or gamma flip. Those concepts live only in the two GEX
projects above. See `DECISION_GUIDE.md` (in this same folder) for how to use
this dashboard together with the GEX dashboards to make an actual buy/sell
decision — that guide is the intended "bridge" between the two tools.

## Why this dashboard exists

The owner asked, in effect: "beyond gamma and call/put walls, what else
should I check before writing or buying an option?" This dashboard answers
that — it is the complementary checklist, not a replacement for the GEX
tools.

## Pipeline (`scripts/compute_indicators.py`, ~700 lines)

Usage: `python3 scripts/compute_indicators.py TICKER` (or `TICKER=AAPL python3 scripts/compute_indicators.py`).
Writes `site/data/<TICKER>.json` and updates `site/data/last_ticker.json` so
the frontend knows what to load by default.

1. **Price history** — 1 year of daily OHLCV via `yfinance`.
2. **Technicals** (`build_technicals`) — SMA20/50/200, RSI(14), MACD,
   Bollinger Bands(20,2), ATR(14), volume vs 20d average, 52-week range,
   trend label. This session's additions:
   - `resistance_levels` / `support_levels` — swing highs/lows over the last
     120 trading days, found via a local-extrema scan (`pivot_levels()`),
     clustered within 1.25% of each other, ranked by number of touches.
   - `trend_line` — 60-day least-squares linear regression on closing price
     (`linear_trend()`), returned as two endpoint dates/values so the
     frontend can draw a straight line without re-deriving the regression.
   - Full 180-day aligned series per date (`price_series[]`): close, volume,
     Bollinger upper/lower, and RSI — used to drive the price/volume/RSI
     charts (previously only the *current* value of each indicator was
     exposed; now the full history is too).
3. **Volatility + liquidity** (`build_volatility_and_liquidity`) — ATM IV
   (avg of ATM call/put IV at the primary expiration), skew (10%-OTM put IV
   minus 10%-OTM call IV), expected move (ATM straddle price), term
   structure label (contango/backwardation vs. a secondary expiration ~20+
   days out), aggregate call/put OI and volume across near-term expirations,
   top OI strikes (**not** gamma-weighted — see note above), average
   bid-ask spread near the money, realized vol at 10/20/30/60 days.
4. **Events** (`build_events`) — next earnings date + historical post-earnings
   move sizes, next ex-dividend date (see bug fix below), upcoming FOMC
   meetings (hardcoded official calendar, flagged for dot-plot meetings),
   short interest.
5. **Regime** (`build_regime`) — VIX level + 1-year percentile, VIX3M term
   structure, SPY trend, beta (from `yfinance` info, with a regression
   fallback), 60-day rolling correlation to SPY, sector ETF relative
   strength.

## Bug fixes made during development

1. **Dividend yield unit mismatch**: `yfinance`'s `get_info()` field
   `dividendYield` is already a percentage number (e.g. `0.33` means 0.33%,
   not a fraction) — the original code multiplied by 100 again, producing
   absurd values like 33%. Fixed to compute `dividendRate / spot * 100` as
   the primary method, with the raw `dividendYield` value as a fallback (no
   rescaling).
2. **Stale ex-dividend date**: `yfinance` only exposes the *last* (historical)
   ex-dividend date, which can be months in the past. Added
   `estimated_next_ex_dividend_date`, projected from the median historical
   dividend-payment cadence, with `days_to_next_ex_dividend` as the
   forward-looking figure. `last_ex_dividend_date` is kept separately for
   reference.
3. **Chart canvas collapsing/ballooning**: Chart.js's `maintainAspectRatio: false`
   needs a sized parent container — without one, canvas height grew
   unbounded (observed at 3614px). Fixed by wrapping every `<canvas>` in a
   `.chart-wrap` div with an explicit inline pixel height.

## Frontend (`site/`)

- Dark finance theme, same design tokens/palette as the GEX dashboards
  (`--color-bg: #0a0e14`, accent `#22d3ee`, call `#3b82f6`, put `#fb7185`,
  positive `#34d399`, negative `#f87171`, warning `#fbbf24`, plus
  `--color-purple: #a78bfa` used for the Market Regime tab and the Bollinger
  Band shading).
- 5 tab panels, manual ticker input + Load button (no auto-refresh, no
  scheduling — by design, per the owner's explicit instruction that ticker
  selection is manual before each run).
- Price/Technical tab (expanded this session) now renders, top to bottom:
  KPI row (Trend, RSI, MACD Cross, ATR) → price chart with SMA20/50/200 +
  Bollinger Band shading + support/resistance dashed lines + 60-day trend
  line overlay → a synced volume bar panel (green/red by up/down day) →
  a Key Support & Resistance card (ranked by touch count) → a 60-Day Trend
  Line KPI card → a standalone RSI(14) chart with 30/70 reference bands →
  Bollinger %B / Volume-vs-avg / 52-week-range mini cards.
- All charts are Chart.js. Support/resistance and reference lines (30/70 on
  RSI) are implemented as constant-value datasets (flat lines) rather than
  an annotation plugin, to avoid adding a new dependency.
- The trend line is drawn as a sparse two-point dataset (`null` everywhere
  except the regression window's start/end index) with `spanGaps: true`,
  so Chart.js draws a single straight segment without needing per-point
  regression values.

## Deployment

- Deployed via `deploy_website` with `project_path=site/`, `entry_point=index.html`.
- **Asset ID for future redeploys: `ccf463a3-c984-4591-b4c8-6450c8c4e748`**
  — always pass this as `update_asset_id` so redeploys update the same
  artifact/URL instead of creating a new one.
- Live preview: the `/computer/a` app attached in the Perplexity Computer
  thread (do not hardcode/share the URL elsewhere — call `deploy_website`
  again with the same `update_asset_id` to refresh it).

## Git status

Local repository only (`git init` was run, commits made under
`agent@local` / "Computer Agent"). **Not pushed to GitHub** — this was an
explicit owner instruction for this project (unlike the two GEX dashboards,
which are on GitHub with Actions automation). Do not add a remote or push
unless the owner explicitly asks.

## Known limitations

1. **`yfinance` is an unofficial API** — occasional stale reads, rate limits,
   or missing fields are possible. The pipeline uses a `safe()` wrapper
   around most calls so a single failed field doesn't crash the whole run.
2. **ETFs and indices** (e.g. SPY) naturally lack sector, earnings, and
   dividend-cadence data — these fields degrade gracefully to `null` /
   a `[warn]` log line rather than crashing.
3. **Support/resistance and trend-line detection are simple, unweighted
   heuristics** (local-extrema clustering, linear regression) — they are a
   starting point for judgment, not a precise technical-analysis engine.
   Thinly-traded or very choppy names may produce fewer or noisier levels.
4. **No gamma-based walls or max pain in this project** — see
   `DECISION_GUIDE.md` for how to pull those from the GEX dashboards
   instead.
5. **Manual refresh workflow**: refreshing a ticker's data requires
   re-running the script and (if you want the live preview to reflect it)
   re-deploying. There is no auto-refresh — this was requested by the owner.

## Natural next enhancements (if asked "what should we add")

- A "compare to GEX dashboard" panel that lets the owner paste in that
  ticker's call wall / put wall / max pain / gamma flip values so both
  data sets render side by side in one view (currently a manual cross-check
  per `DECISION_GUIDE.md`).
- Minimum-liquidity guardrails (flag thin option chains where OI-based
  levels aren't meaningful) — same caveat already noted in the GEX
  dashboard's handover notes.
- A saved-ticker history so multiple past runs for the same name can be
  compared over time.
