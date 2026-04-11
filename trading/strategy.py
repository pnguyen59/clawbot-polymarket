"""
Trading strategy and decision logic.
"""

from typing import Optional, Dict

from .config import CONFIG, BUY, SELL
from .market import check_momentum, fetch_market_price
from .rsi import RSISignalMemory, classify_signal


# Global signal memory
_signal_memory = RSISignalMemory(max_size=CONFIG['rsi_signal_memory_size'])


def calculate_position_size(entry_price: float, target_profit: float = None, 
                            max_position: float = None) -> Dict:
    """
    Calculate position size to achieve target profit.
    
    Args:
        entry_price: Entry price per share
        target_profit: Target profit in dollars (default: from config)
        max_position: Maximum position size (default: from config)
    
    Returns:
        Dict with position sizing details
    """
    if target_profit is None:
        target_profit = CONFIG['target_profit_per_trade']
    if max_position is None:
        max_position = CONFIG['max_position_size']
    
    target_spread = CONFIG['target_sell_spread']
    min_profit_per_share = CONFIG['min_profit_per_share']
    
    exit_price = entry_price + target_spread
    
    # Cap exit price at 0.99 (max token price)
    if exit_price > 0.99:
        exit_price = 0.99
    
    # Actual spread after capping
    actual_spread = exit_price - entry_price
    
    # If entry price is too high, spread becomes too small
    if actual_spread <= 0:
        return {
            'valid': False, 
            'reason': f'Entry price ${entry_price:.3f} too high, no room for profit'
        }
    
    gross_profit_per_share = actual_spread
    fee_per_share = gross_profit_per_share * 0.10
    net_profit_per_share = gross_profit_per_share - fee_per_share
    
    if net_profit_per_share < min_profit_per_share:
        return {
            'valid': False, 
            'reason': f'Net profit ${net_profit_per_share:.3f} < min ${min_profit_per_share:.3f}'
        }
    
    shares_needed = target_profit / net_profit_per_share
    position_size = shares_needed * entry_price
    
    if position_size > max_position:
        position_size = max_position
        shares_needed = position_size / entry_price
    
    expected_profit = shares_needed * net_profit_per_share
    
    return {
        'valid': True,
        'shares': shares_needed,
        'position_size': position_size,
        'entry_price': entry_price,
        'exit_price': exit_price,
        'expected_profit': expected_profit,
        'net_profit_per_share': net_profit_per_share,
    }


