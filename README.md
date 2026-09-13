# Options Indicators Dashboard

Standalone options-trading pre-trade checklist for a single ticker. Not
connected to the GEX (gamma exposure) dashboard projects — see
`DECISION_GUIDE.md` for how to use them together.

## What this shows

1. **Volatility Metrics** — ATM IV, skew, expected move, term structure, realized vol, IV richness
2. **Price / Technical** — trend, RSI, MACD, Bollinger Bands, ATR, price chart w/ SMAs + support/resistance + trend line + volume, 52w range
3. **Liquidity / Positioning** — put/call OI & volume ratios, top OI strikes, bid-ask spreads, short interest
4. **Events** — next earnings + past move history, next ex-dividend (estimated), upcoming FOMC meetings
5. **Market Regime** — VIX level & term structure, SPY trend, beta/correlation, sector relative strength

## Option A: Run it yourself locally (or via Perplexity Computer)

```
python3 scripts/compute_indicators.py TICKER   # e.g. python3 scripts/compute_indicators.py NVDA
```

This writes `site/data/TICKER.json` and updates `site/data/last_ticker.json`.
Then open `site/index.html` (or re-run `deploy_website` if using Perplexity
Computer) to view it — or just type the ticker into the dashboard's "Load"
box if that ticker's JSON file already exists in the deployed `data/` folder.

## Option B: Run it on GitHub, on demand, from any device

Once set up on GitHub (see `GITHUB_SETUP.md`), you don't need Python
installed anywhere — you trigger a run from the GitHub Actions tab and it
publishes the result to a public GitHub Pages URL.

1. Go to the **Actions** tab of the repo.
2. Click **On-Demand Options Indicators** in the left sidebar.
3. Click **Run workflow**, type the ticker (e.g. `AAPL`), click the green **Run workflow** button.
4. Wait about a minute, then open your GitHub Pages link — it now reflects that ticker.

Repeat any time you want to check a different ticker. There's no schedule —
it only runs when you trigger it.

## Project structure

```
.
├── scripts/
│   └── compute_indicators.py       # takes a ticker (env var or arg), computes all 5 tabs' data
├── site/
│   ├── index.html
│   ├── styles.css
│   ├── app.js
│   └── data/
│       └── <TICKER>.json           # one file per ticker you've run
├── .github/workflows/
│   └── on-demand-indicators.yml    # workflow_dispatch only, takes a "ticker" input
├── requirements.txt
├── README.md                       # this file
├── HANDOVER.md                     # architecture notes for handing this off to another AI tool
├── DECISION_GUIDE.md               # how to use this + the GEX dashboard to make a trade decision
└── GITHUB_SETUP.md                 # one-time manual setup steps for GitHub + GitHub Pages
```

## Notes

- Data source: [Yahoo Finance via `yfinance`](https://pypi.org/project/yfinance/).
  This is a free, unofficial source, so occasional stale reads or minor
  quote lag are expected.
- ETFs and indices (e.g. SPY) naturally lack sector/earnings/dividend data —
  the dashboard handles this gracefully rather than failing.
