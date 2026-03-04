#!/usr/bin/env python3
"""
Test script for get_current_rsi_data() method (Task 3.5)

This script tests the get_current_rsi_data() method to ensure it returns
the correct RSI values and classification.
"""

from mock_trader import BinanceRSIStream, classify_signal
from datetime import datetime, timezone


def test_insufficient_data():
    """Test that get_current_rsi_data returns None when insufficient data."""
    print("Test 1: Insufficient data (< 3 RSI values)")
    
    stream = BinanceRSIStream(symbol="BTCUSDT", period=7, buffer_size=20)
    
    # Clear the RSI values to simulate insufficient data
    stream.rsi_values.clear()
    
    result = stream.get_current_rsi_data()
    
    assert result is None, "Should return None when no RSI values"
    print("  ✓ Returns None with 0 RSI values")
    
    # Add 1 RSI value
    stream.rsi_values.append(50.0)
    result = stream.get_current_rsi_data()
    assert result is None, "Should return None with 1 RSI value"
    print("  ✓ Returns None with 1 RSI value")
    
    # Add 2 RSI values
    stream.rsi_values.append(52.0)
    result = stream.get_current_rsi_data()
    assert result is None, "Should return None with 2 RSI values"
    print("  ✓ Returns None with 2 RSI values")
    print()


