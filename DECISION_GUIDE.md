# Options Trading Decision Guide: Using the Indicators Dashboard + the Gamma Exposure Dashboard Together

This is a practical, repeatable process for going from "I'm looking at a
ticker" to "I'm buying/selling this specific call or put, at this strike,
at this expiration." It combines two tools you already have:

| Tool | What it tells you | Where it lives |
|---|---|---|
| **Options Indicators Dashboard** (this project) | Volatility regime, price/technicals, liquidity, events, macro regime | This dashboard's 5 tabs |
| **Gamma Exposure (GEX) dashboard** | Call wall, put wall, max pain, gamma flip | Your on-demand ticker GEX dashboard (`Ticker_dashboard_gamma` repo) |

Neither tool alone tells you what to do. The Indicators Dashboard tells you
**whether conditions favor buying or selling premium, and what the
directional/technical backdrop looks like**. The GEX dashboard tells you
**where dealer hedging flows are likely to push, pin, or accelerate price**.
Combining them turns "I have a hunch" into "I have a specific, defendable
trade."

This is an educational framework, not financial advice — every step below
still requires your own judgment and risk tolerance.

---

## The 7-step process

### Step 1 — Read the macro backdrop first (Market Regime tab)

Before looking at any single-name setup, know what environment you're
trading in.

- **VIX level & percentile**: Low VIX / low percentile → calm market,
  option premiums generally cheap, better environment to be a net option
  *buyer* on conviction plays. High VIX / high percentile → premiums rich,
  better environment to be a net option *seller* — but also higher
  whipsaw/gap risk on any single position.
- **VIX term structure**: Contango (VIX < VIX3M) = calm, complacent market.
  Backwardation (VIX > VIX3M) = near-term fear/event pricing — be cautious
  selling short-dated premium into this.
- **SPY trend**: Fighting the tape is harder. If SPY is in a clear
  downtrend, be more selective about new long-call / bullish positions in
  single names, and vice versa.
- **Beta & 60-day correlation to SPY**: A high-beta, high-correlation name
  will mostly trade with the market regardless of its own story — factor
  that into how much of your thesis is "this stock" vs. "the market."
- **Sector relative strength**: Confirms whether the name is leading or
  lagging its peers — a stock breaking out against a weak sector is a
  different (often stronger) signal than one breaking out with its whole
  sector.

**Output of this step:** a one-line macro read, e.g. *"Calm market,
contango, SPY uptrending, this name is high-beta tech in a strong sector —
tailwind for bullish setups."*

### Step 2 — Check the event calendar (Events tab)

- **Next earnings date**: If it falls inside your intended holding period,
  decide explicitly whether you *want* that exposure. Selling short-dated
  premium through earnings collects a rich IV crush but carries gap risk;
  buying premium into earnings is a pure volatility/move bet, not a
  technical one — don't blend the two theses.
- **Past earnings-day moves**: Compare the historical average move to the
  volatility tab's expected move (Step 3) — if the options market is
  pricing a smaller move than the stock has historically made, that's a
  signal options may be cheap for a buyer (and dangerous for an
  undefined-risk seller).
- **Ex-dividend date**: Matters mainly for short calls (early assignment
  risk when the dividend exceeds remaining extrinsic value) and for
  understanding div-related drift.
- **FOMC meetings**: A meeting inside your window — especially a dot-plot
  meeting — is a market-wide vol event layered on top of anything
  stock-specific.

**Output of this step:** a decision on whether to trade *through* an event
on purpose, *around* it (choose an expiration that avoids it), or *because*
of it (a dedicated earnings/FOMC volatility play).

### Step 3 — Read the volatility regime (Volatility Metrics tab) → buy or sell premium?

This is the single most important tab for deciding **premium direction**
(buyer vs. seller), independent of whether you end up choosing a call or a
put.

- **ATM IV vs. HV20/HV30 ("IV richness")**: IV meaningfully above realized
  vol → premium is rich → lean toward being a net seller (credit spreads,
  cash-secured puts, covered calls). IV at or below realized vol → premium
  is cheap → lean toward being a net buyer (long calls/puts, debit spreads).
