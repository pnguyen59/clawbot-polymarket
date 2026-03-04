#!/usr/bin/env python3
"""
Test for BinanceRSIStream._on_message() method

Tests the WebSocket message processing logic for kline updates.
"""

import json
from collections import deque
from mock_trader import BinanceRSIStream, calculate_rsi


def test_on_message_closed_candle():
    """Test that _on_message processes closed candles correctly."""
    print("\n=== Test: Process Closed Candle ===")
    
    # Create stream instance (will fetch initial data)
    stream = BinanceRSIStream(symbol="BTCUSDT", period=7, buffer_size=20)
    
    # Store initial state
    initial_price_count = len(stream.close_prices)
    initial_rsi_count = len(stream.rsi_values)
    
    print(f"Initial state: {initial_price_count} prices, {initial_rsi_count} RSI values")
    
    # Create a closed candle message
    message = json.dumps({
        "e": "kline",
        "E": 1638747660000,
        "s": "BTCUSDT",
        "k": {
            "t": 1638747600000,
            "T": 1638747659999,
            "s": "BTCUSDT",
            "i": "1m",
            "o": "48000.00",
            "c": "48100.00",
            "h": "48200.00",
            "l": "47900.00",
            "v": "10.5",
            "n": 100,
            "x": True  # Closed candle
        }
    })
    
    # Process message
    stream._on_message(None, message)
    
    # Verify close price was added (deque maintains maxlen, so count stays same if at capacity)
    expected_price_count = min(initial_price_count + 1, stream.buffer_size)
    assert len(stream.close_prices) == expected_price_count, \
        f"Expected {expected_price_count} prices, got {len(stream.close_prices)}"
    
    # Verify last price is correct
    assert stream.close_prices[-1] == 48100.00, \
        f"Expected close price 48100.00, got {stream.close_prices[-1]}"
    
    # Verify RSI was calculated (if enough data)
    if initial_price_count >= stream.period:
        # RSI count should increase by 1 (or stay at maxlen if at capacity)
        expected_rsi_count = min(initial_rsi_count + 1, stream.buffer_size)
        assert len(stream.rsi_values) == expected_rsi_count, \
            f"Expected {expected_rsi_count} RSI values, got {len(stream.rsi_values)}"
        print(f"✓ New RSI calculated: {stream.rsi_values[-1]:.2f}")
    
    print("✓ Closed candle processed correctly")


def test_on_message_open_candle():
    """Test that _on_message ignores open candles."""
    print("\n=== Test: Ignore Open Candle ===")
    
    # Create stream instance
    stream = BinanceRSIStream(symbol="BTCUSDT", period=7, buffer_size=20)
    
    # Store initial state
    initial_price_count = len(stream.close_prices)
    initial_rsi_count = len(stream.rsi_values)
    
    print(f"Initial state: {initial_price_count} prices, {initial_rsi_count} RSI values")
    
    # Create an open candle message (x = False)
    message = json.dumps({
        "e": "kline",
        "E": 1638747660000,
        "s": "BTCUSDT",
        "k": {
            "t": 1638747600000,
            "T": 1638747659999,
            "s": "BTCUSDT",
            "i": "1m",
            "o": "48000.00",
            "c": "48100.00",
            "h": "48200.00",
            "l": "47900.00",
            "v": "10.5",
            "n": 100,
            "x": False  # Open candle (not closed)
        }
    })
    
    # Process message
    stream._on_message(None, message)
    
    # Verify nothing was added
    assert len(stream.close_prices) == initial_price_count, \
        f"Expected {initial_price_count} prices (no change), got {len(stream.close_prices)}"
    assert len(stream.rsi_values) == initial_rsi_count, \
        f"Expected {initial_rsi_count} RSI values (no change), got {len(stream.rsi_values)}"
    
    print("✓ Open candle ignored correctly")


def test_on_message_non_kline_event():
    """Test that _on_message ignores non-kline events."""
    print("\n=== Test: Ignore Non-Kline Event ===")
    
    # Create stream instance
    stream = BinanceRSIStream(symbol="BTCUSDT", period=7, buffer_size=20)
    
    # Store initial state
    initial_price_count = len(stream.close_prices)
    
    # Create a non-kline message
    message = json.dumps({
        "e": "trade",  # Trade event, not kline
        "E": 1638747660000,
        "s": "BTCUSDT",
        "p": "48100.00",
        "q": "1.5"
    })
    
    # Process message
    stream._on_message(None, message)
    
    # Verify nothing was added
    assert len(stream.close_prices) == initial_price_count, \
        f"Expected {initial_price_count} prices (no change), got {len(stream.close_prices)}"
    
    print("✓ Non-kline event ignored correctly")


