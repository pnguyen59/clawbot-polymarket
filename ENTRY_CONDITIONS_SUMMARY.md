# All Entry Conditions for Trade Execution

## Complete Checklist

Your bot will ONLY execute a trade when ALL of these conditions are met:

---

## ✅ 1. Market Discovery

**Condition:** Active fast market exists

```python
markets = discover_fast_market_markets(asset="BTC", window="5m")
if len(markets) == 0:
    SKIP: "No active fast markets found"
```

**Requirements:**
- Market slug exists: `btc-updown-5m-{timestamp}`
- Market is not closed
- Market has valid end_time

---

## ✅ 2. Time Window

**Condition:** Market has enough time remaining

```python
remaining = (end_time - now).total_seconds()
if remaining <= MIN_TIME_REMAINING:  # 30 seconds
    SKIP: "Too close to expiry"
if remaining >= max_remaining:  # 600 seconds (5m × 2)
    SKIP: "Too far in future"
```

**Requirements:**
- Time remaining: **30s < remaining < 600s**
- Default: 30-600 seconds (0.5 - 10 minutes)

**Why:**
- Too close: Not enough time to execute
- Too far: Market hasn't started yet

---

## ✅ 3. Spread Check

**Condition:** Market is liquid (tight spread)

```python
spread_pct = fetch_spread_api(token_id)
if spread_pct > MAX_SPREAD_PCT:  # 10%
    SKIP: "Wide spread — illiquid"
```

**Requirements:**
- Spread: **< 10%**
- Uses Spread API (not order book)

**Why:**
- Wide spread = high execution cost
- Your edge gets eaten by slippage

---

## ✅ 4. Momentum Check

**Condition:** BTC price moved significantly

```python
momentum_pct = abs(momentum["momentum_pct"])
if momentum_pct < MIN_MOMENTUM_PCT:  # 0.5%
    SKIP: "Momentum too weak"
```