- **Skew (OTM put IV − OTM call IV)**: Positive/steep skew (puts bid up)
  is normal and reflects crash-hedging demand — very steep skew can mean
  puts are relatively expensive (favor selling downside premium, e.g. cash
  secured puts, over buying it) while calls stay comparatively cheap
  (favor buying calls for upside exposure).
- **Term structure (contango vs. backwardation)**: Backwardation into a
  near-term expiration (often event-driven, see Step 2) means that specific
  expiration is priced rich relative to the next one — a reason to prefer
  selling that expiration or stepping out to the next one if buying.
- **Expected move**: This is your ruler for Step 7's strike selection —
  it tells you the range the options market has already priced in through
  the primary expiration.

**Output of this step:** a premium-direction call — *buy premium* or *sell
premium* — plus the dollar/percent expected move to use later.

### Step 4 — Pull up the GEX dashboard: gamma flip, call wall, put wall, max pain

Run/refresh the ticker on your GEX dashboard and read these four numbers
alongside the current spot price.

- **Gamma flip** (spot level where dealer gamma flips sign):
  - **Spot above the flip → positive gamma regime**: dealers hedge by
    buying dips / selling rallies, which *dampens* realized volatility and
    tends to pin price. This favors premium **sellers** (theta trades,
    iron condors, credit spreads) and argues against paying up for a big
    directional move.
  - **Spot below the flip → negative gamma regime**: dealers hedge by
    selling into weakness / buying into strength, which *amplifies* moves
    in whichever direction price is already heading. This favors premium
    **buyers** (long calls/puts, debit spreads) and argues for more caution
    on undefined-risk selling — gaps can run further than usual.
- **Call wall** (strike with the largest positive call gamma): acts like a
  magnet/ceiling into expiration, because dealers sell into rallies toward
  it to stay hedged. Use it as (a) a resistance level to fade if you're
  buying puts or selling calls, or (b) your short-call strike if you're
  writing calls and want a level the market itself tends to defend.
- **Put wall** (strike with the largest negative/put gamma): the mirror
  image — acts like a floor. Use it as (a) a support level to buy against,
  or (b) your short-put strike if you're selling cash-secured puts and want
  a level with real dealer-hedging support behind it.
- **Max pain**: the strike that would leave the largest total option value
  worthless at expiration. Treat this as a *secondary, weaker* signal — it
  tends to matter more the closer you get to expiration (roughly the final
  week, especially 0–5 DTE) and less for anything further out. Use it as a
  tiebreaker, not a primary driver.

**Output of this step:** a directional lean (is spot above or below gamma
flip?), a resistance level (call wall), a support level (put wall), and a
secondary pull-toward level (max pain).

### Step 5 — Confirm with price/technical structure (Price/Technical tab)

Now cross-check the GEX levels against pure price action — when they agree,
your conviction should go up; when they conflict, that's a flag to size
down or wait.

- **Trend (SMA20/50/200) & the 60-day trend line**: Is the stock actually
  trending in the direction your volatility/gamma read favors, or would you
  be fighting the trend?
- **RSI(14)**: Overbought (≥70) into a call wall is a weaker place to
  initiate new longs (or a good place to sell calls); oversold (≤30) into
  a put wall is the mirror setup for puts/short puts.
- **MACD cross**: Confirms or questions trend timing — a fresh bullish
  cross supports a call thesis, a bearish cross argues against one even if
  other tabs look bullish.
- **Bollinger %B / Bollinger Bands on the price chart**: Price riding the
  upper band with %B > 1 is stretched — consider whether you're chasing.
- **This dashboard's own support/resistance levels**: These come from
  swing-high/low price clustering (not gamma) — **when a support/resistance
  level here lines up closely with the GEX put/call wall, that price zone
  is confirmed from two independent methods**, which is a meaningfully
  stronger signal than either alone.
