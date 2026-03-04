#!/usr/bin/env python3
"""
Unit tests for RSI Signal Memory functionality.

Tests the signal memory storage, retrieval, and FIFO logic.
"""

import unittest
from datetime import datetime, timezone, timedelta
from mock_trader import (
    add_signal_to_memory,
    get_signal_memory,
    clear_signal_memory,
    get_signal_memory_size,
    _rsi_signal_memory
)


class TestSignalMemory(unittest.TestCase):
    """Test cases for RSI signal memory functionality."""
    
    def setUp(self):
        """Clear signal memory before each test."""
        clear_signal_memory()
    
    def tearDown(self):
        """Clear signal memory after each test."""
        clear_signal_memory()
    
    def test_add_signal_basic(self):
        """Test adding a basic signal to memory."""
        signal = add_signal_to_memory(55.2, 'green')
        
        # Verify signal structure
        self.assertIsInstance(signal, dict)
        self.assertIn('timestamp', signal)
        self.assertIn('rsi_value', signal)
        self.assertIn('classification', signal)
        
        # Verify signal values
        self.assertEqual(signal['rsi_value'], 55.2)
        self.assertEqual(signal['classification'], 'green')
        self.assertIsInstance(signal['timestamp'], datetime)
        
        # Verify signal is in memory
        memory = get_signal_memory()
        self.assertEqual(len(memory), 1)
        self.assertEqual(memory[0]['rsi_value'], 55.2)
    
    def test_add_signal_with_custom_timestamp(self):
        """Test adding a signal with custom timestamp."""
        custom_time = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        signal = add_signal_to_memory(45.8, 'red', timestamp=custom_time)
        
        self.assertEqual(signal['timestamp'], custom_time)
        self.assertEqual(signal['rsi_value'], 45.8)
        self.assertEqual(signal['classification'], 'red')
    
    def test_add_multiple_signals(self):
        """Test adding multiple signals to memory."""
        add_signal_to_memory(50.0, 'neutral')
        add_signal_to_memory(55.0, 'green')
        add_signal_to_memory(60.0, 'green')
        
        memory = get_signal_memory()
        self.assertEqual(len(memory), 3)
        
        # Verify order (oldest to newest)
        self.assertEqual(memory[0]['rsi_value'], 50.0)
        self.assertEqual(memory[1]['rsi_value'], 55.0)
        self.assertEqual(memory[2]['rsi_value'], 60.0)
    
    def test_fifo_logic_max_10_signals(self):
        """Test FIFO logic when memory exceeds max size (10 signals)."""
        # Add 12 signals (exceeds max of 10)
        for i in range(12):
            rsi = 40.0 + i
            classification = 'green' if i % 2 == 0 else 'red'
            add_signal_to_memory(rsi, classification)
        
        memory = get_signal_memory()
        
        # Should only have 10 signals (oldest 2 removed)
        self.assertEqual(len(memory), 10)
        
        # First signal should be the 3rd one added (index 2)
        # because first 2 were removed by FIFO
        self.assertEqual(memory[0]['rsi_value'], 42.0)
        
        # Last signal should be the 12th one added
        self.assertEqual(memory[-1]['rsi_value'], 51.0)
    
    def test_fifo_logic_custom_max_size(self):
        """Test FIFO logic with custom max size."""
        # Add 7 signals with max_size=5
        for i in range(7):
            rsi = 30.0 + i
            add_signal_to_memory(rsi, 'neutral', max_size=5)
        
        memory = get_signal_memory()
        
        # Should only have 5 signals
        self.assertEqual(len(memory), 5)
        
        # First signal should be the 3rd one added (30.0 + 2 = 32.0)
        self.assertEqual(memory[0]['rsi_value'], 32.0)
        
        # Last signal should be the 7th one added (30.0 + 6 = 36.0)
        self.assertEqual(memory[-1]['rsi_value'], 36.0)
    
    def test_get_signal_memory_returns_copy(self):
        """Test that get_signal_memory returns a copy, not reference."""
        add_signal_to_memory(50.0, 'neutral')
        
        memory1 = get_signal_memory()
        memory2 = get_signal_memory()
        
        # Should be equal but not the same object
        self.assertEqual(memory1, memory2)
        self.assertIsNot(memory1, memory2)
        
        # Modifying copy should not affect original
        memory1.append({'rsi_value': 99.0, 'classification': 'green'})
        
        memory3 = get_signal_memory()
        self.assertEqual(len(memory3), 1)  # Original unchanged
    
    def test_clear_signal_memory(self):
        """Test clearing signal memory."""
        # Add some signals
        add_signal_to_memory(50.0, 'neutral')
        add_signal_to_memory(55.0, 'green')
        add_signal_to_memory(60.0, 'green')
        
        self.assertEqual(get_signal_memory_size(), 3)
        
        # Clear memory
        clear_signal_memory()
        
        # Verify memory is empty
        self.assertEqual(get_signal_memory_size(), 0)
        self.assertEqual(len(get_signal_memory()), 0)
    
    def test_get_signal_memory_size(self):
        """Test getting signal memory size."""
        self.assertEqual(get_signal_memory_size(), 0)
        
        add_signal_to_memory(50.0, 'neutral')
        self.assertEqual(get_signal_memory_size(), 1)
        
        add_signal_to_memory(55.0, 'green')
        self.assertEqual(get_signal_memory_size(), 2)
        
        clear_signal_memory()
        self.assertEqual(get_signal_memory_size(), 0)
    
    def test_invalid_rsi_value_type(self):
        """Test that invalid RSI value type raises ValueError."""
        with self.assertRaises(ValueError) as context:
            add_signal_to_memory("invalid", 'green')
        
        self.assertIn("must be a number", str(context.exception))
    
    def test_invalid_rsi_value_range(self):
        """Test that RSI value out of range raises ValueError."""
        # RSI below 0
        with self.assertRaises(ValueError) as context:
            add_signal_to_memory(-5.0, 'green')
        
        self.assertIn("must be between 0 and 100", str(context.exception))
        
        # RSI above 100
        with self.assertRaises(ValueError) as context:
            add_signal_to_memory(105.0, 'green')
        
        self.assertIn("must be between 0 and 100", str(context.exception))
    
    def test_invalid_classification(self):
        """Test that invalid classification raises ValueError."""
        with self.assertRaises(ValueError) as context:
            add_signal_to_memory(50.0, 'invalid')
        
        self.assertIn("must be 'green', 'red', or 'neutral'", str(context.exception))
    
    def test_signal_memory_persistence(self):
        """Test that signal memory persists across function calls."""
        # Add signals in separate calls
        add_signal_to_memory(50.0, 'neutral')
        memory1 = get_signal_memory()
        
        add_signal_to_memory(55.0, 'green')
        memory2 = get_signal_memory()
        
        # Second memory should contain both signals
        self.assertEqual(len(memory1), 1)
        self.assertEqual(len(memory2), 2)
        
        # Verify both signals are present
        self.assertEqual(memory2[0]['rsi_value'], 50.0)
        self.assertEqual(memory2[1]['rsi_value'], 55.0)
    
    def test_signal_timestamps_ordering(self):
        """Test that signals maintain chronological order."""
        base_time = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        
        # Add signals with increasing timestamps
        for i in range(5):
            timestamp = base_time + timedelta(minutes=i)
            add_signal_to_memory(50.0 + i, 'neutral', timestamp=timestamp)
        
        memory = get_signal_memory()
        
        # Verify chronological order
        for i in range(len(memory) - 1):
            self.assertLess(memory[i]['timestamp'], memory[i+1]['timestamp'])
    
    def test_edge_case_exactly_max_size(self):
        """Test behavior when exactly at max size."""
        # Add exactly 10 signals (max size)
        for i in range(10):
            add_signal_to_memory(40.0 + i, 'neutral')
        
        memory = get_signal_memory()
        self.assertEqual(len(memory), 10)
        
        # Add one more signal
        add_signal_to_memory(99.0, 'green')
        
        memory = get_signal_memory()
        
        # Should still be 10 signals
        self.assertEqual(len(memory), 10)
        
        # First signal should be removed (40.0)
        # New first signal should be 41.0
        self.assertEqual(memory[0]['rsi_value'], 41.0)
        
        # Last signal should be the new one (99.0)
        self.assertEqual(memory[-1]['rsi_value'], 99.0)
    
    def test_all_classification_types(self):
        """Test all three classification types."""
        add_signal_to_memory(50.0, 'green')
        add_signal_to_memory(45.0, 'red')
        add_signal_to_memory(48.0, 'neutral')
        
        memory = get_signal_memory()
        
        self.assertEqual(memory[0]['classification'], 'green')
        self.assertEqual(memory[1]['classification'], 'red')
        self.assertEqual(memory[2]['classification'], 'neutral')


