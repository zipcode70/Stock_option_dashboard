"""
Options Trading Indicators Dashboard — data pipeline.

Computes volatility, technical, liquidity, event, and regime indicators for a
single ticker. The options-chain path is defensive: missing, malformed, or
all-NA option data leaves the relevant indicator as null rather than failing
the whole GitHub Actions run.
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
    "Technology": "XLK", "Financial Services": "XLF", "Financials": "XLF",
    "Healthcare": "XLV", "Health Care": "XLV", "Consumer Cyclical": "XLY",
    "Consumer Discretionary": "XLY", "Consumer Defensive": "XLP",
    "Consumer Staples": "XLP", "Energy": "XLE", "Industrials": "XLI",
    "Basic Materials": "XLB", "Materials": "XLB", "Real Estate": "XLRE",
    "Utilities": "XLU", "Communication Services": "XLC",
}

TICKER = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("TICKER", "")).strip().upper()
if not TICKER:
    print("Usage: TICKER=AAPL python3 scripts/compute_indicators.py  (or pass ticker as arg)", file=sys.stderr)
    sys.exit(1)


def _none_safe(x):
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
    return macd_line, signal_line, macd_line - signal_line


def bollinger(series, window=20, num_std=2):
    mid = series.rolling(window).mean()
    std = series.rolling(window).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    return mid, upper, lower, (series - lower) / (upper - lower)


def pivot_levels(hist, lookback=120, order=3, max_levels=3, tol_pct=1.25):
    sub = hist.tail(lookback)
    highs, lows = sub["High"].values, sub["Low"].values
    spot = float(sub["Close"].iloc[-1])
    n = len(sub)
    pivot_highs, pivot_lows = [], []
    for i in range(order, n - order):
        if highs[i] == highs[i - order:i + order + 1].max():
            pivot_highs.append(float(highs[i]))
        if lows[i] == lows[i - order:i + order + 1].min():
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
    resistance.sort(key=lambda c: (-c["touches"], c["level"] - spot))
    support.sort(key=lambda c: (-c["touches"], spot - c["level"]))
    return resistance[:max_levels], support[:max_levels]


def linear_trend(close, window=60):
    sub = close.tail(window).dropna()
    if len(sub) < 5:
        return None
    x = np.arange(len(sub))
    slope, intercept = np.polyfit(x, sub.values, 1)
    start_value = float(intercept)
    end_value = float(slope * (len(sub) - 1) + intercept)
    return {
        "start_date": sub.index[0].strftime("%Y-%m-%d"), "start_value": start_value,
        "end_date": sub.index[-1].strftime("%Y-%m-%d"), "end_value": end_value,
        "window_days": int(window),
        "pct_change_over_window": float((end_value - start_value) / start_value * 100) if start_value else 0.0,
        "direction": "Uptrend" if slope > 0 else "Downtrend" if slope < 0 else "Flat",
    }


def atr(hist, window=14):
    high, low, close = hist["High"], hist["Low"], hist["Close"]
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()


def build_technicals(hist):
    close = hist["Close"]
    spot = float(close.iloc[-1])
    sma20_series, sma50_series, sma200_series = close.rolling(20).mean(), close.rolling(50).mean(), close.rolling(200).mean()
    sma20, sma50 = sma20_series.iloc[-1], sma50_series.iloc[-1]
    sma200 = sma200_series.iloc[-1] if len(close) >= 200 else None
    rsi_series = rsi(close)
    rsi14 = rsi_series.iloc[-1]
    macd_line, signal_line, hist_line = macd(close)
    _, bb_upper, bb_lower, pct_b = bollinger(close)
    atr14 = atr(hist).iloc[-1]
    resistance_levels, support_levels = pivot_levels(hist)
    vol_today = float(hist["Volume"].iloc[-1])
    vol_avg20 = float(hist["Volume"].rolling(20).mean().iloc[-1])
    hi_52w, lo_52w = float(close.tail(252).max()), float(close.tail(252).min())
    prev_close = float(close.iloc[-2]) if len(close) > 1 else spot

    def pct_dist(a, b):
        return None if (a is None or b in (None, 0) or pd.isna(a) or pd.isna(b)) else float((a - b) / b * 100)

    return {
        "spot": spot, "day_change_pct": pct_dist(spot, prev_close),
        "sma20": None if pd.isna(sma20) else float(sma20),
        "sma50": None if pd.isna(sma50) else float(sma50),
        "sma200": None if sma200 is None or pd.isna(sma200) else float(sma200),
        "pct_vs_sma20": pct_dist(spot, sma20), "pct_vs_sma50": pct_dist(spot, sma50), "pct_vs_sma200": pct_dist(spot, sma200),
        "trend_label": "Uptrend" if (not pd.isna(sma50) and sma200 is not None and not pd.isna(sma200) and spot > sma50 > sma200) else "Downtrend" if (not pd.isna(sma50) and sma200 is not None and not pd.isna(sma200) and spot < sma50 < sma200) else "Mixed / transitional",
        "rsi14": None if pd.isna(rsi14) else float(rsi14),
        "rsi_label": "Overbought" if not pd.isna(rsi14) and rsi14 >= 70 else "Oversold" if not pd.isna(rsi14) and rsi14 <= 30 else "Neutral",
        "macd": None if pd.isna(macd_line.iloc[-1]) else float(macd_line.iloc[-1]),
        "macd_signal": None if pd.isna(signal_line.iloc[-1]) else float(signal_line.iloc[-1]),
        "macd_hist": None if pd.isna(hist_line.iloc[-1]) else float(hist_line.iloc[-1]),
        "macd_cross": ("Bullish" if hist_line.iloc[-1] > 0 and hist_line.iloc[-2] <= 0 else "Bearish" if hist_line.iloc[-1] < 0 and hist_line.iloc[-2] >= 0 else "Bullish" if hist_line.iloc[-1] > 0 else "Bearish") if len(hist_line) > 1 and not pd.isna(hist_line.iloc[-1]) else None,
        "bollinger_upper": None if pd.isna(bb_upper.iloc[-1]) else float(bb_upper.iloc[-1]),
        "bollinger_lower": None if pd.isna(bb_lower.iloc[-1]) else float(bb_lower.iloc[-1]),
        "percent_b": None if pd.isna(pct_b.iloc[-1]) else float(pct_b.iloc[-1]),
        "atr14": None if pd.isna(atr14) else float(atr14), "atr_pct": None if pd.isna(atr14) else float(atr14 / spot * 100),
        "volume_today": vol_today, "volume_avg20": vol_avg20, "volume_ratio": None if not vol_avg20 else float(vol_today / vol_avg20),
        "high_52w": hi_52w, "low_52w": lo_52w, "pct_from_52w_high": pct_dist(spot, hi_52w), "pct_from_52w_low": pct_dist(spot, lo_52w),
        "resistance_levels": resistance_levels, "support_levels": support_levels, "trend_line": linear_trend(close, 60),
        "price_series": [{"date": d.strftime("%Y-%m-%d"), "close": None if pd.isna(c) else float(c), "volume": None if pd.isna(v) else float(v), "bollinger_upper": None if pd.isna(bu) else float(bu), "bollinger_lower": None if pd.isna(bl) else float(bl), "rsi": None if pd.isna(r) else float(r)} for d, c, v, bu, bl, r in zip(close.tail(180).index, close.tail(180).values, hist["Volume"].tail(180).values, bb_upper.tail(180).values, bb_lower.tail(180).values, rsi_series.tail(180).values)],
    }


def realized_vol(close, window):
    return np.log(close / close.shift(1)).rolling(window).std() * np.sqrt(252) * 100


# ---------------------------------------------------------------------------
# Options chain: defensive handling of empty/malformed Yahoo data
# ---------------------------------------------------------------------------

def pick_expirations(tkr, spot_date):
    all_exps = safe(lambda: list(tkr.options), default=[], label="option expirations") or []
    if not all_exps:
        return None, None, []
    try:
        today = datetime.strptime(spot_date, "%Y-%m-%d")
        dated = [(e, (datetime.strptime(e, "%Y-%m-%d") - today).days) for e in all_exps]
    except (TypeError, ValueError) as ex:
        print(f"[warn] invalid option expiration data: {ex}", file=sys.stderr)
        return None, None, []
    dated = [(e, dte) for e, dte in dated if dte >= 0]
    if not dated:
        return None, None, []
    primary, primary_dte = next(((e, dte) for e, dte in dated if dte >= 21), dated[0])
    secondary_candidates = [(e, dte) for e, dte in dated if dte >= primary_dte + 20]
    secondary = secondary_candidates[0][0] if secondary_candidates else None
    return primary, secondary, [e for e, dte in dated if dte <= 45]


def clean_option_chain(df, side, ticker, expiration):
    """Return a safe option DataFrame with numeric strike/OI/volume fields.

    Yahoo can return an empty frame or an all-NA strike column transiently,
    particularly during market-data outages. Those states are valid missing
    data, not fatal pipeline errors.
    """
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        print(f"[warn] {ticker} {expiration} {side}: empty option chain", file=sys.stderr)
        return pd.DataFrame()
    if "strike" not in df.columns:
        print(f"[warn] {ticker} {expiration} {side}: missing strike column", file=sys.stderr)
        return pd.DataFrame()
    cleaned = df.copy()
    for col in ("strike", "impliedVolatility", "bid", "ask", "lastPrice", "openInterest", "volume"):
        if col in cleaned.columns:
            cleaned[col] = pd.to_numeric(cleaned[col], errors="coerce")
    before = len(cleaned)
    cleaned = cleaned.dropna(subset=["strike"])
    if cleaned.empty:
        print(f"[warn] {ticker} {expiration} {side}: no valid numeric strikes ({before} rows received)", file=sys.stderr)
    return cleaned


def get_option_chain(tkr, expiration, ticker):
    chain = safe(lambda: tkr.option_chain(expiration), default=None, label=f"{ticker} option chain {expiration}")
    if chain is None:
        return pd.DataFrame(), pd.DataFrame()
    return (
        clean_option_chain(getattr(chain, "calls", None), "calls", ticker, expiration),
        clean_option_chain(getattr(chain, "puts", None), "puts", ticker, expiration),
    )


def nearest_strike_row(df, target):
    """Get row nearest to target only when valid numeric strikes exist."""
    if df is None or df.empty or "strike" not in df.columns or target is None or pd.isna(target):
        return None
    strikes = pd.to_numeric(df["strike"], errors="coerce")
    valid = df.loc[strikes.notna()].copy()
    if valid.empty:
        return None
    distances = (pd.to_numeric(valid["strike"], errors="coerce") - float(target)).abs()
    if distances.empty or distances.isna().all():
        return None
    return valid.loc[distances.idxmin()]


def numeric_value(row, field, default=0.0):
    if row is None:
        return default
    value = pd.to_numeric(pd.Series([row.get(field, np.nan)]), errors="coerce").iloc[0]
    return default if pd.isna(value) else float(value)


def valid_iv(row):
    iv = numeric_value(row, "impliedVolatility", default=np.nan)
    return float(iv) if pd.notna(iv) and iv > 0 else None


def mid_price(row):
    bid, ask, last = numeric_value(row, "bid"), numeric_value(row, "ask"), numeric_value(row, "lastPrice")
    return (bid + ask) / 2 if bid > 0 and ask > 0 else last


def spread_pct(row):
    bid, ask = numeric_value(row, "bid"), numeric_value(row, "ask")
    mid = (bid + ask) / 2
    return None if mid <= 0 else (ask - bid) / mid * 100


def build_volatility_and_liquidity(tkr, spot, as_of_date):
    primary, secondary, near_term_exps = pick_expirations(tkr, as_of_date)
    result_vol = {"primary_expiration": primary, "secondary_expiration": secondary, "secondary_atm_iv_pct": None, "term_structure_label": None}
    result_liq = {}

    if not primary:
        result_vol["note"] = "No listed options found for this ticker."
        return result_vol, result_liq

    calls_p, puts_p = get_option_chain(tkr, primary, TICKER)
    if calls_p.empty and puts_p.empty:
        result_vol["note"] = f"Option-chain data was unavailable or had no valid strikes for {primary}."

    atm_call, atm_put = nearest_strike_row(calls_p, spot), nearest_strike_row(puts_p, spot)
    atm_ivs = [iv for iv in (valid_iv(atm_call), valid_iv(atm_put)) if iv is not None]
    atm_iv = float(np.mean(atm_ivs) * 100) if atm_ivs else None
    result_vol["atm_iv_pct"] = atm_iv

    otm_put, otm_call = nearest_strike_row(puts_p, spot * 0.90), nearest_strike_row(calls_p, spot * 1.10)
    put_iv_raw, call_iv_raw = valid_iv(otm_put), valid_iv(otm_call)
    put_iv = put_iv_raw * 100 if put_iv_raw is not None else None
    call_iv = call_iv_raw * 100 if call_iv_raw is not None else None
    result_vol["otm_put_iv_pct"] = put_iv
    result_vol["otm_call_iv_pct"] = call_iv
    result_vol["skew_pct_pts"] = put_iv - call_iv if put_iv is not None and call_iv is not None else None

    if atm_call is not None and atm_put is not None and spot > 0:
        straddle = mid_price(atm_call) + mid_price(atm_put)
        result_vol["expected_move_dollars"] = float(straddle)
        result_vol["expected_move_pct"] = float(straddle / spot * 100)
    else:
        result_vol["expected_move_dollars"] = None
        result_vol["expected_move_pct"] = None

    if secondary:
        calls_s, puts_s = get_option_chain(tkr, secondary, TICKER)
        atm_call_s, atm_put_s = nearest_strike_row(calls_s, spot), nearest_strike_row(puts_s, spot)
        ivs_s = [iv for iv in (valid_iv(atm_call_s), valid_iv(atm_put_s)) if iv is not None]
        atm_iv_s = float(np.mean(ivs_s) * 100) if ivs_s else None
        result_vol["secondary_atm_iv_pct"] = atm_iv_s
        if atm_iv_s is not None and atm_iv is not None:
            result_vol["term_structure_label"] = "Contango (calm)" if atm_iv_s > atm_iv else "Backwardation (event-priced)"

    total_call_oi = total_put_oi = total_call_vol = total_put_vol = 0.0
    top_call_oi_strike = top_call_oi = top_put_oi_strike = top_put_oi = None
    spreads = []
    for exp in near_term_exps or [primary]:
        calls, puts = (calls_p, puts_p) if exp == primary else get_option_chain(tkr, exp, TICKER)
        for df, is_call in ((calls, True), (puts, False)):
            if df.empty:
                continue
            oi = pd.to_numeric(df.get("openInterest", pd.Series(0.0, index=df.index)), errors="coerce").fillna(0)
            vol = pd.to_numeric(df.get("volume", pd.Series(0.0, index=df.index)), errors="coerce").fillna(0)
            if is_call:
                total_call_oi += float(oi.sum())
                total_call_vol += float(vol.sum())
                if not oi.empty and oi.max() > (top_call_oi if top_call_oi is not None else -1):
                    top_call_oi = float(oi.max())
                    top_call_oi_strike = float(df.loc[oi.idxmax(), "strike"])
            else:
                total_put_oi += float(oi.sum())
                total_put_vol += float(vol.sum())
                if not oi.empty and oi.max() > (top_put_oi if top_put_oi is not None else -1):
                    top_put_oi = float(oi.max())
                    top_put_oi_strike = float(df.loc[oi.idxmax(), "strike"])
        if exp == primary:
            near_calls = calls_p[calls_p["strike"].between(spot * 0.95, spot * 1.05)] if not calls_p.empty else pd.DataFrame()
            near_puts = puts_p[puts_p["strike"].between(spot * 0.95, spot * 1.05)] if not puts_p.empty else pd.DataFrame()
            for _, row in pd.concat([near_calls, near_puts], ignore_index=True).iterrows():
                sp = spread_pct(row)
                if sp is not None:
                    spreads.append(sp)

    result_liq.update({
        "total_call_oi": total_call_oi, "total_put_oi": total_put_oi,
        "put_call_oi_ratio": total_put_oi / total_call_oi if total_call_oi else None,
        "total_call_volume": total_call_vol, "total_put_volume": total_put_vol,
        "put_call_volume_ratio": total_put_vol / total_call_vol if total_call_vol else None,
        "top_call_oi_strike": top_call_oi_strike, "top_call_oi": top_call_oi,
        "top_put_oi_strike": top_put_oi_strike, "top_put_oi": top_put_oi,
        "avg_atm_spread_pct": float(np.mean(spreads)) if spreads else None,
        "near_term_expirations_used": near_term_exps,
    })
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
            next_earnings = {"date": next_dt.strftime("%Y-%m-%d"), "days_until": int((next_dt - today).days), "eps_estimate": _none_safe(future.loc[next_dt].get("EPS Estimate")) if "EPS Estimate" in future.columns else None}
        close = hist["Close"]
        for dt in past.index[:4]:
            try:
                before = close[close.index <= dt - pd.Timedelta(days=1)].iloc[-1]
                after_candidates = close[close.index >= dt]
                if not after_candidates.empty:
                    past_earnings_moves.append({"date": dt.strftime("%Y-%m-%d"), "move_pct": float((after_candidates.iloc[0] - before) / before * 100)})
            except Exception:
                continue
    events["next_earnings"] = next_earnings
    events["earnings_inside_primary_expiration"] = bool(next_earnings and primary_expiration and next_earnings["date"] <= primary_expiration) if next_earnings and primary_expiration else None
    events["past_earnings_moves"] = past_earnings_moves
    if past_earnings_moves:
        events["avg_abs_earnings_move_pct"] = float(np.mean([abs(m["move_pct"]) for m in past_earnings_moves]))

    ex_div_ts = info.get("exDividendDate")
    last_ex_div_date = datetime.fromtimestamp(ex_div_ts, tz=timezone.utc).replace(tzinfo=None) if ex_div_ts else None
    events["last_ex_dividend_date"] = last_ex_div_date.strftime("%Y-%m-%d") if last_ex_div_date else None
    next_ex_div_date = None
    div_history = safe(lambda: tkr.dividends, default=None, label="dividend history")
    if div_history is not None and len(div_history) >= 2:
        div_dates = pd.to_datetime(div_history.index).tz_localize(None)
        gaps = pd.Series(div_dates[1:]) - pd.Series(div_dates[:-1])
        median_gap_days = float(np.median([g.days for g in gaps.tail(4)]))
        base_date = last_ex_div_date or div_dates[-1].to_pydatetime()
        candidate = base_date
        while candidate <= today:
            candidate += pd.Timedelta(days=median_gap_days)
        next_ex_div_date = candidate
    events["estimated_next_ex_dividend_date"] = next_ex_div_date.strftime("%Y-%m-%d") if next_ex_div_date else None
    events["days_to_next_ex_dividend"] = int((next_ex_div_date - today).days) if next_ex_div_date else None
    div_rate, div_yield_raw = info.get("dividendRate"), info.get("dividendYield")
    events["dividend_yield_pct"] = float(div_rate / spot * 100) if div_rate is not None and spot else float(div_yield_raw) if div_yield_raw is not None else None
    upcoming_fomc = [dict(m) for m in FOMC_MEETINGS_2026 if m["decision_date"] >= as_of_date][:3]
    for meeting in upcoming_fomc:
        meeting["days_until"] = (datetime.strptime(meeting["decision_date"], "%Y-%m-%d") - today).days
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
        regime["vix_level"], regime["vix_1y_percentile"] = vix_now, float((vix_close < vix_now).mean() * 100)
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
    if spy_hist is None:
        return regime
    spy_close = spy_hist["Close"]
    spy_now, spy_sma50 = float(spy_close.iloc[-1]), float(spy_close.rolling(50).mean().iloc[-1])
    spy_sma200 = float(spy_close.rolling(200).mean().iloc[-1]) if len(spy_close) >= 200 else None
    regime.update({"spy_price": spy_now, "spy_sma50": spy_sma50, "spy_sma200": spy_sma200, "market_trend_label": "Broad market uptrend" if spy_sma200 and spy_now > spy_sma50 > spy_sma200 else "Broad market downtrend" if spy_sma200 and spy_now < spy_sma50 < spy_sma200 else "Mixed / choppy market"})
    ticker_close, aligned_spy = ticker_hist["Close"].align(spy_close, join="inner")
    aligned = pd.concat([np.log(ticker_close / ticker_close.shift(1)), np.log(aligned_spy / aligned_spy.shift(1))], axis=1).dropna()
    aligned.columns = ["t", "s"]
    beta_computed = corr = None
    if len(aligned) > 20:
        var = aligned["s"].var()
        beta_computed = float(aligned["t"].cov(aligned["s"]) / var) if var else None
        corr = float(aligned["t"].tail(60).corr(aligned["s"].tail(60))) if len(aligned) >= 60 else float(aligned["t"].corr(aligned["s"]))
    regime["beta"] = info.get("beta") if info.get("beta") is not None else beta_computed
    regime["beta_source"] = "reported" if info.get("beta") is not None else "computed (1y regression)"
    regime["correlation_to_spy_60d"] = corr
    sector, etf = info.get("sector"), SECTOR_ETF_MAP.get(info.get("sector"))
    if etf:
        etf_hist = safe(lambda: load_history(etf, period="4mo"), default=None, label=f"{etf} history")
        if etf_hist is not None:
            def ret(series, days):
                return None if len(series) <= days else float((series.iloc[-1] / series.iloc[-1 - days] - 1) * 100)
            spy_1m, spy_3m = ret(spy_close.tail(80), 21), ret(spy_close.tail(80), 63)
            etf_close = etf_hist["Close"]
            etf_1m, etf_3m = ret(etf_close, 21), ret(etf_close, 63)
            regime.update({"sector": sector, "sector_etf": etf, "sector_return_1m_pct": etf_1m, "sector_return_3m_pct": etf_3m, "sector_vs_spy_1m_pct": None if etf_1m is None or spy_1m is None else etf_1m - spy_1m, "sector_vs_spy_3m_pct": None if etf_3m is None or spy_3m is None else etf_3m - spy_3m})
    return regime


def main():
    tkr = yf.Ticker(TICKER)
    hist = load_history(TICKER, period="1y")
    as_of_date = hist.index[-1].strftime("%Y-%m-%d")
    spot = float(hist["Close"].iloc[-1])
    info = safe(lambda: tkr.get_info(), default={}, label="ticker info") or {}
    technicals = build_technicals(hist)
    close = hist["Close"]
    hv10, hv20, hv30, hv60 = (realized_vol(close, window).iloc[-1] for window in (10, 20, 30, 60))
    hv20_series = realized_vol(close, 20).dropna()
    hv20_percentile = float((hv20_series < hv20).mean() * 100) if not pd.isna(hv20) and len(hv20_series) > 20 else None
    volatility, liquidity = build_volatility_and_liquidity(tkr, spot, as_of_date)
    volatility.update({"realized_vol_10d_pct": None if pd.isna(hv10) else float(hv10), "realized_vol_20d_pct": None if pd.isna(hv20) else float(hv20), "realized_vol_30d_pct": None if pd.isna(hv30) else float(hv30), "realized_vol_60d_pct": None if pd.isna(hv60) else float(hv60), "realized_vol_20d_percentile_1y": hv20_percentile})
    if volatility.get("atm_iv_pct") is not None and not pd.isna(hv20):
        volatility["iv_minus_hv20_pts"] = float(volatility["atm_iv_pct"] - hv20)
        volatility["iv_richness_label"] = "Rich (premium selling favored)" if volatility["iv_minus_hv20_pts"] > 5 else "Cheap (premium buying favored)" if volatility["iv_minus_hv20_pts"] < -5 else "Fairly priced"
    liquidity["avg_daily_volume_30d"] = float(hist["Volume"].tail(30).mean())
    liquidity["short_percent_of_float_pct"] = safe(lambda: float(info["shortPercentOfFloat"] * 100) if info.get("shortPercentOfFloat") else None, default=None)
    liquidity["short_ratio_days_to_cover"] = info.get("shortRatio")
    events = build_events(tkr, info, hist, as_of_date, volatility.get("primary_expiration"), spot)
    regime = build_regime(hist, info, as_of_date)
    output = _none_safe({"meta": {"ticker": TICKER, "company_name": info.get("longName") or info.get("shortName") or TICKER, "sector": info.get("sector"), "as_of_date": as_of_date, "generated_at_utc": datetime.now(timezone.utc).isoformat(), "spot": spot, "market_cap": info.get("marketCap")}, "volatility": volatility, "technicals": technicals, "liquidity": liquidity, "events": events, "regime": regime})
    out_path = os.path.join(DATA_DIR, f"{TICKER}.json")
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    with open(os.path.join(DATA_DIR, "last_ticker.json"), "w") as f:
        json.dump({"ticker": TICKER}, f)
    print(f"Wrote {out_path}")
    print(json.dumps(output["meta"], indent=2))


if __name__ == "__main__":
    main()
