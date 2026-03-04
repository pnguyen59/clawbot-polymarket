#!/usr/bin/env python3
"""
Test script for BinanceRSIStream class (Task 3.1)

This script tests the basic structure and WebSocket connection
of the BinanceRSIStream class.
"""

from mock_trader import BinanceRSIStream
import time


def test_class_instantiation():
    """Test that the class can be instantiated with correct parameters."""
    print("Test 1: Class instantiation")
    stream = BinanceRSIStream(symbol="BTCUSDT", period=7, buffer_size=20)
    
    assert stream.symbol == "btcusdt", "Symbol should be lowercase"
    assert stream.period == 7, "Period should be 7"
    assert stream.buffer_size == 20, "Buffer size should be 20"
    assert stream.running == False, "Should not be running initially"
    assert stream.ws is None, "WebSocket should be None initially"
    assert stream.thread is None, "Thread should be None initially"
    # Constructor fetches initial data, so close_prices should have data
    assert len(stream.close_prices) > 0, "Close prices should have initial data"
    assert len(stream.rsi_values) > 0, "RSI values should have initial data"
    
    print("  ✓ Class instantiation successful")
    print(f"    Symbol: {stream.symbol}")
    print(f"    Period: {stream.period}")
    print(f"    Buffer size: {stream.buffer_size}")
    print(f"    Initial close prices: {len(stream.close_prices)}")
    print(f"    Initial RSI values: {len(stream.rsi_values)}")
    print()


def test_websocket_connection():
    """Test that WebSocket connection can be started and stopped."""
    print("Test 2: WebSocket connection")
    stream = BinanceRSIStream(symbol="BTCUSDT", period=7, buffer_size=20)
    
    print("  Starting WebSocket...")
    stream.start()
    
    # Wait for connection
    time.sleep(3)
    
    assert stream.running == True, "WebSocket should be running"
    assert stream.ws is not None, "WebSocket should be initialized"
    assert stream.thread is not None, "Thread should be initialized"
    assert stream.thread.is_alive(), "Thread should be alive"
    
    print("  ✓ WebSocket connected successfully")
    print(f"    Running: {stream.running}")
    print(f"    Thread alive: {stream.thread.is_alive()}")
    
    print("  Stopping WebSocket...")
    stream.stop()
    
    # Wait for cleanup
    time.sleep(1)
    
    assert stream.running == False, "WebSocket should not be running after stop"
    
    print("  ✓ WebSocket stopped successfully")
    print(f"    Running: {stream.running}")
    print()


def test_method_stubs():
    """Test that all required methods exist (even if not implemented yet)."""
    print("Test 3: Method stubs")
    stream = BinanceRSIStream(symbol="BTCUSDT", period=7, buffer_size=20)
    
    # Check that all methods exist
    assert hasattr(stream, '_fetch_initial_data'), "Should have _fetch_initial_data method"
    assert hasattr(stream, '_recalculate_rsi'), "Should have _recalculate_rsi method"
    assert hasattr(stream, '_on_message'), "Should have _on_message method"
    assert hasattr(stream, '_on_error'), "Should have _on_error method"
    assert hasattr(stream, '_on_close'), "Should have _on_close method"
    assert hasattr(stream, '_on_open'), "Should have _on_open method"
    assert hasattr(stream, 'start'), "Should have start method"
    assert hasattr(stream, 'stop'), "Should have stop method"
    assert hasattr(stream, 'get_current_rsi_data'), "Should have get_current_rsi_data method"
    
    print("  ✓ All required methods exist")
    print()


def main():
    """Run all tests."""
    print("="*60)
    print("BinanceRSIStream Class Tests (Task 3.1)")
    print("="*60)
    print()
    
    try:
        test_class_instantiation()
        test_websocket_connection()
        test_method_stubs()
        
        print("="*60)
        print("✓ All tests passed!")
        print("="*60)
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
