#!/usr/bin/env python3
"""
Test exit logic integration.

Tests the exit logic functions:
- create_exit_callback()
- start_position_monitoring()
- stop_position_monitoring()
- get_position_pnl()
- execute_trade_with_monitoring()
- handle_market_resolution_exit()
"""

import sys
import time
from mock_trader import (
    create_exit_callback,
    start_position_monitoring,
    stop_position_monitoring,
    get_position_pnl,
    execute_trade_with_monitoring,
    handle_market_resolution_exit,
    execute_mock_trade,
    execute_mock_exit,
    reset_mock_trading,
    get_mock_balance,
    get_polymarket_monitor,
    PolymarketPositionMonitor,
    CONFIG
)


def test_create_exit_callback():
    """Test exit callback creation."""
    print("="*60)
    print("Test 1: Create Exit Callback")
    print("="*60)
    
    market_id = "0x5f65177b394277fd294cd75650044e32ba009a95022d88a0c1d565897d72f8f1"
    asset_id = "71321045679252212594626385532706912750332728571942532289631379312455583992563"
    
    # Create callback
    callback = create_exit_callback(market_id, asset_id)
    
    # Verify callback is callable
    assert callable(callback), "Callback should be callable"
    print("✅ PASS: Exit callback created successfully")
    print()
    
    return callback


def test_exit_callback_execution():
    """Test exit callback execution with mock position."""
    print("="*60)
    print("Test 2: Exit Callback Execution")
    print("="*60)
    
    # Reset mock trading
    reset_mock_trading(starting_balance=1000.0)
    
    market_id = "0xtest_market"
    asset_id = "test_asset_123"
    
    # Execute a mock trade first
    trade_result = execute_mock_trade(
        market_id=market_id,
        asset_id=asset_id,
        side="BUY",
        position_size=100.0,
        entry_price=0.40
    )
    
    assert trade_result['success'], f"Trade failed: {trade_result.get('error')}"
    
    # Create callback
    callback = create_exit_callback(market_id, asset_id)
    
    # Create position dict (simulating what monitor would provide)
    position = {
        'market_id': market_id,
        'asset_id': asset_id,
        'side': 'BUY',
        'shares': trade_result['shares'],
        'entry_price': 0.40,
        'current_price': 0.45,
        'gross_profit': trade_result['shares'] * 0.05,
        'fee': trade_result['shares'] * 0.05 * 0.10,
        'net_profit': trade_result['shares'] * 0.05 * 0.90,
        'target_profit': 15.0
    }
    
    # Execute callback (should trigger mock exit)
    balance_before = get_mock_balance()
    callback(position, 'profit_target')
    balance_after = get_mock_balance()
    
    # Balance should increase after exit
    assert balance_after > balance_before, "Balance should increase after profitable exit"
    print(f"Balance before: ${balance_before:.2f}")
    print(f"Balance after: ${balance_after:.2f}")
    print("✅ PASS: Exit callback executed successfully")
    print()


def test_position_monitoring_integration():
    """Test position monitoring with PolymarketPositionMonitor."""
    print("="*60)
    print("Test 3: Position Monitoring Integration")
    print("="*60)
    
    # Reset mock trading
    reset_mock_trading(starting_balance=1000.0)
    
    market_id = "0xtest_monitor"
    asset_id = "monitor_asset_456"
    
    # Create a monitor instance directly for testing
    monitor = PolymarketPositionMonitor()
    
    # Track if callback was called
    callback_called = {'value': False, 'reason': None}
    
    def test_callback(position, reason):
        callback_called['value'] = True
        callback_called['reason'] = reason
        print(f"   Callback triggered: {reason}")
    
    # Add position to monitor
    monitor.add_position(
        market_id=market_id,
        asset_id=asset_id,
        side="BUY",
        shares=333.33,
        entry_price=0.40,
        target_profit=15.0,
        exit_callback=test_callback
    )
    
    # Verify position was added
    assert asset_id in monitor.positions, "Position should be in monitor"
    assert asset_id in monitor.subscribed_assets, "Asset should be subscribed"
    
    position = monitor.positions[asset_id]
    assert position['side'] == 'BUY', "Side should be BUY"
    assert position['shares'] == 333.33, "Shares should be 333.33"
    assert position['entry_price'] == 0.40, "Entry price should be 0.40"
    
    print("✅ PASS: Position added to monitor")
    
    # Simulate price update that triggers exit
    # For BUY position with 333.33 shares at $0.40, target profit $15
    # Need price to reach ~$0.45 for $15 profit after fees
    monitor._process_price_update(asset_id, best_bid=0.50, best_ask=0.52)
    
    # Check if callback was triggered
    assert callback_called['value'], "Callback should have been triggered"
    assert callback_called['reason'] == 'profit_target', "Reason should be profit_target"
    
    print("✅ PASS: Exit callback triggered on price update")
    print()


