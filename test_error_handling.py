#!/usr/bin/env python3
"""
Unit tests for error handling functionality.

Tests the error handling for:
- API failures with retry
- Insufficient RSI data
- Market not found
- Insufficient mock balance
- WebSocket disconnections (auto-reconnect)
"""

import unittest
import time
from unittest.mock import Mock, patch, MagicMock
import requests

from mock_trader import (
    retry_with_backoff,
    api_request_with_retry,
    BinanceRSIStream,
    PolymarketPositionMonitor,
    get_mock_balance,
    check_balance_for_trade,
    check_mock_balance_health,
    reset_mock_trading,
    CONFIG,
)


class TestRetryWithBackoff(unittest.TestCase):
    """Test cases for retry_with_backoff utility."""
    
    def test_successful_first_attempt(self):
        """Test that successful first attempt returns immediately."""
        call_count = 0
        
        def success_func():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = retry_with_backoff(success_func, max_retries=3)
        
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 1)
    
    def test_retry_on_failure(self):
        """Test that function retries on failure."""
        call_count = 0
        
        def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise requests.exceptions.RequestException("Connection error")
            return "success"
        
        result = retry_with_backoff(
            fail_then_succeed, 
            max_retries=3,
            base_delay=0.01  # Fast for testing
        )
        
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 3)
    
    def test_raises_after_max_retries(self):
        """Test that exception is raised after max retries."""
        call_count = 0
        
        def always_fail():
            nonlocal call_count
            call_count += 1
            raise requests.exceptions.RequestException("Always fails")
        
        with self.assertRaises(requests.exceptions.RequestException):
            retry_with_backoff(
                always_fail,
                max_retries=2,
                base_delay=0.01
            )
        
        self.assertEqual(call_count, 3)  # Initial + 2 retries
    
    def test_custom_exceptions(self):
        """Test retry with custom exception types."""
        call_count = 0
        
        def fail_with_value_error():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Custom error")
            return "success"
        
        result = retry_with_backoff(
            fail_with_value_error,
            max_retries=3,
            base_delay=0.01,
            exceptions=(ValueError,)
        )
        
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 2)


class TestApiRequestWithRetry(unittest.TestCase):
    """Test cases for api_request_with_retry utility."""
    
    @patch('mock_trader.requests.get')
    def test_successful_request(self, mock_get):
        """Test successful API request."""
        mock_response = Mock()
        mock_response.json.return_value = {"data": "test"}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        response = api_request_with_retry(
            "https://api.example.com/test",
            params={"key": "value"},
            timeout=10
        )
        
        self.assertEqual(response.json(), {"data": "test"})
        mock_get.assert_called_once()
    
    @patch('mock_trader.requests.get')
    def test_retry_on_request_exception(self, mock_get):
        """Test retry on request exception."""
        mock_get.side_effect = [
            requests.exceptions.ConnectionError("Connection failed"),
            Mock(json=lambda: {"data": "test"}, raise_for_status=Mock())
        ]
        
        response = api_request_with_retry(
            "https://api.example.com/test",
            max_retries=2
        )
        
        self.assertEqual(response.json(), {"data": "test"})
        self.assertEqual(mock_get.call_count, 2)


class TestInsufficientRSIData(unittest.TestCase):
    """Test cases for insufficient RSI data handling."""
    
    def setUp(self):
        """Set up test fixtures."""
        with patch.object(BinanceRSIStream, '_fetch_initial_data'):
            self.stream = BinanceRSIStream(symbol="BTCUSDT", period=7, buffer_size=20)
    
    def test_returns_none_with_no_data(self):
        """Test that get_current_rsi_data returns None with no data."""
        result = self.stream.get_current_rsi_data()
        self.assertIsNone(result)
    
    def test_returns_none_with_insufficient_data(self):
        """Test that get_current_rsi_data returns None with < 3 RSI values."""
        self.stream.rsi_values.extend([45.0, 50.0])  # Only 2 values
        
        result = self.stream.get_current_rsi_data()
        self.assertIsNone(result)
    
    def test_returns_data_with_sufficient_values(self):
        """Test that get_current_rsi_data returns data with >= 3 RSI values."""
        self.stream.rsi_values.extend([45.0, 50.0, 55.0])  # 3 values
        
        result = self.stream.get_current_rsi_data()
        
        self.assertIsNotNone(result)
        self.assertEqual(result['current_rsi'], 55.0)
        self.assertEqual(result['rsi_1_bar_ago'], 50.0)
        self.assertEqual(result['rsi_2_bars_ago'], 45.0)
        self.assertEqual(result['data_status'], 'sufficient')
    
    def test_get_rsi_data_status(self):
        """Test get_rsi_data_status method."""
        self.stream.rsi_values.extend([45.0, 50.0])
        self.stream.close_prices.extend([100.0, 101.0, 102.0])
        
        status = self.stream.get_rsi_data_status()
        
        self.assertFalse(status['has_sufficient_data'])
        self.assertEqual(status['rsi_values_count'], 2)
        self.assertEqual(status['close_prices_count'], 3)
        self.assertEqual(status['required_rsi_values'], 3)


