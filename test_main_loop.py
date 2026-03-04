#!/usr/bin/env python3
"""
Tests for the Main Trading Loop (Task 11)

Tests the continuous trading loop functionality including:
- Sleep calculation until next 5-minute interval
- Trading iteration execution
- Position status logging
- Graceful shutdown
"""

import pytest
import time
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from mock_trader import (
    calculate_sleep_until_next_5min,
    run_trading_iteration,
    log_position_status,
    shutdown_gracefully,
    CONFIG,
    reset_mock_trading,
    _mock_positions,
    get_mock_balance,
)


class TestCalculateSleepUntilNext5Min:
    """Tests for calculate_sleep_until_next_5min function."""
    
    def test_returns_positive_value(self):
        """Sleep time should always be positive."""
        sleep_time = calculate_sleep_until_next_5min()
        assert sleep_time > 0
    
    def test_returns_less_than_305_seconds(self):
        """Sleep time should be at most 305 seconds (5 min + 5 sec buffer)."""
        sleep_time = calculate_sleep_until_next_5min()
        assert sleep_time <= 305
    
    def test_includes_buffer(self):
        """Sleep time should include 5-second buffer."""
        # The function adds 5 seconds buffer
        sleep_time = calculate_sleep_until_next_5min()
        assert sleep_time >= 5  # At minimum, we have the buffer


class TestRunTradingIteration:
    """Tests for run_trading_iteration function."""
    
    def setup_method(self):
        """Reset mock trading state before each test."""
        reset_mock_trading(1000.0)
    
    @patch('mock_trader.discover_and_subscribe_market')
    def test_returns_skipped_when_no_market(self, mock_discover):
        """Should return skipped status when market not found."""
        mock_discover.return_value = None
        
        result = run_trading_iteration()
        
        assert result['status'] == 'skipped'
        assert 'not found' in result['reason'].lower() or 'not active' in result['reason'].lower()
    
    @patch('mock_trader.discover_and_subscribe_market')
    @patch('mock_trader.make_trading_decision')
    def test_returns_skipped_when_decision_skip(self, mock_decision, mock_discover):
        """Should return skipped status when trading decision is SKIP."""
        mock_discover.return_value = {
            'market_id': 'test_market',
            'tokens': [{'asset_id': 'test_asset', 'outcome': 'Yes', 'price': 0.5}]
        }
        mock_decision.return_value = {
            'action': 'SKIP',
            'reason': 'Test skip reason'
        }
        
        result = run_trading_iteration()
        
        assert result['status'] == 'skipped'
        assert result['reason'] == 'Test skip reason'
    
    @patch('mock_trader.discover_and_subscribe_market')
    @patch('mock_trader.make_trading_decision')
    @patch('mock_trader.execute_trade_with_monitoring')
    def test_returns_traded_on_success(self, mock_execute, mock_decision, mock_discover):
        """Should return traded status when trade executes successfully."""
        mock_discover.return_value = {
            'market_id': 'test_market',
            'tokens': [{'asset_id': 'test_asset', 'outcome': 'Yes', 'price': 0.5}]
        }
        mock_decision.return_value = {
            'action': 'TRADE',
            'market_id': 'test_market',
            'asset_id': 'test_asset',
            'side': 'BUY',
            'position_size': 100.0,
            'entry_price': 0.5
        }
        mock_execute.return_value = {
            'trade_success': True,
            'position_id': 'mock_0',
            'asset_id': 'test_asset',
            'shares': 200.0,
            'entry_price': 0.5,
            'monitoring_started': True
        }
        
        result = run_trading_iteration()
        
        assert result['status'] == 'traded'
        assert result['position_id'] == 'mock_0'
        assert result['shares'] == 200.0
    
    @patch('mock_trader.discover_and_subscribe_market')
    @patch('mock_trader.make_trading_decision')
    @patch('mock_trader.execute_trade_with_monitoring')
    def test_returns_failed_on_trade_failure(self, mock_execute, mock_decision, mock_discover):
        """Should return failed status when trade execution fails."""
        mock_discover.return_value = {
            'market_id': 'test_market',
            'tokens': [{'asset_id': 'test_asset', 'outcome': 'Yes', 'price': 0.5}]
        }
        mock_decision.return_value = {
            'action': 'TRADE',
            'market_id': 'test_market',
            'asset_id': 'test_asset',
            'side': 'BUY',
            'position_size': 100.0,
            'entry_price': 0.5
        }
        mock_execute.return_value = {
            'trade_success': False,
            'error': 'Insufficient balance'
        }
        
        result = run_trading_iteration()
        
        assert result['status'] == 'failed'
        assert 'Insufficient balance' in result['reason']
    
    @patch('mock_trader.discover_and_subscribe_market')
    def test_handles_exception_gracefully(self, mock_discover):
        """Should return error status when exception occurs."""
        mock_discover.side_effect = Exception("Test error")
        
        result = run_trading_iteration()
        
        assert result['status'] == 'error'
        assert 'Test error' in result['reason']


