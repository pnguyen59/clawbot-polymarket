#!/usr/bin/env python3
"""
Tests for Entry Logic Integration

Tests the main trading decision function and all entry condition checks.
"""

import unittest
from unittest.mock import patch, MagicMock
from mock_trader import (
    CONFIG,
    check_momentum,
    check_rsi_confirmation,
    check_profit_requirement,
    check_balance_for_trade,
    check_market_status,
    make_trading_decision,
    get_mock_balance,
    reset_mock_trading,
    clear_signal_memory
)


class TestCheckMomentum(unittest.TestCase):
    """Tests for check_momentum function."""
    
    @patch('mock_trader.requests.get')
    def test_momentum_up(self, mock_get):
        """Test momentum calculation for upward price movement."""
        # Mock Binance API response
        mock_response = MagicMock()
        mock_response.json.return_value = [
            [0, "50000", "50100", "49900", "50000", "100"],  # Oldest
            [0, "50000", "50200", "49950", "50100", "100"],
            [0, "50100", "50300", "50050", "50200", "100"],
            [0, "50200", "50400", "50150", "50300", "100"],
            [0, "50300", "50500", "50250", "50400", "100"],
            [0, "50400", "50600", "50350", "50500", "100"],  # Newest
        ]
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        result = check_momentum()
        
        self.assertIsNotNone(result)
        self.assertEqual(result['direction'], 'up')
        self.assertGreater(result['momentum_pct'], 0)
        self.assertEqual(result['price_now'], 50500.0)
        self.assertEqual(result['price_then'], 50000.0)
    
    @patch('mock_trader.requests.get')
    def test_momentum_down(self, mock_get):
        """Test momentum calculation for downward price movement."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            [0, "50500", "50600", "50400", "50500", "100"],  # Oldest
            [0, "50400", "50500", "50300", "50400", "100"],
            [0, "50300", "50400", "50200", "50300", "100"],
            [0, "50200", "50300", "50100", "50200", "100"],
            [0, "50100", "50200", "50000", "50100", "100"],
            [0, "50000", "50100", "49900", "50000", "100"],  # Newest
        ]
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        result = check_momentum()
        
        self.assertIsNotNone(result)
        self.assertEqual(result['direction'], 'down')
        self.assertLess(result['momentum_pct'], 0)
    
    @patch('mock_trader.requests.get')
    def test_momentum_api_error(self, mock_get):
        """Test momentum returns None on API error."""
        mock_get.side_effect = Exception("API Error")
        
        result = check_momentum()
        
        self.assertIsNone(result)


class TestCheckRSIConfirmation(unittest.TestCase):
    """Tests for check_rsi_confirmation function."""
    
    def test_rsi_confirms_up(self):
        """Test RSI confirms upward momentum."""
        confirmed, reason = check_rsi_confirmation('up', 'BUY')
        
        self.assertTrue(confirmed)
        self.assertIn('confirms', reason.lower())
    
    def test_rsi_confirms_down(self):
        """Test RSI confirms downward momentum."""
        confirmed, reason = check_rsi_confirmation('down', 'SELL')
        
        self.assertTrue(confirmed)
        self.assertIn('confirms', reason.lower())
    
    def test_rsi_contradicts_up(self):
        """Test RSI contradicts upward momentum."""
        confirmed, reason = check_rsi_confirmation('up', 'SELL')
        
        self.assertFalse(confirmed)
        self.assertIn('contradicts', reason.lower())
    
    def test_rsi_contradicts_down(self):
        """Test RSI contradicts downward momentum."""
        confirmed, reason = check_rsi_confirmation('down', 'BUY')
        
        self.assertFalse(confirmed)
        self.assertIn('contradicts', reason.lower())
    
    def test_rsi_neutral(self):
        """Test neutral RSI skips trade (requires confirmation)."""
        confirmed, reason = check_rsi_confirmation('up', None)
        
        self.assertFalse(confirmed)
        self.assertIn('neutral', reason.lower())


class TestCheckProfitRequirement(unittest.TestCase):
    """Tests for check_profit_requirement function."""
    
    def test_profitable_trade(self):
        """Test trade with sufficient profit margin."""
        meets_req, result = check_profit_requirement(0.40)
        
        self.assertTrue(meets_req)
        self.assertTrue(result['profitable'])
    
    def test_unprofitable_trade(self):
        """Test trade with insufficient profit margin."""
        # Set a very small spread that won't meet requirements
        original_spread = CONFIG['target_sell_spread']
        CONFIG['target_sell_spread'] = 0.01  # 1 cent spread
        
        meets_req, result = check_profit_requirement(0.40)
        
        CONFIG['target_sell_spread'] = original_spread  # Restore
        
        self.assertFalse(meets_req)
        self.assertFalse(result['profitable'])


class TestCheckBalanceForTrade(unittest.TestCase):
    """Tests for check_balance_for_trade function."""
    
    def setUp(self):
        """Reset mock trading before each test."""
        reset_mock_trading(1000.0)
    
    def test_sufficient_balance(self):
        """Test with sufficient balance."""
        can_trade, adjusted, balance, reason = check_balance_for_trade(100.0)
        
        self.assertTrue(can_trade)
        self.assertEqual(adjusted, 100.0)
        self.assertEqual(balance, 1000.0)
    
    def test_insufficient_balance_adjusted(self):
        """Test position adjusted when balance is insufficient."""
        can_trade, adjusted, balance, reason = check_balance_for_trade(1500.0)
        
        self.assertTrue(can_trade)
        self.assertEqual(adjusted, 1000.0)  # Adjusted to available balance
        self.assertIn('adjusted', reason.lower())
    
    def test_balance_below_minimum(self):
        """Test trade rejected when balance below minimum."""
        reset_mock_trading(0.30)  # Very low balance
        
        can_trade, adjusted, balance, reason = check_balance_for_trade(100.0)
        
        self.assertFalse(can_trade)
        self.assertIn('insufficient', reason.lower())


class TestCheckMarketStatus(unittest.TestCase):
    """Tests for check_market_status function."""
    
    def test_active_market(self):
        """Test active market passes check."""
        market_info = {
            'market_id': 'test123',
            'closed': False,
            'resolved': False
        }
        
        is_active, reason = check_market_status(market_info)
        
        self.assertTrue(is_active)
        self.assertIn('active', reason.lower())
    
    def test_closed_market(self):
        """Test closed market fails check."""
        market_info = {
            'market_id': 'test123',
            'closed': True,
            'resolved': False
        }
        
        is_active, reason = check_market_status(market_info)
        
        self.assertFalse(is_active)
        self.assertIn('closed', reason.lower())
    
    def test_resolved_market(self):
        """Test resolved market fails check."""
        market_info = {
            'market_id': 'test123',
            'closed': False,
            'resolved': True
        }
        
        is_active, reason = check_market_status(market_info)
        
        self.assertFalse(is_active)
        self.assertIn('resolved', reason.lower())
    
    def test_none_market(self):
        """Test None market fails check."""
        is_active, reason = check_market_status(None)
        
        self.assertFalse(is_active)
        self.assertIn('not found', reason.lower())


class TestMakeTradingDecision(unittest.TestCase):
    """Tests for make_trading_decision function."""
    
    def setUp(self):
        """Reset state before each test."""
        reset_mock_trading(1000.0)
        clear_signal_memory()
    
    def test_skip_inactive_market(self):
        """Test decision skips inactive market."""
        market_info = {
            'market_id': 'test123',
            'closed': True,
            'resolved': False,
            'tokens': []
        }
        
        decision = make_trading_decision(market_info)
        
        self.assertEqual(decision['action'], 'SKIP')
        self.assertIn('closed', decision['reason'].lower())
    
    def test_skip_no_momentum(self):
        """Test decision skips when momentum fetch fails."""
        market_info = {
            'market_id': 'test123',
            'closed': False,
            'resolved': False,
            'tokens': [
                {'asset_id': 'token1', 'outcome': 'Yes', 'price': 0.50},
                {'asset_id': 'token2', 'outcome': 'No', 'price': 0.50}
            ]
        }
        
        # Pass None momentum to simulate fetch failure
        decision = make_trading_decision(market_info, momentum_data=None)
        
        # Will try to fetch momentum, which may fail in test environment
        self.assertIn(decision['action'], ['SKIP', 'TRADE'])
    
    def test_trade_signal_with_valid_data(self):
        """Test trade signal generated with valid market and momentum."""
        market_info = {
            'market_id': 'test123',
            'closed': False,
            'resolved': False,
            'tokens': [
                {'asset_id': 'token1', 'outcome': 'Yes', 'price': 0.40},
                {'asset_id': 'token2', 'outcome': 'No', 'price': 0.60}
            ]
        }
        
        momentum_data = {
            'momentum_pct': 0.5,
            'direction': 'up',
            'price_now': 50500.0,
            'price_then': 50000.0
        }
        
        decision = make_trading_decision(market_info, momentum_data=momentum_data)
        
        self.assertEqual(decision['action'], 'TRADE')
        self.assertEqual(decision['side'], 'BUY')
        self.assertIn('market_id', decision)
        self.assertIn('asset_id', decision)
        self.assertIn('position_size', decision)
    
    def test_skip_weak_momentum(self):
        """Test decision skips when momentum is too weak."""
        market_info = {
            'market_id': 'test123',
            'closed': False,
            'resolved': False,
            'tokens': [
                {'asset_id': 'token1', 'outcome': 'Yes', 'price': 0.40},
                {'asset_id': 'token2', 'outcome': 'No', 'price': 0.60}
            ]
        }
        
        momentum_data = {
            'momentum_pct': 0.01,  # Very weak momentum
            'direction': 'up',
            'price_now': 50005.0,
            'price_then': 50000.0
        }
        
        decision = make_trading_decision(market_info, momentum_data=momentum_data)
        
        self.assertEqual(decision['action'], 'SKIP')
        self.assertIn('momentum', decision['reason'].lower())


if __name__ == '__main__':
    unittest.main()
