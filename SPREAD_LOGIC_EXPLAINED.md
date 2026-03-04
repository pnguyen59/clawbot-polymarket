# Wide Spread Skip Logic Explained

## What is Bid-Ask Spread?

The **spread** is the difference between the highest price a buyer is willing to pay (bid) and the lowest price a seller is willing to accept (ask).

### Example Order Book:
```
ASKS (Sellers):
  $0.520 - 100 shares  ← Best Ask (lowest seller price)
  $0.525 - 200 shares
  $0.530 - 150 shares

BIDS (Buyers):
  $0.480 - 150 shares  ← Best Bid (highest buyer price)
  $0.475 - 100 shares
  $0.470 - 200 shares
```

**Spread Calculation:**
```python
best_bid = 0.480
best_ask = 0.520
spread = best_ask - best_bid = 0.520 - 0.480 = 0.040
mid = (best_ask + best_bid) / 2 = (0.520 + 0.480) / 2 = 0.500
spread_pct = spread / mid = 0.040 / 0.500 = 0.08 = 8%
```

---

## Why Wide Spreads Matter

### ❌ **Problem with Wide Spreads:**

1. **High Slippage:** You pay more (or receive less) than the midpoint price
2. **Illiquid Market:** Few traders, hard to execute at good prices
3. **Unfavorable Execution:** Your edge gets eaten by the spread

### Example Trade Impact:

**Scenario:** You want to buy YES shares

| Spread | Best Ask | Your Cost | Slippage |
|--------|----------|-----------|----------|
| 2% | $0.505 | $0.505 | $0.005 (1%) |
| 8% | $0.520 | $0.520 | $0.020 (4%) |
| 15% | $0.575 | $0.575 | $0.075 (15%) |

With a 15% spread, you immediately lose 7.5% just from buying at the ask instead of the midpoint!

---

## Your Code's Spread Check

### Configuration:
```python
MAX_SPREAD_PCT = 0.10  # 10% maximum allowed spread
```

### The Check:
```python
book = fetch_orderbook_summary(clob_tokens)
if book:
    spread_pct = book["spread_pct"]
    
    if spread_pct > MAX_SPREAD_PCT:  # > 10%
        # SKIP TRADE - market too illiquid
        log(f"⏸️  Spread {spread_pct:.1%} > 10% — illiquid, skip")
        return
```

---

## Real Examples

### ✅ **Good Spread (Trade Allowed)**
```
Best Bid: $0.495
Best Ask: $0.505
Spread: $0.010
Mid: $0.500
Spread %: 2.0%

✅ 2.0% < 10% → TRADE ALLOWED
```

**Why good?** Tight spread means liquid market, minimal slippage.

---

### ⚠️ **Borderline Spread**
```
Best Bid: $0.475
Best Ask: $0.525
Spread: $0.050
Mid: $0.500
Spread %: 10.0%

⚠️ 10.0% = 10% → TRADE ALLOWED (just barely)
```

**Why borderline?** At the threshold, some slippage but still tradeable.

---

### ❌ **Wide Spread (Trade Skipped)**
```
Best Bid: $0.450
Best Ask: $0.550
Spread: $0.100
Mid: $0.500
Spread %: 20.0%

❌ 20.0% > 10% → TRADE SKIPPED
```

**Why bad?** 
- If you buy at $0.550, you're paying 10% above midpoint
- If you sell at $0.450, you're receiving 10% below midpoint
- Your trading edge needs to be >20% just to break even!

---

## Order Book Depth

Your code also checks **depth** (liquidity):

```python
# Sum top 5 levels of bids and asks
bid_depth_usd = sum of (size × price) for top 5 bids
ask_depth_usd = sum of (size × price) for top 5 asks
```

### Example:
```
ASKS:
  $0.505 × 100 shares = $50.50
  $0.510 × 200 shares = $102.00
  $0.515 × 150 shares = $77.25
  $0.520 × 100 shares = $52.00
  $0.525 × 50 shares  = $26.25
  ────────────────────────────
  Ask Depth: $308.00

BIDS:
  $0.495 × 150 shares = $74.25
  $0.490 × 100 shares = $49.00
  $0.485 × 200 shares = $97.00
  $0.480 × 100 shares = $48.00
  $0.475 × 50 shares  = $23.75
  ────────────────────────────
  Bid Depth: $292.00
```

**Output:**
```
Spread: 2.0% (bid $0.495 / ask $0.505)
Depth: $292 bid / $308 ask (top 5)
```

**What it means:**
- $292 available to buy (if you want to sell)
- $308 available to sell (if you want to buy)
- Good liquidity for trades up to ~$300

---

## When Spreads Get Wide

### Common Causes:

1. **Low Trading Volume:** Few active traders
2. **Market Uncertainty:** Traders unsure of fair value
3. **Off-Hours Trading:** Outside peak trading times
4. **New Markets:** Just launched, not enough liquidity yet
5. **Near Expiry:** Traders exiting positions

### Fast Markets Specifically:

Fast markets (5-minute windows) can have wide spreads because:
- Very short duration → less time for liquidity to build
- Rapid price changes → market makers widen spreads for protection
- Small market size → fewer participants

---

## Strategy Impact

### Your Trading Edge Calculation:

```python
# You need momentum signal to overcome:
1. Spread cost: ~1-5% (half the spread)
2. Fees: 10% on winnings (Polymarket fast market fee)
3. Minimum edge: divergence from 50¢

# If spread is 20%:
- You pay 10% slippage just to enter
- You need >10% edge just to break even
- Plus 10% fee on winnings
- Total: need ~25%+ edge to profit

# If spread is 2%:
- You pay 1% slippage to enter
- You need >1% edge to break even
- Plus 10% fee on winnings
- Total: need ~12%+ edge to profit
```

**The 10% threshold** ensures your trading edge isn't completely eaten by spread costs.

---

## Summary

### Wide Spread Skip Logic:

```
IF spread_pct > 10%:
    ❌ SKIP TRADE
    Reason: "wide spread" (illiquid market)
    
ELSE:
    ✅ Continue to next checks
```

### Why 10%?

- **Below 10%:** Spread cost is manageable, your signal edge can overcome it
- **Above 10%:** Spread cost too high, even good signals won't be profitable

### What You'll See:

```
  Spread: 15.2% (bid $0.424 / ask $0.576)
  Depth: $150 bid / $180 ask (top 5)
  ⏸️  Spread 15.2% > 10% — illiquid, skip

📊 Summary: No trade (wide spread: 15.2%)
```

This protects you from trading in illiquid markets where execution costs would destroy your edge!
