#!/usr/bin/env python3
"""
Tests for the logging module in mock_trader.py

Tests the log() function and related logging utilities.
"""

import sys
import io
from datetime import datetime, timezone
from unittest.mock import patch

# Import the logging functions from mock_trader
from mock_trader import (
    log, log_trade, log_exit, log_signal, log_position, log_rsi,
    log_websocket, log_warn, log_error, log_debug, log_info,
    set_log_quiet, set_log_verbose, enable_file_logging, disable_file_logging,
    CONFIG, _log_config
)


class TestLogFunction:
    """Tests for the main log() function."""
    
    def test_log_basic_message(self, capsys):
        """Test that log() outputs a basic message with timestamp."""
        result = log("Test message", mock_prefix=False)
        captured = capsys.readouterr()
        
        assert "Test message" in captured.out
        assert result is not None
        assert "Test message" in result
    
    def test_log_with_mock_prefix(self, capsys):
        """Test that log() adds [MOCK] prefix when mock trading is enabled."""
        # Ensure mock trading is enabled
        original_mock = CONFIG.get('mock_trading', True)
        CONFIG['mock_trading'] = True
        
        result = log("Test message", mock_prefix=True)
        captured = capsys.readouterr()
        
        assert "[MOCK]" in captured.out
        assert "Test message" in captured.out
        
        CONFIG['mock_trading'] = original_mock
    
    def test_log_without_mock_prefix_when_disabled(self, capsys):
        """Test that log() doesn't add [MOCK] prefix when mock trading is disabled."""
        original_mock = CONFIG.get('mock_trading', True)
        CONFIG['mock_trading'] = False
        
        result = log("Test message", mock_prefix=True)
        captured = capsys.readouterr()
        
        assert "[MOCK]" not in captured.out
        assert "Test message" in captured.out
        
        CONFIG['mock_trading'] = original_mock
    
    def test_log_with_level_trade(self, capsys):
        """Test that log() adds [TRADE] tag for trade level."""
        result = log("Trade executed", level='trade', mock_prefix=False)
        captured = capsys.readouterr()
        
        assert "[TRADE]" in captured.out
        assert "Trade executed" in captured.out
    
    def test_log_with_level_error(self, capsys):
        """Test that log() adds [ERROR] tag for error level."""
        result = log("Something went wrong", level='error', mock_prefix=False)
        captured = capsys.readouterr()
        
        assert "[ERROR]" in captured.out
        assert "Something went wrong" in captured.out
    
    def test_log_with_level_warn(self, capsys):
        """Test that log() adds [WARN] tag for warn level."""
        result = log("Warning message", level='warn', mock_prefix=False)
        captured = capsys.readouterr()
        
        assert "[WARN]" in captured.out
        assert "Warning message" in captured.out
    
    def test_log_quiet_mode_suppresses_info(self, capsys):
        """Test that quiet mode suppresses info messages."""
        set_log_quiet(True)
        
        result = log("Info message", level='info', force=False, mock_prefix=False)
        captured = capsys.readouterr()
        
        # Info should be suppressed in quiet mode
        assert result is None
        assert "Info message" not in captured.out
        
        set_log_quiet(False)
    
    def test_log_force_overrides_quiet_mode(self, capsys):
        """Test that force=True overrides quiet mode."""
        set_log_quiet(True)
        
        result = log("Forced message", level='info', force=True, mock_prefix=False)
        captured = capsys.readouterr()
        
        assert "Forced message" in captured.out
        
        set_log_quiet(False)
    
    def test_log_debug_suppressed_by_default(self, capsys):
        """Test that debug messages are suppressed by default."""
        set_log_verbose(False)
        
        result = log("Debug message", level='debug', mock_prefix=False)
        captured = capsys.readouterr()
        
        assert result is None
        assert "Debug message" not in captured.out
    
    def test_log_debug_shown_in_verbose_mode(self, capsys):
        """Test that debug messages are shown in verbose mode."""
        set_log_verbose(True)
        
        result = log("Debug message", level='debug', mock_prefix=False)
        captured = capsys.readouterr()
        
        assert "[DEBUG]" in captured.out
        assert "Debug message" in captured.out
        
        set_log_verbose(False)
    
    def test_log_includes_timestamp(self, capsys):
        """Test that log() includes a timestamp."""
        result = log("Test message", mock_prefix=False)
        captured = capsys.readouterr()
        
        # Check for timestamp format [YYYY-MM-DD HH:MM:SS]
        assert "[20" in captured.out  # Year starts with 20xx


class TestLogHelperFunctions:
    """Tests for the log helper functions."""
    
    def test_log_trade(self, capsys):
        """Test log_trade() helper function."""
        result = log_trade("Trade message")
        captured = capsys.readouterr()
        
        assert "[TRADE]" in captured.out
        assert "Trade message" in captured.out
    
    def test_log_exit(self, capsys):
        """Test log_exit() helper function."""
        result = log_exit("Exit message")
        captured = capsys.readouterr()
        
        assert "[EXIT]" in captured.out
        assert "Exit message" in captured.out
    
    def test_log_signal(self, capsys):
        """Test log_signal() helper function."""
        result = log_signal("Signal message")
        captured = capsys.readouterr()
        
        assert "[SIGNAL]" in captured.out
        assert "Signal message" in captured.out
    
    def test_log_position(self, capsys):
        """Test log_position() helper function."""
        result = log_position("Position message", force=True)
        captured = capsys.readouterr()
        
        assert "[POSITION]" in captured.out
        assert "Position message" in captured.out
    
    def test_log_rsi(self, capsys):
        """Test log_rsi() helper function."""
        result = log_rsi("RSI message", force=True)
        captured = capsys.readouterr()
        
        assert "[RSI]" in captured.out
        assert "RSI message" in captured.out
    
    def test_log_websocket(self, capsys):
        """Test log_websocket() helper function."""
        result = log_websocket("WebSocket message", force=True)
        captured = capsys.readouterr()
        
        assert "[WS]" in captured.out
        assert "WebSocket message" in captured.out
    
    def test_log_warn(self, capsys):
        """Test log_warn() helper function."""
        result = log_warn("Warning message")
        captured = capsys.readouterr()
        
        assert "[WARN]" in captured.out
        assert "Warning message" in captured.out
    
    def test_log_error(self, capsys):
        """Test log_error() helper function."""
        result = log_error("Error message")
        captured = capsys.readouterr()
        
        assert "[ERROR]" in captured.out
        assert "Error message" in captured.out
    
    def test_log_debug(self, capsys):
        """Test log_debug() helper function."""
        set_log_verbose(True)
        
        result = log_debug("Debug message")
        captured = capsys.readouterr()
        
        assert "[DEBUG]" in captured.out
        assert "Debug message" in captured.out
        
        set_log_verbose(False)
    
    def test_log_info(self, capsys):
        """Test log_info() helper function."""
        result = log_info("Info message", force=True)
        captured = capsys.readouterr()
        
        assert "Info message" in captured.out


class TestLogConfiguration:
    """Tests for log configuration functions."""
    
    def test_set_log_quiet(self):
        """Test set_log_quiet() function."""
        set_log_quiet(True)
        assert _log_config['quiet'] == True
        
        set_log_quiet(False)
        assert _log_config['quiet'] == False
    
    def test_set_log_verbose(self):
        """Test set_log_verbose() function."""
        set_log_verbose(True)
        assert _log_config['verbose'] == True
        
        set_log_verbose(False)
        assert _log_config['verbose'] == False


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
