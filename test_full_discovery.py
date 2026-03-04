#!/usr/bin/env python3
import time
import json
from datetime import datetime, timezone
from urllib.request import urlopen, Request

def _api_request(url, method='GET', data=None, headers=None, timeout=15):
    try:
        req_headers = headers or {}
        if 'User-Agent' not in req_headers:
            req_headers['User-Agent'] = 'simmer-fastloop_market/1.0'
        body = None
        if data:
            body = json.dumps(data).encode('utf-8')
            req_headers['Content-Type'] = 'application/json'
        req = Request(url, data=body, headers=req_headers, method=method)
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        return {'error': str(e)}

def discover_fast_market_markets(asset='BTC', window='5m'):
    import time
    
    # Get current time and round DOWN to last 5-minute boundary
    now_ts = int(time.time())
    rounded_ts = (now_ts // 300) * 300
    
    asset_prefix = asset.lower()
    markets = []
    
    # Query the current 5-minute window market
    slug = f"{asset_prefix}-updown-{window}-{rounded_ts}"
    url = f"https://gamma-api.polymarket.com/markets?slug={slug}"
    result = _api_request(url)
    
    if result and isinstance(result, list) and len(result) > 0:
        m = result[0]
        if not m.get("closed", False):
            end_date_str = m.get("endDate")
            if end_date_str:
                try:
                    end_time = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    end_time = None
            else:
                end_time = None
            
            clob_tokens_raw = m.get("clobTokenIds", "[]")
            if isinstance(clob_tokens_raw, str):
                try:
                    clob_tokens = json.loads(clob_tokens_raw)
                except (json.JSONDecodeError, ValueError):
                    clob_tokens = []
            else:
                clob_tokens = clob_tokens_raw or []
            
            markets.append({
                "question": m.get("question", ""),
                "slug": m.get("slug", ""),
                "condition_id": m.get("conditionId", ""),
                "end_time": end_time,
                "outcomes": m.get("outcomes", []),
                "outcome_prices": m.get("outcomePrices", "[]"),
                "clob_token_ids": clob_tokens,
                "fee_rate_bps": int(m.get("fee_rate_bps") or m.get("feeRateBps") or 0),
            })
    
    # Also check the next 5-minute window
    next_ts = rounded_ts + 300
    slug_next = f"{asset_prefix}-updown-{window}-{next_ts}"
    url_next = f"https://gamma-api.polymarket.com/markets?slug={slug_next}"
    result_next = _api_request(url_next)
    
    if result_next and isinstance(result_next, list) and len(result_next) > 0:
        m = result_next[0]
        if not m.get("closed", False):
            end_date_str = m.get("endDate")
            if end_date_str:
                try:
                    end_time = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    end_time = None
            else:
                end_time = None
            
            clob_tokens_raw = m.get("clobTokenIds", "[]")
            if isinstance(clob_tokens_raw, str):
                try:
                    clob_tokens = json.loads(clob_tokens_raw)
                except (json.JSONDecodeError, ValueError):
                    clob_tokens = []
            else:
                clob_tokens = clob_tokens_raw or []
            
            markets.append({
                "question": m.get("question", ""),
                "slug": m.get("slug", ""),
                "condition_id": m.get("conditionId", ""),
                "end_time": end_time,
                "outcomes": m.get("outcomes", []),
                "outcome_prices": m.get("outcomePrices", "[]"),
                "clob_token_ids": clob_tokens,
                "fee_rate_bps": int(m.get("fee_rate_bps") or m.get("feeRateBps") or 0),
            })
    
    return markets

def find_best_fast_market(markets):
    """Pick the best fast_market to trade: soonest expiring with enough time remaining."""
    MIN_TIME_REMAINING = 30
    WINDOW = "5m"
    _window_seconds = {"5m": 300, "15m": 900, "1h": 3600}
    
    now = datetime.now(timezone.utc)
    max_remaining = _window_seconds.get(WINDOW, 300) * 2
    candidates = []
    
    print(f"\n🔍 Evaluating {len(markets)} markets:")
    print(f"   Current time: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"   Min time remaining: {MIN_TIME_REMAINING}s")
    print(f"   Max time remaining: {max_remaining}s")
    print()
    
    for m in markets:
        end_time = m.get("end_time")
        question = m.get("question", "")[:60]
        
        if not end_time:
            print(f"   ❌ {question} - No end_time")
            continue
            
        remaining = (end_time - now).total_seconds()
        print(f"   📊 {question}")
        print(f"      End time: {end_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"      Remaining: {remaining:.0f}s")
        
        if remaining > MIN_TIME_REMAINING and remaining < max_remaining:
            print(f"      ✅ CANDIDATE")
            candidates.append((remaining, m))
        elif remaining <= MIN_TIME_REMAINING:
            print(f"      ⏸️  Too close to expiry ({remaining:.0f}s < {MIN_TIME_REMAINING}s)")
        else:
            print(f"      ⏸️  Too far in future ({remaining:.0f}s > {max_remaining}s)")
        print()

    if not candidates:
        return None
    
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]

# Run test
print("=" * 60)
print("Testing Fast Market Discovery")
print("=" * 60)

markets = discover_fast_market_markets('BTC', '5m')
print(f"\n✅ Found {len(markets)} markets")

if markets:
    best = find_best_fast_market(markets)
    if best:
        print(f"\n🎯 Best market: {best['question']}")
    else:
        print(f"\n❌ No suitable market found (all too close to expiry or too far)")
else:
    print("\n❌ No markets discovered")
