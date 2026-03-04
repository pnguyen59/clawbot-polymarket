#!/usr/bin/env python3
"""
Unit tests for BinanceRSIStream auto-reconnect functionality.

Tests the auto-reconnect logic with exponential backoff for WebSocket disconnections.
"""

import unittest
import time
from unittest.mock import Mock, patch, MagicMock
from mock_trader import BinanceRSIStream


class TestAutoReconnect(unittest.TestCase):
    """Test cases for auto-reconnect functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock the _fetch_initial_data to avoid API calls
        with patch.object(BinanceRSIStream, '_fetch_initial_data'):
            self.stream = BinanceRSIStream(symbol="BTCUSDT", period=7, buffer_size=20)
    
    def test_initial_reconnect_state(self):
        """Test that reconnect is enabled by default."""
        self.assertTrue(self.stream.reconnect_enabled)
        self.assertEqual(self.stream.reconnect_attempts, 0)
        self.assertEqual(self.stream.base_reconnect_delay, 1.0)
        self.assertEqual(self.stream.max_reconnect_delay, 60.0)
        self.assertEqual(self.stream.max_reconnect_attempts, 10)
    
    def test_exponential_backoff_calculation(self):
        """Test exponential backoff delay calculation."""
        # Test first attempt (2^0 = 1)
        self.stream.reconnect_attempts = 0
        delay = self.stream._calculate_reconnect_delay()
        self.assertEqual(delay, 1.0)
        
        # Test second attempt (2^1 = 2)
        self.stream.reconnect_attempts = 1
        delay = self.stream._calculate_reconnect_delay()
        self.assertEqual(delay, 2.0)
        
        # Test third attempt (2^2 = 4)
        self.stream.reconnect_attempts = 2
        delay = self.stream._calculate_reconnect_delay()
        self.assertEqual(delay, 4.0)
        
        # Test fourth attempt (2^3 = 8)
        self.stream.reconnect_attempts = 3
        delay = self.stream._calculate_reconnect_delay()
        self.assertEqual(delay, 8.0)
        
        # Test fifth attempt (2^4 = 16)
        self.stream.reconnect_attempts = 4
        delay = self.stream._calculate_reconnect_delay()
        self.assertEqual(delay, 16.0)
        
        # Test sixth attempt (2^5 = 32)
        self.stream.reconnect_attempts = 5
        delay = self.stream._calculate_reconnect_delay()
        self.assertEqual(delay, 32.0)
        
        # Test seventh attempt (2^6 = 64, capped at 60)
        self.stream.reconnect_attempts = 6
        delay = self.stream._calculate_reconnect_delay()
        self.assertEqual(delay, 60.0)  # Capped at max_reconnect_delay
        
        # Test eighth attempt (should still be capped at 60)
        self.stream.reconnect_attempts = 7
        delay = self.stream._calculate_reconnect_delay()
        self.assertEqual(delay, 60.0)
    
    def test_reconnect_counter_reset_on_success(self):
        """Test that reconnect counter resets on successful connection."""
        # Simulate some failed reconnection attempts
        self.stream.reconnect_attempts = 5
        
        # Simulate successful connection
        self.stream._on_open(Mock())
        
        # Counter should be reset
        self.assertEqual(self.stream.reconnect_attempts, 0)
        self.assertTrue(self.stream.running)
    
    def test_max_reconnect_attempts_limit(self):
        """Test that reconnection stops after max attempts."""
        # Set reconnect attempts to max
        self.stream.reconnect_attempts = 10
        self.stream.max_reconnect_attempts = 10
        
        # Mock the reconnection timer
        with patch('threading.Timer') as mock_timer:
            # Attempt to schedule reconnect
            self.stream._schedule_reconnect()
            
            # Timer should NOT be created (max attempts reached)
            mock_timer.assert_not_called()
    
    def test_reconnect_scheduling(self):
        """Test that reconnection is scheduled with correct delay."""
        self.stream.reconnect_attempts = 2  # Should give 4 second delay
        
        with patch('threading.Timer') as mock_timer:
            mock_timer_instance = Mock()
            mock_timer.return_value = mock_timer_instance
            
            # Schedule reconnect
            self.stream._schedule_reconnect()
            
            # Verify Timer was created with correct delay
            mock_timer.assert_called_once()
            args, kwargs = mock_timer.call_args
            self.assertEqual(args[0], 4.0)  # 2^2 = 4 seconds
            self.assertEqual(args[1], self.stream._reconnect)
            
            # Verify timer was started
            mock_timer_instance.start.assert_called_once()
            
            # Verify reconnect counter was incremented
            self.assertEqual(self.stream.reconnect_attempts, 3)
    
    def test_on_close_triggers_reconnect(self):
        """Test that _on_close triggers reconnection."""
        self.stream.reconnect_enabled = True
        
        with patch.object(self.stream, '_schedule_reconnect') as mock_schedule:
            # Simulate connection close
            self.stream._on_close(Mock(), 1000, "Normal closure")
            
            # Verify reconnection was scheduled
            mock_schedule.assert_called_once()
            self.assertFalse(self.stream.running)
    
    def test_stop_disables_reconnect(self):
        """Test that stop() disables auto-reconnect."""
        self.stream.reconnect_enabled = True
        self.stream.running = True
        self.stream.ws = Mock()
        
        # Stop the stream
        self.stream.stop()
        
        # Verify reconnect is disabled
        self.assertFalse(self.stream.reconnect_enabled)
        self.assertFalse(self.stream.running)
        
        # Verify WebSocket was closed
        self.stream.ws.close.assert_called_once()
    
    def test_stop_cancels_pending_reconnect(self):
        """Test that stop() cancels pending reconnection attempts."""
        # Create a mock reconnect thread
        mock_thread = Mock()
        mock_thread.is_alive.return_value = True
        self.stream.reconnect_thread = mock_thread
        self.stream.ws = Mock()
        
        # Stop the stream
        self.stream.stop()
        
        # Verify reconnect thread was cancelled
        mock_thread.cancel.assert_called_once()
    
    def test_is_connected(self):
        """Test is_connected() method."""
        # Not connected initially
        self.assertFalse(self.stream.is_connected())
        
        # Simulate connection
        self.stream.running = True
        self.stream.ws = Mock()
        self.assertTrue(self.stream.is_connected())
        
        # Simulate disconnection
        self.stream.running = False
        self.assertFalse(self.stream.is_connected())
    
    def test_get_connection_status(self):
        """Test get_connection_status() method."""
        # Set up some state
        self.stream.running = True
        self.stream.ws = Mock()
        self.stream.reconnect_attempts = 3
        self.stream.close_prices.extend([100.0, 101.0, 102.0])
        self.stream.rsi_values.extend([45.0, 50.0])
        
        # Get status
        status = self.stream.get_connection_status()
        
        # Verify status
        self.assertTrue(status['connected'])
        self.assertEqual(status['reconnect_attempts'], 3)
        self.assertEqual(status['buffer_size'], 3)
        self.assertEqual(status['rsi_values_count'], 2)
        self.assertEqual(status['symbol'], 'BTCUSDT')
        self.assertEqual(status['period'], 7)
    
    def test_reconnect_preserves_buffers(self):
        """Test that reconnection preserves data buffers."""
        # Add some data to buffers
        self.stream.close_prices.extend([100.0, 101.0, 102.0])
        self.stream.rsi_values.extend([45.0, 50.0, 55.0])
        
        # Store original buffer contents
        original_prices = list(self.stream.close_prices)
        original_rsi = list(self.stream.rsi_values)
        
        # Simulate disconnection and reconnection
        self.stream._on_close(Mock(), 1000, "Connection lost")
        
        # Buffers should be preserved
        self.assertEqual(list(self.stream.close_prices), original_prices)
        self.assertEqual(list(self.stream.rsi_values), original_rsi)
    
    def test_reconnect_with_infinite_attempts(self):
        """Test reconnection with infinite attempts (max_reconnect_attempts = None)."""
        self.stream.max_reconnect_attempts = None
        self.stream.reconnect_attempts = 100  # Very high number
        
        with patch('threading.Timer') as mock_timer:
            mock_timer_instance = Mock()
            mock_timer.return_value = mock_timer_instance
            
            # Should still schedule reconnect (no max limit)
            self.stream._schedule_reconnect()
            
            # Timer should be created
            mock_timer.assert_called_once()
            mock_timer_instance.start.assert_called_once()


class TestReconnectIntegration(unittest.TestCase):
    """Integration tests for reconnect functionality."""
    
    @patch('mock_trader.requests.get')
    def test_reconnect_after_error(self, mock_get):
        """Test that stream reconnects after an error."""
        # Mock successful API response for initial data
        mock_response = Mock()
        mock_response.json.return_value = [
            [0, "100", "101", "99", "100.5", "1000", 0, "0", 0, "0", "0", "0"]
            for _ in range(20)
        ]
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        # Create stream
        stream = BinanceRSIStream(symbol="BTCUSDT", period=7, buffer_size=20)
        
        # Verify initial state
        self.assertTrue(stream.reconnect_enabled)
        self.assertEqual(stream.reconnect_attempts, 0)
        
        # Simulate error and close
        with patch.object(stream, '_schedule_reconnect') as mock_schedule:
            stream._on_error(Mock(), "Connection error")
            stream._on_close(Mock(), 1006, "Abnormal closure")
            
            # Verify reconnection was scheduled
            mock_schedule.assert_called_once()


def run_tests():
    """Run all tests."""
    unittest.main(argv=[''], verbosity=2, exit=False)


if __name__ == '__main__':
    run_tests()
