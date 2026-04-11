"""
RSI calculation and Binance WebSocket stream.
"""

import json
import time
import threading
from collections import deque
from typing import Optional, Dict, List

import requests

try:
    import websocket
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False

from .config import BINANCE_WS_URL, CONFIG
from .logger import log, log_rsi, log_websocket, log_error


def calculate_rsi(prices: List[float], period: int = 7) -> Optional[float]:
    """
    Calculate RSI from price list.
    
    Args:
        prices: List of closing prices
        period: RSI period (default: 7)
    
    Returns:
        RSI value (0-100) or None if insufficient data
    """
    if len(prices) < period + 1:
        return None
    
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]
    
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def classify_signal(rsi_current: float, rsi_prev: float, rsi_prev2: float) -> str:
    """
    Classify RSI signal based on momentum (2 consecutive periods).
    
    Args:
        rsi_current: Current RSI value
        rsi_prev: Previous RSI value (1 bar ago)
        rsi_prev2: RSI value 2 bars ago
    
    Returns:
        Classification: 'green', 'red', or 'neutral'
    """
    # Green: RSI increasing for 2 consecutive periods
    if rsi_current > rsi_prev and rsi_prev > rsi_prev2:
        return 'green'
    
    # Red: RSI decreasing for 2 consecutive periods
    if rsi_current < rsi_prev and rsi_prev < rsi_prev2:
        return 'red'
    
    # Neutral: mixed signals
    return 'neutral'


class RSISignalMemory:
    """Memory for RSI signals to detect patterns."""
    
    def __init__(self, max_size: int = 10):
        self._memory = deque(maxlen=max_size)
    
    def add(self, rsi_value: float, classification: str):
        """Add a signal to memory."""
        self._memory.append({
            'rsi': rsi_value,
            'classification': classification,
            'timestamp': time.time()
        })
    
    def get_entry_signal(self, current_rsi_values: List[float]) -> Optional[str]:
        """
        Check for entry signal based on memory and current RSI values.
        
        Requires 3 consecutive green signals for BUY, 3 consecutive red for SELL.
        
        Args:
            current_rsi_values: List of recent RSI values (need at least 3)
        
        Returns:
            'BUY', 'SELL', or None
        """
        # Need at least 2 signals in memory
        if len(self._memory) < 2:
            return None
        
        # Need at least 3 RSI values to calculate current signal
        if len(current_rsi_values) < 3:
            return None
        
        # Get last 2 signals from memory
        signal_1 = self._memory[-2]  # 2nd most recent
        signal_2 = self._memory[-1]  # Most recent
        
        # Calculate current signal from fresh RSI data
        rsi_2_bars_ago = current_rsi_values[-3]
        rsi_1_bar_ago = current_rsi_values[-2]
        rsi_current = current_rsi_values[-1]
        
        current_signal = classify_signal(rsi_current, rsi_1_bar_ago, rsi_2_bars_ago)
        
        # BUY: 3 consecutive green signals
        if (signal_1['classification'] == 'green' and 
            signal_2['classification'] == 'green' and 
            current_signal == 'green'):
            return 'BUY'
        
        # SELL: 3 consecutive red signals
        if (signal_1['classification'] == 'red' and 
            signal_2['classification'] == 'red' and 
            current_signal == 'red'):
            return 'SELL'
        
        return None
    
    def clear(self):
        """Clear the memory."""
        self._memory.clear()
    
    def __len__(self):
        return len(self._memory)