- **ATR(14)**: Use this to sanity-check that your stop distance and strike
  distance are wide enough to survive normal daily noise.

**Output of this step:** confirmation (or contradiction) of the Step 4
directional lean, plus a feel for how "stretched" the setup already is.

### Step 6 — Check liquidity/positioning (Liquidity/Positioning tab) as a tradability filter

Even a perfect thesis is a bad trade if you can't get filled reasonably.

- **Put/call OI and volume ratios**: Extreme positioning (very high P/C)
  can mean the crowd is heavily hedged/bearish already — sometimes a
  contrarian signal, sometimes confirmation, so read it alongside Step 1's
  macro regime rather than in isolation.
- **This dashboard's top call/put OI strikes**: These are raw open-interest
  concentrations, not gamma-weighted like the GEX walls — when they roughly
  agree with the GEX call/put wall, that's a third independent confirmation
  of the level. When they disagree, trust the GEX (gamma-weighted) wall more
  for near-term price magnet behavior, but keep the OI level in mind as a
  psychological round-number/strike-clustering effect.
- **Average bid-ask spread near the money**: Wide spreads erode edge on
  entry and exit — if spreads are wide, favor spreads (which net out some
  of the slippage) over single-leg positions, or size down.
- **Short interest**: High short interest raises squeeze risk (sharper
  up-moves) — relevant if you're selling calls or buying puts against a
  heavily shorted name.

**Output of this step:** a go/no-go on execution quality, and a final sanity
check on the crowd's positioning.

### Step 7 — Put it together: structure, strike, and expiration

Now combine Steps 3 (buy/sell premium) and Steps 4–5 (directional lean) into
a specific structure, then use the levels you've gathered to pick strike and
expiration.

**A. Choose the structure**

| Premium is... | Directional lean | Suggested structure |
|---|---|---|
| Cheap (buy) | Bullish | Long call, or call debit spread if IV isn't uniformly cheap across strikes |
| Cheap (buy) | Bearish | Long put, or put debit spread |
| Rich (sell) | Bullish / neutral-to-up | Cash-secured put (at/near put wall), or put credit spread |
| Rich (sell) | Bearish / neutral-to-down | Covered call or naked call (at/near call wall), or call credit spread |
| Rich (sell) | Neutral / range-bound (positive gamma regime, spot pinned between walls) | Iron condor with shorts at/beyond the call wall and put wall |

**B. Choose the strike**

- **If selling**, anchor your short strike to the wall on the side you're
  selling: short calls at or just outside the call wall, short puts at or
  just outside the put wall. These are levels the market's own dealer
  hedging has a track record of defending, so you're selling where the
  underlying is statistically less likely to trade through by expiration.
  Cross-check against Step 5's price-based resistance/support — prefer the
  strike where both methods agree.
- **If buying a directional option**, make sure your strike is reachable
  within the **expected move** from Step 3 for your chosen expiration —
  buying a call far beyond the expected move (and beyond the call wall) is
  a low-probability lottery ticket unless that's explicitly your intent.
  Buying inside the expected move, ideally with the wall/support-resistance
  level *behind* your strike (i.e., price needs to clear a level that isn't
  right in front of your strike) improves the odds the move actually
  reaches your strike.
- **If running a spread**, use the wall as your short leg (per the selling
  logic above) and set your long leg's width based on how much premium
  you're willing to risk and where the next support/resistance level or
  wall sits.

**C. Choose the expiration**

- **Avoid unintentional event exposure**: if you're not deliberately
  trading earnings or an FOMC meeting (Step 2), pick an expiration that
  either closes before the event or is clearly a longer-dated position that
  accepts the event as one of several inputs.
- **Respect the term structure** (Step 3): don't sell an expiration that's
  priced cheap relative to others just for convenience, and don't buy an
  expiration priced rich relative to others without a specific reason (e.g.
  you need that exact event inside the window).