def test_market_resolution_handling():
    """Test market resolution event handling."""
    print("="*60)
    print("Test 4: Market Resolution Handling")
    print("="*60)
    
    # Reset mock trading
    reset_mock_trading(starting_balance=1000.0)
    
    # Execute a mock trade
    trade_result = execute_mock_trade(
        market_id="0xresolution_test",
        asset_id="resolution_asset",
        side="BUY",
        position_size=100.0,
        entry_price=0.40
    )
    
    assert trade_result['success'], f"Trade failed: {trade_result.get('error')}"
    
    # Create position for resolution test
    position = {
        'asset_id': trade_result['asset_id'],
        'side': 'BUY',
        'shares': trade_result['shares'],
        'entry_price': 0.40
    }
    
    # Test winning resolution (YES wins, BUY position wins)
    balance_before = get_mock_balance()
    result = handle_market_resolution_exit(position, 'Yes')
    
    assert result['success'], "Resolution exit should succeed"
    
    balance_after = get_mock_balance()
    print(f"Balance before resolution: ${balance_before:.2f}")
    print(f"Balance after resolution: ${balance_after:.2f}")
    print(f"Net profit: ${result['net_profit']:.2f}")
    
    print("✅ PASS: Market resolution handled correctly")
    print()


def test_pnl_calculation_in_monitor():
    """Test P&L calculation in position monitor."""
    print("="*60)
    print("Test 5: P&L Calculation in Monitor")
    print("="*60)
    
    monitor = PolymarketPositionMonitor()
    
    market_id = "0xpnl_test"
    asset_id = "pnl_asset"
    
    # Add position
    monitor.add_position(
        market_id=market_id,
        asset_id=asset_id,
        side="BUY",
        shares=100,
        entry_price=0.40,
        target_profit=100.0  # High target so it doesn't trigger exit
    )
    
    # Simulate price update
    monitor._process_price_update(asset_id, best_bid=0.45, best_ask=0.47)
    
    # Get position status
    position = monitor.get_position_status(asset_id)
    
    assert position is not None, "Position should exist"
    assert position['current_price'] == 0.45, "Current price should be best_bid for BUY"
    
    # Calculate expected P&L
    # Gross: (0.45 - 0.40) * 100 = $5.00
    # Fee: $5.00 * 0.10 = $0.50
    # Net: $5.00 - $0.50 = $4.50
    expected_gross = 5.0
    expected_fee = 0.5
    expected_net = 4.5
    
    assert abs(position['gross_profit'] - expected_gross) < 0.01, f"Gross profit should be ${expected_gross:.2f}"
    assert abs(position['fee'] - expected_fee) < 0.01, f"Fee should be ${expected_fee:.2f}"
    assert abs(position['net_profit'] - expected_net) < 0.01, f"Net profit should be ${expected_net:.2f}"
    
    print(f"Entry price: ${position['entry_price']:.3f}")
    print(f"Current price: ${position['current_price']:.3f}")
    print(f"Gross profit: ${position['gross_profit']:.2f}")
    print(f"Fee: ${position['fee']:.2f}")
    print(f"Net profit: ${position['net_profit']:.2f}")
    
    print("✅ PASS: P&L calculation correct")
    print()


def test_sell_position_pnl():
    """Test P&L calculation for SELL positions."""
    print("="*60)
    print("Test 6: SELL Position P&L")
    print("="*60)
    
    monitor = PolymarketPositionMonitor()
    
    market_id = "0xsell_pnl"
    asset_id = "sell_pnl_asset"
    
    # Add SELL position
    monitor.add_position(
        market_id=market_id,
        asset_id=asset_id,
        side="SELL",
        shares=100,
        entry_price=0.60,
        target_profit=100.0  # High target
    )
    
    # Simulate price update (price went down = profit for SELL)
    monitor._process_price_update(asset_id, best_bid=0.53, best_ask=0.55)
    
    position = monitor.get_position_status(asset_id)
    
    assert position is not None, "Position should exist"
    assert position['current_price'] == 0.55, "Current price should be best_ask for SELL"
    
    # Calculate expected P&L for SELL
    # Gross: (0.60 - 0.55) * 100 = $5.00 (profit when price goes down)
    # Fee: $5.00 * 0.10 = $0.50
    # Net: $5.00 - $0.50 = $4.50
    expected_gross = 5.0
    expected_net = 4.5
    
    assert abs(position['gross_profit'] - expected_gross) < 0.01, f"Gross profit should be ${expected_gross:.2f}"
    assert abs(position['net_profit'] - expected_net) < 0.01, f"Net profit should be ${expected_net:.2f}"
    
    print(f"Entry price: ${position['entry_price']:.3f}")
    print(f"Current price: ${position['current_price']:.3f}")
    print(f"Gross profit: ${position['gross_profit']:.2f}")
    print(f"Net profit: ${position['net_profit']:.2f}")
    
    print("✅ PASS: SELL position P&L correct")
    print()


def run_all_tests():
    """Run all exit logic tests."""
    print()
    print("="*60)
    print("Exit Logic Integration Tests")
    print("="*60)
    print()
    
    test_create_exit_callback()
    test_exit_callback_execution()
    test_position_monitoring_integration()
    test_market_resolution_handling()
    test_pnl_calculation_in_monitor()
    test_sell_position_pnl()
    
    print()
    print("="*60)
    print("All Exit Logic Tests Passed! ✅")
    print("="*60)
    print()


if __name__ == "__main__":
    try:
        run_all_tests()
        print("Exit logic tests completed successfully!")
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