def make_trading_decision(market_info: Dict, momentum_data: Dict = None, 
                          rsi_data: Dict = None, open_positions: Dict = None) -> Dict:
    """
    Make trading decision based on market conditions.
    
    Args:
        market_info: Market information from discover_current_market()
        momentum_data: Pre-fetched momentum data (optional)
        rsi_data: Pre-fetched RSI data (optional)
        open_positions: Current open positions dict (optional)
    
    Returns:
        Trading decision dict with action and details
    """
    global _signal_memory
    
    if open_positions is None:
        open_positions = {}
    
    print()
    print("="*60)
    print("🧠 Trading Decision Analysis")
    print("="*60)
    
    # Check 1: Market Status
    print("\n📋 Check 1: Market Status")
    if not market_info:
        print("   ❌ No market info")
        return {'action': 'SKIP', 'reason': 'No market info'}
    
    if market_info.get('closed') or market_info.get('resolved'):
        print("   ❌ Market not active")
        return {'action': 'SKIP', 'reason': 'Market not active'}
    
    print("   ✅ Market active")
    
    # Check 2: Position limit
    print("\n📊 Check 2: Position Limit")
    if len(open_positions) >= CONFIG['max_open_positions']:
        print(f"   ❌ Max positions reached ({len(open_positions)}/{CONFIG['max_open_positions']})")
        return {'action': 'SKIP', 'reason': 'Max positions reached'}
    print(f"   ✅ Positions: {len(open_positions)}/{CONFIG['max_open_positions']}")
    
    # Check 3: Momentum
    print("\n📈 Check 3: Momentum")
    if momentum_data is None:
        momentum_data = check_momentum()
    
    if not momentum_data:
        print("   ❌ Failed to get momentum")
        return {'action': 'SKIP', 'reason': 'Momentum unavailable'}
    
    momentum_pct = abs(momentum_data['momentum_pct'])
    direction = momentum_data['direction']
    min_momentum = CONFIG['min_momentum_pct']
    
    print(f"   Price: ${momentum_data['price_now']:,.2f}")
    print(f"   Momentum: {momentum_data['momentum_pct']:+.3f}%")
    print(f"   Direction: {direction}")
    
    if momentum_pct < min_momentum:
        print(f"   ❌ Momentum {momentum_pct:.3f}% < min {min_momentum}%")
        return {'action': 'SKIP', 'reason': f'Weak momentum: {momentum_pct:.3f}%'}
    
    print(f"   ✅ Momentum sufficient")
    
    # Check 4: RSI (optional)
    print("\n📉 Check 4: RSI Signal")
    rsi_signal = None
    
    if CONFIG['rsi_enabled']:
        if rsi_data:
            rsi_values = rsi_data.get('rsi_values', [])
            
            # Calculate current classification from fresh RSI data
            if len(rsi_values) >= 3:
                current_classification = classify_signal(
                    rsi_values[-1], rsi_values[-2], rsi_values[-3]
                )
                _signal_memory.add(rsi_data['current_rsi'], current_classification)
                
                # Get entry signal (requires 3 consecutive green/red)
                rsi_signal = _signal_memory.get_entry_signal(rsi_values)
                
                print(f"   RSI: {rsi_data['current_rsi']:.1f} ({current_classification})")
                print(f"   Signal: {rsi_signal or 'NEUTRAL'}")
                
                if CONFIG['rsi_require_confirmation']:
                    # RSI must have a clear signal (not neutral)
                    if rsi_signal is None:
                        print("   ❌ RSI signal is NEUTRAL - skipping")
                        return {'action': 'SKIP', 'reason': 'RSI signal is neutral'}
                    
                    # RSI must confirm momentum direction
                    if direction == 'up' and rsi_signal == 'SELL':
                        print("   ❌ RSI SELL conflicts with UP momentum")
                        return {'action': 'SKIP', 'reason': 'RSI conflicts with momentum'}
                    if direction == 'down' and rsi_signal == 'BUY':
                        print("   ❌ RSI BUY conflicts with DOWN momentum")
                        return {'action': 'SKIP', 'reason': 'RSI conflicts with momentum'}
                    
                    print("   ✅ RSI confirms momentum")
            else:
                print("   ⚠️ Insufficient RSI data")
                if CONFIG['rsi_require_confirmation']:
                    return {'action': 'SKIP', 'reason': 'Insufficient RSI data'}
        else:
            print("   ⚠️ RSI data unavailable")
            if CONFIG['rsi_require_confirmation']:
                return {'action': 'SKIP', 'reason': 'RSI data unavailable'}
    else:
        print("   ⏭️ RSI disabled")
    
    # Determine trade side and token based on momentum direction
    tokens = market_info.get('tokens', [])
    
    if direction == 'up':
        # Buy YES token when expecting price to go up
        token = market_info.get('yes_token') or tokens[0]
    else:
        # Buy NO token when expecting price to go down
        token = market_info.get('no_token') or (tokens[1] if len(tokens) > 1 else tokens[0])
    
    asset_id = token['asset_id']
    side = BUY  # Always BUY the token (YES or NO)
    
    # Fetch REAL market price from CLOB API /price endpoint
    print("\n📖 Fetching market price...")
    entry_price = fetch_market_price(asset_id, side)
    
    if entry_price:
        print(f"   Market price ({side}): ${entry_price:.3f}")
    else:
        # Fallback to Gamma API price (less accurate)
        entry_price = token['price']
        print(f"   ⚠️ Using Gamma API price (may be stale): ${entry_price:.3f}")
    
    # Check 5: Position sizing
    print("\n💰 Check 5: Position Sizing")
    sizing = calculate_position_size(entry_price)
    
    if not sizing['valid']:
        print(f"   ❌ {sizing['reason']}")
        return {'action': 'SKIP', 'reason': sizing['reason']}
    
    print(f"   Entry: ${entry_price:.3f}")
    print(f"   Target exit: ${sizing['exit_price']:.3f}")
    print(f"   Shares: {sizing['shares']:.2f}")
    print(f"   Position: ${sizing['position_size']:.2f}")
    print(f"   Expected profit: ${sizing['expected_profit']:.2f}")
    print("   ✅ Position sizing valid")
    
    # All checks passed
    print("\n" + "="*60)
    print("✅ ALL CHECKS PASSED - TRADE SIGNAL")
    print("="*60)
    
    return {
        'action': 'TRADE',
        'side': side,
        'token_id': asset_id,
        'outcome': token['outcome'],
        'entry_price': entry_price,
        'exit_price': sizing['exit_price'],
        'shares': sizing['shares'],
        'position_size': sizing['position_size'],
        'expected_profit': sizing['expected_profit'],
        'market_id': market_info['market_id'],
        'market_slug': market_info['slug'],
        'momentum': momentum_data,
        'rsi_signal': rsi_signal,
    }


def get_signal_memory() -> RSISignalMemory:
    """Get the global signal memory."""
    return _signal_memory


def clear_signal_memory():
    """Clear the global signal memory."""
    _signal_memory.clear()
