#!/usr/bin/env python3
"""
Unit tests for RSI calculation edge cases

Tests comprehensive edge cases for the calculate_rsi() function:
- Insufficient data handling
- Division by zero cases
- Different price patterns (all gains, all losses, mixed)
- Minimum required data
- Extended data
"""

import unittest
import numpy as np
from mock_trader import calculate_rsi


class TestRSIEdgeCases(unittest.TestCase):
    """Comprehensive edge case tests for RSI calculation."""
    
    # =========================================================================
    # Insufficient Data Tests
    # =========================================================================
    
    def test_empty_prices(self):
        """Test RSI with empty price list."""
        with self.assertRaises(ValueError) as context:
            calculate_rsi([], period=7)
        self.assertIn("cannot be empty", str(context.exception))
    
    def test_none_prices(self):
        """Test RSI with None as prices."""
        with self.assertRaises(ValueError) as context:
            calculate_rsi(None, period=7)
        self.assertIn("cannot be empty", str(context.exception))
    
    def test_insufficient_data_one_price(self):
        """Test RSI with only 1 price (need at least period+1)."""
        prices = [100.0]
        result = calculate_rsi(prices, period=7)
        self.assertIsNone(result, "Should return None with insufficient data")
    
    def test_insufficient_data_exact_period(self):
        """Test RSI with exactly period prices (need period+1)."""
        prices = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0]  # 7 prices
        result = calculate_rsi(prices, period=7)
        self.assertIsNone(result, "Should return None when len(prices) == period")
    
    def test_minimum_required_data(self):
        """Test RSI with minimum required data (period+1 prices)."""
        prices = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0]  # 8 prices
        result = calculate_rsi(prices, period=7)
        self.assertIsNotNone(result, "Should calculate RSI with period+1 prices")
        self.assertGreaterEqual(result, 0.0)
        self.assertLessEqual(result, 100.0)
    
    # =========================================================================
    # Invalid Period Tests
    # =========================================================================
    
    def test_zero_period(self):
        """Test RSI with period=0."""
        prices = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0]
        with self.assertRaises(ValueError) as context:
            calculate_rsi(prices, period=0)
        self.assertIn("must be positive", str(context.exception))
    
    def test_negative_period(self):
        """Test RSI with negative period."""
        prices = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0]
        with self.assertRaises(ValueError) as context:
            calculate_rsi(prices, period=-5)
        self.assertIn("must be positive", str(context.exception))
    
    # =========================================================================
    # Division by Zero Tests
    # =========================================================================
    
    def test_all_gains_no_losses(self):
        """Test RSI when prices only increase (avg_loss=0, should return 100)."""
        prices = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0]
        rsi = calculate_rsi(prices, period=7)
        self.assertEqual(rsi, 100.0, "RSI should be 100 when only gains")
    
    def test_all_losses_no_gains(self):
        """Test RSI when prices only decrease (avg_gain=0, should return 0)."""
        prices = [108.0, 107.0, 106.0, 105.0, 104.0, 103.0, 102.0, 101.0, 100.0]
        rsi = calculate_rsi(prices, period=7)
        self.assertEqual(rsi, 0.0, "RSI should be 0 when only losses")
    
    def test_no_change_flat_prices(self):
        """Test RSI when prices don't change (no gains, no losses, should return 50)."""
        prices = [100.0] * 10
        rsi = calculate_rsi(prices, period=7)
        self.assertEqual(rsi, 50.0, "RSI should be 50 when no price movement")
    
    def test_single_gain_then_flat(self):
        """Test RSI with one gain followed by flat prices."""
        prices = [100.0, 101.0, 101.0, 101.0, 101.0, 101.0, 101.0, 101.0, 101.0]
        rsi = calculate_rsi(prices, period=7)
        self.assertIsNotNone(rsi)
        self.assertGreater(rsi, 50.0, "RSI should be > 50 with net gain")
    
    def test_single_loss_then_flat(self):
        """Test RSI with one loss followed by flat prices."""
        prices = [100.0, 99.0, 99.0, 99.0, 99.0, 99.0, 99.0, 99.0, 99.0]
        rsi = calculate_rsi(prices, period=7)
        self.assertIsNotNone(rsi)
        self.assertLess(rsi, 50.0, "RSI should be < 50 with net loss")
    
    # =========================================================================
    # Different Price Pattern Tests
    # =========================================================================
    
    def test_mixed_gains_and_losses(self):
        """Test RSI with mixed gains and losses."""
        prices = [100.0, 102.0, 101.0, 103.0, 102.0, 104.0, 103.0, 105.0, 104.0]
        rsi = calculate_rsi(prices, period=7)
        self.assertIsNotNone(rsi)
        self.assertGreaterEqual(rsi, 0.0)
        self.assertLessEqual(rsi, 100.0)
        # Net movement is up, so RSI should be > 50
        self.assertGreater(rsi, 50.0)
    
    def test_alternating_up_down(self):
        """Test RSI with alternating up/down movements."""
        prices = [100.0, 101.0, 100.0, 101.0, 100.0, 101.0, 100.0, 101.0, 100.0]
        rsi = calculate_rsi(prices, period=7)
        self.assertIsNotNone(rsi)
        # Equal gains and losses should result in RSI near 50
        self.assertGreater(rsi, 40.0)
        self.assertLess(rsi, 60.0)
    
    def test_strong_uptrend(self):
        """Test RSI with strong uptrend."""
        prices = [100.0, 105.0, 110.0, 115.0, 120.0, 125.0, 130.0, 135.0, 140.0]
        rsi = calculate_rsi(prices, period=7)
        self.assertEqual(rsi, 100.0, "Strong uptrend should give RSI=100")
    
    def test_strong_downtrend(self):
        """Test RSI with strong downtrend."""
        prices = [140.0, 135.0, 130.0, 125.0, 120.0, 115.0, 110.0, 105.0, 100.0]
        rsi = calculate_rsi(prices, period=7)
        self.assertEqual(rsi, 0.0, "Strong downtrend should give RSI=0")
    
    def test_volatile_prices(self):
        """Test RSI with volatile price movements."""
        prices = [100.0, 110.0, 95.0, 115.0, 90.0, 120.0, 85.0, 125.0, 130.0]
        rsi = calculate_rsi(prices, period=7)
        self.assertIsNotNone(rsi)
        self.assertGreaterEqual(rsi, 0.0)
        self.assertLessEqual(rsi, 100.0)
    
    def test_small_movements(self):
        """Test RSI with very small price movements."""
        prices = [100.0, 100.01, 100.02, 100.01, 100.03, 100.02, 100.04, 100.03, 100.05]
        rsi = calculate_rsi(prices, period=7)
        self.assertIsNotNone(rsi)
        self.assertGreater(rsi, 50.0, "Net upward movement should give RSI > 50")
    
    def test_large_movements(self):
        """Test RSI with large price movements."""
        prices = [100.0, 200.0, 150.0, 250.0, 175.0, 275.0, 200.0, 300.0, 225.0]
        rsi = calculate_rsi(prices, period=7)
        self.assertIsNotNone(rsi)
        self.assertGreaterEqual(rsi, 0.0)
        self.assertLessEqual(rsi, 100.0)
    
    # =========================================================================
    # Extended Data Tests
    # =========================================================================
    
    def test_extended_data_20_prices(self):
        """Test RSI with extended data (20 prices)."""
        prices = [100.0 + i * 0.5 for i in range(20)]  # Gradual uptrend
        rsi = calculate_rsi(prices, period=7)
        self.assertIsNotNone(rsi)
        self.assertGreater(rsi, 50.0, "Uptrend should give RSI > 50")
    
    def test_extended_data_50_prices(self):
        """Test RSI with extended data (50 prices)."""
        prices = [100.0 + i * 0.2 for i in range(50)]  # Gradual uptrend
        rsi = calculate_rsi(prices, period=7)
        self.assertIsNotNone(rsi)
        self.assertGreater(rsi, 50.0, "Uptrend should give RSI > 50")
    
    def test_extended_data_100_prices(self):
        """Test RSI with extended data (100 prices)."""
        # Create a sine wave pattern
        prices = [100.0 + 10.0 * np.sin(i * 0.1) for i in range(100)]
        rsi = calculate_rsi(prices, period=7)
        self.assertIsNotNone(rsi)
        self.assertGreaterEqual(rsi, 0.0)
        self.assertLessEqual(rsi, 100.0)
    
    # =========================================================================
    # Different Period Tests
    # =========================================================================
    
    def test_period_3(self):
        """Test RSI with period=3."""
        prices = [100.0, 101.0, 102.0, 103.0, 104.0]
        rsi = calculate_rsi(prices, period=3)
        self.assertIsNotNone(rsi)
        self.assertEqual(rsi, 100.0, "All gains should give RSI=100")
    
    def test_period_14(self):
        """Test RSI with period=14 (common default)."""
        prices = [100.0 + i * 0.5 for i in range(20)]
        rsi = calculate_rsi(prices, period=14)
        self.assertIsNotNone(rsi)
        self.assertGreater(rsi, 50.0)
    
    def test_period_21(self):
        """Test RSI with period=21."""
        prices = [100.0 + i * 0.3 for i in range(30)]
        rsi = calculate_rsi(prices, period=21)
        self.assertIsNotNone(rsi)
        self.assertGreater(rsi, 50.0)
    
    # =========================================================================
    # Boundary Value Tests
    # =========================================================================
    
    def test_very_small_prices(self):
        """Test RSI with very small price values."""
        prices = [0.01, 0.02, 0.015, 0.025, 0.02, 0.03, 0.025, 0.035, 0.04]
        rsi = calculate_rsi(prices, period=7)
        self.assertIsNotNone(rsi)
        self.assertGreaterEqual(rsi, 0.0)
        self.assertLessEqual(rsi, 100.0)
    
    def test_very_large_prices(self):
        """Test RSI with very large price values."""
        prices = [100000.0 + i * 100 for i in range(10)]
        rsi = calculate_rsi(prices, period=7)
        self.assertIsNotNone(rsi)
        self.assertGreater(rsi, 50.0)
    
    def test_negative_prices(self):
        """Test RSI with negative prices (unusual but valid)."""
        prices = [-100.0, -99.0, -98.0, -97.0, -96.0, -95.0, -94.0, -93.0, -92.0]
        rsi = calculate_rsi(prices, period=7)
        self.assertIsNotNone(rsi)
        self.assertEqual(rsi, 100.0, "Increasing prices should give RSI=100")
    
    def test_prices_crossing_zero(self):
        """Test RSI with prices crossing zero."""
        prices = [-2.0, -1.0, 0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        rsi = calculate_rsi(prices, period=7)
        self.assertIsNotNone(rsi)
        self.assertEqual(rsi, 100.0, "All gains should give RSI=100")
    
    # =========================================================================
    # Data Type Tests
    # =========================================================================
    
    def test_integer_prices(self):
        """Test RSI with integer prices."""
        prices = [100, 101, 102, 103, 104, 105, 106, 107, 108]
        rsi = calculate_rsi(prices, period=7)
        self.assertIsNotNone(rsi)
        self.assertEqual(rsi, 100.0)
    
    def test_numpy_array_prices(self):
        """Test RSI with numpy array input."""
        prices = np.array([100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0])
        rsi = calculate_rsi(prices, period=7)
        self.assertIsNotNone(rsi)
        self.assertEqual(rsi, 100.0)
    
    def test_mixed_int_float_prices(self):
        """Test RSI with mixed integer and float prices."""
        prices = [100, 101.5, 102, 103.5, 104, 105.5, 106, 107.5, 108]
        rsi = calculate_rsi(prices, period=7)
        self.assertIsNotNone(rsi)
        self.assertGreater(rsi, 50.0)
    
    # =========================================================================
    # Real-World Scenario Tests
    # =========================================================================
    
    def test_btc_like_prices(self):
        """Test RSI with BTC-like price movements."""
        # Simulating BTC prices around $50,000
        prices = [50000.0, 50500.0, 50200.0, 51000.0, 50800.0, 51500.0, 51200.0, 52000.0, 51800.0]
        rsi = calculate_rsi(prices, period=7)
        self.assertIsNotNone(rsi)
        self.assertGreater(rsi, 50.0, "Net upward movement should give RSI > 50")
    
    def test_eth_like_prices(self):
        """Test RSI with ETH-like price movements."""
        # Simulating ETH prices around $3,000
        prices = [3000.0, 3050.0, 2980.0, 3100.0, 3020.0, 3150.0, 3080.0, 3200.0, 3120.0]
        rsi = calculate_rsi(prices, period=7)
        self.assertIsNotNone(rsi)
        self.assertGreater(rsi, 50.0)
    
    def test_market_crash_scenario(self):
        """Test RSI during a market crash (rapid decline)."""
        prices = [50000.0, 48000.0, 45000.0, 42000.0, 40000.0, 38000.0, 36000.0, 35000.0, 34000.0]
        rsi = calculate_rsi(prices, period=7)
        self.assertEqual(rsi, 0.0, "Continuous decline should give RSI=0")
    
    def test_market_rally_scenario(self):
        """Test RSI during a market rally (rapid increase)."""
        prices = [30000.0, 32000.0, 35000.0, 38000.0, 42000.0, 45000.0, 48000.0, 50000.0, 52000.0]
        rsi = calculate_rsi(prices, period=7)
        self.assertEqual(rsi, 100.0, "Continuous increase should give RSI=100")
    
    def test_consolidation_scenario(self):
        """Test RSI during price consolidation (sideways movement)."""
        prices = [50000.0, 50100.0, 49900.0, 50050.0, 49950.0, 50000.0, 50100.0, 49900.0, 50000.0]
        rsi = calculate_rsi(prices, period=7)
        self.assertIsNotNone(rsi)
        # Consolidation should give RSI near 50
        self.assertGreater(rsi, 40.0)
        self.assertLess(rsi, 60.0)


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
