#!/usr/bin/env python3
"""
Check current BTC fast market spread
"""
import time
import json
import ssl
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from urllib.parse import quote

def _api_request(url):
    try:
        req = Request(url, headers={"User-Agent": "simmer-fastloop/1.0"})
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        with urlopen(req, timeout=10, context=ssl_context) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}

# Get current market
now_ts = int(time.time())
rounded_ts = (now_ts // 300) * 300
slug = f"btc-updown-5m-{rounded_ts}"

print("=" * 60)
print("BTC Fast Market Spread Check")
print("=" * 60)
print(f"\nCurrent time: {datetime.fromtimestamp(now_ts, tz=timezone.utc)}")
print(f"Market slug: {slug}")
print()

# Fetch market
result = _api_request(f"https://gamma-api.polymarket.com/markets?slug={slug}")

if not result or not isinstance(result, list) or len(result) == 0:
    print("❌ No market found")
    exit(1)

m = result[0]
print(f"Market: {m.get('question')}")
print(f"End Date: {m.get('endDate')}")
print()

# Get CLOB token
clob_tokens_raw = m.get("clobTokenIds", "[]")
if isinstance(clob_tokens_raw, str):
    clob_tokens = json.loads(clob_tokens_raw)
else:
    clob_tokens = clob_tokens_raw

if not clob_tokens:
    print("❌ No CLOB tokens found")
    exit(1)

yes_token = clob_tokens[0]
print(f"YES Token ID: {yes_token[:20]}...")
print()
print(f"token id:{yes_token}")
# Fetch order book
book_result = _api_request(f"https://clob.polymarket.com/book?token_id={quote(str(yes_token))}")

if book_result.get("error"):
    print(f"❌ Order book error: {book_result.get('error')}")
    exit(1)

bids = book_result.get("bids", [])
asks = book_result.get("asks", [])

if not bids or not asks:
    print("❌ No bids or asks in order book")
    exit(1)

print("📊 Order Book Analysis:")
print("-" * 60)

# Try spread API first
spread_result = _api_request(f"https://clob.polymarket.com/spread?token_id={quote(str(yes_token))}")

if spread_result and not spread_result.get("error"):
    # Spread API worked
    spread_pct = float(spread_result.get("spread", 0))
    print(f"\n✅ Using Spread API")
    print(f"Spread %: {spread_pct:.2%}")
    print()
    
    # Verdict
    if spread_pct > 0.10:
        print(f"❌ ILLIQUID - Spread {spread_pct:.1%} > 10%")
        print("   Your code will SKIP this market")
    else:
        print(f"✅ LIQUID - Spread {spread_pct:.1%} < 10%")
        print("   Your code will TRADE this market")
    
    print()
    print("Note: Spread API doesn't provide bid/ask/depth details")
    print("      Fetching order book for additional info...")
    print()

# Fetch order book for details
book_result = _api_request(f"https://clob.polymarket.com/book?token_id={quote(str(yes_token))}")

if book_result.get("error"):
    print(f"❌ Order book error: {book_result.get('error')}")
    exit(1)

bids = book_result.get("bids", [])
asks = book_result.get("asks", [])

if not bids or not asks:
    print("❌ No bids or asks in order book")
    exit(1)

# Best prices
best_bid = float(bids[0]["price"])
best_ask = float(asks[0]["price"])
spread = best_ask - best_bid
mid = (best_ask + best_bid) / 2
spread_pct_calc = spread / mid if mid > 0 else 0

print(f"📖 Order Book Details:")
print(f"Best Bid: ${best_bid:.3f}")
print(f"Best Ask: ${best_ask:.3f}")
print(f"Spread: ${spread:.3f}")
print(f"Mid: ${mid:.3f}")
print(f"Spread % (calculated): {spread_pct_calc:.2%}")
print()

# Show top 5 levels
print("Top 5 Asks (Sellers):")
for i, ask in enumerate(asks[:5]):
    price = float(ask.get("price", 0))
    size = float(ask.get("size", 0))
    value = price * size
    print(f"  {i+1}. ${price:.3f} × {size:.1f} shares = ${value:.2f}")

print()
print("Top 5 Bids (Buyers):")
for i, bid in enumerate(bids[:5]):
    price = float(bid.get("price", 0))
    size = float(bid.get("size", 0))
    value = price * size
    print(f"  {i+1}. ${price:.3f} × {size:.1f} shares = ${value:.2f}")

print()
print("=" * 60)

# Calculate depth
bid_depth = sum(float(b.get("size", 0)) * float(b.get("price", 0)) for b in bids[:5])
ask_depth = sum(float(a.get("size", 0)) * float(a.get("price", 0)) for a in asks[:5])

print(f"Bid Depth (top 5): ${bid_depth:.2f}")
print(f"Ask Depth (top 5): ${ask_depth:.2f}")
print()

# Time analysis
now_et = datetime.fromtimestamp(now_ts, tz=timezone.utc).replace(tzinfo=None)
now_et = now_et.replace(hour=now_et.hour - 5)  # Rough ET conversion
hour_et = now_et.hour

print("⏰ Time Analysis:")
if 9 <= hour_et < 16:
    print(f"   US Market: OPEN (hour {hour_et} ET)")
    print("   Expected: Good liquidity")
else:
    print(f"   US Market: CLOSED (hour {hour_et} ET)")
    print("   Expected: Poor liquidity")