class TestLogPositionStatus:
    """Tests for log_position_status function."""
    
    def setup_method(self):
        """Reset mock trading state before each test."""
        reset_mock_trading(1000.0)
    
    @patch('mock_trader.get_polymarket_monitor')
    def test_no_output_when_no_positions(self, mock_monitor, capsys):
        """Should not print anything when no positions exist."""
        # Ensure _mock_positions is empty
        import mock_trader
        mock_trader._mock_positions = {}
        
        log_position_status()
        
        captured = capsys.readouterr()
        # Should not print position header when no positions
        assert "Open Positions Status" not in captured.out or captured.out.strip() == ""


class TestShutdownGracefully:
    """Tests for shutdown_gracefully function."""
    
    def setup_method(self):
        """Reset state before each test."""
        reset_mock_trading(1000.0)
    
    @patch('mock_trader._binance_rsi_stream', None)
    @patch('mock_trader._polymarket_monitor', None)
    @patch('mock_trader.save_mock_history')
    @patch('mock_trader.show_mock_stats')
    def test_saves_mock_history(self, mock_stats, mock_save):
        """Should save mock history when mock trading is enabled."""
        CONFIG['mock_trading'] = True
        
        shutdown_gracefully()
        
        mock_save.assert_called_once_with("mock_trades.json")
    
    @patch('mock_trader._binance_rsi_stream')
    @patch('mock_trader._polymarket_monitor', None)
    @patch('mock_trader.save_mock_history')
    @patch('mock_trader.show_mock_stats')
    def test_stops_binance_stream(self, mock_stats, mock_save, mock_stream):
        """Should stop Binance RSI stream if running."""
        import mock_trader
        mock_stream_instance = MagicMock()
        mock_trader._binance_rsi_stream = mock_stream_instance
        
        shutdown_gracefully()
        
        mock_stream_instance.stop.assert_called_once()
    
    @patch('mock_trader._binance_rsi_stream', None)
    @patch('mock_trader._polymarket_monitor')
    @patch('mock_trader.save_mock_history')
    @patch('mock_trader.show_mock_stats')
    def test_stops_polymarket_monitor(self, mock_stats, mock_save, mock_monitor):
        """Should stop Polymarket monitor if running."""
        import mock_trader
        mock_monitor_instance = MagicMock()
        mock_trader._polymarket_monitor = mock_monitor_instance
        
        shutdown_gracefully()
        
        mock_monitor_instance.stop.assert_called_once()


class TestMainLoopIntegration:
    """Integration tests for the main loop components."""
    
    def setup_method(self):
        """Reset state before each test."""
        reset_mock_trading(1000.0)
    
    def test_config_has_required_keys(self):
        """CONFIG should have all required keys for main loop."""
        required_keys = [
            'rsi_enabled',
            'rsi_period',
            'mock_trading',
            'mock_balance',
            'target_profit_per_trade',
            'min_profit_per_share',
            'target_sell_spread',
        ]
        
        for key in required_keys:
            assert key in CONFIG, f"Missing required config key: {key}"
    
    def test_reset_mock_trading_resets_balance(self):
        """reset_mock_trading should reset balance to specified value."""
        reset_mock_trading(5000.0)
        
        assert get_mock_balance() == 5000.0
    
    def test_sleep_calculation_is_deterministic(self):
        """Sleep calculation should be consistent for same time."""
        # Call twice in quick succession
        sleep1 = calculate_sleep_until_next_5min()
        sleep2 = calculate_sleep_until_next_5min()
        
        # Should be very close (within 1 second)
        assert abs(sleep1 - sleep2) < 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
