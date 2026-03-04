#!/usr/bin/env python3
"""
Demo: Mock Trading Engine

This script demonstrates the mock trading functionality with a simple example.
"""

from mock_trader import (
    get_mock_balance,
    execute_mock_trade,
    execute_mock_exit,
    show_mock_stats,
    reset_mock_trading,
    save_mock_history
)


def main():
    print("="*60)
    print("Mock Trading Engine Demo")
    print("="*60)
    print()
    
    # Show initial balance
    print(f"Starting balance: ${get_mock_balance():.2f}")
    print()
    
    # Simulate Trade 1: BUY at $0.40, exit at $0.45 (profitable)
    print("Trade 1: BUY 333 shares at $0.40")
    result1 = execute_mock_trade(
        market_id="0xmarket1",
        asset_id="asset1",
        side="BUY",
        position_size=133.33,
        entry_price=0.40
    )
    
    if result1['success']:
        # Simulate price movement and exit
        print("Price moved to $0.45 - Exiting position...")
        position1 = {
            'asset_id': result1['asset_id'],
            'side': 'BUY',
            'shares': result1['shares'],
            'entry_price': result1['price']
        }
        exit1 = execute_mock_exit(position1, exit_price=0.45)
        print(f"Result: ${exit1['net_profit']:.2f} profit")
    
    # Simulate Trade 2: BUY at $0.50, exit at $0.48 (loss)
    print("\nTrade 2: BUY 200 shares at $0.50")
    result2 = execute_mock_trade(
        market_id="0xmarket2",
        asset_id="asset2",
        side="BUY",
        position_size=100.0,
        entry_price=0.50
    )
    
    if result2['success']:
        print("Price dropped to $0.48 - Exiting position...")
        position2 = {
            'asset_id': result2['asset_id'],
            'side': 'BUY',
            'shares': result2['shares'],
            'entry_price': result2['price']
        }
        exit2 = execute_mock_exit(position2, exit_price=0.48)
        print(f"Result: ${exit2['net_profit']:.2f} loss")
    
    # Show final stats
    print("\nFinal Performance:")
    show_mock_stats()
    
    # Save history
    print("Saving trade history...")
    save_mock_history("demo_trades.json")
    
    print("Demo completed!")


if __name__ == "__main__":
    main()
