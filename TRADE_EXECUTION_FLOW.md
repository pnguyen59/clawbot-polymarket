# Trade Execution Flow (When Spread < 10%)

## Complete Flow Diagram

```
START
  ↓
1. DISCOVER MARKETS
  ├─ Query: btc-updown-5m-{current_timestamp}
  ├─ Query: btc-updown-5m-{next_timestamp}
  └─ Found: 0-2 markets
  ↓
2. SELECT BEST MARKET
  ├─ Filter: 30s < time_remaining < 600s
  └─ Pick: Soonest expiring
  ↓
3. GET PRICE SIGNAL
  ├─ Fetch: Binance BTC price (last 5 minutes)
  ├─ Calculate: momentum_pct = (now - then) / then
  └─ Determine: direction = "up" or "down"
  ↓
4. CHECK SPREAD ⚠️ [YOUR QUESTION]
  ├─ Fetch order book from CLOB
  ├─ Calculate: spread_pct = (ask - bid) / mid
  ├─ IF spread_pct > 10%:
  │   └─ ❌ SKIP: "wide spread — illiquid"
  └─ IF spread_pct ≤ 10%:
      └─ ✅ CONTINUE (spread is acceptable)
  ↓
5. CHECK MOMENTUM
  ├─ IF momentum_pct < 0.5%:
  │   └─ ❌ SKIP: "momentum too weak"
  └─ ELSE:
      └─ ✅ CONTINUE
  ↓
6. CALCULATE TRADE DIRECTION
  ├─ IF direction == "up":
  │   ├─ side = "yes"
  │   └─ divergence = 0.50 + 0.05 - market_yes_price
  └─ IF direction == "down":
      ├─ side = "no"
      └─ divergence = market_yes_price - (0.50 - 0.05)
  ↓
7. CHECK VOLUME (if enabled)
  ├─ IF volume_ratio < 0.5:
  │   └─ ❌ SKIP: "low volume"
  └─ ELSE:
      └─ ✅ CONTINUE
  ↓
8. CHECK DIVERGENCE
  ├─ IF divergence ≤ 0:
  │   └─ ❌ SKIP: "market already priced in"
  └─ ELSE:
      └─ ✅ CONTINUE
  ↓
9. CHECK FEES
  ├─ Calculate: fee_cost = (1 - buy_price) × 0.10
  ├─ Calculate: min_divergence = fee_cost + 0.02
  ├─ IF divergence < min_divergence:
  │   └─ ❌ SKIP: "fees eat the edge"
  └─ ELSE:
      └─ ✅ CONTINUE
  ↓
10. CHECK BUDGET
  ├─ IF daily_spent ≥ daily_budget:
  │   └─ ❌ SKIP: "daily budget exhausted"
  ├─ IF position_size < $0.50:
  │   └─ ❌ SKIP: "budget too small"
  └─ ELSE:
      └─ ✅ CONTINUE
  ↓
11. IMPORT MARKET TO SIMMER
  ├─ Call: import_fast_market_market(slug)
  ├─ Returns: market_id
  └─ IF error:
      └─ ❌ ABORT: "import failed"
  ↓
12. EXECUTE TRADE ✅ [ANSWER TO YOUR QUESTION]
  ├─ Call: execute_trade(market_id, side, amount)
  │   ├─ Uses: Simmer SDK client.trade()
  │   ├─ Parameters:
  │   │   ├─ market_id: from import step
  │   │   ├─ side: "yes" or "no"
  │   │   ├─ amount: position_size in USD
  │   │   └─ source: "sdk:fastloop"
  │   └─ Simmer SDK handles:
  │       ├─ Fetching current market price
  │       ├─ Calculating shares to buy
  │       ├─ Placing order on Polymarket CLOB
  │       └─ Waiting for fill
  ↓
13. TRADE RESULT
  ├─ IF success:
  │   ├─ Log: shares bought, price paid
  │   ├─ Update: daily spend tracker
  │   └─ Log: trade journal (if available)
  └─ IF failed:
      └─ Log: error message
  ↓
END
```

---

## Detailed: How Trade Execution Works (Step 12)

When spread < 10% and all checks pass, here's what happens:

### Step 12A: Import Market to Simmer

```python
market_id, import_error = import_fast_market_market(best["slug"])
# Example: slug = "btc-updown-5m-1772442600"
# Returns: market_id = "0x1234...abcd"
```

**What this does:**
- Tells Simmer SDK about the Polymarket market
- Simmer fetches market details from Polymarket
- Returns a market_id for trading

### Step 12B: Execute Trade via Simmer SDK

```python
result = get_client().trade(
    market_id=market_id,      # "0x1234...abcd"
    side=side,                 # "yes" or "no"
    amount=amount,             # $5.00 (example)
    source="sdk:fastloop",
    skill_slug="polymarket-fast-loop"
)
```

