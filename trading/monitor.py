"""
Polymarket WebSocket position monitor.
"""

import json
import time
import threading
from typing import Optional, Dict, Callable

try:
    import websocket
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False

from .config import POLYMARKET_WS_URL, CONFIG
from .logger import log, log_exit, log_position, log_websocket, log_error


class PolymarketPositionMonitor:
    """Monitor positions via Polymarket WebSocket for real-time exit signals."""
    
    def __init__(self, exit_callback: Callable = None):
        """
        Initialize position monitor.
        
        Args:
            exit_callback: Function to call when exit condition is met.
                          Signature: callback(position: Dict, reason: str)
        """
        self.ws = None
        self.thread = None
        self.running = False
        
        self.positions = {}  # {asset_id: position_data}
        self.exit_callback = exit_callback
        self.subscribed_assets = set()
        
        self.heartbeat_thread = None
        self.reconnect_enabled = True
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
    
    def _on_message(self, ws, message):
        try:
            if not message or message.strip() == "" or message == "PONG":
                return
            
            data = json.loads(message)
            event_type = data.get('event_type')
            
            if event_type == 'book':
                asset_id = data.get('asset_id')
                bids = data.get('bids', [])
                asks = data.get('asks', [])
                best_bid = float(bids[0]['price']) if bids else None
                best_ask = float(asks[0]['price']) if asks else None
                self._process_price_update(asset_id, best_bid, best_ask)
                
            elif event_type == 'price_change':
                for change in data.get('price_changes', []):
                    asset_id = change.get('asset_id')
                    best_bid = float(change['best_bid']) if change.get('best_bid') else None
                    best_ask = float(change['best_ask']) if change.get('best_ask') else None
                    self._process_price_update(asset_id, best_bid, best_ask)
            
            elif event_type == 'market_resolved':
                market_id = data.get('market')
                winning_outcome = data.get('winning_outcome')
                log_exit(f"Market resolved: {market_id} → {winning_outcome}")
                self._handle_market_resolution(market_id, winning_outcome)
                
        except json.JSONDecodeError:
            pass
        except Exception as e:
            log_error(f"Polymarket message error: {e}")
    
    def _process_price_update(self, asset_id: str, best_bid: float, best_ask: float):
        """Process price update and check exit conditions."""
        if asset_id not in self.positions:
            return
        
        position = self.positions[asset_id]
        if position.get('exit_triggered'):
            return
        
        # For BUY positions, we sell at best_bid
        current_price = best_bid if best_bid else best_ask
        if current_price is None:
            return
        
        entry_price = position['entry_price']
        shares = position['shares']
        
        gross_profit = (current_price - entry_price) * shares
        fee = gross_profit * 0.10 if gross_profit > 0 else 0
        net_profit = gross_profit - fee
        
        position['current_price'] = current_price
        position['gross_profit'] = gross_profit
        position['fee'] = fee
        position['net_profit'] = net_profit
        
        target_profit = position.get('target_profit', CONFIG['target_profit_per_trade'])
        
        if net_profit >= target_profit:
            log_exit(f"Exit signal: {asset_id[:16]}... profit ${net_profit:.2f}")
            position['exit_triggered'] = True
            
            if self.exit_callback:
                try:
                    self.exit_callback(position, 'profit_target')
                except Exception as e:
                    log_error(f"Exit callback error: {e}")
    
    def _handle_market_resolution(self, market_id: str, winning_outcome: str):
        """Handle market resolution."""
        positions_to_close = [
            (aid, pos) for aid, pos in self.positions.items()
            if pos['market_id'] == market_id
        ]
        
        for asset_id, position in positions_to_close:
            log_position(f"Position closed by resolution: {asset_id[:16]}...")
            if self.exit_callback:
                try:
                    self.exit_callback(position, 'market_resolved')
                except Exception as e:
                    log_error(f"Exit callback error: {e}")
            
            self.positions.pop(asset_id, None)
    
    def _on_error(self, ws, error):
        log_websocket(f"Polymarket error: {error}")
    
    def _on_close(self, ws, close_status_code, close_msg):
        log_websocket(f"Polymarket closed: {close_status_code}")
        self.running = False
        if self.reconnect_enabled and self.reconnect_attempts < self.max_reconnect_attempts:
            self._schedule_reconnect()
    
    def _on_open(self, ws):
        log_websocket("Polymarket connected")
        self.running = True
        self.reconnect_attempts = 0
        if self.subscribed_assets:
            self._send_subscription(list(self.subscribed_assets))
    
    def _schedule_reconnect(self):
        delay = min(2 ** self.reconnect_attempts, 60)
        self.reconnect_attempts += 1
        log_websocket(f"Polymarket reconnecting in {delay}s...")
        threading.Timer(delay, self._reconnect).start()
    
    def _reconnect(self):
        if not self.running:
            self.start()
    
    def _send_subscription(self, asset_ids: list):
        if not self.ws or not self.running:
            return
        try:
            msg = json.dumps({"assets_ids": asset_ids, "type": "market"})
            self.ws.send(msg)
            log_websocket(f"Subscribed to {len(asset_ids)} assets")
        except Exception as e:
            log_error(f"Subscription error: {e}")
    
    def _send_heartbeat(self):
        while self.running:
            try:
                if self.ws:
                    self.ws.send("PING")
                time.sleep(30)
            except:
                break
    
    def start(self):
        """Start the WebSocket connection."""
        if self.running or not WEBSOCKET_AVAILABLE:
            return
        
        import ssl
        
        self.ws = websocket.WebSocketApp(
            POLYMARKET_WS_URL,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
            on_open=self._on_open
        )
        
        # SSL context that doesn't verify certificates (for networks with SSL inspection)
        self.thread = threading.Thread(
            target=lambda: self.ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE}),
            daemon=True
        )
        self.thread.start()
        
        self.heartbeat_thread = threading.Thread(target=self._send_heartbeat, daemon=True)
        self.heartbeat_thread.start()
    
    def stop(self):
        """Stop the WebSocket connection."""
        self.reconnect_enabled = False
        self.running = False
        if self.ws:
            self.ws.close()
    
    def add_position(self, market_id: str, asset_id: str, side: str, shares: float, 
                     entry_price: float, target_profit: float = None):
        """Add a position to monitor."""
        if target_profit is None:
            target_profit = CONFIG['target_profit_per_trade']
        
        self.positions[asset_id] = {
            'market_id': market_id,
            'asset_id': asset_id,
            'side': side,
            'shares': shares,
            'entry_price': entry_price,
            'target_profit': target_profit,
            'current_price': entry_price,
            'gross_profit': 0,
            'fee': 0,
            'net_profit': 0,
            'exit_triggered': False,
            'entry_time': time.time()
        }
        
        self.subscribed_assets.add(asset_id)
        if self.running:
            self._send_subscription([asset_id])
        
        log_position(f"Monitoring: {asset_id[:16]}... @ ${entry_price:.3f}")
    
    def remove_position(self, asset_id: str):
        """Remove a position from monitoring."""
        self.positions.pop(asset_id, None)
        self.subscribed_assets.discard(asset_id)
    
    def get_position(self, asset_id: str) -> Optional[Dict]:
        """Get position data."""
        return self.positions.get(asset_id)
    
    def get_all_positions(self) -> Dict:
        """Get all positions."""
        return self.positions.copy()
    
    def is_connected(self) -> bool:
        """Check if connected."""
        return self.running