def test_sufficient_data_green_signal():
    """Test that get_current_rsi_data returns correct data for green signal."""
    print("Test 2: Sufficient data - Green signal (increasing RSI)")
    
    stream = BinanceRSIStream(symbol="BTCUSDT", period=7, buffer_size=20)
    
    # Clear and add 3 RSI values showing increasing trend (green signal)
    stream.rsi_values.clear()
    stream.rsi_values.append(45.0)  # 2 bars ago
    stream.rsi_values.append(50.0)  # 1 bar ago
    stream.rsi_values.append(55.0)  # current
    
    result = stream.get_current_rsi_data()
    
    assert result is not None, "Should return data with 3 RSI values"
    assert 'rsi_values' in result, "Should have rsi_values key"
    assert 'current_rsi' in result, "Should have current_rsi key"
    assert 'rsi_1_bar_ago' in result, "Should have rsi_1_bar_ago key"
    assert 'rsi_2_bars_ago' in result, "Should have rsi_2_bars_ago key"
    assert 'classification' in result, "Should have classification key"
    assert 'timestamp' in result, "Should have timestamp key"
    
    print("  ✓ Returns dict with all required keys")
    
    # Check values
    assert result['current_rsi'] == 55.0, f"Current RSI should be 55.0, got {result['current_rsi']}"
    assert result['rsi_1_bar_ago'] == 50.0, f"RSI 1 bar ago should be 50.0, got {result['rsi_1_bar_ago']}"
    assert result['rsi_2_bars_ago'] == 45.0, f"RSI 2 bars ago should be 45.0, got {result['rsi_2_bars_ago']}"
    assert result['classification'] == 'green', f"Classification should be 'green', got {result['classification']}"
    
    print("  ✓ RSI values are correct:")
    print(f"    Current RSI: {result['current_rsi']}")
    print(f"    RSI 1 bar ago: {result['rsi_1_bar_ago']}")
    print(f"    RSI 2 bars ago: {result['rsi_2_bars_ago']}")
    print(f"    Classification: {result['classification']}")
    
    # Check timestamp
    assert isinstance(result['timestamp'], datetime), "Timestamp should be datetime object"
    assert result['timestamp'].tzinfo is not None, "Timestamp should be timezone-aware"
    
    print(f"    Timestamp: {result['timestamp'].strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    # Check rsi_values list
    assert len(result['rsi_values']) == 3, f"Should have 3 RSI values, got {len(result['rsi_values'])}"
    assert result['rsi_values'] == [45.0, 50.0, 55.0], f"RSI values list incorrect: {result['rsi_values']}"
    
    print("  ✓ RSI values list is correct")
    print()


def test_sufficient_data_red_signal():
    """Test that get_current_rsi_data returns correct data for red signal."""
    print("Test 3: Sufficient data - Red signal (decreasing RSI)")
    
    stream = BinanceRSIStream(symbol="BTCUSDT", period=7, buffer_size=20)
    
    # Clear and add 3 RSI values showing decreasing trend (red signal)
    stream.rsi_values.clear()
    stream.rsi_values.append(55.0)  # 2 bars ago
    stream.rsi_values.append(50.0)  # 1 bar ago
    stream.rsi_values.append(45.0)  # current
    
    result = stream.get_current_rsi_data()
    
    assert result is not None, "Should return data with 3 RSI values"
    assert result['current_rsi'] == 45.0, f"Current RSI should be 45.0, got {result['current_rsi']}"
    assert result['rsi_1_bar_ago'] == 50.0, f"RSI 1 bar ago should be 50.0, got {result['rsi_1_bar_ago']}"
    assert result['rsi_2_bars_ago'] == 55.0, f"RSI 2 bars ago should be 55.0, got {result['rsi_2_bars_ago']}"
    assert result['classification'] == 'red', f"Classification should be 'red', got {result['classification']}"
    
    print("  ✓ RSI values are correct:")
    print(f"    Current RSI: {result['current_rsi']}")
    print(f"    RSI 1 bar ago: {result['rsi_1_bar_ago']}")
    print(f"    RSI 2 bars ago: {result['rsi_2_bars_ago']}")
    print(f"    Classification: {result['classification']}")
    print()


def test_sufficient_data_neutral_signal():
    """Test that get_current_rsi_data returns correct data for neutral signal."""
    print("Test 4: Sufficient data - Neutral signal (mixed RSI)")
    
    stream = BinanceRSIStream(symbol="BTCUSDT", period=7, buffer_size=20)
    
    # Clear and add 3 RSI values showing mixed trend (neutral signal)
    stream.rsi_values.clear()
    stream.rsi_values.append(50.0)  # 2 bars ago
    stream.rsi_values.append(45.0)  # 1 bar ago (down)
    stream.rsi_values.append(52.0)  # current (up)
    
    result = stream.get_current_rsi_data()
    
    assert result is not None, "Should return data with 3 RSI values"
    assert result['current_rsi'] == 52.0, f"Current RSI should be 52.0, got {result['current_rsi']}"
    assert result['rsi_1_bar_ago'] == 45.0, f"RSI 1 bar ago should be 45.0, got {result['rsi_1_bar_ago']}"
    assert result['rsi_2_bars_ago'] == 50.0, f"RSI 2 bars ago should be 50.0, got {result['rsi_2_bars_ago']}"
    assert result['classification'] == 'neutral', f"Classification should be 'neutral', got {result['classification']}"
    
    print("  ✓ RSI values are correct:")
    print(f"    Current RSI: {result['current_rsi']}")
    print(f"    RSI 1 bar ago: {result['rsi_1_bar_ago']}")
    print(f"    RSI 2 bars ago: {result['rsi_2_bars_ago']}")
    print(f"    Classification: {result['classification']}")
    print()


def test_with_more_rsi_values():
    """Test that get_current_rsi_data works correctly with more than 3 RSI values."""
    print("Test 5: More than 3 RSI values (should use last 3)")
    
    stream = BinanceRSIStream(symbol="BTCUSDT", period=7, buffer_size=20)
    
    # Clear and add 5 RSI values
    stream.rsi_values.clear()
    stream.rsi_values.append(40.0)
    stream.rsi_values.append(42.0)
    stream.rsi_values.append(45.0)  # 2 bars ago (for classification)
    stream.rsi_values.append(50.0)  # 1 bar ago
    stream.rsi_values.append(55.0)  # current
    
    result = stream.get_current_rsi_data()
    
    assert result is not None, "Should return data"
    assert result['current_rsi'] == 55.0, f"Current RSI should be 55.0, got {result['current_rsi']}"
    assert result['rsi_1_bar_ago'] == 50.0, f"RSI 1 bar ago should be 50.0, got {result['rsi_1_bar_ago']}"
    assert result['rsi_2_bars_ago'] == 45.0, f"RSI 2 bars ago should be 45.0, got {result['rsi_2_bars_ago']}"
    assert result['classification'] == 'green', f"Classification should be 'green', got {result['classification']}"
    
    print("  ✓ Uses last 3 RSI values correctly:")
    print(f"    Current RSI: {result['current_rsi']}")
    print(f"    RSI 1 bar ago: {result['rsi_1_bar_ago']}")
    print(f"    RSI 2 bars ago: {result['rsi_2_bars_ago']}")
    print(f"    Classification: {result['classification']}")
    
    # Check that rsi_values list contains all values
    assert len(result['rsi_values']) == 5, f"Should have 5 RSI values, got {len(result['rsi_values'])}"
    assert result['rsi_values'] == [40.0, 42.0, 45.0, 50.0, 55.0], f"RSI values list incorrect: {result['rsi_values']}"
    
    print("  ✓ RSI values list contains all values")
    print()


def main():
    """Run all tests."""
    print("="*60)
    print("get_current_rsi_data() Method Tests (Task 3.5)")
    print("="*60)
    print()
    
    try:
        test_insufficient_data()
        test_sufficient_data_green_signal()
        test_sufficient_data_red_signal()
        test_sufficient_data_neutral_signal()
        test_with_more_rsi_values()
        
        print("="*60)
        print("✓ All tests passed!")
        print("="*60)
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