def test_on_message_invalid_json():
    """Test that _on_message handles invalid JSON gracefully."""
    print("\n=== Test: Handle Invalid JSON ===")
    
    # Create stream instance
    stream = BinanceRSIStream(symbol="BTCUSDT", period=7, buffer_size=20)
    
    # Store initial state
    initial_price_count = len(stream.close_prices)
    
    # Create invalid JSON
    message = "{ invalid json }"
    
    # Process message (should not crash)
    stream._on_message(None, message)
    
    # Verify nothing was added
    assert len(stream.close_prices) == initial_price_count, \
        f"Expected {initial_price_count} prices (no change), got {len(stream.close_prices)}"
    
    print("✓ Invalid JSON handled gracefully")


def test_on_message_missing_fields():
    """Test that _on_message handles missing fields gracefully."""
    print("\n=== Test: Handle Missing Fields ===")
    
    # Create stream instance
    stream = BinanceRSIStream(symbol="BTCUSDT", period=7, buffer_size=20)
    
    # Store initial state
    initial_price_count = len(stream.close_prices)
    
    # Create message with missing 'k' field
    message = json.dumps({
        "e": "kline",
        "E": 1638747660000,
        "s": "BTCUSDT"
        # Missing 'k' field
    })
    
    # Process message (should not crash)
    stream._on_message(None, message)
    
    # Verify nothing was added
    assert len(stream.close_prices) == initial_price_count, \
        f"Expected {initial_price_count} prices (no change), got {len(stream.close_prices)}"
    
    print("✓ Missing fields handled gracefully")


def test_on_message_rsi_calculation():
    """Test that RSI is calculated correctly after adding new price."""
    print("\n=== Test: RSI Calculation After New Price ===")
    
    # Create stream instance
    stream = BinanceRSIStream(symbol="BTCUSDT", period=7, buffer_size=20)
    
    # Ensure we have enough data for RSI
    if len(stream.close_prices) < stream.period + 1:
        print("⚠ Skipping test: insufficient initial data")
        return
    
    # Store initial RSI
    initial_rsi = stream.rsi_values[-1] if len(stream.rsi_values) > 0 else None
    print(f"Initial RSI: {initial_rsi:.2f}" if initial_rsi else "Initial RSI: None")
    
    # Get current last price
    last_price = stream.close_prices[-1]
    
    # Create a closed candle with a higher price (should increase RSI)
    new_price = last_price * 1.01  # 1% higher
    
    message = json.dumps({
        "e": "kline",
        "E": 1638747660000,
        "s": "BTCUSDT",
        "k": {
            "t": 1638747600000,
            "T": 1638747659999,
            "s": "BTCUSDT",
            "i": "1m",
            "o": str(last_price),
            "c": str(new_price),
            "h": str(new_price),
            "l": str(last_price),
            "v": "10.5",
            "n": 100,
            "x": True
        }
    })
    
    # Process message
    stream._on_message(None, message)
    
    # Verify RSI was calculated
    assert len(stream.rsi_values) > 0, "Expected RSI values to be calculated"
    
    new_rsi = stream.rsi_values[-1]
    print(f"New RSI: {new_rsi:.2f}")
    
    # Verify RSI is in valid range
    assert 0 <= new_rsi <= 100, f"RSI should be between 0 and 100, got {new_rsi}"
    
    print("✓ RSI calculated correctly after new price")


def main():
    """Run all tests."""
    print("="*60)
    print("Testing BinanceRSIStream._on_message()")
    print("="*60)
    
    try:
        test_on_message_closed_candle()
        test_on_message_open_candle()
        test_on_message_non_kline_event()
        test_on_message_invalid_json()
        test_on_message_missing_fields()
        test_on_message_rsi_calculation()
        
        print("\n" + "="*60)
        print("✓ All tests passed!")
        print("="*60)
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
