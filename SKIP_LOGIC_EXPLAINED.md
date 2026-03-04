# Fast Market Skip Logic Explained

## Overview
Your code discovers fast markets and filters them based on time remaining until expiry. Markets get "skipped" when they don't meet the timing criteria.

## The Skip Conditions

### 1. **Discovery Phase** (`discover_fast_market_markets`)
- Queries current 5-minute window: `btc-updown-5m-{rounded_timestamp}`
- Queries next 5-minute window: `btc-updown-5m-{rounded_timestamp + 300}`
- Returns 0-2 markets

### 2. **Selection Phase** (`find_best_fast_market`)
This is where markets get filtered/skipped:

```python
now = datetime.now(timezone.utc)
max_remaining = _window_seconds.get(WINDOW, 300) * 2  # 600 seconds for 5m window
MIN_TIME_REMAINING = 30  # seconds (or configured value)

for m in markets:
    end_time = m.get("end_time")
    remaining = (end_time - now).total_seconds()
    
    # Market is ACCEPTED if:
    if remaining > MIN_TIME_REMAINING and remaining < max_remaining:
        candidates.append((remaining, m))
    # Otherwise SKIPPED
```

## Skip Reasons

### ❌ **Skip Reason 1: Too Close to Expiry**
```
remaining <= MIN_TIME_REMAINING (default: 30 seconds)
```

**Example:**
- Current time: 8:54:35 UTC
- Market ends: 8:55:00 UTC
- Remaining: 25 seconds
- **Result:** SKIPPED (25s < 30s minimum)

**Why?** Not enough time to analyze signal and execute trade before market closes.

---

### ❌ **Skip Reason 2: Too Far in Future**
```
remaining >= max_remaining (600 seconds for 5m window)
```

**Example:**
- Current time: 8:45:00 UTC
- Market ends: 8:55:00 UTC
- Remaining: 600 seconds
- **Result:** SKIPPED (600s >= 600s maximum)

**Why?** Market hasn't started yet or is too far away. Price signal may not be relevant.

---

### ✅ **Accepted: Goldilocks Zone**
```
MIN_TIME_REMAINING < remaining < max_remaining
30s < remaining < 600s
```

**Example:**
- Current time: 8:53:00 UTC
- Market ends: 8:55:00 UTC
- Remaining: 120 seconds
- **Result:** ACCEPTED ✅

---

## Your Original Error

You saw:
```
Skipped: Bitcoin Up or Down - December 19, 11:35AM-11:40AM ... (25259653s left < 30s min)
```

**What happened:**
- 25,259,653 seconds = ~292 days
- The year parsing was wrong (parsed as 2026 instead of 2025)
- Market was actually EXPIRED (December 2025 vs March 2026)
- But appeared to be 292 days in the FUTURE
- Got skipped because 25259653s > 600s (too far in future)

**The message was misleading** - it said "< 30s min" but actually meant "> 600s max"

---

## Current Behavior (After Fix)

Now with proper `endDate` parsing from API:

**Example at 8:53:00 UTC:**

1. **Discover markets:**
   - Current window: `btc-updown-5m-1772441400` (ends 8:55:00)
   - Next window: `btc-updown-5m-1772441700` (ends 9:00:00)

2. **Filter markets:**
   - Market 1: 120s remaining → ✅ ACCEPTED (30s < 120s < 600s)
   - Market 2: 420s remaining → ✅ ACCEPTED (30s < 420s < 600s)

3. **Pick best:**
   - Chooses Market 1 (soonest expiring with enough time)

---

## Configuration

You can adjust the skip thresholds:

```bash
# Minimum time before expiry (default: 30s, or auto: 10% of window)
python fastloop_trader.py --set min_time_remaining=60

# Window size (affects max_remaining = window * 2)
python fastloop_trader.py --set window=15m
```

**Auto mode (min_time_remaining=0):**
- 5m window → 30s minimum (10% of 300s)
- 15m window → 90s minimum (10% of 900s)

---

## Summary

Markets get skipped when:
1. ❌ **Too close to expiry** (< 30s remaining) - not enough time to trade
2. ❌ **Too far in future** (> 600s remaining for 5m) - market hasn't started
3. ❌ **No end_time** - API data incomplete
4. ✅ **Accepted** - in the 30s to 600s "sweet spot"

The original bug made expired 2025 markets appear as future 2026 markets, causing incorrect skip messages.
