"""
Options Trading Indicators Dashboard — data pipeline.

Computes a five-panel indicator set for a single ticker, ranked by importance
for a trader deciding whether to write or buy puts/calls:

  1. volatility     — ATM IV, term structure, skew, realized vol, IV-HV spread,
                       expected move (most directly informs buy-vs-sell-premium)
  2. technicals     — trend (SMAs), RSI, MACD, Bollinger Bands, ATR, volume,
                       52-week range (informs strike/timing selection)
  3. liquidity       — open interest, volume, put/call ratios, bid-ask spread
                       health, short interest (informs tradability/fill risk)
  4. events          — earnings date, ex-dividend date, past earnings-day
                       moves, upcoming FOMC meetings (informs event risk)
  5. regime          — VIX level/percentile, VIX term structure, SPY trend,
                       sector relative strength, beta, correlation (informs
                       the macro backdrop the trade sits inside)

Usage:
    TICKER=AAPL python3 scripts/compute_indicators.py
    python3 scripts/compute_indicators.py AAPL

Writes site/data/<TICKER>.json and updates site/data/last_ticker.json so the
frontend knows which ticker to load by default. No API keys required
(yfinance only). Meant to be run manually/on-demand — not on a schedule.
"""
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import yfinance as yf

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "site", "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Official Fed calendar (federalreserve.gov/monetarypolicy/fomccalendars.htm).
# Meetings marked with a Summary of Economic Projections ("dot plot") use *.
# Update this list at the start of each year.
FOMC_MEETINGS_2026 = [
    {"range": "Jan 27-28, 2026", "decision_date": "2026-01-28", "has_sep": False},
    {"range": "Mar 17-18, 2026", "decision_date": "2026-03-18", "has_sep": True},
    {"range": "Apr 28-29, 2026", "decision_date": "2026-04-29", "has_sep": False},
    {"range": "Jun 16-17, 2026", "decision_date": "2026-06-17", "has_sep": True},
    {"range": "Jul 28-29, 2026", "decision_date": "2026-07-29", "has_sep": False},
    {"range": "Sep 15-16, 2026", "decision_date": "2026-09-16", "has_sep": True},
    {"range": "Oct 27-28, 2026", "decision_date": "2026-10-28", "has_sep": False},
    {"range": "Dec 8-9, 2026", "decision_date": "2026-12-09", "has_sep": True},
]

SECTOR_ETF_MAP = {
    "Technology": "XLK",
    "Financial Services": "XLF",
    "Financials": "XLF",
    "Healthcare": "XLV",
    "Health Care": "XLV",
    "Consumer Cyclical": "XLY",
    "Consumer Discretionary": "XLY",
    "Consumer Defensive": "XLP",
    "Consumer Staples": "XLP",
    "Energy": "XLE",
    "Industrials": "XLI",
    "Basic Materials": "XLB",
    "Materials": "XLB",
    "Real Estate": "XLRE",
    "Utilities": "XLU",
    "Communication Services": "XLC",
}

TICKER = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("TICKER", "")).strip().upper()
if not TICKER:
    print("Usage: TICKER=AAPL python3 scripts/compute_indicators.py  (or pass ticker as arg)", file=sys.stderr)
    sys.exit(1)


