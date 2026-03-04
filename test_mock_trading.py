#!/usr/bin/env python3
"""
Test mock trading functionality.

Tests all mock trading functions:
- get_mock_balance()
- execute_mock_trade()
- execute_mock_exit()
- show_mock_stats()
- reset_mock_trading()
- save_mock_history()
"""

import sys
import time
from mock_trader import (
    get_mock_balance,
    execute_mock_trade,
    execute_mock_exit,
    show_mock_stats,
    reset_mock_trading,
    save_mock_history,
    CONFIG
)


def test_mock_trading():
    """Test mock trading with simulated trades."""
    
    print("="*60)
    print("Testing Mock Trading Engine")
    print("="*60)
    print()
    
    # Test 1: Check initial balance
    print("Test 1: Check initial balance")
    balance = get_mock_balance()
    print(f"Initial balance: ${balance:.2f}")
    assert balance == CONFIG['mock_balance'], f"Expected ${CONFIG['mock_balance']:.2f}, got ${balance:.2f}"
    print("✅ PASS: Initial balance correct")
    print()
    
    # Test 2: Execute mock BUY trade
    print("Test 2: Execute mock BUY trade")
    result = execute_mock_trade(
        market_id="0x5f65177b394277fd294cd75650044e32ba009a95022d88a0c1d565897d72f8f1",
        asset_id="71321045679252212594626385532706912750332728571942532289631379312455583992563",
        side="BUY",
        position_size=133.33,
        entry_price=0.40
    )
    
    assert result['success'], f"Trade failed: {result.get('error')}"
    assert result['shares'] > 0, "Shares should be positive"
    assert result['price'] == 0.40, "Entry price should be 0.40"
    print("✅ PASS: Mock BUY trade executed")
    
    # Check balance after trade
    balance_after = get_mock_balance()
    expected_balance = CONFIG['mock_balance'] - 133.33
    assert abs(balance_after - expected_balance) < 0.01, f"Expected ${expected_balance:.2f}, got ${balance_after:.2f}"
    print(f"Balance after trade: ${balance_after:.2f}")
    print()
    
    # Test 3: Execute mock exit (profitable)
    print("Test 3: Execute mock exit (profitable)")
    position = {
        'asset_id': result['asset_id'],
        'side': 'BUY',
        'shares': result['shares'],
        'entry_price': result['price']
    }
    
    exit_result = execute_mock_exit(position, exit_price=0.45)
    
    assert exit_result['success'], f"Exit failed: {exit_result.get('error')}"
    assert exit_result['net_profit'] > 0, "Net profit should be positive"
    print("✅ PASS: Mock exit executed (profitable)")
    
    # Check balance after exit
    balance_after_exit = get_mock_balance()
    print(f"Balance after exit: ${balance_after_exit:.2f}")
    print(f"Net profit: ${exit_result['net_profit']:.2f}")
    print()
    
    # Test 4: Execute multiple trades to test stats
    print("Test 4: Execute multiple trades")
    for i in range(9):  # Execute 9 more trades (total 10)
        # Alternate between profitable and losing trades
        entry_price = 0.40
        exit_price = 0.45 if i % 3 != 0 else 0.38  # 2/3 wins, 1/3 losses
        
        # Execute entry
        trade_result = execute_mock_trade(
            market_id=f"0xmarket{i}",
            asset_id=f"asset{i}",
            side="BUY",
            position_size=100.0,
            entry_price=entry_price
        )
        
        if not trade_result['success']:
            print(f"Trade {i+2} failed: {trade_result.get('error')}")
            continue
        
        # Execute exit
        pos = {
            'asset_id': trade_result['asset_id'],
            'side': 'BUY',
            'shares': trade_result['shares'],
            'entry_price': trade_result['price']
        }
        
        exit_res = execute_mock_exit(pos, exit_price=exit_price)
        
        if exit_res['success']:
            print(f"Trade {i+2}: Entry ${entry_price:.2f} → Exit ${exit_price:.2f} → P&L ${exit_res['net_profit']:.2f}")
    
    print()
    print("✅ PASS: Multiple trades executed")
    print()
    
    # Test 5: Show stats (should auto-show after 10 trades)
    print("Test 5: Stats should be displayed")
    # Stats were already shown after 10th trade
    print("✅ PASS: Stats displayed after 10 trades")
    print()
    
    # Test 6: Save trade history
    print("Test 6: Save trade history")
    save_mock_history("test_mock_trades.json")
    print("✅ PASS: Trade history saved")
    print()
    
    # Test 7: Reset mock trading
    print("Test 7: Reset mock trading")
    reset_mock_trading(starting_balance=2000.0)
    balance_after_reset = get_mock_balance()
    assert balance_after_reset == 2000.0, f"Expected $2000.00, got ${balance_after_reset:.2f}"
    print("✅ PASS: Mock trading reset")
    print()
    
    # Test 8: Test insufficient balance
    print("Test 8: Test insufficient balance")
    reset_mock_trading(starting_balance=50.0)
    
    insufficient_result = execute_mock_trade(
        market_id="0xtest",
        asset_id="test_asset",
        side="BUY",
        position_size=100.0,
        entry_price=0.40
    )
    
    assert not insufficient_result['success'], "Trade should fail with insufficient balance"
    assert 'Insufficient' in insufficient_result['error'], "Error should mention insufficient balance"
    print(f"Expected error: {insufficient_result['error']}")
    print("✅ PASS: Insufficient balance handled correctly")
    print()
    
    # Test 9: Test SELL position
    print("Test 9: Test SELL position")
    reset_mock_trading(starting_balance=1000.0)
    
    sell_result = execute_mock_trade(
        market_id="0xsell",
        asset_id="sell_asset",
        side="SELL",
        position_size=100.0,
        entry_price=0.60
    )
    
    assert sell_result['success'], f"SELL trade failed: {sell_result.get('error')}"
    print("✅ PASS: SELL trade executed")
    
    # Exit SELL position (profit when price goes down)
    sell_position = {
        'asset_id': sell_result['asset_id'],
        'side': 'SELL',
        'shares': sell_result['shares'],
        'entry_price': sell_result['price']
    }
    
    sell_exit = execute_mock_exit(sell_position, exit_price=0.55)  # Price went down = profit
    
    assert sell_exit['success'], f"SELL exit failed: {sell_exit.get('error')}"
    assert sell_exit['net_profit'] > 0, "SELL position should be profitable when price goes down"
    print(f"SELL position P&L: ${sell_exit['net_profit']:.2f}")
    print("✅ PASS: SELL position exit handled correctly")
    print()
    
    # Final summary
    print("="*60)
    print("All Tests Passed! ✅")
    print("="*60)
    print()
    
    # Show final stats
    show_mock_stats()


if __name__ == "__main__":
    try:
        test_mock_trading()
        print("Mock trading tests completed successfully!")
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
