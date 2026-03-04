#!/usr/bin/env python3
"""
Test profit calculation functions.

Tests:
- calculate_profit_and_position() for entry analysis
- check_balance_and_adjust_position() for balance checks

Covers various scenarios from requirements:
- Profitable trades (sufficient spread)
- Unprofitable trades (insufficient spread)
- Position sizing for target profit
- Balance checks and adjustments
- Edge cases
"""

import sys
from mock_trader import (
    calculate_profit_and_position,
    check_balance_and_adjust_position,
    reset_mock_trading,
    get_mock_balance,
    CONFIG
)


def test_calculate_profit_and_position():
    """Test profit calculation and position sizing."""
    
    print("="*60)
    print("Testing calculate_profit_and_position()")
    print("="*60)
    print()
    
    # Test 1: Profitable trade - 6¢ spread (from requirements - need 5.56¢+ for 5¢ net)
    print("Test 1: Profitable trade - 6¢ spread")
    print("Buy at $0.40, sell at $0.46")
    print("Expected: Gross $0.06 → Fee $0.006 → Net $0.054 ✅")
    
    result = calculate_profit_and_position(0.40, 0.46)
    
    assert result['profitable'], f"Trade should be profitable, got: {result.get('reason', 'unknown')}"
    assert abs(result['spread'] - 0.06) < 0.001, f"Spread should be 0.06, got {result['spread']}"
    assert abs(result['net_profit_per_share'] - 0.054) < 0.001, f"Net profit per share should be 0.054, got {result['net_profit_per_share']}"
    
    print(f"✅ Spread: ${result['spread']:.3f}")
    print(f"✅ Net profit per share: ${result['net_profit_per_share']:.3f}")
    print(f"✅ Required shares: {result['required_shares']:.2f}")
    print(f"✅ Position size: ${result['position_size']:.2f}")
    print(f"✅ Expected net profit: ${result['expected_net_profit']:.2f}")
    print()
    
    # Test 2: Unprofitable trade - 5¢ spread (from requirements 8.6 - need 5.56¢+ for 5¢ net)
    print("Test 2: Unprofitable trade - 5¢ spread (below minimum)")
    print("Buy at $0.40, sell at $0.45")
    print("Expected: Gross $0.05 → Fee $0.005 → Net $0.045 ❌ (< 5¢ minimum)")
    
    result = calculate_profit_and_position(0.40, 0.45)
    
    assert not result['profitable'], "Trade should NOT be profitable (net < 5¢)"
    assert 'reason' in result, "Should have a reason for rejection"
    assert abs(result['spread'] - 0.05) < 0.001, f"Spread should be 0.05, got {result['spread']}"
    assert abs(result['net_profit_per_share'] - 0.045) < 0.001, f"Net profit per share should be 0.045, got {result['net_profit_per_share']}"
    
    print(f"✅ Not profitable: {result['reason']}")
    print(f"✅ Spread: ${result['spread']:.3f}")
    print(f"✅ Net profit per share: ${result['net_profit_per_share']:.4f}")
    print()
    
    # Test 3: Unprofitable trade - spread too small (from requirements 8.9)
    print("Test 3: Unprofitable trade - spread too small")
    print("Buy 1000 shares at $0.40, sell at $0.405")
    print("Expected: Gross $5 → Fee $0.50 → Net $4.50 ❌")
    
    result = calculate_profit_and_position(0.40, 0.405)
    
    assert not result['profitable'], "Trade should NOT be profitable"
    assert 'reason' in result, "Should have a reason for rejection"
    assert abs(result['spread'] - 0.005) < 0.001, f"Spread should be 0.005, got {result['spread']}"
    assert abs(result['net_profit_per_share'] - 0.0045) < 0.001, f"Net profit per share should be 0.0045, got {result['net_profit_per_share']}"
    
    print(f"✅ Not profitable: {result['reason']}")
    print(f"✅ Spread: ${result['spread']:.3f}")
    print(f"✅ Net profit per share: ${result['net_profit_per_share']:.4f}")
    print()
    
    # Test 4: Large spread - 10¢ (from requirements 10.5)
    print("Test 4: Large spread - 10¢")
    print("Buy at $0.40, sell at $0.50")
    print("Expected: Net $0.09/share → Need 167 shares → Cost $66.67")
    
    result = calculate_profit_and_position(0.40, 0.50)
    
    assert result['profitable'], "Trade should be profitable"
    assert abs(result['spread'] - 0.10) < 0.001, f"Spread should be 0.10, got {result['spread']}"
    assert abs(result['net_profit_per_share'] - 0.09) < 0.001, f"Net profit per share should be 0.09, got {result['net_profit_per_share']}"
    
    # For $15 target profit with 9¢ net per share: 15 / 0.09 = 166.67 shares
    # Cost: 166.67 * 0.40 = $66.67
    assert abs(result['required_shares'] - 166.67) < 0.1, f"Should need ~167 shares, got {result['required_shares']}"
    assert abs(result['position_size'] - 66.67) < 0.1, f"Position should be ~$66.67, got {result['position_size']}"
    
    print(f"✅ Net profit per share: ${result['net_profit_per_share']:.3f}")
    print(f"✅ Required shares: {result['required_shares']:.2f}")
    print(f"✅ Position size: ${result['position_size']:.2f}")
    print()
    
    # Test 5: Custom target profit
    print("Test 5: Custom target profit - $20")
    
    result = calculate_profit_and_position(0.40, 0.50, target_profit=20.0)
    
    assert result['profitable'], "Trade should be profitable"
    # For $20 target with 9¢ net per share: 20 / 0.09 = 222.22 shares
    # Cost: 222.22 * 0.40 = $88.89
    assert abs(result['required_shares'] - 222.22) < 0.1, f"Should need ~222 shares, got {result['required_shares']}"
    assert abs(result['position_size'] - 88.89) < 0.1, f"Position should be ~$88.89, got {result['position_size']}"
    assert abs(result['expected_net_profit'] - 20.0) < 0.1, f"Expected profit should be ~$20, got {result['expected_net_profit']}"
    
    print(f"✅ Required shares: {result['required_shares']:.2f}")
    print(f"✅ Position size: ${result['position_size']:.2f}")
    print(f"✅ Expected net profit: ${result['expected_net_profit']:.2f}")
    print()
    
    # Test 6: Max position size cap
    print("Test 6: Max position size cap - $50")
    
    result = calculate_profit_and_position(0.40, 0.50, max_position_size=50.0)
    
    assert result['profitable'], "Trade should be profitable"
    assert result['position_size'] <= 50.0, f"Position should be capped at $50, got ${result['position_size']}"
    
    # With $50 cap: 50 / 0.40 = 125 shares
    # Expected profit: 125 * 0.09 = $11.25
    assert abs(result['required_shares'] - 125.0) < 0.1, f"Should have 125 shares, got {result['required_shares']}"
    assert abs(result['expected_net_profit'] - 11.25) < 0.1, f"Expected profit should be ~$11.25, got {result['expected_net_profit']}"
    
    print(f"✅ Position size capped: ${result['position_size']:.2f}")
    print(f"✅ Shares: {result['required_shares']:.2f}")
    print(f"✅ Expected net profit: ${result['expected_net_profit']:.2f}")
    print()
    
    # Test 7: Minimum spread boundary (exactly 5.5¢)
    print("Test 7: Minimum spread boundary - exactly 5.5¢")
    
    result = calculate_profit_and_position(0.40, 0.455)
    
    # 5.5¢ spread → 10% fee = 0.55¢ → net 4.95¢ (just below 5¢ minimum)
    # Should be rejected
    assert not result['profitable'], "Trade with 5.5¢ spread should be rejected (net < 5¢)"
    
    print(f"✅ Correctly rejected: {result['reason']}")
    print()
    
    # Test 8: Just above minimum (5.6¢ spread)
    print("Test 8: Just above minimum - 5.6¢ spread")
    
    result = calculate_profit_and_position(0.40, 0.456)
    
    # 5.6¢ spread → 10% fee = 0.56¢ → net 5.04¢ (just above 5¢ minimum)
    assert result['profitable'], "Trade with 5.6¢ spread should be profitable"
    assert result['net_profit_per_share'] >= 0.05, f"Net profit should be >= 5¢, got {result['net_profit_per_share']}"
    
    print(f"✅ Profitable: ${result['net_profit_per_share']:.4f} per share")
    print()
    
    print("="*60)
    print("All calculate_profit_and_position() tests passed! ✅")
    print("="*60)
    print()


