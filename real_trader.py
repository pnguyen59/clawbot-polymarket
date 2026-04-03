#!/usr/bin/env python3
"""
Real Trading Bot for Polymarket

Usage:
    export POLYMARKET_PRIVATE_KEY=0x...
    python real_trader.py [options]

Options:
    --dry-run               Simulate trades without executing
    --target-profit FLOAT   Target profit per trade (default: 15.0)
    --max-position FLOAT    Maximum position size (default: 100.0)
    --no-rsi                Disable RSI confirmation
    --min-momentum FLOAT    Minimum momentum percent (default: 0.1)
"""

import sys
import time
import argparse
from datetime import datetime, timezone

from trading.config import CONFIG, BUY, SELL
from trading.logger import log, log_error
from trading.client import PolymarketTrader
from trading.rsi import BinanceRSIStream
from trading.monitor import PolymarketPositionMonitor
from trading.market import discover_current_market, fetch_market_by_slug, fetch_market_price
from trading.strategy import make_trading_decision


# Global state
_binance_rsi_stream = None
_polymarket_monitor = None
_trader_client = None
_open_positions = {}


def execute_exit(position: dict, reason: str):
    """Execute exit for a position."""
    global _trader_client, _open_positions, _polymarket_monitor
    
    asset_id = position.get('asset_id')
    shares = position.get('shares', 0)
    entry_price = position.get('entry_price', 0)
    current_price = position.get('current_price', 0)
    net_profit = position.get('net_profit', 0)
    
    if not asset_id:
        log_error("Exit failed: No asset_id in position")
        return
    
    log(f"Executing exit: {asset_id[:20]}...", 'exit')
    log(f"  Reason: {reason}", 'exit')
    log(f"  Shares: {shares:.2f}", 'exit')
    log(f"  Entry: ${entry_price:.3f} → Current: ${current_price:.3f}", 'exit')
    log(f"  P&L: ${net_profit:+.2f}", 'exit')
    
    if CONFIG['dry_run']:
        log("  DRY RUN - Exit not executed", 'exit')
    else:
        # Wait for token balance to settle
        actual_shares = _trader_client.wait_for_token_balance(asset_id, shares)
        
        if actual_shares > 0:
            log(f"  Selling {actual_shares:.2f} shares of {asset_id[:20]}...", 'exit')
            response = _trader_client.place_market_order(asset_id, SELL, actual_shares)
            if response:
                taking_amount = response.get('takingAmount', '0')
                log(f"  ✅ Exit executed! Received: {taking_amount}", 'exit')
            else:
                log_error("  Exit order failed - no response")
        else:
            log("  ⚠️ No shares to sell (balance = 0)", 'warn')
    
    # Remove from tracking
    _open_positions.pop(asset_id, None)
    if _polymarket_monitor:
        _polymarket_monitor.remove_position(asset_id)


def execute_trade(decision: dict) -> dict:
    """Execute a trade based on decision."""
    global _trader_client, _open_positions, _polymarket_monitor
    
    if decision.get('action') != 'TRADE':
        return {'success': False, 'error': 'No trade signal'}
    
    token_id = decision['token_id']
    side = decision['side']
    position_size = decision['position_size']
    entry_price = decision['entry_price']
    market_id = decision['market_id']
    
    # Check balance
    balance = _trader_client.get_usdc_balance()
    if balance is None or balance < position_size:
        log_error(f"Insufficient balance: ${balance:.2f} < ${position_size:.2f}")
        return {'success': False, 'error': 'Insufficient balance'}
    
    log(f"Balance: ${balance:.2f}")
    
    # Execute buy order
    response = _trader_client.place_market_order(token_id, side, position_size)
    
    if not response:
        return {'success': False, 'error': 'Order failed'}
    
    # Get shares from response
    taking_amount = response.get('takingAmount', '0')
    shares = float(taking_amount) if taking_amount else position_size / entry_price
    
    # Track position
    position_data = {
        'market_id': market_id,
        'asset_id': token_id,
        'side': side,
        'shares': shares,
        'entry_price': entry_price,
        'target_profit': CONFIG['target_profit_per_trade'],
        'entry_time': time.time(),
        'market_slug': decision.get('market_slug'),
    }
    
    _open_positions[token_id] = position_data
    
    # Start position monitoring
    if _polymarket_monitor:
        _polymarket_monitor.add_position(
            market_id=market_id,
            asset_id=token_id,
            side=side,
            shares=shares,
            entry_price=entry_price,
            target_profit=CONFIG['target_profit_per_trade']
        )
    
    return {'success': True, 'position_id': token_id, 'shares': shares, 'entry_price': entry_price}