def _none_safe(x):
    """Recursively convert numpy/pandas scalars to plain Python + NaN->None."""
    if isinstance(x, dict):
        return {k: _none_safe(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_none_safe(v) for v in x]
    if isinstance(x, (np.floating, np.integer)):
        x = x.item()
    if isinstance(x, float) and (np.isnan(x) or np.isinf(x)):
        return None
    if isinstance(x, (pd.Timestamp, datetime)):
        return x.strftime("%Y-%m-%d")
    return x


def safe(fn, default=None, label=""):
    try:
        return fn()
    except Exception as ex:
        print(f"[warn] {label or fn}: {ex}", file=sys.stderr)
        return default


# ---------------------------------------------------------------------------
# Price history + technical indicators
# ---------------------------------------------------------------------------

def load_history(ticker, period="1y"):
    h = yf.Ticker(ticker).history(period=period, auto_adjust=False)
    if h.empty:
        raise RuntimeError(f"no price history for {ticker}")
    h.index = pd.to_datetime(h.index).tz_localize(None)
    return h


def rsi(series, window=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def bollinger(series, window=20, num_std=2):
    mid = series.rolling(window).mean()
    std = series.rolling(window).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    pct_b = (series - lower) / (upper - lower)
    return mid, upper, lower, pct_b


def pivot_levels(hist, lookback=120, order=3, max_levels=3, tol_pct=1.25):
    """Cluster recent swing highs/lows into a handful of key support and
    resistance price levels around the current spot.

    A bar is a pivot high/low if its High/Low is the most extreme value in a
    window of `order` bars on each side. Nearby pivots (within `tol_pct` of
    each other) are merged into one level, weighted by how many times price
    touched that zone (more touches = more significant level).
    """
    sub = hist.tail(lookback)
    highs, lows = sub["High"].values, sub["Low"].values
    spot = float(sub["Close"].iloc[-1])
    n = len(sub)

    pivot_highs, pivot_lows = [], []
    for i in range(order, n - order):
        window_h = highs[i - order:i + order + 1]
        window_l = lows[i - order:i + order + 1]
        if highs[i] == window_h.max():
            pivot_highs.append(float(highs[i]))
        if lows[i] == window_l.min():
            pivot_lows.append(float(lows[i]))

    def cluster(levels):
        if not levels:
            return []
        levels = sorted(levels)
        clusters = [[levels[0]]]
        for lv in levels[1:]:
            if abs(lv - clusters[-1][-1]) / clusters[-1][-1] * 100 <= tol_pct:
                clusters[-1].append(lv)
            else:
                clusters.append([lv])
        return [{"level": float(np.mean(c)), "touches": len(c)} for c in clusters]

    resistance = [c for c in cluster(pivot_highs) if c["level"] > spot]
    support = [c for c in cluster(pivot_lows) if c["level"] < spot]

    # Prefer levels touched more often; break ties by proximity to spot.
    resistance.sort(key=lambda c: (-c["touches"], c["level"] - spot))
    support.sort(key=lambda c: (-c["touches"], spot - c["level"]))

    return resistance[:max_levels], support[:max_levels]


def linear_trend(close, window=60):
    """Least-squares trend line over the last `window` closes. Returns the
    line's endpoints (for chart overlay) plus a direction label."""
    sub = close.tail(window).dropna()
    if len(sub) < 5:
        return None
    x = np.arange(len(sub))
    slope, intercept = np.polyfit(x, sub.values, 1)
    start_value = float(intercept)
    end_value = float(slope * (len(sub) - 1) + intercept)
    pct_change_over_window = (end_value - start_value) / start_value * 100 if start_value else 0.0
    return {
        "start_date": sub.index[0].strftime("%Y-%m-%d"),
        "start_value": start_value,
        "end_date": sub.index[-1].strftime("%Y-%m-%d"),
        "end_value": end_value,
        "window_days": int(window),
        "pct_change_over_window": float(pct_change_over_window),
        "direction": "Uptrend" if slope > 0 else "Downtrend" if slope < 0 else "Flat",
    }


def atr(hist, window=14):
    high, low, close = hist["High"], hist["Low"], hist["Close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()


def build_technicals(hist):
    close = hist["Close"]
    spot = float(close.iloc[-1])
    sma20_series = close.rolling(20).mean()
    sma50_series = close.rolling(50).mean()
    sma200_series = close.rolling(200).mean()
    sma20 = sma20_series.iloc[-1]
    sma50 = sma50_series.iloc[-1]
    sma200 = sma200_series.iloc[-1] if len(close) >= 200 else None
    rsi_series = rsi(close)
    rsi14 = rsi_series.iloc[-1]
    macd_line, signal_line, hist_line = macd(close)
    bb_mid, bb_upper, bb_lower, pct_b = bollinger(close)
    atr14 = atr(hist).iloc[-1]
    resistance_levels, support_levels = pivot_levels(hist)
    trend_line = linear_trend(close, window=60)
    vol_today = float(hist["Volume"].iloc[-1])
    vol_avg20 = float(hist["Volume"].rolling(20).mean().iloc[-1])
    hi_52w = float(close.tail(252).max())
    lo_52w = float(close.tail(252).min())
    prev_close = float(close.iloc[-2]) if len(close) > 1 else spot

    def pct_dist(a, b):
        return None if (a is None or b in (None, 0) or pd.isna(a) or pd.isna(b)) else float((a - b) / b * 100)

    return {
        "spot": spot,
        "day_change_pct": pct_dist(spot, prev_close),
        "sma20": None if pd.isna(sma20) else float(sma20),
        "sma50": None if pd.isna(sma50) else float(sma50),
        "sma200": None if sma200 is None or pd.isna(sma200) else float(sma200),
        "pct_vs_sma20": pct_dist(spot, sma20),
        "pct_vs_sma50": pct_dist(spot, sma50),
        "pct_vs_sma200": pct_dist(spot, sma200),
        "trend_label": (
            "Uptrend" if (not pd.isna(sma50) and sma200 is not None and not pd.isna(sma200) and spot > sma50 > sma200)
            else "Downtrend" if (not pd.isna(sma50) and sma200 is not None and not pd.isna(sma200) and spot < sma50 < sma200)
            else "Mixed / transitional"
        ),
        "rsi14": None if pd.isna(rsi14) else float(rsi14),
        "rsi_label": (
            "Overbought" if not pd.isna(rsi14) and rsi14 >= 70
            else "Oversold" if not pd.isna(rsi14) and rsi14 <= 30
            else "Neutral"
        ),
        "macd": None if pd.isna(macd_line.iloc[-1]) else float(macd_line.iloc[-1]),
        "macd_signal": None if pd.isna(signal_line.iloc[-1]) else float(signal_line.iloc[-1]),
        "macd_hist": None if pd.isna(hist_line.iloc[-1]) else float(hist_line.iloc[-1]),
        "macd_cross": (
            "Bullish" if hist_line.iloc[-1] > 0 and hist_line.iloc[-2] <= 0
            else "Bearish" if hist_line.iloc[-1] < 0 and hist_line.iloc[-2] >= 0
            else "Bullish" if hist_line.iloc[-1] > 0 else "Bearish"
        ) if len(hist_line) > 1 and not pd.isna(hist_line.iloc[-1]) else None,
        "bollinger_upper": None if pd.isna(bb_upper.iloc[-1]) else float(bb_upper.iloc[-1]),
        "bollinger_lower": None if pd.isna(bb_lower.iloc[-1]) else float(bb_lower.iloc[-1]),
        "percent_b": None if pd.isna(pct_b.iloc[-1]) else float(pct_b.iloc[-1]),
        "atr14": None if pd.isna(atr14) else float(atr14),
        "atr_pct": None if pd.isna(atr14) else float(atr14 / spot * 100),
        "volume_today": vol_today,
        "volume_avg20": vol_avg20,
        "volume_ratio": None if not vol_avg20 else float(vol_today / vol_avg20),
        "high_52w": hi_52w,
        "low_52w": lo_52w,
        "pct_from_52w_high": pct_dist(spot, hi_52w),
        "pct_from_52w_low": pct_dist(spot, lo_52w),
        "resistance_levels": resistance_levels,
        "support_levels": support_levels,
        "trend_line": trend_line,
        "price_series": [
            {
                "date": d.strftime("%Y-%m-%d"),
                "close": None if pd.isna(c) else float(c),
                "volume": None if pd.isna(v) else float(v),
                "bollinger_upper": None if pd.isna(bu) else float(bu),
                "bollinger_lower": None if pd.isna(bl) else float(bl),
                "rsi": None if pd.isna(r) else float(r),
            }
            for d, c, v, bu, bl, r in zip(
                close.tail(180).index,
                close.tail(180).values,
                hist["Volume"].tail(180).values,
                bb_upper.tail(180).values,
                bb_lower.tail(180).values,
                rsi_series.tail(180).values,
            )
        ],
    }


def realized_vol(close, window):
    log_ret = np.log(close / close.shift(1))
    return log_ret.rolling(window).std() * np.sqrt(252) * 100


# ---------------------------------------------------------------------------
# Options chain: volatility + liquidity metrics
# ---------------------------------------------------------------------------

def pick_expirations(tkr, spot_date):
    all_exps = list(tkr.options)
    if not all_exps:
        return None, None, []
    today = datetime.strptime(spot_date, "%Y-%m-%d")
    dated = [(e, (datetime.strptime(e, "%Y-%m-%d") - today).days) for e in all_exps]
    dated = [d for d in dated if d[1] >= 0]
    if not dated:
        return None, None, []
    primary = next((e for e, dte in dated if dte >= 21), dated[0][0])
    primary_dte = dict(dated)[primary]
    secondary_candidates = [(e, dte) for e, dte in dated if dte >= primary_dte + 20]
    secondary = secondary_candidates[0][0] if secondary_candidates else None
    near_term = [e for e, dte in dated if dte <= 45]
    return primary, secondary, near_term


def nearest_strike_row(df, target):
    if df.empty:
        return None
    idx = (df["strike"] - target).abs().idxmin()
    return df.loc[idx]


def mid_price(row):
    bid, ask, last = float(row.get("bid", 0) or 0), float(row.get("ask", 0) or 0), float(row.get("lastPrice", 0) or 0)
    if bid > 0 and ask > 0:
        return (bid + ask) / 2
    return last


def spread_pct(row):
    bid, ask = float(row.get("bid", 0) or 0), float(row.get("ask", 0) or 0)
    mid = (bid + ask) / 2
    if mid <= 0:
        return None
    return (ask - bid) / mid * 100


def build_volatility_and_liquidity(tkr, spot, as_of_date):
    primary, secondary, near_term_exps = pick_expirations(tkr, as_of_date)
    result_vol = {"primary_expiration": primary, "secondary_expiration": secondary}
    result_liq = {}

    if not primary:
        result_vol["note"] = "No listed options found for this ticker."
        return result_vol, result_liq

    chain_primary = tkr.option_chain(primary)
    calls_p, puts_p = chain_primary.calls, chain_primary.puts

    atm_call = nearest_strike_row(calls_p, spot)
    atm_put = nearest_strike_row(puts_p, spot)
    atm_iv = None
    if atm_call is not None and atm_put is not None:
        ivs = [v for v in [atm_call.get("impliedVolatility"), atm_put.get("impliedVolatility")] if v and v > 0]
        atm_iv = float(np.mean(ivs) * 100) if ivs else None
    result_vol["atm_iv_pct"] = atm_iv

    # Skew: ~10% OTM put vs ~10% OTM call, same (primary) expiry
    otm_put = nearest_strike_row(puts_p, spot * 0.90)
    otm_call = nearest_strike_row(calls_p, spot * 1.10)
    put_iv = float(otm_put["impliedVolatility"] * 100) if otm_put is not None and otm_put.get("impliedVolatility") else None
    call_iv = float(otm_call["impliedVolatility"] * 100) if otm_call is not None and otm_call.get("impliedVolatility") else None
    result_vol["otm_put_iv_pct"] = put_iv
    result_vol["otm_call_iv_pct"] = call_iv
    result_vol["skew_pct_pts"] = (put_iv - call_iv) if (put_iv is not None and call_iv is not None) else None

    # Expected move from ATM straddle
    if atm_call is not None and atm_put is not None:
        straddle = mid_price(atm_call) + mid_price(atm_put)
        result_vol["expected_move_dollars"] = float(straddle)
        result_vol["expected_move_pct"] = float(straddle / spot * 100)
    else:
        result_vol["expected_move_dollars"] = None
        result_vol["expected_move_pct"] = None

    # Term structure vs secondary expiration
    if secondary:
        chain_secondary = tkr.option_chain(secondary)
        calls_s, puts_s = chain_secondary.calls, chain_secondary.puts
        atm_call_s = nearest_strike_row(calls_s, spot)
        atm_put_s = nearest_strike_row(puts_s, spot)
        if atm_call_s is not None and atm_put_s is not None:
            ivs_s = [v for v in [atm_call_s.get("impliedVolatility"), atm_put_s.get("impliedVolatility")] if v and v > 0]
            atm_iv_s = float(np.mean(ivs_s) * 100) if ivs_s else None
            result_vol["secondary_atm_iv_pct"] = atm_iv_s
            if atm_iv_s and atm_iv:
                result_vol["term_structure_label"] = "Contango (calm)" if atm_iv_s > atm_iv else "Backwardation (event-priced)"
    else:
        result_vol["secondary_atm_iv_pct"] = None

    # Liquidity: aggregate OI/volume across near-term expirations, bid-ask spread near ATM
    total_call_oi = total_put_oi = total_call_vol = total_put_vol = 0.0
    top_call_oi_strike = top_call_oi = top_put_oi_strike = top_put_oi = None
    spreads = []
    for exp in near_term_exps or [primary]:
        try:
            ch = tkr.option_chain(exp)
        except Exception:
            continue
        for df, is_call in ((ch.calls, True), (ch.puts, False)):
            oi = df["openInterest"].fillna(0)
            vol = df["volume"].fillna(0)
            if is_call:
                total_call_oi += float(oi.sum())
                total_call_vol += float(vol.sum())
                if not oi.empty and oi.max() > (top_call_oi or -1):
                    top_call_oi = float(oi.max())
                    top_call_oi_strike = float(df.loc[oi.idxmax(), "strike"])
            else:
                total_put_oi += float(oi.sum())
                total_put_vol += float(vol.sum())
                if not oi.empty and oi.max() > (top_put_oi or -1):
                    top_put_oi = float(oi.max())
                    top_put_oi_strike = float(df.loc[oi.idxmax(), "strike"])
        if exp == primary:
            near_calls = calls_p[(calls_p["strike"] >= spot * 0.95) & (calls_p["strike"] <= spot * 1.05)]
            near_puts = puts_p[(puts_p["strike"] >= spot * 0.95) & (puts_p["strike"] <= spot * 1.05)]
            for _, r in pd.concat([near_calls, near_puts]).iterrows():
                sp = spread_pct(r)
                if sp is not None:
                    spreads.append(sp)

    result_liq["total_call_oi"] = total_call_oi
    result_liq["total_put_oi"] = total_put_oi
    result_liq["put_call_oi_ratio"] = (total_put_oi / total_call_oi) if total_call_oi else None
    result_liq["total_call_volume"] = total_call_vol
    result_liq["total_put_volume"] = total_put_vol
    result_liq["put_call_volume_ratio"] = (total_put_vol / total_call_vol) if total_call_vol else None
    result_liq["top_call_oi_strike"] = top_call_oi_strike
    result_liq["top_call_oi"] = top_call_oi
    result_liq["top_put_oi_strike"] = top_put_oi_strike
    result_liq["top_put_oi"] = top_put_oi
    result_liq["avg_atm_spread_pct"] = float(np.mean(spreads)) if spreads else None
    result_liq["near_term_expirations_used"] = near_term_exps

    return result_vol, result_liq


# ---------------------------------------------------------------------------
# Events: earnings, dividends, FOMC
# ---------------------------------------------------------------------------

def build_events(tkr, info, hist, as_of_date, primary_expiration, spot):
    today = datetime.strptime(as_of_date, "%Y-%m-%d")
    events = {}

    earnings_df = safe(lambda: tkr.get_earnings_dates(limit=12), default=None, label="earnings dates")
    next_earnings, past_earnings_moves = None, []
    if earnings_df is not None and not earnings_df.empty:
        earnings_df = earnings_df.copy()
        earnings_df.index = pd.to_datetime(earnings_df.index).tz_localize(None)
        future = earnings_df[earnings_df.index.normalize() >= today]
        past = earnings_df[earnings_df.index.normalize() < today].sort_index(ascending=False)
        if not future.empty:
            next_dt = future.index.min()
            next_earnings = {
                "date": next_dt.strftime("%Y-%m-%d"),
                "days_until": int((next_dt - today).days),
                "eps_estimate": _none_safe(future.loc[next_dt].get("EPS Estimate")) if "EPS Estimate" in future.columns else None,
            }
        close = hist["Close"]
        for dt in past.index[:4]:
            try:
                before = close[close.index <= dt - pd.Timedelta(days=1)].iloc[-1]
                after_candidates = close[close.index >= dt]
                if after_candidates.empty:
                    continue
                after = after_candidates.iloc[0]
                move_pct = float((after - before) / before * 100)
                past_earnings_moves.append({"date": dt.strftime("%Y-%m-%d"), "move_pct": move_pct})
            except Exception:
                continue

    events["next_earnings"] = next_earnings
    events["earnings_inside_primary_expiration"] = (
        bool(next_earnings and primary_expiration and next_earnings["date"] <= primary_expiration)
        if next_earnings and primary_expiration else None
    )
    events["past_earnings_moves"] = past_earnings_moves
    if past_earnings_moves:
        events["avg_abs_earnings_move_pct"] = float(np.mean([abs(m["move_pct"]) for m in past_earnings_moves]))

    ex_div_ts = info.get("exDividendDate")
    last_ex_div_date = None
    if ex_div_ts:
        last_ex_div_date = datetime.fromtimestamp(ex_div_ts, tz=timezone.utc).replace(tzinfo=None)
    events["last_ex_dividend_date"] = last_ex_div_date.strftime("%Y-%m-%d") if last_ex_div_date else None

    # yfinance's exDividendDate is the most recent *past* ex-div date, not a
    # forward projection. Estimate the next one from the historical payment
    # cadence (median gap between the last several dividend dates) so we can
    # show a forward-looking days-to-next-ex-div figure.
    next_ex_div_date = None
    div_history = safe(lambda: tkr.dividends, default=None, label="dividend history")
    if div_history is not None and len(div_history) >= 2:
        div_dates = pd.to_datetime(div_history.index).tz_localize(None)
        gaps = pd.Series(div_dates[1:]) - pd.Series(div_dates[:-1])
        median_gap_days = float(np.median([g.days for g in gaps.tail(4)]))
        base_date = last_ex_div_date or div_dates[-1].to_pydatetime()
        candidate = base_date
        while candidate <= today:
            candidate = candidate + pd.Timedelta(days=median_gap_days)
        next_ex_div_date = candidate
    events["estimated_next_ex_dividend_date"] = next_ex_div_date.strftime("%Y-%m-%d") if next_ex_div_date else None
    events["days_to_next_ex_dividend"] = int((next_ex_div_date - today).days) if next_ex_div_date else None
    # yfinance's `get_info()` reports dividendYield already as a percentage
    # number (e.g. 0.33 means 0.33%), not a fraction — do not rescale it.
    # dividendRate (annual $/share) / spot is the more reliable cross-check
    # when available, since the raw yield field's units have shifted across
    # yfinance versions in the past.
    div_rate = info.get("dividendRate")
    div_yield_raw = info.get("dividendYield")
    if div_rate is not None and spot:
        events["dividend_yield_pct"] = float(div_rate / spot * 100)
    elif div_yield_raw is not None:
        events["dividend_yield_pct"] = float(div_yield_raw)
    else:
        events["dividend_yield_pct"] = None

    upcoming_fomc = [m for m in FOMC_MEETINGS_2026 if m["decision_date"] >= as_of_date][:3]
    for m in upcoming_fomc:
        m["days_until"] = (datetime.strptime(m["decision_date"], "%Y-%m-%d") - today).days
    events["upcoming_fomc_meetings"] = upcoming_fomc

    return events


# ---------------------------------------------------------------------------
# Market regime
# ---------------------------------------------------------------------------

def build_regime(ticker_hist, info, as_of_date):
    regime = {}

    vix_hist = safe(lambda: load_history("^VIX", period="1y"), default=None, label="VIX history")
    if vix_hist is not None:
        vix_close = vix_hist["Close"]
        vix_now = float(vix_close.iloc[-1])
        vix_pctile = float((vix_close < vix_now).mean() * 100)
        regime["vix_level"] = vix_now
        regime["vix_1y_percentile"] = vix_pctile
    else:
        regime["vix_level"] = regime["vix_1y_percentile"] = None

    vix3m_hist = safe(lambda: load_history("^VIX3M", period="5d"), default=None, label="VIX3M history")
    if vix3m_hist is not None and regime.get("vix_level"):
        vix3m_now = float(vix3m_hist["Close"].iloc[-1])
        regime["vix3m_level"] = vix3m_now
        regime["vix_term_structure_label"] = "Contango (calm)" if vix3m_now > regime["vix_level"] else "Backwardation (stressed)"
    else:
        regime["vix3m_level"] = regime["vix_term_structure_label"] = None

    spy_hist = safe(lambda: load_history("SPY", period="1y"), default=None, label="SPY history")
    if spy_hist is not None:
        spy_close = spy_hist["Close"]
        spy_now = float(spy_close.iloc[-1])
        spy_sma50 = float(spy_close.rolling(50).mean().iloc[-1])
        spy_sma200 = float(spy_close.rolling(200).mean().iloc[-1]) if len(spy_close) >= 200 else None
        if spy_sma200 and spy_now > spy_sma50 > spy_sma200:
            label = "Broad market uptrend"
        elif spy_sma200 and spy_now < spy_sma50 < spy_sma200:
            label = "Broad market downtrend"
        else:
            label = "Mixed / choppy market"
        regime["spy_price"] = spy_now
        regime["spy_sma50"] = spy_sma50
        regime["spy_sma200"] = spy_sma200
        regime["market_trend_label"] = label

        # Beta + correlation vs SPY using the ticker's own history
        common = ticker_hist["Close"].align(spy_close, join="inner")
        t_ret = np.log(common[0] / common[0].shift(1)).dropna()
        s_ret = np.log(common[1] / common[1].shift(1)).dropna()
        aligned = pd.concat([t_ret, s_ret], axis=1).dropna()
        aligned.columns = ["t", "s"]
        beta_computed = None
        corr = None
        if len(aligned) > 20:
            cov = aligned["t"].cov(aligned["s"])
            var = aligned["s"].var()
            beta_computed = float(cov / var) if var else None
            corr = float(aligned["t"].tail(60).corr(aligned["s"].tail(60))) if len(aligned) >= 60 else float(aligned["t"].corr(aligned["s"]))
        regime["beta"] = info.get("beta") if info.get("beta") is not None else beta_computed
        regime["beta_source"] = "reported" if info.get("beta") is not None else "computed (1y regression)"
        regime["correlation_to_spy_60d"] = corr

        # Sector relative strength
        sector = info.get("sector")
        etf = SECTOR_ETF_MAP.get(sector)
        if etf:
            etf_hist = safe(lambda: load_history(etf, period="4mo"), default=None, label=f"{etf} history")
            if etf_hist is not None:
                def ret(series, days):
                    if len(series) <= days:
                        return None
                    return float((series.iloc[-1] / series.iloc[-1 - days] - 1) * 100)
                spy_1m, spy_3m = ret(spy_close.tail(80), 21), ret(spy_close.tail(80), 63)
                etf_close = etf_hist["Close"]
                etf_1m, etf_3m = ret(etf_close, 21), ret(etf_close, 63)
                regime["sector"] = sector
                regime["sector_etf"] = etf
                regime["sector_return_1m_pct"] = etf_1m
                regime["sector_return_3m_pct"] = etf_3m
                regime["sector_vs_spy_1m_pct"] = None if etf_1m is None or spy_1m is None else etf_1m - spy_1m
                regime["sector_vs_spy_3m_pct"] = None if etf_3m is None or spy_3m is None else etf_3m - spy_3m
    return regime


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    tkr = yf.Ticker(TICKER)
    hist = load_history(TICKER, period="1y")
    as_of_date = hist.index[-1].strftime("%Y-%m-%d")
    spot = float(hist["Close"].iloc[-1])

    info = safe(lambda: tkr.get_info(), default={}, label="ticker info") or {}

    technicals = build_technicals(hist)

    close = hist["Close"]
    hv10 = realized_vol(close, 10).iloc[-1]
    hv20 = realized_vol(close, 20).iloc[-1]
    hv30 = realized_vol(close, 30).iloc[-1]
    hv60 = realized_vol(close, 60).iloc[-1]
    hv20_series = realized_vol(close, 20).dropna()
    hv20_percentile = float((hv20_series < hv20).mean() * 100) if not pd.isna(hv20) and len(hv20_series) > 20 else None

    volatility, liquidity = build_volatility_and_liquidity(tkr, spot, as_of_date)
    volatility["realized_vol_10d_pct"] = None if pd.isna(hv10) else float(hv10)
    volatility["realized_vol_20d_pct"] = None if pd.isna(hv20) else float(hv20)
    volatility["realized_vol_30d_pct"] = None if pd.isna(hv30) else float(hv30)
    volatility["realized_vol_60d_pct"] = None if pd.isna(hv60) else float(hv60)
    volatility["realized_vol_20d_percentile_1y"] = hv20_percentile
    if volatility.get("atm_iv_pct") is not None and not pd.isna(hv20):
        volatility["iv_minus_hv20_pts"] = float(volatility["atm_iv_pct"] - hv20)
        volatility["iv_richness_label"] = (
            "Rich (premium selling favored)" if volatility["iv_minus_hv20_pts"] > 5
            else "Cheap (premium buying favored)" if volatility["iv_minus_hv20_pts"] < -5
            else "Fairly priced"
        )

    liquidity["avg_daily_volume_30d"] = float(hist["Volume"].tail(30).mean())
    liquidity["short_percent_of_float_pct"] = safe(
        lambda: float(info["shortPercentOfFloat"] * 100) if info.get("shortPercentOfFloat") else None,
        default=None,
    )
    liquidity["short_ratio_days_to_cover"] = info.get("shortRatio")

    events = build_events(tkr, info, hist, as_of_date, volatility.get("primary_expiration"), spot)
    regime = build_regime(hist, info, as_of_date)

    output = {
        "meta": {
            "ticker": TICKER,
            "company_name": info.get("longName") or info.get("shortName") or TICKER,
            "sector": info.get("sector"),
            "as_of_date": as_of_date,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "spot": spot,
            "market_cap": info.get("marketCap"),
        },
        "volatility": volatility,
        "technicals": technicals,
        "liquidity": liquidity,
        "events": events,
        "regime": regime,
    }
    output = _none_safe(output)

    out_path = os.path.join(DATA_DIR, f"{TICKER}.json")
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    with open(os.path.join(DATA_DIR, "last_ticker.json"), "w") as f:
        json.dump({"ticker": TICKER}, f)

    print(f"Wrote {out_path}")
    print(json.dumps(output["meta"], indent=2))


if __name__ == "__main__":
    main()
