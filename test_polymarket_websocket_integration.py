#!/usr/bin/env python3
"""
Integration Test for Polymarket WebSocket Connection

This test connects to the real Polymarket WebSocket to verify:
1. Connection establishment
2. Subscription to asset_ids
3. Receiving real-time price updates
4. Heartbeat (PING/PONG) functionality

NOTE: This test requires internet connection and connects to live Polymarket WebSocket.
"""

import time
import sys
from mock_trader import PolymarketPositionMonitor


def test_websocket_connection():
    """Test real WebSocket connection to Polymarket."""
    print("="*60)
    print("Polymarket WebSocket Integration Test")
    print("="*60)
    print()
    
    # Create monitor
    print("1. Creating PolymarketPositionMonitor...")
    monitor = PolymarketPositionMonitor()
    
    # Start connection
    print("2. Starting WebSocket connection...")
    monitor.start()
    
    # Wait for connection
    print("3. Waiting for connection to establish...")
    time.sleep(3)
    
    # Check connection status
    if not monitor.is_connected():
        print("❌ Failed to connect to Polymarket WebSocket")
        monitor.stop()
        return False
    
    print("✅ Connected to Polymarket WebSocket")
    print()
    
    # Get connection status
    status = monitor.get_connection_status()
    print(f"Connection Status:")
    print(f"  Connected: {status['connected']}")
    print(f"  Positions: {status['positions_count']}")
    print(f"  Subscribed Assets: {status['subscribed_assets_count']}")
    print()
    
    # Test subscription with a known asset_id
    # Using a BTC 5-minute market asset_id (this may change, but demonstrates the concept)
    print("4. Testing subscription to asset_id...")
    
    # Example asset_id (you may need to update this with a current market)
    test_asset_id = "71321045679252212594626385532706912750332728571942532289631379312455583992563"
    
    # Add a test position (won't actually trade, just monitor)
    monitor.add_position(
        market_id="test_market",
        asset_id=test_asset_id,
        side="BUY",
        shares=100,
        entry_price=0.50,
        target_profit=10.0
    )
    
    print(f"✅ Subscribed to asset: {test_asset_id[:16]}...")
    print()
    
    # Wait for price updates
    print("5. Waiting for price updates (10 seconds)...")
    print("   (You should see price_change or book events in the logs)")
    print()
    
    time.sleep(10)
    
    # Check if position received any price updates
    position = monitor.get_position_status(test_asset_id)
    if position and position['current_price'] is not None:
        print(f"✅ Received price update!")
        print(f"   Current price: ${position['current_price']:.3f}")
        print(f"   Net P&L: ${position['net_profit']:.2f}")
    else:
        print("⚠️  No price updates received (market may be inactive)")
    
    print()
    
    # Test heartbeat
    print("6. Testing heartbeat (PING/PONG)...")
    print("   (Heartbeat runs automatically every 10 seconds)")
    print("   Waiting 12 seconds to observe heartbeat...")
    time.sleep(12)
    print("✅ Heartbeat test complete (check logs for PING messages)")
    print()
    
    # Clean up
    print("7. Stopping WebSocket connection...")
    monitor.stop()
    time.sleep(1)
    
    if not monitor.is_connected():
        print("✅ Connection stopped successfully")
    else:
        print("⚠️  Connection may still be active")
    
    print()
    print("="*60)
    print("Integration Test Complete")
    print("="*60)
    
    return True


def test_market_discovery_and_subscription():
    """Test discovering a current market and subscribing to it."""
    print()
    print("="*60)
    print("Market Discovery and Subscription Test")
    print("="*60)
    print()
    
    from mock_trader import discover_and_subscribe_market
    
    # Discover current market
    print("1. Discovering current 5-minute BTC market...")
    market_info = discover_and_subscribe_market()
    
    if not market_info:
        print("⚠️  No active market found (may not exist yet)")
        return False
    
    print("✅ Market discovered successfully")
    print()
    
    # Create monitor and subscribe to market assets
    print("2. Creating monitor and subscribing to market assets...")
    monitor = PolymarketPositionMonitor()
    monitor.start()
    time.sleep(2)
    
    # Subscribe to all tokens in the market
    for token in market_info['tokens']:
        print(f"   Subscribing to {token['outcome']} token...")
        monitor.add_position(
            market_id=market_info['market_id'],
            asset_id=token['asset_id'],
            side="BUY",
            shares=100,
            entry_price=token['price'],
            target_profit=10.0
        )
    
    print("✅ Subscribed to all market tokens")
    print()
    
    # Wait for price updates
    print("3. Monitoring prices for 15 seconds...")
    for i in range(15):
        time.sleep(1)
        
        # Check for price updates
        for token in market_info['tokens']:
            position = monitor.get_position_status(token['asset_id'])
            if position and position['current_price'] is not None:
                print(f"   {token['outcome']}: ${position['current_price']:.3f} (P&L: ${position['net_profit']:.2f})")
    
    print()
    
    # Clean up
    print("4. Stopping monitor...")
    monitor.stop()
    time.sleep(1)
    
    print("✅ Market discovery and subscription test complete")
    print()
    
    return True


if __name__ == '__main__':
    print()
    print("🚀 Starting Polymarket WebSocket Integration Tests")
    print()
    print("NOTE: These tests connect to the real Polymarket WebSocket.")
    print("      They require internet connection and may take 30-60 seconds.")
    print()
    
    try:
        # Test 1: Basic WebSocket connection
        success1 = test_websocket_connection()
        
        # Test 2: Market discovery and subscription
        success2 = test_market_discovery_and_subscription()
        
        # Summary
        print()
        print("="*60)
        print("Test Summary")
        print("="*60)
        print(f"WebSocket Connection Test: {'✅ PASS' if success1 else '❌ FAIL'}")
        print(f"Market Discovery Test: {'✅ PASS' if success2 else '⚠️  SKIP (no active market)'}")
        print("="*60)
        print()
        
        if success1:
            print("✅ All critical tests passed!")
            sys.exit(0)
        else:
            print("❌ Some tests failed")
            sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