**What Simmer SDK does internally:**

1. **Fetch Current Price**
   - Queries Polymarket CLOB for current best ask (if buying YES)
   - Or current best bid (if buying NO)

2. **Calculate Shares**
   ```python
   # Example: Buying YES at $0.52
   shares = amount / price = $5.00 / $0.52 = 9.6 shares
   ```

3. **Place Order on Polymarket**
   - Creates a market order on Polymarket CLOB
   - Order type: "BUY" at market price
   - Size: 9.6 shares

4. **Wait for Fill**
   - Order gets matched with sellers
   - May fill at multiple price levels if large order
   - Returns execution details

5. **Return Result**
   ```python
   {
       "success": True,
       "trade_id": "trade_12345",
       "shares_bought": 9.6,
       "simulated": False  # (True if --dry-run)
   }
   ```

---

## Example: Complete Trade Flow

### Scenario: BTC momentum is UP, spread is good

**Market Conditions:**
```
Time: 10:30 AM ET (active trading hours)
BTC Price: $95,000 → $95,500 (+0.53% in 5 min)
Market: "Bitcoin Up or Down - 10:30AM-10:35AM ET"

Order Book:
  Best Bid: $0.485
  Best Ask: $0.515
  Spread: 6% ✅ (< 10%)
  
Market YES Price: $0.515 (from best ask)
```

**Trade Decision:**
```python
# Step 6: Calculate direction
direction = "up"  # BTC went up
side = "yes"      # Bet on UP
divergence = 0.50 + 0.05 - 0.515 = 0.035  # 3.5¢ edge

# Step 9: Check fees
buy_price = 0.515
fee_cost = (1 - 0.515) × 0.10 = 0.0485
min_divergence = 0.0485 + 0.02 = 0.0685
# divergence (0.035) < min_divergence (0.0685)
# ❌ Would skip: "fees eat the edge"
```

**Better Scenario (larger divergence):**
```
Market YES Price: $0.45 (underpriced!)
divergence = 0.50 + 0.05 - 0.45 = 0.10  # 10¢ edge ✅

fee_cost = (1 - 0.45) × 0.10 = 0.055
min_divergence = 0.055 + 0.02 = 0.075
# divergence (0.10) > min_divergence (0.075) ✅
```

**Execution:**
```python
# Step 11: Import
market_id = import_fast_market_market("btc-updown-5m-1772442600")
# Returns: "0xabc123..."

# Step 12: Trade
result = execute_trade(
    market_id="0xabc123...",
    side="yes",
    amount=5.00  # $5 position
)

# Simmer SDK:
# 1. Fetches best ask: $0.45
# 2. Calculates shares: $5.00 / $0.45 = 11.1 shares
# 3. Places order: BUY 11.1 YES shares at market
# 4. Order fills at $0.45
# 5. Returns: success=True, shares_bought=11.1

# Result:
# ✅ Bought 11.1 YES shares @ $0.45
# Cost: $5.00
# If BTC goes up: Win $6.11 (11.1 × $1.00 - 10% fee)
# Profit: $1.11 (22% return)
```

---

## Key Points

### 1. **Spread Check is a Gate**
```
IF spread > 10%:
    ❌ STOP - Don't even try to trade
ELSE:
    ✅ Continue to other checks
```

### 2. **Simmer SDK Handles Order Placement**
You don't manually place orders on Polymarket. The SDK:
- Fetches current prices
- Calculates shares
- Places market orders
- Handles execution

### 3. **Market Orders (Not Limit Orders)**
The code uses **market orders**:
- Buys at current best ask (if buying YES)
- Sells at current best bid (if selling YES)
- Executes immediately at market price
- May have slippage if large order

### 4. **Price Used for Execution**
```python
# For decision: uses midpoint or Gamma snapshot
market_yes_price = 0.515  # From Gamma API

# For execution: Simmer SDK uses live CLOB prices
actual_execution_price = 0.518  # May differ slightly
```

### 5. **Dry Run vs Live**
```python
# Dry run (--dry-run):
result.simulated = True
# Shows what would happen, no real trade

# Live (--live):
result.simulated = False
# Real money, real trade on Polymarket
```

---

## Summary

**When spread < 10%:**

1. ✅ Spread check passes
2. ✅ Other checks (momentum, fees, budget) pass
3. 🔗 Import market to Simmer
4. 💰 Execute trade via Simmer SDK
   - SDK fetches live price from CLOB
   - SDK calculates shares
   - SDK places market order
   - Order fills at current market price
5. ✅ Trade complete, shares in your account

**The spread check ensures you only trade when:**
- Market is liquid (tight spread)
- Execution cost is reasonable
- Your edge won't be eaten by slippage
