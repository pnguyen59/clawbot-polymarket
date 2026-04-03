"""
Market discovery and momentum analysis.
"""

import json
import time
from typing import Optional, Dict, Tuple

import requests

from .config import GAMMA_API_HOST, CLOB_HOST, CONFIG
from .logger import log, log_error, log_warn


def round_to_5min(timestamp: int = None) -> int:
    """Round timestamp to nearest 5-minute interval."""
    if timestamp is None:
        timestamp = int(time.time())
    return (timestamp // 300) * 300


def generate_market_slug(timestamp: int = None) -> Tuple[str, int]:
    """Generate BTC 5-minute market slug."""
    rounded_ts = round_to_5min(timestamp)
    return f"btc-updown-5m-{rounded_ts}", rounded_ts


def fetch_market_by_slug(slug: str) -> Optional[Dict]:
    """
    Fetch market details from Polymarket Gamma API.
    
    Args:
        slug: Market slug (e.g., "btc-updown-5m-1705308300")
    
    Returns:
        Market info dict or None if not found
    """
    url = f"{GAMMA_API_HOST}/markets?slug={slug}"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if not data:
            return None
        
        market = data[0]
        
        # Parse token data
        clob_token_ids = market.get('clobTokenIds', [])
        outcomes = market.get('outcomes', [])
        outcome_prices = market.get('outcomePrices', [])
        
        if isinstance(clob_token_ids, str):
            clob_token_ids = json.loads(clob_token_ids)
        if isinstance(outcomes, str):
            outcomes = json.loads(outcomes)
        if isinstance(outcome_prices, str):
            outcome_prices = json.loads(outcome_prices)
        
        tokens = []
        yes_token = None
        no_token = None
        
        for i, (token_id, outcome) in enumerate(zip(clob_token_ids, outcomes)):
            price = float(outcome_prices[i]) if i < len(outcome_prices) else 0.0
            token_info = {'asset_id': token_id, 'outcome': outcome, 'price': price}
            tokens.append(token_info)
            
            outcome_upper = outcome.upper()
            if outcome_upper in ('YES', 'UP'):
                yes_token = token_info
            elif outcome_upper in ('NO', 'DOWN'):
                no_token = token_info
        
        if not yes_token and tokens:
            yes_token = tokens[0]
        if not no_token and len(tokens) > 1:
            no_token = tokens[1]
        
        return {
            'market_id': market.get('conditionId'),
            'slug': slug,
            'question': market.get('question', 'N/A'),
            'tokens': tokens,
            'yes_token': yes_token,
            'no_token': no_token,
            'closed': market.get('closed', False),
            'resolved': market.get('archived', False),
        }
        
    except Exception as e:
        log_error(f"Market fetch error: {e}")
        return None


def discover_current_market(max_retries: int = 3, retry_delay: int = 5) -> Optional[Dict]:
    """
    Discover current 5-minute BTC market.
    
    Args:
        max_retries: Maximum retry attempts
        retry_delay: Delay between retries in seconds
    
    Returns:
        Market info dict or None if not found
    """
    slug, rounded_ts = generate_market_slug()
    
    log(f"Discovering market: {slug}")
    
    for attempt in range(max_retries + 1):
        market_info = fetch_market_by_slug(slug)
        
        if market_info:
            if market_info.get('closed') or market_info.get('resolved'):
                log_warn("Market is closed/resolved")
                return None
            
            log(f"  ✅ Market found: {market_info['question'][:50]}...", 'success')
            return market_info
        
        if attempt < max_retries:
            log(f"  Retrying in {retry_delay}s...")
            time.sleep(retry_delay)
    
    return None


def check_momentum(asset: str = "BTC", lookback_minutes: int = None) -> Optional[Dict]:
    """
    Get price momentum from Binance API.
    
    Args:
        asset: Asset symbol (default: BTC)
        lookback_minutes: Minutes to look back (default: from config)
    
    Returns:
        Momentum data dict or None on error
    """
    if lookback_minutes is None:
        lookback_minutes = CONFIG['lookback_minutes']
    
    symbol = f"{asset}USDT"
    
    try:
        url = "https://api.binance.com/api/v3/klines"
        params = {'symbol': symbol, 'interval': '1m', 'limit': lookback_minutes + 1}
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        candles = response.json()
        
        if not candles or len(candles) < 2:
            return None
        
        price_then = float(candles[0][1])
        price_now = float(candles[-1][4])
        
        momentum_pct = ((price_now - price_then) / price_then) * 100
        direction = "up" if momentum_pct > 0 else "down"
        
        return {
            'momentum_pct': momentum_pct,
            'direction': direction,
            'price_now': price_now,
            'price_then': price_then
        }
        
    except Exception as e:
        log_error(f"Momentum error: {e}")
        return None


def fetch_current_price(asset_id: str, market_slug: str = None) -> Optional[float]:
    """
    Fetch current price for an asset.
    
    Args:
        asset_id: Token ID
        market_slug: Market slug (optional, for efficiency)
    
    Returns:
        Current price or None
    """
    if market_slug:
        market = fetch_market_by_slug(market_slug)
        if market:
            for token in market.get('tokens', []):
                if token['asset_id'] == asset_id:
                    return token['price']
    return None


def fetch_orderbook_price(token_id: str) -> Optional[Dict]:
    """
    Fetch current orderbook price from Polymarket CLOB API.
    
    This gets the REAL price you'll pay/receive, not the stale Gamma API price.
    
    Args:
        token_id: Token ID (asset_id)
    
    Returns:
        Dict with best_bid, best_ask, mid_price or None on error
    """
    url = f"{CLOB_HOST}/book"
    params = {'token_id': token_id}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        bids = data.get('bids', [])
        asks = data.get('asks', [])
        
        best_bid = float(bids[0]['price']) if bids else None
        best_ask = float(asks[0]['price']) if asks else None
        
        mid_price = None
        if best_bid and best_ask:
            mid_price = (best_bid + best_ask) / 2
        elif best_ask:
            mid_price = best_ask
        elif best_bid:
            mid_price = best_bid
        
        return {
            'best_bid': best_bid,
            'best_ask': best_ask,
            'mid_price': mid_price,
            # For BUY orders, you pay the ask price
            'buy_price': best_ask,
            # For SELL orders, you receive the bid price
            'sell_price': best_bid,
        }
        
    except Exception as e:
        log_error(f"Orderbook fetch error: {e}")
        return None


def fetch_market_price(token_id: str, side: str) -> Optional[float]:
    """
    Fetch market price from Polymarket CLOB API /price endpoint.
    
    Args:
        token_id: Token ID (asset_id)
        side: 'BUY' or 'SELL'
    
    Returns:
        Market price or None on error
    """
    url = f"{CLOB_HOST}/price"
    params = {'token_id': token_id, 'side': side}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        price = data.get('price')
        if price is not None:
            return float(price)
        return None
        
    except Exception as e:
        log_error(f"Market price fetch error: {e}")
        return None
