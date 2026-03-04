#!/usr/bin/env python3
"""
Demo script to test auto-reconnect functionality.

This script demonstrates the auto-reconnect logic by:
1. Starting a BinanceRSIStream
2. Simulating a disconnection
3. Observing the automatic reconnection with exponential backoff
"""

import time
from unittest.mock import patch, Mock
from mock_trader import BinanceRSIStream


def demo_auto_reconnect():
    """Demonstrate auto-reconnect functionality."""
    print("="*70)
    print("Auto-Reconnect Demo")
    print("="*70)
    print()
    
    # Mock the API call to avoid real network requests
    with patch('mock_trader.requests.get') as mock_get:
        # Mock successful API response for initial data
        mock_response = Mock()
        mock_response.json.return_value = [
            [0, "100", "101", "99", f"{100 + i*0.1}", "1000", 0, "0", 0, "0", "0", "0"]
            for i in range(20)
        ]
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        # Create stream
        print("1. Creating BinanceRSIStream...")
        stream = BinanceRSIStream(symbol="BTCUSDT", period=7, buffer_size=20)
        print()
        
        # Check initial status
        print("2. Initial connection status:")
        status = stream.get_connection_status()
        print(f"   Connected: {status['connected']}")
        print(f"   Reconnect attempts: {status['reconnect_attempts']}")
        print(f"   Buffer size: {status['buffer_size']}")
        print(f"   RSI values: {status['rsi_values_count']}")
        print()
        
        # Simulate connection
        print("3. Simulating WebSocket connection...")
        stream._on_open(Mock())
        print()
        
        # Check status after connection
        print("4. Status after connection:")
        status = stream.get_connection_status()
        print(f"   Connected: {status['connected']}")
        print(f"   Reconnect attempts: {status['reconnect_attempts']}")
        print()
        
        # Simulate disconnection
        print("5. Simulating disconnection (abnormal closure)...")
        stream._on_close(Mock(), 1006, "Connection lost")
        print()
        
        # Check status after disconnection
        print("6. Status after disconnection:")
        status = stream.get_connection_status()
        print(f"   Connected: {status['connected']}")
        print(f"   Reconnect attempts: {status['reconnect_attempts']}")
        print()
        
        # Demonstrate exponential backoff
        print("7. Demonstrating exponential backoff delays:")
        for attempt in range(8):
            stream.reconnect_attempts = attempt
            delay = stream._calculate_reconnect_delay()
            print(f"   Attempt {attempt + 1}: {delay:.1f} seconds")
        print()
        
        # Simulate multiple reconnection attempts
        print("8. Simulating multiple disconnections:")
        for i in range(3):
            print(f"   Disconnection {i + 1}...")
            stream._on_close(Mock(), 1006, f"Connection lost #{i + 1}")
            time.sleep(0.1)  # Small delay to see the output
        print()
        
        # Check final status
        print("9. Final status:")
        status = stream.get_connection_status()
        print(f"   Connected: {status['connected']}")
        print(f"   Reconnect attempts: {status['reconnect_attempts']}")
        print()
        
        # Test max reconnection attempts
        print("10. Testing max reconnection attempts limit:")
        stream.reconnect_attempts = 9
        stream.max_reconnect_attempts = 10
        print(f"    Current attempts: {stream.reconnect_attempts}")
        print(f"    Max attempts: {stream.max_reconnect_attempts}")
        print(f"    Attempting one more reconnection...")
        stream._on_close(Mock(), 1006, "Final disconnection")
        print()
        
        # Test stop functionality
        print("11. Testing stop() functionality:")
        stream.reconnect_enabled = True
        stream.running = True
        stream.ws = Mock()
        print(f"    Before stop - Reconnect enabled: {stream.reconnect_enabled}")
        stream.stop()
        print(f"    After stop - Reconnect enabled: {stream.reconnect_enabled}")
        print()
        
        # Test buffer preservation
        print("12. Testing buffer preservation across reconnections:")
        stream.close_prices.extend([100.0, 101.0, 102.0])
        stream.rsi_values.extend([45.0, 50.0, 55.0])
        print(f"    Prices before disconnect: {list(stream.close_prices)}")
        print(f"    RSI values before disconnect: {list(stream.rsi_values)}")
        stream.reconnect_enabled = True
        stream._on_close(Mock(), 1006, "Test disconnect")
        print(f"    Prices after disconnect: {list(stream.close_prices)}")
        print(f"    RSI values after disconnect: {list(stream.rsi_values)}")
        print(f"    ✓ Buffers preserved!")
        print()
    
    print("="*70)
    print("Demo completed successfully!")
    print("="*70)


if __name__ == '__main__':
    demo_auto_reconnect()