**Requirements:**
- BTC moved: **> 0.5%** in last 5 minutes
- Direction: UP or DOWN (doesn't matter which)

**Why:**
- Weak moves are noise, not signal
- Need strong momentum for edge

---

## ✅ 5. Volume Confidence (Optional)

**Condition:** High volume confirms signal strength

```python
if VOLUME_CONFIDENCE and momentum["volume_ratio"] < 0.5:
    SKIP: "Low volume — weak signal"
```

**Requirements:**
- Volume ratio: **> 0.5x** average
- Latest volume > 50% of average

**Why:**
- Low volume = unreliable signal
- High volume = strong conviction

**Config:**
```python
VOLUME_CONFIDENCE = True  # Enable this check
```

---

## ✅ 6. Divergence Check

**Condition:** Market is mispriced vs momentum

```python
# If BTC went UP:
divergence = 0.50 + ENTRY_THRESHOLD - market_yes_price
# If BTC went DOWN:
divergence = market_yes_price - (0.50 - ENTRY_THRESHOLD)

if divergence <= 0:
    SKIP: "Market already priced in"
```

**Requirements:**
- Divergence: **> 0** (market underpriced)
- Entry threshold: **0.05** (5¢ minimum edge)

**Example:**
```
BTC up +0.6%
Market YES: $0.45
Fair value: $0.55 (0.50 + 0.05)
Divergence: 0.55 - 0.45 = 0.10 (10¢ edge) ✅
```

**Why:**
- Need edge over market price
- Must overcome fees + spread

---

## ✅ 7. Fee-Aware EV Check

**Condition:** Edge is large enough to overcome fees

```python
buy_price = market_yes_price  # or (1 - market_yes_price) for NO
fee_cost = (1 - buy_price) × 0.10  # 10% fee on winnings
min_divergence = fee_cost + 0.02  # Fee + 2¢ buffer

if divergence < min_divergence:
    SKIP: "Fees eat the edge"
```

**Requirements:**
- Divergence > fee_cost + 2¢

**Example:**
```
Buy YES at $0.45
Fee cost: (1 - 0.45) × 0.10 = 0.055 (5.5¢)
Min divergence: 0.055 + 0.02 = 0.075 (7.5¢)
Actual divergence: 0.10 (10¢) ✅
```

**Why:**
- 10% fee on winnings
- Need edge > fees to be profitable

---

## ✅ 8. Daily Budget Check

**Condition:** Haven't exceeded daily spending limit

```python
remaining_budget = DAILY_BUDGET - daily_spend["spent"]
if remaining_budget <= 0:
    SKIP: "Daily budget exhausted"
if position_size > remaining_budget:
    position_size = remaining_budget  # Cap at remaining
if position_size < 0.50:
    SKIP: "Remaining budget too small"
```

**Requirements:**
- Daily spent: **< DAILY_BUDGET** ($10 default)
- Position size: **≥ $0.50** minimum

**Why:**
- Risk management
- Prevents catastrophic loss

---

## ✅ 9. Minimum Order Size

**Condition:** Position large enough for Polymarket minimum

```python
min_cost = MIN_SHARES_PER_ORDER × price  # 5 shares × price
if min_cost > position_size:
    SKIP: "Position too small"
```

**Requirements:**
- Can buy at least **5 shares** (Polymarket minimum)

**Example:**
```
Price: $0.50
Min cost: 5 × $0.50 = $2.50
Position: $5.00 ✅
```

**Why:**
- Polymarket requires minimum 5 shares per order

---

## ✅ 10. Market Import

**Condition:** Market can be imported to Simmer

```python
market_id, error = import_fast_market_market(slug)
if not market_id:
    SKIP: "Import failed"
```

**Requirements:**
- Market exists on Polymarket
- Simmer can access market data
- Market not resolved yet

**Why:**
- Need market_id to execute trade

---

## Summary Table

| # | Condition | Threshold | Skip Reason |
|---|-----------|-----------|-------------|
| 1 | Market exists | Yes | "No active fast markets" |
| 2 | Time remaining | 30s - 600s | "Too close/far" |
| 3 | Spread | < 10% | "Wide spread" |
| 4 | Momentum | > 0.5% | "Momentum too weak" |
| 5 | Volume (optional) | > 0.5x avg | "Low volume" |
| 6 | Divergence | > 0 | "Market priced in" |
| 7 | Fee-adjusted edge | > fee + 2¢ | "Fees eat edge" |
| 8 | Daily budget | < $10 | "Budget exhausted" |
| 9 | Min order size | ≥ 5 shares | "Position too small" |
| 10 | Import success | Yes | "Import failed" |

---

## Configuration Values

### Default Settings:
```python
ENTRY_THRESHOLD = 0.05        # 5¢ minimum divergence
MIN_MOMENTUM_PCT = 0.5        # 0.5% minimum BTC move
MAX_POSITION_USD = 5.0        # $5 per trade
MAX_SPREAD_PCT = 0.10         # 10% maximum spread
MIN_TIME_REMAINING = 30       # 30 seconds minimum
DAILY_BUDGET = 10.0           # $10 per day
VOLUME_CONFIDENCE = True      # Enable volume check
LOOKBACK_MINUTES = 5          # 5 minutes of price history
```

### Adjust Settings:
```bash
# Increase momentum threshold (more selective)
python fastloop_trader.py --set min_momentum_pct=1.0

# Increase entry threshold (larger edge required)
python fastloop_trader.py --set entry_threshold=0.08

# Increase daily budget
python fastloop_trader.py --set daily_budget=20.0

# Disable volume check
python fastloop_trader.py --set volume_confidence=false
```

---

## Example: Trade Execution

### Scenario: All Conditions Met ✅

```
1. Market: btc-updown-5m-1772454000 ✅
2. Time remaining: 120 seconds ✅
3. Spread: 2.0% ✅
4. BTC momentum: +0.8% UP ✅
5. Volume ratio: 1.5x avg ✅
6. Market YES: $0.42, Fair: $0.55, Divergence: 0.13 ✅
7. Fee cost: 0.058, Min: 0.078, Divergence: 0.13 ✅
8. Daily spent: $5/$10, Remaining: $5 ✅
9. Position: $5, Min cost: $2.10 (5 × $0.42) ✅
10. Import: market_id = "0xabc..." ✅

→ EXECUTE TRADE: Buy YES for $5.00
```

### Scenario: One Condition Failed ❌

```
1. Market: btc-updown-5m-1772454000 ✅
2. Time remaining: 120 seconds ✅
3. Spread: 15.0% ❌ FAIL
   
→ SKIP: "Wide spread — illiquid"
(All other checks skipped)
```

---

## Trade Flow

```
START
  ↓
Check 1: Market exists? → NO → SKIP
  ↓ YES
Check 2: Time OK? → NO → SKIP
  ↓ YES
Check 3: Spread OK? → NO → SKIP
  ↓ YES
Check 4: Momentum OK? → NO → SKIP
  ↓ YES
Check 5: Volume OK? → NO → SKIP
  ↓ YES
Check 6: Divergence OK? → NO → SKIP
  ↓ YES
Check 7: Fees OK? → NO → SKIP
  ↓ YES
Check 8: Budget OK? → NO → SKIP
  ↓ YES
Check 9: Min size OK? → NO → SKIP
  ↓ YES
Check 10: Import OK? → NO → SKIP
  ↓ YES
EXECUTE TRADE ✅
```

---

## Quick Reference

**Must have ALL of:**
- ✅ Active market (30s - 10min remaining)
- ✅ Tight spread (< 10%)
- ✅ Strong momentum (> 0.5%)
- ✅ Good volume (> 0.5x avg, if enabled)
- ✅ Market mispriced (divergence > 0)
- ✅ Edge > fees (divergence > fee + 2¢)
- ✅ Budget available (< $10/day spent)
- ✅ Position large enough (≥ 5 shares)
- ✅ Market imports successfully

**If ANY condition fails → SKIP trade**

---

## Best Time to Trade

**Optimal hours (most conditions met):**
- **9:30 PM - 1:00 AM Vietnam** (US market open)
- Spread: 1-5% ✅
- Volume: High ✅
- Momentum: Frequent ✅
- Expected: 3-5 trades per session

**Poor hours (many conditions fail):**
- **8:00 AM - 8:00 PM Vietnam** (US market closed)
- Spread: 50-200% ❌
- Volume: Low ❌
- Momentum: Rare ❌
- Expected: 0 trades (all skipped)
