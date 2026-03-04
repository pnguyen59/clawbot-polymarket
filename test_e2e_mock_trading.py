#!/usr/bin/env python3
"""
End-to-End Test: Full Mock Trading Flow

This test validates the complete trading flow:
1. RSI calculation and signal classification
2. Signal memory storage
3. Entry signal detection
4. Market discovery
5. Profit calculation
6. Balance checking
7. Mock trade execution
8. Position monitoring
9. Mock exit execution
10. Performance tracking
"""

import time
from datetime import datetime, timezone
from mock_trader import (
    # RSI functions
    calculate_rsi,
    classify_signal,
    check_rsi_entry_signal,
    # Signal memory
    add_signal_to_memory,
    get_signal_memory,
    clear_signal_memory,
    # Market discovery
    round_to_5min,
    generate_market_slug,
    fetch_market_by_slug,
    discover_and_subscribe_market,
    # Profit calculation
    calculate_profit_and_position,
    check_balance_and_adjust_position,
    # Mock trading
    get_mock_balance,
    execute_mock_trade,
    execute_mock_exit,
    show_mock_stats,
    reset_mock_trading,
    save_mock_history,
    # Position monitoring
    PolymarketPositionMonitor,
    # Config
    CONFIG
)


def test_rsi_flow():
    """Test RSI calculation and signal classification flow."""
    print("\n" + "="*60)
    print("Test 1: RSI Calculation and Signal Classification")
    print("="*60)
    
    # Simulate price data (increasing trend)
    prices = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110]
    
    # Calculate RSI
    rsi = calculate_rsi(prices, period=7)
    assert rsi is not None, "RSI should be calculated"
    assert 0 <= rsi <= 100, f"RSI should be between 0-100, got {rsi}"
    print(f"✅ RSI calculated: {rsi:.2f}")
    
    # Test signal classification
    signal = classify_signal(60, 55, 50)  # Increasing RSI
    assert signal == "green", f"Expected green signal, got {signal}"
    print(f"✅ Signal classified: {signal}")
    
    return True


def test_signal_memory_flow():
    """Test signal memory storage and retrieval."""
    print("\n" + "="*60)
    print("Test 2: Signal Memory Flow")
    print("="*60)
    
    # Clear memory
    clear_signal_memory()
    
    # Add signals
    add_signal_to_memory(50.0, 'green')
    add_signal_to_memory(55.0, 'green')
    add_signal_to_memory(60.0, 'green')
    
    memory = get_signal_memory()
    assert len(memory) == 3, f"Expected 3 signals, got {len(memory)}"
    print(f"✅ Signal memory has {len(memory)} signals")
    
    # Test entry signal detection
    rsi_values = [50.0, 55.0, 60.0]  # Increasing RSI
    entry_signal = check_rsi_entry_signal(memory, rsi_values)
    assert entry_signal == "BUY", f"Expected BUY signal, got {entry_signal}"
    print(f"✅ Entry signal detected: {entry_signal}")
    
    # Clear memory for next test
    clear_signal_memory()
    
    return True


def test_market_discovery_flow():
    """Test market discovery flow."""
    print("\n" + "="*60)
    print("Test 3: Market Discovery Flow")
    print("="*60)
    
    # Test timestamp rounding
    current_ts = int(time.time())
    rounded_ts = round_to_5min(current_ts)
    assert rounded_ts <= current_ts, "Rounded timestamp should be <= current"
    assert rounded_ts % 300 == 0, "Rounded timestamp should be divisible by 300"
    print(f"✅ Timestamp rounded: {current_ts} → {rounded_ts}")
    
    # Test slug generation
    slug, ts = generate_market_slug()
    assert slug.startswith("btc-updown-5m-"), f"Invalid slug format: {slug}"
    print(f"✅ Market slug generated: {slug}")
    
    # Test market fetch (may fail if market doesn't exist)
    market = fetch_market_by_slug(slug)
    if market:
        assert 'market_id' in market, "Market should have market_id"
        assert 'tokens' in market, "Market should have tokens"
        print(f"✅ Market found: {market['market_id'][:20]}...")
    else:
        print("⚠️  Market not found (expected if market doesn't exist yet)")
    
    return True