class BinanceRSIStream:
    """Real-time RSI calculation from Binance WebSocket."""
    
    def __init__(self, symbol: str = "BTCUSDT", period: int = 7, buffer_size: int = 20):
        """
        Initialize Binance RSI stream.
        
        Args:
            symbol: Trading pair (default: BTCUSDT)
            period: RSI period (default: 7)
            buffer_size: Price buffer size (default: 20)
        """
        self.symbol = symbol.lower()
        self.period = period
        self.buffer_size = buffer_size
        
        self.close_prices = deque(maxlen=buffer_size)
        self.rsi_values = deque(maxlen=buffer_size)
        
        self.ws = None
        self.thread = None
        self.running = False
        
        self.reconnect_enabled = True
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        
        self._fetch_initial_data()
    
    def _fetch_initial_data(self):
        """Fetch historical candles to initialize buffer."""
        try:
            url = "https://api.binance.com/api/v3/klines"
            params = {'symbol': self.symbol.upper(), 'interval': '1m', 'limit': self.buffer_size}
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            candles = response.json()
            
            for candle in candles:
                self.close_prices.append(float(candle[4]))
            
            self._recalculate_rsi()
            log(f"Binance: Fetched {len(self.close_prices)} candles", 'rsi')
        except Exception as e:
            log_error(f"Binance: Error fetching initial data: {e}")
    
    def _recalculate_rsi(self):
        """Recalculate RSI for all prices in buffer."""
        if len(self.close_prices) < self.period + 1:
            return
        
        prices = list(self.close_prices)
        self.rsi_values.clear()
        
        for i in range(self.period, len(prices)):
            rsi = calculate_rsi(prices[:i+1], self.period)
            if rsi is not None:
                self.rsi_values.append(rsi)
    
    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            if data.get('e') != 'kline':
                return
            
            kline = data.get('k')
            if not kline or not kline.get('x'):
                return
            
            close_price = float(kline['c'])
            self.close_prices.append(close_price)
            
            if len(self.close_prices) >= self.period + 1:
                rsi = calculate_rsi(list(self.close_prices), self.period)
                if rsi is not None:
                    self.rsi_values.append(rsi)
                    log_rsi(f"RSI: {rsi:.2f} (close: ${close_price:.2f})")
        except Exception as e:
            log_error(f"Binance message error: {e}")
    
    def _on_error(self, ws, error):
        log_websocket(f"Binance error: {error}")
    
    def _on_close(self, ws, close_status_code, close_msg):
        log_websocket(f"Binance closed: {close_status_code}")
        self.running = False
        if self.reconnect_enabled and self.reconnect_attempts < self.max_reconnect_attempts:
            self._schedule_reconnect()
    
    def _on_open(self, ws):
        log_websocket("Binance connected")
        self.running = True
        self.reconnect_attempts = 0
    
    def _schedule_reconnect(self):
        delay = min(2 ** self.reconnect_attempts, 60)
        self.reconnect_attempts += 1
        log_websocket(f"Binance reconnecting in {delay}s...")
        threading.Timer(delay, self._reconnect).start()
    
    def _reconnect(self):
        if not self.running:
            self.start()
    
    def start(self):
        """Start the WebSocket connection."""
        if self.running or not WEBSOCKET_AVAILABLE:
            return
        
        import ssl
        
        ws_url = f"{BINANCE_WS_URL}/{self.symbol}@kline_1m"
        self.ws = websocket.WebSocketApp(
            ws_url,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
            on_open=self._on_open
        )
        
        # SSL context that doesn't verify certificates (for networks with SSL inspection)
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        self.thread = threading.Thread(
            target=lambda: self.ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE}),
            daemon=True
        )
        self.thread.start()
    
    def stop(self):
        """Stop the WebSocket connection."""
        self.reconnect_enabled = False
        self.running = False
        if self.ws:
            self.ws.close()
    
    def get_current_rsi_data(self) -> Optional[Dict]:
        """Get current RSI data."""
        if len(self.rsi_values) < 3:
            return None
        
        rsi_list = list(self.rsi_values)
        rsi_current = rsi_list[-1]
        rsi_prev = rsi_list[-2]
        rsi_prev2 = rsi_list[-3]
        
        # Classify using 3 RSI values
        classification = classify_signal(rsi_current, rsi_prev, rsi_prev2)
        
        return {
            'current_rsi': rsi_current,
            'rsi_values': rsi_list,
            'classification': classification
        }
    
    def is_connected(self) -> bool:
        """Check if connected."""
        return self.running
