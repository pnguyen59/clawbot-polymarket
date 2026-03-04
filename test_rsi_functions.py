#!/usr/bin/env python3
"""
Unit tests for RSI functions in mock_trader.py

Tests cover:
- calculate_rsi() function
- classify_signal() function
- check_rsi_entry_signal() function
"""

import sys
import unittest
from mock_trader import calculate_rsi, classify_signal, check_rsi_entry_signal


class TestCalculateRSI(unittest.TestCase):
    """Test cases for calculate_rsi() function."""
    
    def test_insufficient_data(self):
        """Test RSI calculation with insufficient data."""
        prices = [100, 102, 101]  # Only 3 prices, need at least 8 for period=7
        result = calculate_rsi(prices, period=7)
        self.assertIsNone(result)
    
    def test_empty_prices(self):
        """Test RSI calculation with empty prices."""
        with self.assertRaises(ValueError):
            calculate_rsi([], period=7)
    
    def test_invalid_period(self):
        """Test RSI calculation with invalid period."""
        prices = [100, 102, 101, 103, 105, 104, 106, 108]
        with self.assertRaises(ValueError):
            calculate_rsi(prices, period=0)
    
    def test_all_gains_no_losses(self):
        """Test RSI when prices only increase (should return 100)."""
        prices = [100, 101, 102, 103, 104, 105, 106, 107, 108]
        rsi = calculate_rsi(prices, period=7)
        self.assertEqual(rsi, 100.0)
    
    def test_all_losses_no_gains(self):
        """Test RSI when prices only decrease (should return 0)."""
        prices = [108, 107, 106, 105, 104, 103, 102, 101, 100]
        rsi = calculate_rsi(prices, period=7)
        self.assertEqual(rsi, 0.0)
    
    def test_no_change(self):
        """Test RSI when prices don't change (should return 50)."""
        prices = [100] * 10
        rsi = calculate_rsi(prices, period=7)
        self.assertEqual(rsi, 50.0)


class TestClassifySignal(unittest.TestCase):
    """Test cases for classify_signal() function.
    
    Tests signal classification based on RSI momentum:
    - Green: RSI increasing for 2 consecutive periods (current > prev > prev2)
    - Red: RSI decreasing for 2 consecutive periods (current < prev < prev2)
    - Neutral: Mixed signals (neither green nor red)
    """
    
    def test_green_signal_increasing_rsi(self):
        """Test green signal when RSI is increasing for 2 periods."""
        # Requirement 2.1: current_rsi > previous_rsi AND previous_rsi > rsi_before_previous
        result = classify_signal(55, 50, 45)
        self.assertEqual(result, "green")
    
    def test_red_signal_decreasing_rsi(self):
        """Test red signal when RSI is decreasing for 2 periods."""
        # Requirement 2.2: current_rsi < previous_rsi AND previous_rsi < rsi_before_previous
        result = classify_signal(45, 50, 55)
        self.assertEqual(result, "red")
    
    def test_neutral_signal_mixed(self):
        """Test neutral signal with mixed RSI movements (down then up)."""
        # Requirement 2.3: Neither green nor red condition is met
        result = classify_signal(50, 45, 50)
        self.assertEqual(result, "neutral")
    
    def test_neutral_signal_up_then_down(self):
        """Test neutral signal when RSI goes up then down."""
        result = classify_signal(45, 50, 45)
        self.assertEqual(result, "neutral")
    
    def test_neutral_signal_equal_values(self):
        """Test neutral signal when RSI values are equal."""
        # All equal values should be neutral
        result = classify_signal(50, 50, 50)
        self.assertEqual(result, "neutral")
    
    def test_neutral_signal_first_equal(self):
        """Test neutral when current equals previous (no momentum)."""
        result = classify_signal(50, 50, 45)
        self.assertEqual(result, "neutral")
    
    def test_neutral_signal_second_equal(self):
        """Test neutral when previous equals prev2 (no prior momentum)."""
        result = classify_signal(55, 50, 50)
        self.assertEqual(result, "neutral")
    
    def test_green_signal_extreme_values(self):
        """Test green signal with extreme RSI values (near boundaries)."""
        # RSI near 100 (overbought territory)
        result = classify_signal(95, 90, 85)
        self.assertEqual(result, "green")
    
    def test_red_signal_extreme_values(self):
        """Test red signal with extreme RSI values (near boundaries)."""
        # RSI near 0 (oversold territory)
        result = classify_signal(15, 20, 25)
        self.assertEqual(result, "red")
    
    def test_green_signal_small_increments(self):
        """Test green signal with small RSI increments."""
        result = classify_signal(50.3, 50.2, 50.1)
        self.assertEqual(result, "green")
    
    def test_red_signal_small_decrements(self):
        """Test red signal with small RSI decrements."""
        result = classify_signal(50.1, 50.2, 50.3)
        self.assertEqual(result, "red")