def test_profit_calculation_flow():
    """Test profit calculation and position sizing."""
    print("\n" + "="*60)
    print("Test 4: Profit Calculation Flow")
    print("="*60)
    
    # Test profitable trade (6¢ spread)
    result = calculate_profit_and_position(0.40, 0.46)
    assert result['profitable'], f"Trade should be profitable: {result.get('reason')}"
    assert result['spread'] == 0.06, f"Spread should be 0.06, got {result['spread']}"
    print(f"✅ Profitable trade: spread=${result['spread']:.3f}, net=${result['net_profit_per_share']:.3f}/share")
    
    # Test unprofitable trade (5¢ spread - below minimum)
    result = calculate_profit_and_position(0.40, 0.45)
    assert not result['profitable'], "Trade should NOT be profitable (net < 5¢)"
    print(f"✅ Unprofitable trade rejected: {result['reason']}")
    
    return True


def test_balance_check_flow():
    """Test balance checking and position adjustment."""
    print("\n" + "="*60)
    print("Test 5: Balance Check Flow")
    print("="*60)
    
    # Reset mock trading
    reset_mock_trading(starting_balance=1000.0)
    
    # Test sufficient balance
    result = check_balance_and_adjust_position(100.0, balance=1000.0)
    assert result['sufficient'], "Balance should be sufficient"
    assert not result['adjustment_made'], "No adjustment should be needed"
    print(f"✅ Sufficient balance: ${result['balance']:.2f}")
    
    # Test insufficient balance (needs adjustment)
    result = check_balance_and_adjust_position(500.0, balance=100.0)
    assert result['sufficient'], "Should still be able to trade"
    assert result['adjustment_made'], "Position should be adjusted"
    assert result['adjusted_position'] == 100.0, "Position should be adjusted to balance"
    print(f"✅ Position adjusted: ${result['requested_position']:.2f} → ${result['adjusted_position']:.2f}")
    
    return True


def test_mock_trading_flow():
    """Test mock trade execution flow."""
    print("\n" + "="*60)
    print("Test 6: Mock Trading Flow")
    print("="*60)
    
    # Reset mock trading
    reset_mock_trading(starting_balance=1000.0)
    initial_balance = get_mock_balance()
    print(f"Initial balance: ${initial_balance:.2f}")
    
    # Execute mock trade
    trade_result = execute_mock_trade(
        market_id="0xtest_market",
        asset_id="test_asset",
        side="BUY",
        position_size=100.0,
        entry_price=0.40
    )
    
    assert trade_result['success'], f"Trade should succeed: {trade_result.get('error')}"
    assert trade_result['shares'] > 0, "Should have shares"
    print(f"✅ Trade executed: {trade_result['shares']:.2f} shares @ ${trade_result['price']:.2f}")
    
    # Check balance after trade
    balance_after_trade = get_mock_balance()
    assert balance_after_trade < initial_balance, "Balance should decrease after trade"
    print(f"✅ Balance after trade: ${balance_after_trade:.2f}")
    
    # Execute mock exit (profitable)
    position = {
        'asset_id': trade_result['asset_id'],
        'side': 'BUY',
        'shares': trade_result['shares'],
        'entry_price': trade_result['price']
    }
    
    exit_result = execute_mock_exit(position, exit_price=0.46)
    
    assert exit_result['success'], f"Exit should succeed: {exit_result.get('error')}"
    assert exit_result['net_profit'] > 0, "Should have profit"
    print(f"✅ Exit executed: ${exit_result['net_profit']:.2f} profit")
    
    # Check final balance
    final_balance = get_mock_balance()
    assert final_balance > initial_balance, "Final balance should be higher (profitable trade)"
    print(f"✅ Final balance: ${final_balance:.2f} (profit: ${final_balance - initial_balance:.2f})")
    
    return True


def test_position_monitoring_flow():
    """Test position monitoring flow."""
    print("\n" + "="*60)
    print("Test 7: Position Monitoring Flow")
    print("="*60)
    
    # Create monitor
    monitor = PolymarketPositionMonitor()
    
    # Add position
    exit_called = [False]
    exit_reason = [None]
    
    def exit_callback(position, reason):
        exit_called[0] = True
        exit_reason[0] = reason
    
    monitor.add_position(
        market_id="0xtest_market",
        asset_id="test_asset",
        side="BUY",
        shares=250,
        entry_price=0.40,
        target_profit=13.0,  # Lower target for test
        exit_callback=exit_callback
    )
    
    # Verify position added
    status = monitor.get_position_status("test_asset")
    assert status is not None, "Position should exist"
    assert status['shares'] == 250, "Shares should match"
    print(f"✅ Position added: {status['shares']} shares @ ${status['entry_price']:.2f}")
    
    # Simulate price update (not at target)
    monitor._process_price_update("test_asset", best_bid=0.43, best_ask=0.44)
    assert not exit_called[0], "Exit should not be called yet"
    print(f"✅ Price update processed: current P&L = ${status['net_profit']:.2f}")
    
    # Simulate price update (at target)
    monitor._process_price_update("test_asset", best_bid=0.46, best_ask=0.47)
    assert exit_called[0], "Exit callback should be called"
    assert exit_reason[0] == 'profit_target', f"Exit reason should be profit_target, got {exit_reason[0]}"
    print(f"✅ Exit triggered: reason = {exit_reason[0]}")
    
    return True