class TestInsufficientMockBalance(unittest.TestCase):
    """Test cases for insufficient mock balance handling."""
    
    def setUp(self):
        """Set up test fixtures."""
        reset_mock_trading(starting_balance=100.0)
    
    def tearDown(self):
        """Clean up after tests."""
        reset_mock_trading(starting_balance=1000.0)
    
    def test_check_balance_sufficient(self):
        """Test balance check with sufficient balance."""
        can_trade, adjusted, balance, reason = check_balance_for_trade(50.0)
        
        self.assertTrue(can_trade)
        self.assertEqual(adjusted, 50.0)
        self.assertEqual(balance, 100.0)
        self.assertEqual(reason, "Sufficient balance")
    
    def test_check_balance_adjusted(self):
        """Test balance check with position adjusted."""
        can_trade, adjusted, balance, reason = check_balance_for_trade(150.0)
        
        self.assertTrue(can_trade)
        self.assertEqual(adjusted, 100.0)  # Adjusted to available balance
        self.assertEqual(balance, 100.0)
        self.assertIn("adjusted", reason.lower())
    
    def test_check_balance_insufficient(self):
        """Test balance check with insufficient balance."""
        reset_mock_trading(starting_balance=0.30)
        
        can_trade, adjusted, balance, reason = check_balance_for_trade(50.0)
        
        self.assertFalse(can_trade)
        self.assertEqual(adjusted, 0)
        self.assertEqual(balance, 0.30)
        self.assertIn("insufficient", reason.lower())
    
    def test_check_mock_balance_health_healthy(self):
        """Test balance health check with healthy balance."""
        reset_mock_trading(starting_balance=1000.0)
        
        health = check_mock_balance_health()
        
        self.assertEqual(health['status'], 'healthy')
        self.assertTrue(health['can_trade'])
        self.assertEqual(health['balance'], 1000.0)
    
    def test_check_mock_balance_health_low(self):
        """Test balance health check with low balance."""
        reset_mock_trading(starting_balance=50.0)
        CONFIG['mock_balance'] = 1000.0  # Set starting balance for comparison
        
        health = check_mock_balance_health()
        
        self.assertEqual(health['status'], 'low')
        self.assertTrue(health['can_trade'])
    
    def test_check_mock_balance_health_critical(self):
        """Test balance health check with critical balance."""
        reset_mock_trading(starting_balance=0.30)
        
        health = check_mock_balance_health()
        
        self.assertEqual(health['status'], 'critical')
        self.assertFalse(health['can_trade'])


class TestPolymarketAutoReconnect(unittest.TestCase):
    """Test cases for Polymarket WebSocket auto-reconnect."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.monitor = PolymarketPositionMonitor()
    
    def test_initial_reconnect_state(self):
        """Test that reconnect is enabled by default."""
        self.assertTrue(self.monitor.reconnect_enabled)
        self.assertEqual(self.monitor.reconnect_attempts, 0)
        self.assertEqual(self.monitor.base_reconnect_delay, 1.0)
        self.assertEqual(self.monitor.max_reconnect_delay, 60.0)
        self.assertEqual(self.monitor.max_reconnect_attempts, 10)
    
    def test_exponential_backoff_calculation(self):
        """Test exponential backoff delay calculation."""
        # Test first attempt (2^0 = 1)
        self.monitor.reconnect_attempts = 0
        delay = self.monitor._calculate_reconnect_delay()
        self.assertEqual(delay, 1.0)
        
        # Test second attempt (2^1 = 2)
        self.monitor.reconnect_attempts = 1
        delay = self.monitor._calculate_reconnect_delay()
        self.assertEqual(delay, 2.0)
        
        # Test capped at max
        self.monitor.reconnect_attempts = 10
        delay = self.monitor._calculate_reconnect_delay()
        self.assertEqual(delay, 60.0)
    
    def test_reconnect_counter_reset_on_success(self):
        """Test that reconnect counter resets on successful connection."""
        self.monitor.reconnect_attempts = 5
        
        # Simulate successful connection
        self.monitor._on_open(Mock())
        
        self.assertEqual(self.monitor.reconnect_attempts, 0)
        self.assertTrue(self.monitor.running)
    
    def test_on_close_triggers_reconnect(self):
        """Test that _on_close triggers reconnection."""
        self.monitor.reconnect_enabled = True
        
        with patch.object(self.monitor, '_schedule_reconnect') as mock_schedule:
            self.monitor._on_close(Mock(), 1000, "Normal closure")
            
            mock_schedule.assert_called_once()
            self.assertFalse(self.monitor.running)
    
    def test_stop_disables_reconnect(self):
        """Test that stop() disables auto-reconnect."""
        self.monitor.reconnect_enabled = True
        self.monitor.running = True
        self.monitor.ws = Mock()
        
        self.monitor.stop()
        
        self.assertFalse(self.monitor.reconnect_enabled)
        self.assertFalse(self.monitor.running)
    
    def test_get_connection_status_includes_reconnect_attempts(self):
        """Test that connection status includes reconnect attempts."""
        self.monitor.reconnect_attempts = 3
        self.monitor.running = True
        self.monitor.ws = Mock()
        
        status = self.monitor.get_connection_status()
        
        self.assertEqual(status['reconnect_attempts'], 3)
        self.assertTrue(status['connected'])


def run_tests():
    """Run all tests."""
    unittest.main(argv=[''], verbosity=2, exit=False)


if __name__ == '__main__':
    run_tests()