class TestCheckRSIEntrySignal(unittest.TestCase):
    """Test cases for check_rsi_entry_signal() function."""
    
    def test_buy_signal_three_green(self):
        """Test BUY signal with 3 consecutive green signals."""
        memory = [
            {'classification': 'green'},
            {'classification': 'green'}
        ]
        rsi_values = [45.0, 50.0, 55.0]  # Increasing RSI
        result = check_rsi_entry_signal(memory, rsi_values)
        self.assertEqual(result, "BUY")
    
    def test_sell_signal_three_red(self):
        """Test SELL signal with 3 consecutive red signals."""
        memory = [
            {'classification': 'red'},
            {'classification': 'red'}
        ]
        rsi_values = [55.0, 50.0, 45.0]  # Decreasing RSI
        result = check_rsi_entry_signal(memory, rsi_values)
        self.assertEqual(result, "SELL")
    
    def test_no_signal_mixed_memory(self):
        """Test no signal when memory has mixed signals."""
        memory = [
            {'classification': 'green'},
            {'classification': 'red'}
        ]
        rsi_values = [45.0, 50.0, 55.0]
        result = check_rsi_entry_signal(memory, rsi_values)
        self.assertIsNone(result)
    
    def test_no_signal_current_neutral(self):
        """Test no signal when current signal is neutral."""
        memory = [
            {'classification': 'green'},
            {'classification': 'green'}
        ]
        rsi_values = [50.0, 45.0, 50.0]  # Neutral current signal
        result = check_rsi_entry_signal(memory, rsi_values)
        self.assertIsNone(result)
    
    def test_insufficient_memory(self):
        """Test no signal with insufficient memory."""
        memory = [
            {'classification': 'green'}
        ]
        rsi_values = [45.0, 50.0, 55.0]
        result = check_rsi_entry_signal(memory, rsi_values)
        self.assertIsNone(result)
    
    def test_insufficient_rsi_values(self):
        """Test no signal with insufficient RSI values."""
        memory = [
            {'classification': 'green'},
            {'classification': 'green'}
        ]
        rsi_values = [50.0, 55.0]  # Only 2 values, need 3
        result = check_rsi_entry_signal(memory, rsi_values)
        self.assertIsNone(result)
    
    def test_none_inputs(self):
        """Test no signal with None inputs."""
        result = check_rsi_entry_signal(None, None)
        self.assertIsNone(result)
    
    def test_invalid_signal_structure(self):
        """Test no signal with invalid signal structure."""
        memory = [
            {'wrong_key': 'green'},
            {'classification': 'green'}
        ]
        rsi_values = [45.0, 50.0, 55.0]
        result = check_rsi_entry_signal(memory, rsi_values)
        self.assertIsNone(result)
    
    def test_buy_signal_with_more_memory(self):
        """Test BUY signal with more than 2 signals in memory."""
        memory = [
            {'classification': 'red'},
            {'classification': 'neutral'},
            {'classification': 'green'},
            {'classification': 'green'}
        ]
        rsi_values = [45.0, 50.0, 55.0]  # Increasing RSI
        result = check_rsi_entry_signal(memory, rsi_values)
        self.assertEqual(result, "BUY")
    
    def test_sell_signal_with_more_memory(self):
        """Test SELL signal with more than 2 signals in memory."""
        memory = [
            {'classification': 'green'},
            {'classification': 'neutral'},
            {'classification': 'red'},
            {'classification': 'red'}
        ]
        rsi_values = [55.0, 50.0, 45.0]  # Decreasing RSI
        result = check_rsi_entry_signal(memory, rsi_values)
        self.assertEqual(result, "SELL")


if __name__ == '__main__':
    unittest.main()