def test_full_trading_cycle():
    """Test complete trading cycle from signal to exit."""
    print("\n" + "="*60)
    print("Test 8: Full Trading Cycle")
    print("="*60)
    
    # Reset state
    reset_mock_trading(starting_balance=1000.0)
    clear_signal_memory()
    
    # Step 1: Generate RSI signals (simulating 3 green signals)
    print("\nStep 1: Generate RSI signals")
    add_signal_to_memory(50.0, 'green')
    add_signal_to_memory(55.0, 'green')
    
    # Step 2: Check entry signal
    print("Step 2: Check entry signal")
    memory = get_signal_memory()
    rsi_values = [50.0, 55.0, 60.0]  # Current RSI increasing
    entry_signal = check_rsi_entry_signal(memory, rsi_values)
    assert entry_signal == "BUY", f"Expected BUY signal, got {entry_signal}"
    print(f"✅ Entry signal: {entry_signal}")
    
    # Step 3: Calculate profit and position
    print("Step 3: Calculate profit and position")
    profit_result = calculate_profit_and_position(0.40, 0.46)
    assert profit_result['profitable'], "Trade should be profitable"
    print(f"✅ Position size: ${profit_result['position_size']:.2f}")
    
    # Step 4: Check balance
    print("Step 4: Check balance")
    balance_result = check_balance_and_adjust_position(profit_result['position_size'])
    assert balance_result['sufficient'], "Balance should be sufficient"
    print(f"✅ Balance check passed: ${balance_result['adjusted_position']:.2f}")
    
    # Step 5: Execute trade
    print("Step 5: Execute trade")
    trade_result = execute_mock_trade(
        market_id="0xfull_cycle_test",
        asset_id="full_cycle_asset",
        side="BUY",
        position_size=balance_result['adjusted_position'],
        entry_price=0.40
    )
    assert trade_result['success'], f"Trade should succeed: {trade_result.get('error')}"
    print(f"✅ Trade executed: {trade_result['shares']:.2f} shares")
    
    # Step 6: Exit trade
    print("Step 6: Exit trade")
    position = {
        'asset_id': trade_result['asset_id'],
        'side': 'BUY',
        'shares': trade_result['shares'],
        'entry_price': trade_result['price']
    }
    exit_result = execute_mock_exit(position, exit_price=0.46)
    assert exit_result['success'], f"Exit should succeed: {exit_result.get('error')}"
    print(f"✅ Exit executed: ${exit_result['net_profit']:.2f} profit")
    
    # Step 7: Verify final state
    print("Step 7: Verify final state")
    final_balance = get_mock_balance()
    assert final_balance > 1000.0, "Should have profit"
    print(f"✅ Final balance: ${final_balance:.2f}")
    
    return True


def run_all_tests():
    """Run all end-to-end tests."""
    print("\n" + "="*70)
    print("END-TO-END MOCK TRADING TESTS")
    print("="*70)
    
    tests = [
        ("RSI Flow", test_rsi_flow),
        ("Signal Memory Flow", test_signal_memory_flow),
        ("Market Discovery Flow", test_market_discovery_flow),
        ("Profit Calculation Flow", test_profit_calculation_flow),
        ("Balance Check Flow", test_balance_check_flow),
        ("Mock Trading Flow", test_mock_trading_flow),
        ("Position Monitoring Flow", test_position_monitoring_flow),
        ("Full Trading Cycle", test_full_trading_cycle),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success, None))
        except Exception as e:
            results.append((name, False, str(e)))
            import traceback
            traceback.print_exc()
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, success, _ in results if success)
    failed = sum(1 for _, success, _ in results if not success)
    
    for name, success, error in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {name}")
        if error:
            print(f"       Error: {error}")
    
    print()
    print(f"Total: {passed} passed, {failed} failed")
    print("="*70)
    
    return failed == 0


if __name__ == "__main__":
    import sys
    success = run_all_tests()
    sys.exit(0 if success else 1)
