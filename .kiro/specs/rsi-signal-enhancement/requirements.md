# Polymarket Direct Trading with RSI - Requirements

## Overview
Build a trading bot that trades BTC 5-minute fast markets on Polymarket DIRECTLY (no Simmer SDK). Uses RSI(7) technical analysis on 1-minute candles combined with price momentum. Includes early exit functionality to lock in profits.

## Feature Name
polymarket-direct-trading

## Architecture Change
**CRITICAL:** This is a complete rewrite from the existing Simmer-based bot to direct Polymarket CLOB API integration.

### What's Changing:
- ❌ Remove: Simmer SDK dependency
- ✅ Add: Direct Polymarket CLOB API integration
- ✅ Add: Polymarket WebSocket for real-time market data and position monitoring
- ✅ Add: Binance WebSocket for real-time RSI calculation
- ✅ Add: Early exit / profit-taking functionality
- ✅ Add: Position monitoring and management

### WebSocket Architecture:
1. **Binance WebSocket**: Real-time 1-minute candles for RSI calculation
2. **Polymarket WebSocket**: Real-time price updates for position monitoring and early exit

## User Stories

### 1. RSI Calculation (Real-time via WebSocket)
**As a trader**, I want the bot to calculate RSI(7) on 1-minute BTC candles in real-time, so that I can identify momentum shifts immediately.

**Acceptance Criteria:**
- 1.1 Connect to Binance WebSocket for 1-minute kline stream
- 1.2 Fetch initial 20 candles via REST API on startup
- 1.3 Calculate RSI with 7-period lookback using standard formula: RSI = 100 - (100 / (1 + RS))
- 1.4 Update RSI automatically when each 1-minute candle closes (k.x = true)
- 1.5 Maintain rolling buffer of last 20 close prices
- 1.6 WebSocket runs in background thread (non-blocking)
- 1.7 Handle WebSocket disconnections and reconnect automatically
- 1.8 Handle edge cases (insufficient data, API errors, connection failures)

### 2. Signal Classification (Green/Red)
**As a trader**, I want each candle to be classified as "green" or "red" based on RSI momentum, so that I can identify bullish/bearish trends.

**Acceptance Criteria:**
- 2.1 A candle is "green" if: current_rsi > previous_rsi AND previous_rsi > rsi_before_previous
- 2.2 A candle is "red" if: current_rsi < previous_rsi AND previous_rsi < rsi_before_previous
- 2.3 A candle is "neutral" if neither condition is met
- 2.4 Classification is calculated for each new 1-minute candle

### 3. Signal Memory Storage
**As a trader**, I want the bot to store the last N RSI signals in memory, so that I can analyze signal patterns over time.

**Acceptance Criteria:**
- 3.1 Store last 10 RSI signals in memory (timestamp, rsi_value, classification)
- 3.2 Memory persists during bot runtime (in-memory only, no file storage)
- 3.3 Memory is FIFO (first-in-first-out) - oldest signals are removed when limit reached
- 3.4 Memory is accessible for trade decision logic

### 4. Entry Signal Logic
**As a trader**, I want the bot to enter BUY trades when RSI shows strong bullish momentum, so that I can capitalize on upward trends.

**Acceptance Criteria:**
- 4.1 Check last 2 signals in memory: both must be "green"
- 4.2 Check current candle: must be "green" (3 consecutive green signals)
- 4.3 If all conditions met: signal = "BUY"
- 4.4 BUY signal works alongside existing momentum checks (both must pass)

### 5. Exit Signal Logic
**As a trader**, I want the bot to enter SELL trades when RSI shows strong bearish momentum, so that I can profit from downward trends.

**Acceptance Criteria:**
- 5.1 Check last 2 signals in memory: both must be "red"
- 5.2 Check current candle: must be "red" (3 consecutive red signals)
- 5.3 If all conditions met: signal = "SELL"
- 5.4 SELL signal works alongside existing momentum checks (both must pass)

### 6. Integration with Existing Strategy
**As a trader**, I want RSI signals to enhance (not replace) the existing momentum strategy, so that I have multiple confirmation signals.

**Acceptance Criteria:**
- 6.1 RSI check is OPTIONAL (can be enabled/disabled via config)
- 6.2 When enabled, BOTH momentum AND RSI must agree on direction
- 6.3 If momentum says UP but RSI says SELL → SKIP trade
- 6.4 If momentum says DOWN but RSI says BUY → SKIP trade
- 6.5 If RSI is neutral → use momentum signal only

### 7. Market Resolution Check
**As a trader**, I want to ensure the market is not already resolved before entering a trade, so that I don't waste capital on closed markets.

**Acceptance Criteria:**
- 7.1 Check market status via Simmer API before trade execution
- 7.2 If market is resolved → SKIP trade with reason "Market already resolved"
- 7.3 If market status check fails → SKIP trade with reason "Cannot verify market status"
- 7.4 Only proceed to trade if market status is "open" or "active"

### 8. Minimum Profit Requirement (Early Exit Trading)
**As a trader**, I want to ensure potential profit covers fees plus minimum target when selling shares, so that I don't enter unprofitable trades.

**Acceptance Criteria:**
- 8.1 Trading model: Buy shares at price A, sell at price B (early exit, not waiting for resolution)
- 8.2 Calculate potential profit: `gross_profit = (sell_price - buy_price) × shares`
- 8.3 Fee calculation: `fee = gross_profit × 0.10` (10% on profit)
- 8.4 Net profit: `net_profit = gross_profit - fee`
- 8.5 Minimum profit per share: $0.05 (5¢) after fees
- 8.6 If `(sell_price - buy_price) < 0.055` → SKIP (need 5.5¢+ spread to net 5¢ after 10% fee)
- 8.7 Example: Buy 1000 shares at $0.40, sell at $0.45 → Gross $50 → Fee $5 → Net $45 ✅
- 8.8 Example: Buy 1000 shares at $0.40, sell at $0.44 → Gross $40 → Fee $4 → Net $36 ✅
- 8.9 Example: Buy 1000 shares at $0.40, sell at $0.405 → Gross $5 → Fee $0.50 → Net $4.50 ❌

### 9. Balance Check
**As a trader**, I want to verify sufficient balance before entering a trade, so that I don't attempt trades that will fail.

**Acceptance Criteria:**
- 9.1 Fetch current USDC balance from Simmer API before trade
- 9.2 If balance fetch fails → SKIP trade with reason "Cannot verify balance"
- 9.3 If balance < minimum trade size ($0.50) → SKIP trade with reason "Insufficient balance"
- 9.4 If balance < calculated position size → Reduce position size to available balance
- 9.5 Log current balance in trade decision output

### 10. Position Sizing for Target Profit
**As a trader**, I want to calculate position size to achieve minimum $15 profit target, so that each trade is worth the risk.