def run_trading_iteration() -> dict:
    """Run a single trading iteration."""
    global _binance_rsi_stream, _open_positions
    
    print()
    print("="*60)
    print(f"🔄 Trading Iteration - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("="*60)
    
    try:
        market_info = discover_current_market()
        
        if not market_info:
            return {'status': 'skipped', 'reason': 'Market not found'}
        
        # Get RSI data if available
        rsi_data = None
        if _binance_rsi_stream and CONFIG['rsi_enabled']:
            rsi_data = _binance_rsi_stream.get_current_rsi_data()
        
        decision = make_trading_decision(market_info, rsi_data=rsi_data, open_positions=_open_positions)
        
        if decision['action'] == 'SKIP':
            return {'status': 'skipped', 'reason': decision.get('reason')}
        
        result = execute_trade(decision)
        
        if result['success']:
            return {
                'status': 'traded',
                'position_id': result['position_id'],
                'shares': result['shares'],
                'entry_price': result['entry_price']
            }
        else:
            return {'status': 'failed', 'reason': result.get('error')}
            
    except Exception as e:
        log_error(f"Iteration error: {e}")
        return {'status': 'error', 'reason': str(e)}


def update_position_prices():
    """Update position prices - fallback if WebSocket isn't updating."""
    global _open_positions, _polymarket_monitor
    
    # If WebSocket monitor is connected and has positions, it handles updates
    if _polymarket_monitor and _polymarket_monitor.is_connected() and _polymarket_monitor.positions:
        # Sync from monitor to local
        for asset_id, pos in _polymarket_monitor.positions.items():
            if asset_id in _open_positions:
                _open_positions[asset_id]['current_price'] = pos.get('current_price', _open_positions[asset_id]['entry_price'])
                _open_positions[asset_id]['net_profit'] = pos.get('net_profit', 0)
                
                # Check exit condition
                target_profit = _open_positions[asset_id].get('target_profit', CONFIG['target_profit_per_trade'])
                if pos.get('net_profit', 0) >= target_profit and not pos.get('exit_triggered'):
                    log(f"Exit target reached: ${pos['net_profit']:.2f}", 'exit')
                    execute_exit(_open_positions[asset_id], 'profit_target')
        return
    
    # Fallback: fetch from API if WebSocket not working
    for asset_id, pos in list(_open_positions.items()):
        try:
            current_price = fetch_market_price(asset_id, SELL)
            
            if current_price:
                entry_price = pos['entry_price']
                shares = pos['shares']
                
                gross_profit = (current_price - entry_price) * shares
                fee = gross_profit * 0.10 if gross_profit > 0 else 0
                net_profit = gross_profit - fee
                
                pos['current_price'] = current_price
                pos['gross_profit'] = gross_profit
                pos['fee'] = fee
                pos['net_profit'] = net_profit
                
                target_profit = pos.get('target_profit', CONFIG['target_profit_per_trade'])
                if net_profit >= target_profit:
                    log(f"Exit target reached: ${net_profit:.2f}", 'exit')
                    execute_exit(pos, 'profit_target')
                    
        except Exception as e:
            log_error(f"Price update error: {e}")


def log_position_status():
    """Log current position status from WebSocket monitor."""
    global _polymarket_monitor, _open_positions
    
    # Prefer WebSocket monitor positions (real-time) over local tracking
    if _polymarket_monitor and _polymarket_monitor.positions:
        for asset_id, pos in _polymarket_monitor.positions.items():
            net_profit = pos.get('net_profit', 0)
            current_price = pos.get('current_price', pos.get('entry_price', 0))
            entry_price = pos.get('entry_price', 0)
            print(f"   {asset_id[:16]}... entry=${entry_price:.3f} now=${current_price:.3f} P&L: ${net_profit:+.2f}")
            
            # Sync to local positions
            if asset_id in _open_positions:
                _open_positions[asset_id]['current_price'] = current_price
                _open_positions[asset_id]['net_profit'] = net_profit
    else:
        # Fallback to local positions
        for asset_id, pos in _open_positions.items():
            net_profit = pos.get('net_profit', 0)
            current_price = pos.get('current_price', pos['entry_price'])
            print(f"   {asset_id[:16]}... @ ${current_price:.3f} P&L: ${net_profit:+.2f}")


def calculate_sleep_until_next_5min():
    """Calculate seconds until next 5-minute interval."""
    now = time.time()
    current_5min = (int(now) // 300) * 300
    next_5min = current_5min + 300
    return next_5min - now + 5


def run_main_loop():
    """Run the main continuous trading loop."""
    global _binance_rsi_stream, _polymarket_monitor
    
    log("🚀 Starting Main Trading Loop")
    print("="*60)
    
    iteration_count = 0
    last_position_log = time.time()
    
    # Initialize WebSocket connections
    log("Initializing WebSocket connections...")
    
    if CONFIG['rsi_enabled']:
        log("  Starting Binance RSI stream...")
        try:
            _binance_rsi_stream = BinanceRSIStream(symbol="BTCUSDT", period=CONFIG['rsi_period'])
            _binance_rsi_stream.start()
            time.sleep(2)
            log("  ✅ Binance RSI stream connected", 'success')
        except Exception as e:
            log(f"  ⚠️ Binance stream failed: {e}", 'warn')
            CONFIG['rsi_enabled'] = False
    
    log("  Starting Polymarket monitor...")
    try:
        _polymarket_monitor = PolymarketPositionMonitor(exit_callback=execute_exit)
        _polymarket_monitor.start()
        time.sleep(1)
        log("  ✅ Polymarket monitor connected", 'success')
    except Exception as e:
        log(f"  ⚠️ Polymarket monitor failed: {e}", 'warn')
    
    print("="*60)
    log("Trading loop started. Press Ctrl+C to stop.")
    print("="*60)
    
    while True:
        try:
            iteration_count += 1
            
            print(f"\n{'='*60}")
            print(f"📈 Iteration #{iteration_count}")
            print(f"{'='*60}")
            
            sleep_seconds = calculate_sleep_until_next_5min()
            next_time = datetime.now(timezone.utc).timestamp() + sleep_seconds
            next_dt = datetime.fromtimestamp(next_time, tz=timezone.utc)
            
            print(f"⏳ Monitoring until {next_dt.strftime('%H:%M:%S UTC')} ({sleep_seconds:.0f}s)")
            
            loop_start = time.time()
            last_trade_check = 0
            last_price_update = 0
            traded_this_iteration = False
            
            while time.time() - loop_start < sleep_seconds:
                current_time = time.time()
                
                # Check entry conditions every 5 seconds
                if not traded_this_iteration and (current_time - last_trade_check >= 5):
                    last_trade_check = current_time
                    elapsed = int(current_time - loop_start)
                    
                    print(f"\n🔍 Checking entry conditions ({elapsed}s elapsed)...")
                    
                    result = run_trading_iteration()
                    status = result.get('status')
                    
                    if status == 'traded':
                        print(f"\n✅ Trade executed")
                        print(f"   Shares: {result.get('shares', 0):.2f}")
                        print(f"   Entry: ${result.get('entry_price', 0):.3f}")
                        traded_this_iteration = True
                    elif status == 'skipped':
                        print(f"   ⏭️ No entry: {result.get('reason')}")
                    elif status == 'failed':
                        print(f"   ❌ Failed: {result.get('reason')}")
                
                # Update position prices every 5 seconds
                if len(_open_positions) > 0 and (current_time - last_price_update >= 5):
                    last_price_update = current_time
                    update_position_prices()
                
                # Log position status every 30 seconds
                if current_time - last_position_log >= 30:
                    if len(_open_positions) > 0:
                        print(f"\n📊 Position status:")
                        log_position_status()
                    last_position_log = current_time
                
                remaining = sleep_seconds - (time.time() - loop_start)
                if remaining > 0:
                    time.sleep(min(1, remaining))
            
            print(f"\n{'='*60}")
            if traded_this_iteration:
                print(f"✅ Iteration #{iteration_count} complete - Trade executed")
            else:
                print(f"⏭️ Iteration #{iteration_count} complete - No trade")
            print(f"   Open positions: {len(_open_positions)}")
            print(f"{'='*60}")
            
        except Exception as e:
            log_error(f"Main loop error: {e}")
            time.sleep(10)


def shutdown_gracefully():
    """Shutdown the bot gracefully."""
    global _binance_rsi_stream, _polymarket_monitor, _trader_client
    
    print()
    print("="*60)
    print("🛑 Shutting down...")
    print("="*60)
    
    if _binance_rsi_stream:
        log("Stopping Binance stream...")
        _binance_rsi_stream.stop()
    
    if _polymarket_monitor:
        log("Stopping Polymarket monitor...")
        _polymarket_monitor.stop()
    
    if _trader_client:
        stats = _trader_client.get_stats()
        print()
        print("📊 Trading Statistics:")
        print(f"   Total trades: {stats['total_trades']}")
        print(f"   Successful: {stats['successful_trades']}")
        print(f"   Failed: {stats['failed_trades']}")
        print(f"   Volume: ${stats['total_volume']:.2f}")
    
    print()
    print("="*60)
    print("👋 Bot stopped. Goodbye!")
    print("="*60)


def main():
    """Main entry point."""
    global CONFIG, _trader_client
    
    parser = argparse.ArgumentParser(description='Real Trading Bot for Polymarket')
    parser.add_argument('--private-key', type=str, help='Ethereum private key')
    parser.add_argument('--dry-run', action='store_true', help='Simulate without executing')
    parser.add_argument('--target-profit', type=float, default=15.0, help='Target profit per trade')
    parser.add_argument('--max-position', type=float, default=100.0, help='Max position size')
    parser.add_argument('--no-rsi', action='store_true', help='Disable RSI')
    parser.add_argument('--min-momentum', type=float, default=0.1, help='Min momentum percent')
    args = parser.parse_args()
    
    # Update config
    CONFIG['dry_run'] = args.dry_run
    CONFIG['target_profit_per_trade'] = args.target_profit
    CONFIG['max_position_size'] = args.max_position
    CONFIG['rsi_enabled'] = not args.no_rsi
    CONFIG['min_momentum_pct'] = args.min_momentum
    
    print()
    print("="*60)
    print("🤖 Real Trading Bot - Polymarket")
    print("="*60)
    print(f"Started: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print()
    
    print("📋 Configuration:")
    print(f"   Dry Run: {CONFIG['dry_run']}")
    print(f"   Target Profit: ${CONFIG['target_profit_per_trade']:.2f}")
    print(f"   Max Position: ${CONFIG['max_position_size']:.2f}")
    print(f"   RSI Enabled: {CONFIG['rsi_enabled']}")
    print(f"   Min Momentum: {CONFIG['min_momentum_pct']}%")
    print()
    
    # Initialize trader
    import os
    private_key = args.private_key or os.environ.get('POLYMARKET_PRIVATE_KEY')
    
    if not private_key:
        print("❌ Private key required")
        print("   Set POLYMARKET_PRIVATE_KEY env var or use --private-key")
        sys.exit(1)
    
    try:
        _trader_client = PolymarketTrader(private_key=private_key, dry_run=CONFIG['dry_run'])
        
        if not _trader_client.initialize():
            print("❌ Failed to initialize trader")
            sys.exit(1)
        
        balance = _trader_client.get_usdc_balance()
        if balance:
            print(f"💵 USDC Balance: ${balance:,.2f}")
        print()
        
        if not CONFIG['dry_run']:
            print("⚠️  WARNING: REAL TRADING MODE!")
            print("⚠️  Real trades will be executed!")
            print("⚠️  Press Ctrl+C within 5 seconds to abort...")
            try:
                time.sleep(5)
            except KeyboardInterrupt:
                print("\n🛑 Aborted.")
                sys.exit(0)
            print("Proceeding with real trading...")
            print()
        
        run_main_loop()
        
    except KeyboardInterrupt:
        shutdown_gracefully()
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        shutdown_gracefully()
        sys.exit(1)


if __name__ == "__main__":
    main()