- **Match DTE to conviction and theta tolerance**: shorter-dated options
  have more gamma risk and faster theta decay (good for sellers wanting
  quick decay, risky for buyers needing time to be right); longer-dated
  options give a directional buyer more room to be right but cost more
  premium and are less sensitive to near-term wall/pin dynamics.
- **Near-dated (weekly, especially the final few days) trades should weight
  max pain more heavily** (per Step 4) since pin risk toward that strike
  increases into expiration. Anything more than ~2 weeks out should treat
  max pain as background noise, not a driver.

---

## Worked example (illustrative numbers only — not a live trade recommendation)

Say you're evaluating a hypothetical stock "XYZ" trading at $100:

1. **Regime**: VIX at a low percentile, contango, SPY in an uptrend, XYZ is
   in a leading sector → tailwind for bullish setups.
2. **Events**: Earnings are 45 days out — outside your intended 2-3 week
   window, so no event overlay to worry about.
3. **Volatility**: ATM IV (22%) is close to HV20 (20%) — premium is
   roughly fair, slight lean toward buying. Expected move to the nearest
   monthly expiration is ±$6 (±6%).
4. **GEX dashboard**: Spot ($100) is above the gamma flip ($95) → positive
   gamma regime, which normally favors sellers — but combined with "fair,
   not rich" IV from Step 3, this argues for a modest, defined-risk bullish
   position rather than an aggressive premium sale. Call wall is at $108,
   put wall is at $96.
5. **Price/technicals**: Uptrend confirmed (price > SMA20 > SMA50), RSI at
   58 (room to run before overbought), and this dashboard's own resistance
   level at $107 sits almost exactly on the GEX call wall at $108 —
   independent confirmation of that ceiling.
6. **Liquidity**: Put/call OI ratio is neutral, bid-ask spreads near the
   money are tight (<3%) — good execution quality, single-leg positions are
   fine here.
7. **Decision**: Fair-to-slightly-cheap IV plus a confirmed uptrend and a
   defined ceiling suggests a **call debit spread**: long the $102 call
   (inside the expected move), short the $107–108 call (right at the
   confirmed resistance/call-wall zone), expiring in ~3 weeks (before
   earnings, long enough for the move to develop without paying for extra
   time you don't need).

---

## Risk management checklist (apply regardless of the above)

- Size any single position so a full loss doesn't meaningfully impair your
  account — defined-risk structures (spreads) make this easier to enforce
  than naked single legs.
- Know your assignment risk on any short option approaching the money,
  especially short calls near an ex-dividend date (Step 2).
- Decide your exit plan (profit target and stop/adjustment trigger) *before*
  entering, using the ATR and expected-move figures from this dashboard as
  your ruler.
- Re-check the GEX dashboard's walls periodically for longer-dated
  positions — gamma walls shift as new open interest builds and as old
  expirations roll off; a wall that was valid at entry is not guaranteed to
  hold for the life of a multi-week position.
- Treat every signal in this guide as probabilistic, not deterministic —
  the goal is to stack multiple independent confirmations (volatility +
  gamma + price structure + liquidity), not to rely on any single metric.

---

## One-page quick reference

| Question | Where to look | Signal |
|---|---|---|
| Is the market calm or fearful? | Market Regime tab | VIX level/percentile, term structure |
| Is there an event in my window? | Events tab | Earnings, ex-div, FOMC |
| Should I buy or sell premium? | Volatility Metrics tab | IV vs. HV, skew, term structure |
| Will moves be dampened or amplified? | GEX dashboard | Spot vs. gamma flip |
| Where's the ceiling / floor? | GEX dashboard + Price/Technical tab | Call wall / put wall, cross-checked against this dashboard's support/resistance |
| Is price already stretched? | Price/Technical tab | RSI, Bollinger %B, trend line |
| Can I get filled well? | Liquidity/Positioning tab | Bid-ask spread, OI, P/C ratio |
| What strike? | GEX walls + expected move + support/resistance | Sell at/beyond walls; buy within expected move |
| What expiration? | Events + term structure + DTE tolerance | Avoid unintended events; respect term structure; match DTE to conviction |
