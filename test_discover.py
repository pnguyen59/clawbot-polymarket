#!/usr/bin/env python3
import time
import json
from datetime import datetime, timezone
from urllib.request import urlopen, Request

def _api_request(url, method='GET', data=None, headers=None, timeout=15):
    try:
        import ssl
        req_headers = headers or {}
        if 'User-Agent' not in req_headers:
            req_headers['User-Agent'] = 'simmer-fastloop_market/1.0'
        body = None
        if data:
            body = json.dumps(data).encode('utf-8')
            req_headers['Content-Type'] = 'application/json'
        req = Request(url, data=body, headers=req_headers, method=method)
        
        # Create SSL context that doesn't verify certificates
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        with urlopen(req, timeout=timeout, context=ssl_context) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        return {'error': str(e)}

def discover_fast_market_markets(asset='BTC', window='5m'):
    # Get current time and round DOWN to last 5-minute boundary
    now_ts = int(time.time())
    rounded_ts = (now_ts // 300) * 300
    
    print(f'Current timestamp: {now_ts}')
    print(f'Rounded timestamp: {rounded_ts}')
    print(f'Current time: {datetime.fromtimestamp(now_ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")}')
    print(f'Rounded time: {datetime.fromtimestamp(rounded_ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")}')
    print()
    
    asset_prefix = asset.lower()
    markets = []
    
    # Query the current 5-minute window market
    slug = f'{asset_prefix}-updown-{window}-{rounded_ts}'
    url = f'https://gamma-api.polymarket.com/markets?slug={slug}'
    print(f'Querying: {slug}')
    print(f'URL: {url}')
    result = _api_request(url)
    
    if result and isinstance(result, list) and len(result) > 0:
        m = result[0]
        print(f'✅ Found market: {m.get("question")}')
        print(f'   Slug: {m.get("slug")}')
        print(f'   End Date: {m.get("endDate")}')
        print(f'   Closed: {m.get("closed")}')
        markets.append(m)
    else:
        print(f'❌ No market found for current window')
        if isinstance(result, dict) and result.get('error'):
            print(f'   Error: {result.get("error")}')
    
    print()
    
    # Also check the next 5-minute window
    next_ts = rounded_ts + 300
    slug_next = f'{asset_prefix}-updown-{window}-{next_ts}'
    print(f'Querying next window: {slug_next}')
    print(f'Next time: {datetime.fromtimestamp(next_ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")}')
    url_next = f'https://gamma-api.polymarket.com/markets?slug={slug_next}'
    result_next = _api_request(url_next)
    
    if result_next and isinstance(result_next, list) and len(result_next) > 0:
        m = result_next[0]
        print(f'✅ Found market: {m.get("question")}')
        print(f'   Slug: {m.get("slug")}')
        print(f'   End Date: {m.get("endDate")}')
        print(f'   Closed: {m.get("closed")}')
        markets.append(m)
    else:
        print(f'❌ No market found for next window')
        if isinstance(result_next, dict) and result_next.get('error'):
            print(f'   Error: {result_next.get("error")}')
    
    print()
    print(f'Total markets found: {len(markets)}')
    return markets

# Run the function
if __name__ == '__main__':
    discover_fast_market_markets('BTC', '5m')