def test_check_balance_and_adjust_position():
    """Test balance checking and position adjustment."""
    
    print("="*60)
    print("Testing check_balance_and_adjust_position()")
    print("="*60)
    print()
    
    # Reset mock trading to known state
    reset_mock_trading(starting_balance=1000.0)
    
    # Test 1: Sufficient balance - no adjustment needed
    print("Test 1: Sufficient balance - no adjustment")
    print("Balance: $1000, Position: $133.33")
    
    result = check_balance_and_adjust_position(133.33, balance=1000.0)
    
    assert result['sufficient'], "Balance should be sufficient"
    assert not result['adjustment_made'], "No adjustment should be needed"
    assert result['adjusted_position'] == 133.33, f"Position should remain $133.33, got ${result['adjusted_position']}"
    
    print(f"✅ Sufficient: {result['sufficient']}")
    print(f"✅ Adjusted position: ${result['adjusted_position']:.2f}")
    print(f"✅ No adjustment made")
    print()
    
    # Test 2: Insufficient balance - adjust down
    print("Test 2: Insufficient balance - adjust down")
    print("Balance: $100, Position: $133.33")
    
    result = check_balance_and_adjust_position(133.33, balance=100.0)
    
    assert result['sufficient'], "Should still be able to trade (balance > minimum)"
    assert result['adjustment_made'], "Adjustment should be made"
    assert result['adjusted_position'] == 100.0, f"Position should be adjusted to $100, got ${result['adjusted_position']}"
    assert 'adjustment_reason' in result, "Should have adjustment reason"
    
    print(f"✅ Sufficient: {result['sufficient']}")
    print(f"✅ Adjusted position: ${result['adjusted_position']:.2f}")
    print(f"✅ Adjustment reason: {result['adjustment_reason']}")
    print()
    
    # Test 3: Balance below minimum - cannot trade
    print("Test 3: Balance below minimum - cannot trade")
    print("Balance: $0.30, Position: $133.33, Minimum: $0.50")
    
    result = check_balance_and_adjust_position(133.33, balance=0.30, min_position=0.50)
    
    assert not result['sufficient'], "Balance should be insufficient"
    assert 'reason' in result, "Should have rejection reason"
    assert 'Insufficient balance' in result['reason'], "Reason should mention insufficient balance"
    
    print(f"✅ Insufficient: {result['sufficient']}")
    print(f"✅ Reason: {result['reason']}")
    print()
    
    # Test 4: Balance exactly at minimum
    print("Test 4: Balance exactly at minimum")
    print("Balance: $0.50, Position: $133.33, Minimum: $0.50")
    
    result = check_balance_and_adjust_position(133.33, balance=0.50, min_position=0.50)
    
    assert result['sufficient'], "Balance at minimum should be sufficient"
    assert result['adjustment_made'], "Position should be adjusted down"
    assert result['adjusted_position'] == 0.50, f"Position should be $0.50, got ${result['adjusted_position']}"
    
    print(f"✅ Sufficient: {result['sufficient']}")
    print(f"✅ Adjusted position: ${result['adjusted_position']:.2f}")
    print()
    
    # Test 5: Use mock balance (no balance parameter)
    print("Test 5: Use mock balance from get_mock_balance()")
    
    reset_mock_trading(starting_balance=500.0)
    current_balance = get_mock_balance()
    print(f"Current mock balance: ${current_balance:.2f}")
    
    result = check_balance_and_adjust_position(133.33)  # No balance parameter
    
    assert result['sufficient'], "Balance should be sufficient"
    assert result['balance'] == 500.0, f"Should use mock balance of $500, got ${result['balance']}"
    assert not result['adjustment_made'], "No adjustment needed"
    
    print(f"✅ Used mock balance: ${result['balance']:.2f}")
    print(f"✅ Adjusted position: ${result['adjusted_position']:.2f}")
    print()
    
    # Test 6: Large position with small balance
    print("Test 6: Large position with small balance")
    print("Balance: $50, Position: $500")
    
    result = check_balance_and_adjust_position(500.0, balance=50.0)
    
    assert result['sufficient'], "Should be able to trade with reduced position"
    assert result['adjustment_made'], "Position should be adjusted"
    assert result['adjusted_position'] == 50.0, f"Position should be $50, got ${result['adjusted_position']}"
    
    print(f"✅ Adjusted from ${result['requested_position']:.2f} to ${result['adjusted_position']:.2f}")
    print()
    
    # Test 7: Custom minimum position
    print("Test 7: Custom minimum position - $10")
    print("Balance: $5, Position: $100, Minimum: $10")
    
    result = check_balance_and_adjust_position(100.0, balance=5.0, min_position=10.0)
    
    assert not result['sufficient'], "Balance below custom minimum"
    assert '$5.00 < $10.00' in result['reason'], "Should show custom minimum in reason"
    
    print(f"✅ Correctly rejected: {result['reason']}")
    print()
    
    # Test 8: Edge case - balance exactly equals position
    print("Test 8: Balance exactly equals position")
    print("Balance: $133.33, Position: $133.33")
    
    result = check_balance_and_adjust_position(133.33, balance=133.33)
    
    assert result['sufficient'], "Balance should be sufficient"
    assert not result['adjustment_made'], "No adjustment needed"
    assert result['adjusted_position'] == 133.33, "Position should remain unchanged"
    
    print(f"✅ Exact match - no adjustment")
    print()
    
    print("="*60)
    print("All check_balance_and_adjust_position() tests passed! ✅")
    print("="*60)
    print()