**Acceptance Criteria:**
- 10.1 Target profit: $15.00 per trade (net, after fees)
- 10.2 Calculate required shares: `shares = target_profit / net_profit_per_share`
- 10.3 Calculate position size (cost): `position_size = shares × buy_price`
- 10.4 Example: Buy $0.40, sell $0.45 → Net $0.045/share → Need 333 shares → Cost $133.33
- 10.5 Example: Buy $0.40, sell $0.50 → Net $0.09/share → Need 167 shares → Cost $66.67
- 10.6 Cap position size at available balance
- 10.7 Cap position size at configured `max_position` (if set)
- 10.8 If calculated position < minimum ($0.50) → Use minimum
- 10.9 If calculated position > balance → Use full balance (may not hit $15 target)

### 11. Configuration
**As a trader**, I want to configure RSI parameters and profit targets, so that I can tune the strategy to market conditions.

**Acceptance Criteria:**
- 11.1 Config: `rsi_enabled` (bool, default: False)
- 11.2 Config: `rsi_period` (int, default: 7)
- 11.3 Config: `rsi_signal_memory_size` (int, default: 10)
- 11.4 Config: `rsi_require_confirmation` (bool, default: True) - require RSI to confirm momentum
- 11.5 Config: `min_profit_per_share` (float, default: 0.05) - minimum 5¢ net profit per share
- 11.6 Config: `target_profit_per_trade` (float, default: 15.0) - target $15 profit per trade
- 11.7 Config: `max_position_size` (float, default: None) - optional cap on position size
- 11.8 Config: `target_sell_spread` (float, default: 0.05) - target 5¢ spread for exit
- 11.9 Config: `mock_trading` (bool, default: True) - enable mock trading mode (no real trades)
- 11.10 Config: `mock_balance` (float, default: 1000.0) - starting balance for mock trading
- 11.11 All configs accessible via `--set` CLI flag

### 11a. Mock Trading Mode
**As a trader**, I want to test the strategy with mock trades before risking real money, so that I can validate the logic and tune parameters safely.

**Acceptance Criteria:**
- 11a.1 When `mock_trading=True`, all trades are simulated (no real API calls to place orders)
- 11a.2 Mock trades use real market data (prices, spreads, RSI) but simulate execution
- 11a.3 Track mock balance: starts at `mock_balance` (default $1000)
- 11a.4 Deduct position cost from mock balance on entry
- 11a.5 Add proceeds to mock balance on exit
- 11a.6 Mock trades follow same entry/exit logic as real trades
- 11a.7 Mock positions are monitored via real Polymarket WebSocket (real prices)
- 11a.8 Log all mock trades with clear "[MOCK]" prefix
- 11a.9 Track mock trading performance: total trades, wins, losses, P&L, win rate
- 11a.10 Display mock balance and performance summary every 10 trades
- 11a.11 Mock trades respect all entry conditions (spread, RSI, momentum, balance, etc.)
- 11a.12 Mock exit uses real market prices from WebSocket
- 11a.13 Can switch to real trading by setting `mock_trading=False` (requires confirmation)

### 14. Market Discovery and Subscription
**As a trader**, I want the bot to automatically discover 5-minute BTC markets and subscribe to them, so that I can trade continuously without manual intervention.

**Acceptance Criteria:**
- 14.1 Generate market slug from current timestamp: `btc-updown-5m-{rounded_timestamp}`
- 14.2 Round timestamp to nearest 5-minute interval (e.g., 8:26 → 8:25)
- 14.3 Fetch market details from Polymarket Gamma API by slug
- 14.4 Extract market_id and asset_ids (YES/NO token IDs) from API response
- 14.5 Subscribe to Polymarket WebSocket for those asset_ids
- 14.6 Check market every 5 minutes for new trading opportunities
- 14.7 If market doesn't exist yet, wait and retry
- 14.8 If market is resolved, move to next 5-minute window
- 14.9 Handle API errors gracefully (retry with backoff)
- 14.10 Log market discovery: slug, market_id, asset_ids, end_time

### 15. Continuous Trading Loop
**As a trader**, I want the bot to run continuously and trade every 5-minute market during active hours, so that I can maximize trading opportunities.

