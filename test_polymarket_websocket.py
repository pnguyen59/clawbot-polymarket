#!/usr/bin/env python3
"""
Tests for PolymarketPositionMonitor WebSocket Integration

Tests the Polymarket WebSocket connection, message handling, position monitoring,
and P&L calculation functionality.
"""

import unittest
import json
import time
from unittest.mock import Mock, MagicMock, patch, call
from mock_trader import PolymarketPositionMonitor, get_polymarket_monitor


class TestPolymarketPositionMonitor(unittest.TestCase):
    """Test PolymarketPositionMonitor class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.monitor = PolymarketPositionMonitor()
    
    def tearDown(self):
        """Clean up after tests."""
        if self.monitor.running:
            self.monitor.stop()
    
    def test_initialization(self):
        """Test monitor initialization."""
        self.assertIsNone(self.monitor.ws)
        self.assertIsNone(self.monitor.thread)
        self.assertFalse(self.monitor.running)
        self.assertEqual(len(self.monitor.positions), 0)
        self.assertEqual(len(self.monitor.callbacks), 0)
        self.assertEqual(len(self.monitor.subscribed_assets), 0)
    
    def test_add_position(self):
        """Test adding a position to monitor."""
        market_id = "0x5f65177b394277fd294cd75650044e32ba009a95022d88a0c1d565897d72f8f1"
        asset_id = "71321045679252212594626385532706912750332728571942532289631379312455583992563"
        
        callback = Mock()
        
        self.monitor.add_position(
            market_id=market_id,
            asset_id=asset_id,
            side="BUY",
            shares=333,
            entry_price=0.40,
            target_profit=15.0,
            exit_callback=callback
        )
        
        # Check position was added
        self.assertIn(asset_id, self.monitor.positions)
        position = self.monitor.positions[asset_id]
        
        self.assertEqual(position['market_id'], market_id)
        self.assertEqual(position['asset_id'], asset_id)
        self.assertEqual(position['side'], "BUY")
        self.assertEqual(position['shares'], 333)
        self.assertEqual(position['entry_price'], 0.40)
        self.assertEqual(position['target_profit'], 15.0)
        self.assertIsNotNone(position['entry_time'])
        self.assertIsNone(position['current_price'])
        self.assertEqual(position['net_profit'], 0)
        
        # Check callback was registered
        self.assertIn(asset_id, self.monitor.callbacks)
        self.assertEqual(self.monitor.callbacks[asset_id], callback)
        
        # Check asset was added to subscribed set
        self.assertIn(asset_id, self.monitor.subscribed_assets)
    
    def test_remove_position(self):
        """Test removing a position from monitoring."""
        asset_id = "71321045679252212594626385532706912750332728571942532289631379312455583992563"
        
        # Add position first
        self.monitor.add_position(
            market_id="0x5f65...",
            asset_id=asset_id,
            side="BUY",
            shares=100,
            entry_price=0.50
        )
        
        # Remove position
        self.monitor.remove_position(asset_id)
        
        # Check position was removed
        self.assertNotIn(asset_id, self.monitor.positions)
        self.assertNotIn(asset_id, self.monitor.callbacks)
    
    def test_get_position_status(self):
        """Test getting position status."""
        asset_id = "71321045679252212594626385532706912750332728571942532289631379312455583992563"
        
        # Add position
        self.monitor.add_position(
            market_id="0x5f65...",
            asset_id=asset_id,
            side="BUY",
            shares=333,
            entry_price=0.40,
            target_profit=15.0
        )
        
        # Get status
        status = self.monitor.get_position_status(asset_id)
        
        self.assertIsNotNone(status)
        self.assertEqual(status['shares'], 333)
        self.assertEqual(status['entry_price'], 0.40)
        
        # Test non-existent position
        status = self.monitor.get_position_status("nonexistent")
        self.assertIsNone(status)
    
    def test_process_price_update_buy_position(self):
        """Test price update processing for BUY position."""
        asset_id = "71321045679252212594626385532706912750332728571942532289631379312455583992563"
        
        callback = Mock()
        
        # Add BUY position
        self.monitor.add_position(
            market_id="0x5f65...",
            asset_id=asset_id,
            side="BUY",
            shares=333,
            entry_price=0.40,
            target_profit=14.0,  # Lower target to account for rounding
            exit_callback=callback
        )
        
        # Process price update (not at target yet)
        self.monitor._process_price_update(asset_id, best_bid=0.43, best_ask=0.44)
        
        position = self.monitor.positions[asset_id]
        self.assertEqual(position['current_price'], 0.43)  # Uses best_bid for BUY
        
        # Calculate expected P&L
        # Gross profit: (0.43 - 0.40) * 333 = 9.99
        # Fee: 9.99 * 0.10 = 0.999
        # Net profit: 9.99 - 0.999 = 8.991
        self.assertAlmostEqual(position['gross_profit'], 9.99, places=2)
        self.assertAlmostEqual(position['fee'], 0.999, places=2)
        self.assertAlmostEqual(position['net_profit'], 8.991, places=2)
        
        # Callback should not be called yet (not at target)
        callback.assert_not_called()
        
        # Process price update at target
        self.monitor._process_price_update(asset_id, best_bid=0.45, best_ask=0.46)
        
        position = self.monitor.positions[asset_id]
        self.assertEqual(position['current_price'], 0.45)
        
        # Calculate expected P&L at target
        # Gross profit: (0.45 - 0.40) * 333 = 16.65
        # Fee: 16.65 * 0.10 = 1.665
        # Net profit: 16.65 - 1.665 = 14.985 (>= 14.0 target)
        self.assertAlmostEqual(position['net_profit'], 14.985, places=2)
        
        # Callback should be called now (at target)
        callback.assert_called_once()
        call_args = callback.call_args[0]
        self.assertEqual(call_args[0], position)
        self.assertEqual(call_args[1], 'profit_target')
    
    def test_process_price_update_sell_position(self):
        """Test price update processing for SELL position."""
        asset_id = "65818619657568813474341868652308942079804919287380422192892211131408793125422"
        
        # Add SELL position
        self.monitor.add_position(
            market_id="0x5f65...",
            asset_id=asset_id,
            side="SELL",
            shares=333,
            entry_price=0.60,
            target_profit=15.0
        )
        
        # Process price update (SELL position uses best_ask)
        self.monitor._process_price_update(asset_id, best_bid=0.56, best_ask=0.57)
        
        position = self.monitor.positions[asset_id]
        self.assertEqual(position['current_price'], 0.57)  # Uses best_ask for SELL
        
        # For SELL position: profit = (entry - current) * shares
        # Gross profit: (0.60 - 0.57) * 333 = 9.99
        # Fee: 9.99 * 0.10 = 0.999
        # Net profit: 9.99 - 0.999 = 8.991
        self.assertAlmostEqual(position['gross_profit'], 9.99, places=2)
        self.assertAlmostEqual(position['net_profit'], 8.991, places=2)
    
    def test_handle_market_resolution(self):
        """Test market resolution handling."""
        market_id = "0x5f65177b394277fd294cd75650044e32ba009a95022d88a0c1d565897d72f8f1"
        asset_id_1 = "71321045679252212594626385532706912750332728571942532289631379312455583992563"
        asset_id_2 = "65818619657568813474341868652308942079804919287380422192892211131408793125422"
        
        callback_1 = Mock()
        callback_2 = Mock()
        
        # Add two positions for the same market
        self.monitor.add_position(
            market_id=market_id,
            asset_id=asset_id_1,
            side="BUY",
            shares=100,
            entry_price=0.50,
            exit_callback=callback_1
        )
        
        self.monitor.add_position(
            market_id=market_id,
            asset_id=asset_id_2,
            side="SELL",
            shares=200,
            entry_price=0.50,
            exit_callback=callback_2
        )
        
        # Handle market resolution
        self.monitor._handle_market_resolution(market_id, "YES")
        
        # Both callbacks should be called with 'market_resolved' reason
        callback_1.assert_called_once()
        self.assertEqual(callback_1.call_args[0][1], 'market_resolved')
        
        callback_2.assert_called_once()
        self.assertEqual(callback_2.call_args[0][1], 'market_resolved')
        
        # Both positions should be removed
        self.assertNotIn(asset_id_1, self.monitor.positions)
        self.assertNotIn(asset_id_2, self.monitor.positions)
    
    def test_on_message_book_event(self):
        """Test handling of 'book' event messages."""
        asset_id = "71321045679252212594626385532706912750332728571942532289631379312455583992563"
        
        # Add position
        self.monitor.add_position(
            market_id="0x5f65...",
            asset_id=asset_id,
            side="BUY",
            shares=333,
            entry_price=0.40
        )
        
        # Create book message
        message = json.dumps({
            "event_type": "book",
            "asset_id": asset_id,
            "bids": [
                {"price": "0.43", "size": "100"},
                {"price": "0.42", "size": "200"}
            ],
            "asks": [
                {"price": "0.44", "size": "150"},
                {"price": "0.45", "size": "250"}
            ]
        })
        
        # Process message
        self.monitor._on_message(None, message)
        
        # Check position was updated with best_bid
        position = self.monitor.positions[asset_id]
        self.assertEqual(position['current_price'], 0.43)
    
    def test_on_message_price_change_event(self):
        """Test handling of 'price_change' event messages."""
        asset_id = "71321045679252212594626385532706912750332728571942532289631379312455583992563"
        
        # Add position
        self.monitor.add_position(
            market_id="0x5f65...",
            asset_id=asset_id,
            side="BUY",
            shares=333,
            entry_price=0.40
        )
        
        # Create price_change message
        message = json.dumps({
            "event_type": "price_change",
            "market": "0x5f65177b394277fd294cd75650044e32ba009a95022d88a0c1d565897d72f8f1",
            "price_changes": [
                {
                    "asset_id": asset_id,
                    "price": "0.43",
                    "size": "100",
                    "side": "BUY",
                    "best_bid": "0.43",
                    "best_ask": "0.44"
                }
            ],
            "timestamp": "1757908892351"
        })
        
        # Process message
        self.monitor._on_message(None, message)
        
        # Check position was updated
        position = self.monitor.positions[asset_id]
        self.assertEqual(position['current_price'], 0.43)
    
    def test_on_message_market_resolved_event(self):
        """Test handling of 'market_resolved' event messages."""
        market_id = "0x5f65177b394277fd294cd75650044e32ba009a95022d88a0c1d565897d72f8f1"
        asset_id = "71321045679252212594626385532706912750332728571942532289631379312455583992563"
        
        callback = Mock()
        
        # Add position
        self.monitor.add_position(
            market_id=market_id,
            asset_id=asset_id,
            side="BUY",
            shares=333,
            entry_price=0.40,
            exit_callback=callback
        )
        
        # Create market_resolved message
        message = json.dumps({
            "event_type": "market_resolved",
            "market": market_id,
            "winning_outcome": "YES"
        })
        
        # Process message
        self.monitor._on_message(None, message)
        
        # Check callback was called
        callback.assert_called_once()
        self.assertEqual(callback.call_args[0][1], 'market_resolved')
        
        # Check position was removed
        self.assertNotIn(asset_id, self.monitor.positions)
    
    def test_on_message_pong_response(self):
        """Test handling of PONG response to PING heartbeat."""
        # Should not raise any errors
        self.monitor._on_message(None, "PONG")
    
    def test_on_message_invalid_json(self):
        """Test handling of invalid JSON messages."""
        # Should not raise errors, just log them
        self.monitor._on_message(None, "invalid json {")
    
    def test_send_subscription(self):
        """Test sending subscription message."""
        # Mock WebSocket
        self.monitor.ws = Mock()
        self.monitor.running = True
        
        asset_ids = [
            "71321045679252212594626385532706912750332728571942532289631379312455583992563",
            "65818619657568813474341868652308942079804919287380422192892211131408793125422"
        ]
        
        # Send subscription
        self.monitor._send_subscription(asset_ids)
        
        # Check WebSocket send was called
        self.monitor.ws.send.assert_called_once()
        
        # Parse the sent message
        sent_message = json.loads(self.monitor.ws.send.call_args[0][0])
        
        self.assertEqual(sent_message['assets_ids'], asset_ids)
        self.assertEqual(sent_message['type'], 'market')
        self.assertTrue(sent_message['custom_feature_enabled'])
    
    def test_connection_status(self):
        """Test connection status methods."""
        # Initially not connected
        self.assertFalse(self.monitor.is_connected())
        
        status = self.monitor.get_connection_status()
        self.assertFalse(status['connected'])
        self.assertEqual(status['positions_count'], 0)
        self.assertEqual(status['subscribed_assets_count'], 0)
        
        # Simulate connection
        self.monitor.ws = Mock()
        self.monitor.running = True
        
        self.assertTrue(self.monitor.is_connected())
        
        # Add position
        self.monitor.add_position(
            market_id="0x5f65...",
            asset_id="71321...",
            side="BUY",
            shares=100,
            entry_price=0.50
        )
        
        status = self.monitor.get_connection_status()
        self.assertTrue(status['connected'])
        self.assertEqual(status['positions_count'], 1)
        self.assertEqual(status['subscribed_assets_count'], 1)


class TestGetPolymarketMonitor(unittest.TestCase):
    """Test get_polymarket_monitor() global function."""
    
    def setUp(self):
        """Reset global monitor before each test."""
        import mock_trader
        mock_trader._polymarket_monitor = None
    
    @patch('mock_trader.PolymarketPositionMonitor')
    def test_get_polymarket_monitor_creates_instance(self, mock_class):
        """Test that get_polymarket_monitor creates and starts monitor."""
        mock_instance = Mock()
        mock_class.return_value = mock_instance
        
        monitor = get_polymarket_monitor()
        
        # Check instance was created
        mock_class.assert_called_once()
        
        # Check start was called
        mock_instance.start.assert_called_once()
        
        # Check same instance is returned on second call
        monitor2 = get_polymarket_monitor()
        self.assertEqual(monitor, monitor2)
        
        # start should only be called once
        mock_instance.start.assert_called_once()


class TestProfitCalculations(unittest.TestCase):
    """Test P&L calculation accuracy."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.monitor = PolymarketPositionMonitor()
    
    def test_profit_calculation_scenario_1(self):
        """Test profit calculation: Buy 333 shares at $0.40, sell at $0.45."""
        asset_id = "test_asset_1"
        
        self.monitor.add_position(
            market_id="test_market",
            asset_id=asset_id,
            side="BUY",
            shares=333,
            entry_price=0.40,
            target_profit=15.0
        )
        
        # Update price to $0.45
        self.monitor._process_price_update(asset_id, best_bid=0.45, best_ask=0.46)
        
        position = self.monitor.positions[asset_id]
        
        # Expected: (0.45 - 0.40) * 333 = 16.65 gross
        # Fee: 16.65 * 0.10 = 1.665
        # Net: 16.65 - 1.665 = 14.985
        self.assertAlmostEqual(position['gross_profit'], 16.65, places=2)
        self.assertAlmostEqual(position['fee'], 1.665, places=2)
        self.assertAlmostEqual(position['net_profit'], 14.985, places=2)
    
    def test_profit_calculation_scenario_2(self):
        """Test profit calculation: Buy 167 shares at $0.40, sell at $0.50."""
        asset_id = "test_asset_2"
        
        self.monitor.add_position(
            market_id="test_market",
            asset_id=asset_id,
            side="BUY",
            shares=167,
            entry_price=0.40,
            target_profit=15.0
        )
        
        # Update price to $0.50
        self.monitor._process_price_update(asset_id, best_bid=0.50, best_ask=0.51)
        
        position = self.monitor.positions[asset_id]
        
        # Expected: (0.50 - 0.40) * 167 = 16.70 gross
        # Fee: 16.70 * 0.10 = 1.67
        # Net: 16.70 - 1.67 = 15.03
        self.assertAlmostEqual(position['gross_profit'], 16.70, places=2)
        self.assertAlmostEqual(position['fee'], 1.67, places=2)
        self.assertAlmostEqual(position['net_profit'], 15.03, places=2)
    
    def test_profit_calculation_small_spread(self):
        """Test profit calculation with small spread (should not trigger exit)."""
        asset_id = "test_asset_3"
        
        callback = Mock()
        
        self.monitor.add_position(
            market_id="test_market",
            asset_id=asset_id,
            side="BUY",
            shares=1000,
            entry_price=0.40,
            target_profit=15.0,
            exit_callback=callback
        )
        
        # Update price to $0.405 (only 0.5¢ spread)
        self.monitor._process_price_update(asset_id, best_bid=0.405, best_ask=0.41)
        
        position = self.monitor.positions[asset_id]
        
        # Expected: (0.405 - 0.40) * 1000 = 5.00 gross
        # Fee: 5.00 * 0.10 = 0.50
        # Net: 5.00 - 0.50 = 4.50 (< $15 target)
        self.assertAlmostEqual(position['net_profit'], 4.50, places=2)
        
        # Callback should NOT be called (not at target)
        callback.assert_not_called()


if __name__ == '__main__':
    unittest.main()