class TestSignalMemoryIntegration(unittest.TestCase):
    """Integration tests for signal memory with RSI calculation."""
    
    def setUp(self):
        """Clear signal memory before each test."""
        clear_signal_memory()
    
    def tearDown(self):
        """Clear signal memory after each test."""
        clear_signal_memory()
    
    def test_realistic_signal_pattern_buy(self):
        """Test realistic BUY signal pattern (3 consecutive green)."""
        # Add 2 green signals to memory
        add_signal_to_memory(45.0, 'green')
        add_signal_to_memory(50.0, 'green')
        
        # Simulate current signal being green
        # In real usage, this would come from check_rsi_entry_signal
        memory = get_signal_memory()
        
        # Verify we have 2 green signals in memory
        self.assertEqual(len(memory), 2)
        self.assertEqual(memory[-2]['classification'], 'green')
        self.assertEqual(memory[-1]['classification'], 'green')
        
        # If current signal is also green, we'd have BUY signal
        # (This would be checked by check_rsi_entry_signal function)
    
    def test_realistic_signal_pattern_sell(self):
        """Test realistic SELL signal pattern (3 consecutive red)."""
        # Add 2 red signals to memory
        add_signal_to_memory(55.0, 'red')
        add_signal_to_memory(50.0, 'red')
        
        memory = get_signal_memory()
        
        # Verify we have 2 red signals in memory
        self.assertEqual(len(memory), 2)
        self.assertEqual(memory[-2]['classification'], 'red')
        self.assertEqual(memory[-1]['classification'], 'red')
    
    def test_realistic_signal_pattern_mixed(self):
        """Test mixed signal pattern (no clear entry)."""
        # Add mixed signals
        add_signal_to_memory(50.0, 'green')
        add_signal_to_memory(48.0, 'red')
        add_signal_to_memory(52.0, 'neutral')
        
        memory = get_signal_memory()
        
        # Verify mixed signals
        self.assertEqual(len(memory), 3)
        self.assertEqual(memory[0]['classification'], 'green')
        self.assertEqual(memory[1]['classification'], 'red')
        self.assertEqual(memory[2]['classification'], 'neutral')


if __name__ == '__main__':
    unittest.main()