**Acceptance Criteria:**
- 15.1 Run main loop continuously (24/7 or during configured hours)
- 15.2 Every 5 minutes: discover new market, check entry conditions, execute trade if conditions met
- 15.3 Monitor all open positions in parallel via WebSocket
- 15.4 Exit positions when target profit is reached
- 15.5 Handle multiple concurrent positions (if enabled)
- 15.6 Sleep between iterations to avoid API rate limits
- 15.7 Log all activity with timestamps
- 15.8 Handle keyboard interrupt (Ctrl+C) gracefully - close WebSockets, save mock history
- 15.9 Restart WebSocket connections if they disconnect
- 15.10 Continue trading even if one market fails (don't crash entire bot)

### 16. Continuous Monitoring (Don't Skip Iteration)
**As a trader**, I want the bot to continuously check entry conditions during the wait period, so that I can enter trades as soon as conditions are met.

**Acceptance Criteria:**
- 16.1 Check entry conditions continuously (every 5 seconds) during the wait period
- 16.2 If entry conditions are met at any point, execute trade immediately
- 16.3 After a trade is executed, stop checking entry conditions for that iteration (avoid double entry)
- 16.4 Continue monitoring existing positions even after trade execution
- 16.5 Log position status during the wait period (every 30 seconds)
- 16.6 Check for exit conditions on existing positions continuously
- 16.7 Display clear status: "Checking entry conditions (Xs elapsed)..."
- 16.8 Keep WebSocket connections alive during wait period
- 16.9 Process price updates from Polymarket WebSocket during wait
- 16.10 The main loop should NEVER stop checking - always be ready to trade when conditions are met

### 17. Expired Position Handling
**As a trader**, I want positions that didn't exit before market resolution to be automatically closed as losses, so that my position tracking stays accurate.

**Acceptance Criteria:**
- 17.1 At the start of each iteration, check for expired positions from previous markets
- 17.2 A position is expired if its market's 5-minute window has passed
- 17.3 Expired positions are closed as losses (assume worst case: lost entire position cost)
- 17.4 Update mock balance and stats to reflect the loss
- 17.5 Remove expired positions from tracking
- 17.6 Log each expired position with loss amount
- 17.7 Show updated stats after closing expired positions
- 17.8 Position expiry is determined by market_slug timestamp + 5 minutes
**As a trader**, I want to automatically sell my position when it becomes profitable, so that I can lock in gains without waiting for market resolution.

**Acceptance Criteria:**
- 12.1 After entering a position, subscribe to Polymarket WebSocket for that asset_id
- 12.2 Listen for `price_change` events to get real-time best_bid/best_ask updates
- 12.3 For BUY positions: Monitor best_bid (price you can sell at)
- 12.4 For SELL positions: Monitor best_ask (price you can buy back at)
- 12.5 Calculate current profit: `(current_price - entry_price) × shares - fees`
- 12.6 If current profit ≥ target profit (after fees) → Execute sell order via CLOB API
- 12.7 Target exit spread: configurable (default 5¢ above entry)
- 12.8 Example: Buy 1000 shares at $0.40 → Target sell at $0.45 → Monitor best_bid until ≥ $0.45
- 12.9 Use limit orders for exit (not market orders) to ensure target price
- 12.10 If market resolves before exit target → Accept resolution outcome
- 12.11 Listen for `market_resolved` events to detect early resolution
- 12.12 Log exit reason: "Profit target reached" or "Market resolved"
- 12.13 Track position entry time and exit time for performance analysis

### 13. Position Monitoring (Polymarket WebSocket)
**As a trader**, I want to track all open positions and their current P&L in real-time, so that I know when to exit.

**Acceptance Criteria:**
- 13.1 Store open positions in memory: {market_id, asset_id, side, shares, entry_price, entry_time}
- 13.2 Subscribe to Polymarket WebSocket market channel for position's asset_id
- 13.3 Listen for `price_change` events to get real-time best_bid/best_ask updates
- 13.4 Calculate real-time P&L: `(current_price - entry_price) × shares - fees`
- 13.5 Check exit conditions every time price updates
- 13.6 If multiple positions open → Monitor all simultaneously (subscribe to multiple asset_ids)
- 13.7 If bot restarts → Fetch open positions from Polymarket API
- 13.8 Log position status every 30 seconds: "Position: 1000 shares @ $0.40, current $0.43, P&L: +$27"
- 13.9 Handle WebSocket disconnections and reconnect automatically
- 13.10 Send PING heartbeat every 10 seconds to keep connection alive

## Technical Requirements

### Data Source

#### Binance WebSocket (Real-time Candles for RSI)
- **WebSocket URL:** `wss://stream.binance.com:9443/ws/btcusdt@kline_1m`
- **Symbol:** BTCUSDT (or configurable asset)
- **Interval:** 1m (1-minute candles)
- **Stream Type:** Kline/Candlestick stream
- **Update Frequency:** Real-time (updates every second, finalizes every minute)

#### Polymarket WebSocket (Real-time Market Data for Position Monitoring)
- **WebSocket URL:** `wss://ws-subscriptions-clob.polymarket.com/ws/market`
- **Channel:** Market channel (public, no auth required)
- **Purpose:** Monitor position prices and detect market resolution
- **Heartbeat:** Send PING every 10 seconds, server responds with PONG
- **Custom Features:** Enable `best_bid_ask`, `new_market`, `market_resolved` events

#### Polymarket WebSocket Message Types:
1. **book**: Full orderbook snapshot (on subscribe and after trades)
2. **price_change**: Price level updates (includes best_bid/best_ask)
3. **market_resolved**: Market resolution notification
4. **best_bid_ask**: Best price updates (requires custom_feature_enabled: true)

#### Initial Data (REST API)
- **Binance API:** `/api/v3/klines` - Fetch historical candles on startup (need 20+ candles for RSI calculation)
- **Polymarket API:** `/markets` - Fetch market details and status

#### Binance WebSocket Message Format
```json
{
  "e": "kline",
  "E": 1638747660000,
  "s": "BTCUSDT",
  "k": {
    "t": 1638747600000,  // Kline start time
    "T": 1638747659999,  // Kline close time
    "s": "BTCUSDT",      // Symbol
    "i": "1m",           // Interval
    "f": 100,            // First trade ID
    "L": 200,            // Last trade ID
    "o": "48000.00",     // Open price
    "c": "48100.00",     // Close price (current)
    "h": "48200.00",     // High price
    "l": "47900.00",     // Low price
    "v": "10.5",         // Base asset volume
    "n": 100,            // Number of trades
    "x": false,          // Is this kline closed?
    "q": "504000.00",    // Quote asset volume
    "V": "5.0",          // Taker buy base asset volume
    "Q": "240000.00",    // Taker buy quote asset volume
    "B": "0"             // Ignore
  }
}
```

**Key field:** `k.x` (is kline closed) - only process RSI when `true`

#### Polymarket WebSocket Subscription Format
```json
{
  "assets_ids": ["65818619657568813474341868652308942079804919287380422192892211131408793125422"],
  "type": "market",
  "custom_feature_enabled": true
}
```

#### Polymarket price_change Message Format
```json
{
  "market": "0x5f65177b394277fd294cd75650044e32ba009a95022d88a0c1d565897d72f8f1",
  "price_changes": [
    {
      "asset_id": "71321045679252212594626385532706912750332728571942532289631379312455583992563",
      "price": "0.5",
      "size": "200",
      "side": "BUY",
      "hash": "56621a121a47ed9333273e21c83b660cff37ae50",
      "best_bid": "0.5",
      "best_ask": "1"
    }
  ],
  "timestamp": "1757908892351",
  "event_type": "price_change"
}
```

**Key fields:** `best_bid` (price to sell at), `best_ask` (price to buy at)

### RSI Calculation
```python
# Standard RSI formula
def calculate_rsi(prices, period=7):
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    
    rs = avg_gain / avg_loss if avg_loss != 0 else 0
    rsi = 100 - (100 / (1 + rs))
    return rsi
```

### Signal Classification Logic
```python
def classify_signal(rsi_current, rsi_prev, rsi_prev2):
    # Green: RSI increasing for 2 consecutive periods
    if rsi_current > rsi_prev and rsi_prev > rsi_prev2:
        return "green"
    
    # Red: RSI decreasing for 2 consecutive periods
    if rsi_current < rsi_prev and rsi_prev < rsi_prev2:
        return "red"
    
    # Neutral: mixed signals
    return "neutral"
```

### Entry Logic
```python
def check_rsi_entry_signal(signal_memory, current_rsi_values):
    """
    Check if RSI signals indicate entry.
    
    CRITICAL: current_signal is calculated from FRESH RSI data (last 3 bars),
    NOT from memory. This ensures we're using the most recent RSI values.
    
    Args:
        signal_memory: List of past signals from memory (for historical context)
        current_rsi_values: Fresh RSI calculation - list of RSI values
                           Need at least last 3 values: [rsi_n-2, rsi_n-1, rsi_n]
    """
    # Need at least 2 signals in memory
    if len(signal_memory) < 2:
        return None
    
    # Need at least 3 fresh RSI values to calculate current signal
    if len(current_rsi_values) < 3:
        return None
    
    # Get last 2 signals from memory (for pattern matching)
    signal_1 = signal_memory[-2]  # 2nd most recent (older)
    signal_2 = signal_memory[-1]  # Most recent
    
    # Get last 3 RSI values from FRESH data (not from memory!)
    rsi_2_bars_ago = current_rsi_values[-3]  # 3rd from end
    rsi_1_bar_ago = current_rsi_values[-2]   # 2nd from end
    rsi_current = current_rsi_values[-1]     # Most recent
    
    # Calculate current signal using FRESH RSI data
    # This is the key fix: we use fresh data, not memory
    current_signal = classify_signal(rsi_current, rsi_1_bar_ago, rsi_2_bars_ago)
    
    # Check for BUY: Last 2 memory signals + current = all green
    if signal_1['classification'] == 'green' and \
       signal_2['classification'] == 'green' and \
       current_signal == 'green':
        return "BUY"
    
    # Check for SELL: Last 2 memory signals + current = all red
    if signal_1['classification'] == 'red' and \
       signal_2['classification'] == 'red' and \
       current_signal == 'red':
        return "SELL"
    
    return None  # No clear signal
```

## Integration Points

### 1. Add Binance WebSocket Manager
Location: New class or module for WebSocket handling

```python
import websocket
import json
import threading
from collections import deque

class BinanceRSIStream:
    """
    Manages Binance WebSocket connection for real-time RSI calculation.
    """
    def __init__(self, symbol="BTCUSDT", period=7, buffer_size=20):
        self.symbol = symbol.lower()
        self.period = period
        self.buffer_size = buffer_size
        self.close_prices = deque(maxlen=buffer_size)
        self.rsi_values = deque(maxlen=buffer_size)
        self.ws = None
        self.thread = None
        self.running = False
        
        # Initialize with historical data
        self._fetch_initial_data()
    
    def _fetch_initial_data(self):
        """Fetch historical candles to initialize buffer."""
        url = f"https://api.binance.com/api/v3/klines?symbol={self.symbol.upper()}&interval=1m&limit={self.buffer_size}"
        response = requests.get(url)
        candles = response.json()
        
        # Extract close prices
        for candle in candles:
            close_price = float(candle[4])
            self.close_prices.append(close_price)
        
        # Calculate initial RSI values
        self._recalculate_rsi()
    
    def _recalculate_rsi(self):
        """Recalculate RSI for all prices in buffer."""
        if len(self.close_prices) < self.period + 1:
            return
        
        prices = list(self.close_prices)
        self.rsi_values.clear()
        
        for i in range(self.period, len(prices)):
            rsi = calculate_rsi(prices[:i+1], self.period)
            self.rsi_values.append(rsi)
    
    def _on_message(self, ws, message):
        """Handle incoming WebSocket messages."""
        data = json.loads(message)
        
        # Only process closed candles
        if data['e'] == 'kline' and data['k']['x']:
            close_price = float(data['k']['c'])
            
            # Add to buffer
            self.close_prices.append(close_price)
            
            # Calculate new RSI
            if len(self.close_prices) >= self.period + 1:
                prices = list(self.close_prices)
                rsi = calculate_rsi(prices, self.period)
                self.rsi_values.append(rsi)
                
                # Log new RSI
                print(f"New RSI: {rsi:.2f} (close: ${close_price:.2f})")
    
    def _on_error(self, ws, error):
        """Handle WebSocket errors."""
        print(f"WebSocket error: {error}")
    
    def _on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close."""
        print("WebSocket connection closed")
        self.running = False
    
    def _on_open(self, ws):
        """Handle WebSocket open."""
        print(f"WebSocket connected: {self.symbol}@kline_1m")
        self.running = True
    
    def start(self):
        """Start WebSocket connection in background thread."""
        ws_url = f"wss://stream.binance.com:9443/ws/{self.symbol}@kline_1m"
        
        self.ws = websocket.WebSocketApp(
            ws_url,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
            on_open=self._on_open
        )
        
        self.thread = threading.Thread(target=self.ws.run_forever)
        self.thread.daemon = True
        self.thread.start()
    
    def stop(self):
        """Stop WebSocket connection."""
        self.running = False
        if self.ws:
            self.ws.close()
    
    def get_current_rsi_data(self):
        """
        Get current RSI data for signal classification.
        
        Returns:
            dict with RSI values and classification, or None if insufficient data
        """
        if len(self.rsi_values) < 3:
            return None
        
        # Get last 3 RSI values
        rsi_values_list = list(self.rsi_values)
        rsi_2_bars_ago = rsi_values_list[-3]
        rsi_1_bar_ago = rsi_values_list[-2]
        rsi_current = rsi_values_list[-1]
        
        # Classify current signal
        classification = classify_signal(rsi_current, rsi_1_bar_ago, rsi_2_bars_ago)
        
        return {
            'rsi_values': rsi_values_list,
            'current_rsi': rsi_current,
            'rsi_1_bar_ago': rsi_1_bar_ago,
            'rsi_2_bars_ago': rsi_2_bars_ago,
            'classification': classification,
            'timestamp': datetime.now(timezone.utc)
        }

# Global instance
_binance_rsi_stream = None

def get_binance_rsi(symbol="BTCUSDT", period=7):
    """
    Get current RSI data from WebSocket stream.
    
    Returns:
        dict with RSI values and classification
    """
    global _binance_rsi_stream
    
    # Initialize stream on first call
    if _binance_rsi_stream is None:
        _binance_rsi_stream = BinanceRSIStream(symbol, period)
        _binance_rsi_stream.start()
        
        # Wait for initial data
        import time
        time.sleep(2)
    
    return _binance_rsi_stream.get_current_rsi_data()
```

### 2. Add Polymarket WebSocket Manager
Location: New class for Polymarket market data streaming

```python
import websocket
import json
import threading
import time

class PolymarketPositionMonitor:
    """
    Manages Polymarket WebSocket connection for position monitoring and early exit.
    """
    def __init__(self):
        self.ws = None
        self.thread = None
        self.running = False
        self.positions = {}  # {asset_id: position_data}
        self.callbacks = {}  # {asset_id: callback_function}
        self.subscribed_assets = set()
        
    def _on_message(self, ws, message):
        """Handle incoming WebSocket messages."""
        data = json.loads(message)
        event_type = data.get('event_type')
        
        if event_type == 'book':
            # Full orderbook snapshot
            asset_id = data['asset_id']
            best_bid = data['bids'][0]['price'] if data['bids'] else None
            best_ask = data['asks'][0]['price'] if data['asks'] else None
            
            self._process_price_update(asset_id, best_bid, best_ask)
            
        elif event_type == 'price_change':
            # Price level updates
            for change in data['price_changes']:
                asset_id = change['asset_id']
                best_bid = change.get('best_bid')
                best_ask = change.get('best_ask')
                
                self._process_price_update(asset_id, best_bid, best_ask)
        
        elif event_type == 'market_resolved':
            # Market resolved - close all positions for this market
            market_id = data['market']
            winning_outcome = data.get('winning_outcome')
            
            print(f"Market resolved: {market_id} → {winning_outcome}")
            self._handle_market_resolution(market_id, winning_outcome)
    
    def _process_price_update(self, asset_id, best_bid, best_ask):
        """Process price update and check exit conditions."""
        if asset_id not in self.positions:
            return
        
        position = self.positions[asset_id]
        
        # Determine current price based on position side
        if position['side'] == 'BUY':
            # For BUY positions, we sell at best_bid
            current_price = float(best_bid) if best_bid else None
        else:
            # For SELL positions, we buy back at best_ask
            current_price = float(best_ask) if best_ask else None
        
        if not current_price:
            return
        
        # Calculate current P&L
        entry_price = position['entry_price']
        shares = position['shares']
        
        gross_profit = (current_price - entry_price) * shares
        fee = abs(gross_profit) * 0.10
        net_profit = gross_profit - fee
        
        # Update position
        position['current_price'] = current_price
        position['net_profit'] = net_profit
        
        # Check exit condition
        target_profit = position.get('target_profit', 15.0)
        
        if net_profit >= target_profit:
            print(f"Exit signal: Asset {asset_id} reached target profit ${net_profit:.2f}")
            
            # Call exit callback if registered
            if asset_id in self.callbacks:
                self.callbacks[asset_id](position, 'profit_target')
    
    def _handle_market_resolution(self, market_id, winning_outcome):
        """Handle market resolution event."""
        # Find all positions for this market
        for asset_id, position in list(self.positions.items()):
            if position['market_id'] == market_id:
                print(f"Position closed by resolution: {asset_id}")
                
                # Call exit callback
                if asset_id in self.callbacks:
                    self.callbacks[asset_id](position, 'market_resolved')
                
                # Remove position
                del self.positions[asset_id]
    
    def _on_error(self, ws, error):
        """Handle WebSocket errors."""
        print(f"Polymarket WebSocket error: {error}")
    
    def _on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close."""
        print("Polymarket WebSocket connection closed")
        self.running = False
    
    def _on_open(self, ws):
        """Handle WebSocket open."""
        print("Polymarket WebSocket connected")
        self.running = True
        
        # Subscribe to assets
        if self.subscribed_assets:
            self._send_subscription(list(self.subscribed_assets))
    
    def _send_subscription(self, asset_ids):
        """Send subscription message."""
        subscription = {
            "assets_ids": asset_ids,
            "type": "market",
            "custom_feature_enabled": True  # Enable best_bid_ask, market_resolved
        }
        self.ws.send(json.dumps(subscription))
        print(f"Subscribed to {len(asset_ids)} assets")
    
    def _send_heartbeat(self):
        """Send PING heartbeat every 10 seconds."""
        while self.running:
            time.sleep(10)
            if self.ws and self.running:
                try:
                    self.ws.send("PING")
                except Exception as e:
                    print(f"Heartbeat error: {e}")
    
    def start(self):
        """Start WebSocket connection in background thread."""
        ws_url = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
        
        self.ws = websocket.WebSocketApp(
            ws_url,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
            on_open=self._on_open
        )
        
        # Start WebSocket thread
        self.thread = threading.Thread(target=self.ws.run_forever)
        self.thread.daemon = True
        self.thread.start()
        
        # Start heartbeat thread
        heartbeat_thread = threading.Thread(target=self._send_heartbeat)
        heartbeat_thread.daemon = True
        heartbeat_thread.start()
    
    def stop(self):
        """Stop WebSocket connection."""
        self.running = False
        if self.ws:
            self.ws.close()
    
    def add_position(self, market_id, asset_id, side, shares, entry_price, target_profit=15.0, exit_callback=None):
        """
        Add a position to monitor.
        
        Args:
            market_id: Polymarket market ID
            asset_id: Token ID to monitor
            side: 'BUY' or 'SELL'
            shares: Number of shares
            entry_price: Entry price per share
            target_profit: Target net profit in dollars
            exit_callback: Function to call when exit condition is met
        """
        self.positions[asset_id] = {
            'market_id': market_id,
            'asset_id': asset_id,
            'side': side,
            'shares': shares,
            'entry_price': entry_price,
            'target_profit': target_profit,
            'entry_time': time.time(),
            'current_price': None,
            'net_profit': 0
        }
        
        if exit_callback:
            self.callbacks[asset_id] = exit_callback
        
        # Subscribe to this asset
        self.subscribed_assets.add(asset_id)
        
        if self.running:
            # Dynamic subscription (add to existing)
            subscribe_msg = {
                "type": "subscribe",
                "assets_ids": [asset_id]
            }
            self.ws.send(json.dumps(subscribe_msg))
    
    def remove_position(self, asset_id):
        """Remove a position from monitoring."""
        if asset_id in self.positions:
            del self.positions[asset_id]
        
        if asset_id in self.callbacks:
            del self.callbacks[asset_id]
        
        # Unsubscribe from this asset
        if asset_id in self.subscribed_assets:
            self.subscribed_assets.remove(asset_id)
            
            if self.running:
                unsubscribe_msg = {
                    "type": "unsubscribe",
                    "assets_ids": [asset_id]
                }
                self.ws.send(json.dumps(unsubscribe_msg))
    
    def get_position_status(self, asset_id):
        """Get current status of a position."""
        return self.positions.get(asset_id)

# Global instance
_polymarket_monitor = None

def get_polymarket_monitor():
    """Get or create Polymarket position monitor."""
    global _polymarket_monitor
    
    if _polymarket_monitor is None:
        _polymarket_monitor = PolymarketPositionMonitor()
        _polymarket_monitor.start()
        time.sleep(1)  # Wait for connection
    
    return _polymarket_monitor
```
Location: Global variable or class attribute

```python
_rsi_signal_memory = []  # Stores last N signals
```

### 3. Add Signal Memory
Location: Before trade execution

```python
def calculate_profit_and_position(buy_price, sell_price, target_profit=15.0, min_profit_per_share=0.05):
    """
    Calculate if trade is profitable and determine position size.
    
    Trading model: Buy at buy_price, sell at sell_price (early exit).
    
    Args:
        buy_price: Entry price per share (e.g., 0.40)
        sell_price: Target exit price per share (e.g., 0.45)
        target_profit: Target net profit in dollars (default: $15)
        min_profit_per_share: Minimum net profit per share after fees (default: $0.05)
    
    Returns:
        (shares_needed, net_profit_per_share) or (None, error_message)
    """
    # Calculate profit per share
    gross_profit_per_share = sell_price - buy_price
    
    # Fee is 10% of gross profit
    fee_per_share = gross_profit_per_share * 0.10
    
    # Net profit per share after fees
    net_profit_per_share = gross_profit_per_share - fee_per_share
    
    # Check minimum profit requirement
    if net_profit_per_share < min_profit_per_share:
        return None, f"Profit too small: ${net_profit_per_share:.3f}/share < ${min_profit_per_share:.3f} minimum"
    
    # Calculate shares needed for target profit
    shares_needed = target_profit / net_profit_per_share
    
    # Calculate position size (cost to buy shares)
    position_size = shares_needed * buy_price
    
    return shares_needed, position_size, net_profit_per_share
```

### 4. Add Profit Calculation Function
Location: Before trade execution

```python
def check_balance_and_adjust_position(position_size, min_balance=0.50):
    """Check balance and adjust position size if needed."""
    balance = get_portfolio()['balance_usdc']
    
    if balance < min_balance:
        return None, "Insufficient balance"
    
    if position_size > balance:
        position_size = balance
    
    return position_size, balance
```

### 5. Add Balance Check Function
Location: After market import, before trade execution

```python
def check_market_status(market_id):
    """Verify market is not resolved."""
    market = get_market_details(market_id)
    
    if not market:
        return False, "Cannot fetch market status"
    
    if market.get('resolved', False):
        return False, "Market already resolved"
    
    return True, "Market active"
```

### 6. Add Market Status Check
Location: In `run_fast_market_strategy()`, after momentum check

```python
def check_market_status(market_id):
    """Verify market is not resolved."""
    market = get_market_details(market_id)
    
    if not market:
        return False, "Cannot fetch market status"
    
    if market.get('resolved', False):
        return False, "Market already resolved"
    
    return True, "Market active"
```

### 7. Modify Decision Logic and Add Position Monitoring
Location: In `run_fast_market_strategy()`, after trade execution

```python
# Execute trade (real or mock)
if MOCK_TRADING:
    result = execute_mock_trade(market_id, asset_id, side, position_size, entry_price)
else:
    result = execute_trade(market_id, side, position_size)

if result['success']:
    # Get position details
    asset_id = result['asset_id']  # Token ID from trade result
    shares = result['shares']
    actual_entry_price = result['price']
    
    # Define exit callback
    def on_exit(position, reason):
        """Called when exit condition is met."""
        log(f"Exit triggered: {reason}")
        log(f"  Asset: {position['asset_id']}")
        log(f"  Entry: ${position['entry_price']:.3f}")
        log(f"  Current: ${position['current_price']:.3f}")
        log(f"  Net profit: ${position['net_profit']:.2f}")
        
        # Execute exit trade (real or mock)
        exit_side = 'SELL' if position['side'] == 'BUY' else 'BUY'
        
        if MOCK_TRADING:
            exit_result = execute_mock_exit(
                position=position,
                exit_price=position['current_price']
            )
        else:
            exit_result = execute_trade(
                market_id=position['market_id'],
                side=exit_side,
                size=position['shares'],
                price=position['current_price']  # Limit order at current price
            )
        
        if exit_result['success']:
            log(f"  ✅ Position closed successfully")
            
            # Remove from monitoring
            monitor = get_polymarket_monitor()
            monitor.remove_position(position['asset_id'])
        else:
            log(f"  ❌ Failed to close position: {exit_result['error']}")
    
    # Add position to monitor
    monitor = get_polymarket_monitor()
    monitor.add_position(
        market_id=market_id,
        asset_id=asset_id,
        side=side,
        shares=shares,
        entry_price=actual_entry_price,
        target_profit=TARGET_PROFIT_PER_TRADE,
        exit_callback=on_exit
    )
    
    log(f"  📊 Position added to monitor (target: ${TARGET_PROFIT_PER_TRADE:.2f})")
```

### 8. Add Mock Trading Implementation
Location: New module or section for mock trading

```python
# Mock trading state
_mock_balance = 1000.0
_mock_positions = {}
_mock_trade_history = []
_mock_stats = {
    'total_trades': 0,
    'wins': 0,
    'losses': 0,
    'total_pnl': 0.0,
    'total_fees': 0.0
}

def get_mock_balance():
    """Get current mock balance."""
    return _mock_balance

def execute_mock_trade(market_id, asset_id, side, position_size, entry_price):
    """
    Execute a mock trade (no real API call).
    
    Args:
        market_id: Market ID
        asset_id: Token ID
        side: 'BUY' or 'SELL'
        position_size: Dollar amount to trade
        entry_price: Price per share
    
    Returns:
        dict with success, asset_id, shares, price
    """
    global _mock_balance, _mock_positions, _mock_trade_history, _mock_stats
    
    # Calculate shares
    shares = position_size / entry_price
    cost = shares * entry_price
    
    # Check balance
    if cost > _mock_balance:
        return {
            'success': False,
            'error': f'Insufficient mock balance: ${_mock_balance:.2f} < ${cost:.2f}'
        }
    
    # Deduct from balance
    _mock_balance -= cost
    
    # Create position
    position_id = f"mock_{len(_mock_trade_history)}"
    
    trade_record = {
        'id': position_id,
        'market_id': market_id,
        'asset_id': asset_id,
        'side': side,
        'shares': shares,
        'entry_price': entry_price,
        'cost': cost,
        'entry_time': time.time(),
        'status': 'open'
    }
    
    _mock_positions[asset_id] = trade_record
    _mock_trade_history.append(trade_record)
    _mock_stats['total_trades'] += 1
    
    log(f"[MOCK] Trade executed:")
    log(f"  Side: {side}")
    log(f"  Shares: {shares:.2f}")
    log(f"  Entry price: ${entry_price:.3f}")
    log(f"  Cost: ${cost:.2f}")
    log(f"  Mock balance: ${_mock_balance:.2f}")
    
    return {
        'success': True,
        'asset_id': asset_id,
        'shares': shares,
        'price': entry_price,
        'position_id': position_id
    }

def execute_mock_exit(position, exit_price):
    """
    Execute a mock exit trade.
    
    Args:
        position: Position dict from monitor
        exit_price: Exit price per share
    
    Returns:
        dict with success status
    """
    global _mock_balance, _mock_positions, _mock_stats
    
    asset_id = position['asset_id']
    
    if asset_id not in _mock_positions:
        return {
            'success': False,
            'error': 'Position not found in mock positions'
        }
    
    trade_record = _mock_positions[asset_id]
    
    # Calculate P&L
    entry_price = trade_record['entry_price']
    shares = trade_record['shares']
    
    gross_profit = (exit_price - entry_price) * shares
    fee = abs(gross_profit) * 0.10
    net_profit = gross_profit - fee
    
    # Calculate proceeds
    proceeds = shares * exit_price
    
    # Add to balance
    _mock_balance += proceeds
    
    # Update stats
    if net_profit > 0:
        _mock_stats['wins'] += 1
    else:
        _mock_stats['losses'] += 1
    
    _mock_stats['total_pnl'] += net_profit
    _mock_stats['total_fees'] += fee
    
    # Update trade record
    trade_record['exit_price'] = exit_price
    trade_record['exit_time'] = time.time()
    trade_record['gross_profit'] = gross_profit
    trade_record['fee'] = fee
    trade_record['net_profit'] = net_profit
    trade_record['status'] = 'closed'
    
    # Remove from open positions
    del _mock_positions[asset_id]
    
    log(f"[MOCK] Exit executed:")
    log(f"  Exit price: ${exit_price:.3f}")
    log(f"  Gross profit: ${gross_profit:.2f}")
    log(f"  Fee: ${fee:.2f}")
    log(f"  Net profit: ${net_profit:.2f}")
    log(f"  Mock balance: ${_mock_balance:.2f}")
    
    # Show stats every 10 trades
    if _mock_stats['total_trades'] % 10 == 0:
        show_mock_stats()
    
    return {
        'success': True,
        'net_profit': net_profit
    }

def show_mock_stats():
    """Display mock trading performance summary."""
    total = _mock_stats['total_trades']
    wins = _mock_stats['wins']
    losses = _mock_stats['losses']
    win_rate = (wins / total * 100) if total > 0 else 0
    
    log("\n" + "="*50)
    log("[MOCK] Trading Performance Summary")
    log("="*50)
    log(f"Total trades: {total}")
    log(f"Wins: {wins} | Losses: {losses}")
    log(f"Win rate: {win_rate:.1f}%")
    log(f"Total P&L: ${_mock_stats['total_pnl']:.2f}")
    log(f"Total fees: ${_mock_stats['total_fees']:.2f}")
    log(f"Current balance: ${_mock_balance:.2f}")
    log(f"Starting balance: $1000.00")
    log(f"Net change: ${_mock_balance - 1000:.2f} ({((_mock_balance - 1000) / 1000 * 100):.1f}%)")
    log("="*50 + "\n")

def reset_mock_trading(starting_balance=1000.0):
    """Reset mock trading state."""
    global _mock_balance, _mock_positions, _mock_trade_history, _mock_stats
    
    _mock_balance = starting_balance
    _mock_positions = {}
    _mock_trade_history = []
    _mock_stats = {
        'total_trades': 0,
        'wins': 0,
        'losses': 0,
        'total_pnl': 0.0,
        'total_fees': 0.0
    }
    
    log(f"[MOCK] Trading reset - Starting balance: ${starting_balance:.2f}")

def save_mock_history(filename="mock_trades.json"):
    """Save mock trade history to file."""
    import json
    
    data = {
        'balance': _mock_balance,
        'stats': _mock_stats,
        'history': _mock_trade_history
    }
    
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)
    
    log(f"[MOCK] Trade history saved to {filename}")
```

### 9. Add Market Discovery Functions
Location: New functions for discovering and fetching market details

```python
import requests
from datetime import datetime, timezone
import time

def round_to_5min(timestamp=None):
    """
    Round timestamp to nearest 5-minute interval.
    
    Args:
        timestamp: Unix timestamp (default: current time)
    
    Returns:
        Rounded unix timestamp
    """
    if timestamp is None:
        timestamp = int(time.time())
    
    # Round down to nearest 5 minutes (300 seconds)
    rounded = (timestamp // 300) * 300
    
    return rounded

def generate_market_slug(timestamp=None):
    """
    Generate BTC 5-minute market slug from timestamp.
    
    Args:
        timestamp: Unix timestamp (default: current time)
    
    Returns:
        Market slug (e.g., "btc-updown-5m-1772439600")
    """
    rounded_ts = round_to_5min(timestamp)
    slug = f"btc-updown-5m-{rounded_ts}"
    
    return slug, rounded_ts

def fetch_market_by_slug(slug):
    """
    Fetch market details from Polymarket Gamma API by slug.
    
    Args:
        slug: Market slug (e.g., "btc-updown-5m-1772439600")
    
    Returns:
        dict with market details or None if not found
    """
    url = f"https://gamma-api.polymarket.com/markets?slug={slug}"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if not data or len(data) == 0:
            return None
        
        market = data[0]  # First result
        
        # Extract key fields
        market_info = {
            'market_id': market.get('condition_id'),  # This is the market ID
            'slug': market.get('market_slug'),
            'question': market.get('question'),
            'end_date': market.get('end_date_iso'),
            'closed': market.get('closed', False),
            'resolved': market.get('resolved', False),
            'tokens': []
        }
        
        # Extract token IDs (asset_ids for YES/NO)
        tokens = market.get('tokens', [])
        for token in tokens:
            market_info['tokens'].append({
                'asset_id': token.get('token_id'),
                'outcome': token.get('outcome'),
                'price': float(token.get('price', 0))
            })
        
        return market_info
        
    except requests.exceptions.RequestException as e:
        log(f"Error fetching market by slug: {e}")
        return None

def discover_and_subscribe_market(timestamp=None):
    """
    Discover current 5-minute BTC market and subscribe to WebSocket.
    
    Args:
        timestamp: Unix timestamp (default: current time)
    
    Returns:
        dict with market_info or None if not found
    """
    slug, rounded_ts = generate_market_slug(timestamp)
    
    log(f"🔍 Discovering market: {slug}")
    log(f"   Timestamp: {rounded_ts} ({datetime.fromtimestamp(rounded_ts, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')})")
    
    market_info = fetch_market_by_slug(slug)
    
    if not market_info:
        log(f"   ❌ Market not found")
        return None
    
    log(f"   ✅ Market found:")
    log(f"      Market ID: {market_info['market_id']}")
    log(f"      Question: {market_info['question']}")
    log(f"      End date: {market_info['end_date']}")
    log(f"      Closed: {market_info['closed']}")
    log(f"      Resolved: {market_info['resolved']}")
    
    # Check if market is still active
    if market_info['closed'] or market_info['resolved']:
        log(f"   ⚠️  Market is closed/resolved")
        return None
    
    # Extract asset IDs
    asset_ids = [token['asset_id'] for token in market_info['tokens']]
    log(f"      Asset IDs: {len(asset_ids)} tokens")
    
    for token in market_info['tokens']:
        log(f"         {token['outcome']}: {token['asset_id']} (${token['price']:.3f})")
    
    # Subscribe to WebSocket
    monitor = get_polymarket_monitor()
    
    # Subscribe to all asset IDs for this market (for price monitoring)
    for asset_id in asset_ids:
        # Note: We'll add positions later when we actually trade
        # This just ensures we're subscribed to price updates
        pass
    
    return market_info
```

```python
# Existing momentum check
momentum = get_momentum(ASSET, SIGNAL_SOURCE, LOOKBACK_MINUTES)

# NEW: RSI check (if enabled)
if RSI_ENABLED:
    # Fetch fresh RSI data
    rsi_data = get_binance_rsi(ASSET_SYMBOLS[ASSET], RSI_PERIOD)
    
    if not rsi_data:
        log("  ⚠️  Failed to fetch RSI data, using momentum only")
    else:
        # Store current signal in memory
        _rsi_signal_memory.append({
            'timestamp': rsi_data['timestamp'],
            'rsi': rsi_data['current_rsi'],
            'classification': rsi_data['classification']
        })
        
        # Keep only last N signals
        if len(_rsi_signal_memory) > RSI_SIGNAL_MEMORY_SIZE:
            _rsi_signal_memory.pop(0)
        
        # Check entry signal using memory + fresh RSI data
        rsi_signal = check_rsi_entry_signal(_rsi_signal_memory, rsi_data['rsi_values'])
        
        log(f"  RSI: {rsi_data['current_rsi']:.1f} ({rsi_data['classification']})")
        log(f"  RSI Signal: {rsi_signal or 'NEUTRAL'}")
        
        # Check if RSI confirms momentum
        if RSI_REQUIRE_CONFIRMATION:
            if momentum['direction'] == 'up' and rsi_signal == 'SELL':
                SKIP: "RSI contradicts momentum (momentum UP, RSI SELL)"
            if momentum['direction'] == 'down' and rsi_signal == 'BUY':
                SKIP: "RSI contradicts momentum (momentum DOWN, RSI BUY)"

# NEW: Check profit potential
position_size, net_profit = calculate_profit_and_position(
    buy_price=market_yes_price,
    target_profit=TARGET_PROFIT_PER_TRADE,
    min_profit_per_share=MIN_PROFIT_PER_SHARE
)

if not position_size:
    SKIP: "Profit too small to cover fees"

# NEW: Check balance
position_size, balance = check_balance_and_adjust_position(position_size)

if not position_size:
    SKIP: "Insufficient balance"

log(f"  Balance: ${balance:.2f}")
log(f"  Position size: ${position_size:.2f} (target profit: ${TARGET_PROFIT_PER_TRADE:.2f})")
log(f"  Net profit per share: ${net_profit:.3f}")

# Import market
market_id, error = import_fast_market_market(slug)

# NEW: Check market status
is_active, status_msg = check_market_status(market_id)

if not is_active:
    SKIP: status_msg

# Execute trade
execute_trade(market_id, side, position_size)
```

## Non-Functional Requirements

### Performance
- RSI calculation should complete in < 100ms (in-memory, no API calls)
- WebSocket updates should process in < 50ms
- Initial data fetch (REST API) should complete in < 2 seconds
- No polling needed - WebSocket provides real-time updates

### Reliability
- Handle WebSocket disconnections gracefully (reconnect automatically)
- Handle API failures gracefully (fall back to momentum-only)
- Validate RSI values (0-100 range)
- WebSocket connection should auto-reconnect on network issues
- If WebSocket fails, log error and continue with momentum-only strategy

### Maintainability
- RSI logic should be in separate functions (not mixed with momentum)
- Clear logging of RSI signals for debugging

## Out of Scope

- ❌ Multiple RSI periods (only RSI(7) for now)
- ❌ Other technical indicators (MACD, Bollinger Bands, etc.)
- ❌ Machine learning / adaptive RSI thresholds
- ❌ Backtesting framework

## Success Metrics

- Bot connects to Binance WebSocket successfully
- RSI(7) is calculated in real-time from 1-minute candles
- RSI updates automatically every minute when candle closes
- Signal memory stores last 10 signals correctly
- Entry logic requires 3 consecutive green/red signals
- RSI can be enabled/disabled via config
- When enabled, RSI + momentum both must agree for trade
- WebSocket runs in background without blocking main trading loop
- Market status is verified before every trade
- Minimum 5¢ net profit per share is enforced
- Position size is calculated to target $15 profit
- Balance is checked before every trade
- Trades are skipped if balance is insufficient
- Early exit functionality monitors positions and sells at target profit
- Mock trading mode works correctly with simulated trades
- Mock balance is tracked accurately
- Mock trades use real market prices from WebSocket
- Mock trading stats are displayed every 10 trades
- Can switch between mock and real trading via config

## Example Trade Calculation (Early Exit Model)

### Scenario 1: Good Trade (5¢ spread) - Mock Mode
```
[MOCK] Entry:
Buy price: $0.40
Sell price: $0.45 (target exit)
Shares: 333

Cost: 333 × $0.40 = $133.33
Mock balance before: $1000.00
Mock balance after: $866.67

[MOCK] Monitoring via WebSocket:
Current price: $0.41 → P&L: +$3.00 (not yet at target)
Current price: $0.43 → P&L: +$9.00 (not yet at target)
Current price: $0.45 → P&L: +$15.00 ✅ (target reached!)

[MOCK] Exit:
Exit price: $0.45
Gross profit: ($0.45 - $0.40) × 333 = $16.65
Fee (10%): $1.67
Net profit: $15.00 ✅

Proceeds: 333 × $0.45 = $149.85
Mock balance after: $866.67 + $149.85 = $1016.52

[MOCK] Stats:
Total trades: 1
Wins: 1 | Losses: 0
Win rate: 100%
Total P&L: +$15.00
Current balance: $1016.52
```

### Scenario 2: Better Trade (10¢ spread) - Mock Mode
```
Buy price: $0.40
Sell price: $0.50 (target exit)
Shares: 167

Gross profit: ($0.50 - $0.40) × 167 = $16.70
Fee (10%): $1.67
Net profit: $15.00 ✅

Position cost: 167 × $0.40 = $66.80
Mock balance: $1016.52 - $66.80 = $949.72

Exit proceeds: 167 × $0.50 = $83.50
Mock balance after: $949.72 + $83.50 = $1033.22
```

### Scenario 3: Marginal Trade (Too Small Spread)
```
Buy price: $0.40
Sell price: $0.405 (only 0.5¢ spread)
Shares: 1000

Gross profit: ($0.405 - $0.40) × 1000 = $5.00
Fee (10%): $5.00 × 0.10 = $0.50
Net profit: $5.00 - $0.50 = $4.50

Net profit per share: $0.0045 ❌ (< 5¢ minimum)

→ SKIP: "Profit too small to cover fees"
```

### Scenario 4: Insufficient Balance (Mock)
```
Buy price: $0.40
Sell price: $0.50
Net profit per share: $0.09 ✅

For $15 target:
Required shares: 167
Position size: $66.67

Mock balance check: $50.00 available ⚠️
Adjusted shares: $50.00 / $0.40 = 125 shares
Expected profit: 125 × $0.09 = $11.25 (< $15 target, but still profitable)

→ TRADE with reduced position (mock)
```

### Scenario 5: Market Already Resolved
```
All checks pass ✅
Market import successful ✅
Market status check: RESOLVED ❌

→ SKIP: "Market already resolved"
```

### Mock Trading Performance Summary (After 10 Trades)
```
==================================================
[MOCK] Trading Performance Summary
==================================================
Total trades: 10
Wins: 7 | Losses: 3
Win rate: 70.0%
Total P&L: $45.00
Total fees: $15.00
Current balance: $1045.00
Starting balance: $1000.00
Net change: +$45.00 (+4.5%)
==================================================
```

## Dependencies

- Existing: Binance API access (already used for momentum)
- New: `websocket-client` library for Binance and Polymarket WebSocket connections
- New: NumPy (for RSI calculation) - optional, can use pure Python
- New: Threading for background WebSocket management
- New: JSON for mock trade persistence (optional)

**Installation:**
```bash
pip install websocket-client numpy
```

## Questions / Decisions Needed

1. **Should RSI be required or optional?**
   - Recommendation: Optional (default OFF) - let users test before enabling

2. **What if RSI and momentum disagree?**
   - Recommendation: SKIP trade (conservative approach)

3. **Should we store signals to file for analysis?**
   - Recommendation: No (keep it simple, in-memory only)

4. **Should we add RSI overbought/oversold levels (30/70)?**
   - Recommendation: No (focus on momentum direction, not levels)

5. **How to handle insufficient data (< 7 candles)?**
   - Recommendation: Skip RSI check, use momentum only

## Next Steps

1. Review and approve requirements
2. Create design document with detailed implementation plan
3. Break down into implementation tasks
4. Implement RSI calculation function
5. Implement signal memory
6. Integrate with existing strategy
7. Test with paper trading
8. Deploy to live trading (if successful)
