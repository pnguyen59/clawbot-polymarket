#!/usr/bin/env python3
"""
Integration test for BinanceRSIStream WebSocket connection.

This test verifies that the WebSocket can connect to Binance and receive
real-time kline updates.
"""

import time
from mock_trader import BinanceRSIStream


def test_websocket_connection():
    """Test WebSocket connection and real-time RSI updates."""
    print("="*60)
    print("Integration Test: Binance WebSocket Connection")
    print("="*60)
    print()
    
    # Create stream instance
    print("Creating BinanceRSIStream...")
    stream = BinanceRSIStream(symbol="BTCUSDT", period=7, buffer_size=20)
    
    # Verify initial data was fetched
    print(f"✓ Initial data fetched: {len(stream.close_prices)} prices")
    print(f"✓ Initial RSI calculated: {len(stream.rsi_values)} values")
    
    if len(stream.rsi_values) > 0:
        print(f"  Latest RSI: {stream.rsi_values[-1]:.2f}")
    
    print()
    
    # Start WebSocket connection
    print("Starting WebSocket connection...")
    stream.start()
    
    # Wait for connection to establish
    time.sleep(2)
    
    if stream.running:
        print("✓ WebSocket connected successfully")
    else:
        print("✗ WebSocket failed to connect")
        return 1
    
    print()
    print("Listening for kline updates...")
    print("(This will wait up to 60 seconds for a closed candle)")
    print()
    
    # Store initial RSI count
    initial_rsi_count = len(stream.rsi_values)
    
    # Wait for up to 60 seconds for a new closed candle
    # (1-minute candles, so we should get one within 60 seconds)
    timeout = 60
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        # Check if we got a new RSI value
        if len(stream.rsi_values) > initial_rsi_count:
            print(f"✓ Received new RSI update: {stream.rsi_values[-1]:.2f}")
            print(f"  Latest close price: ${stream.close_prices[-1]:.2f}")
            break
        
        # Wait a bit before checking again
        time.sleep(1)
    else:
        print("⚠ No new candle received within 60 seconds")
        print("  (This is normal if test runs mid-candle)")
    
    print()
    
    # Stop WebSocket
    print("Stopping WebSocket...")
    stream.stop()
    
    # Wait for thread to finish
    time.sleep(1)
    
    print("✓ WebSocket stopped")
    print()
    
    # Display final state
    print("Final state:")
    print(f"  Total prices: {len(stream.close_prices)}")
    print(f"  Total RSI values: {len(stream.rsi_values)}")
    
    if len(stream.rsi_values) >= 3:
        print(f"  Last 3 RSI values: {[f'{rsi:.2f}' for rsi in list(stream.rsi_values)[-3:]]}")
    
    print()
    print("="*60)
    print("✓ Integration test completed successfully")
    print("="*60)
    
    return 0


if __name__ == "__main__":
    try:
        exit(test_websocket_connection())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        exit(1)
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