def test_integrated_scenario():
    """Test integrated scenario: calculate profit + check balance."""
    
    print("="*60)
    print("Testing Integrated Scenario")
    print("="*60)
    print()
    
    # Scenario: Trader wants to enter a trade
    # Buy at $0.40, sell at $0.46 (6¢ spread for 5.4¢ net), balance $100
    
    print("Scenario: Buy at $0.40, sell at $0.46")
    print("Available balance: $100")
    print()
    
    # Step 1: Calculate profit and position
    print("Step 1: Calculate profit and position")
    profit_result = calculate_profit_and_position(0.40, 0.46)
    
    if not profit_result['profitable']:
        print(f"❌ Trade rejected: {profit_result['reason']}")
        return
    
    print(f"✅ Trade is profitable")
    print(f"   Spread: ${profit_result['spread']:.3f}")
    print(f"   Net profit per share: ${profit_result['net_profit_per_share']:.3f}")
    print(f"   Required position: ${profit_result['position_size']:.2f}")
    print(f"   Expected profit: ${profit_result['expected_net_profit']:.2f}")
    print()
    
    # Step 2: Check balance and adjust if needed
    print("Step 2: Check balance and adjust position")
    balance_result = check_balance_and_adjust_position(
        profit_result['position_size'],
        balance=100.0
    )
    
    if not balance_result['sufficient']:
        print(f"❌ Trade rejected: {balance_result['reason']}")
        return
    
    print(f"✅ Balance check passed")
    print(f"   Available balance: ${balance_result['balance']:.2f}")
    print(f"   Requested position: ${balance_result['requested_position']:.2f}")
    print(f"   Final position: ${balance_result['adjusted_position']:.2f}")
    
    if balance_result['adjustment_made']:
        print(f"   ⚠️  Position adjusted: {balance_result['adjustment_reason']}")
        
        # Recalculate expected profit with adjusted position
        adjusted_shares = balance_result['adjusted_position'] / 0.40
        adjusted_profit = adjusted_shares * profit_result['net_profit_per_share']
        
        print(f"   Adjusted shares: {adjusted_shares:.2f}")
        print(f"   Adjusted expected profit: ${adjusted_profit:.2f}")
        print(f"   (Note: May not reach $15 target due to balance constraint)")
    
    print()
    print("✅ Trade ready to execute!")
    print()
    
    print("="*60)
    print("Integrated scenario test passed! ✅")
    print("="*60)
    print()


def run_all_tests():
    """Run all profit calculation tests."""
    
    print("\n")
    print("="*60)
    print("PROFIT CALCULATION TESTS")
    print("="*60)
    print("\n")
    
    try:
        # Test profit calculation
        test_calculate_profit_and_position()
        
        # Test balance checking
        test_check_balance_and_adjust_position()
        
        # Test integrated scenario
        test_integrated_scenario()
        
        # Final summary
        print("\n")
        print("="*60)
        print("ALL TESTS PASSED! ✅")
        print("="*60)
        print("\n")
        
        return True
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
