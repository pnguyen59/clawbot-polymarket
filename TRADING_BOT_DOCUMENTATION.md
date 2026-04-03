# Real Trading Bot Documentation

## Overview

A real trading bot for Polymarket BTC 5-minute up/down markets. Uses RSI signals from Binance combined with price momentum to make trading decisions, with real-time position monitoring via WebSocket.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        real_trader.py                           │
│                      (Main Entry Point)                         │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│  trading/     │    │  trading/     │    │  trading/     │
│  rsi.py       │    │  monitor.py   │    │  client.py    │
│               │    │               │    │               │
│ Binance WS    │    │ Polymarket WS │    │ CLOB API      │
│ RSI Stream    │    │ Price Monitor │    │ Order Exec    │
└───────────────┘    └───────────────┘    └───────────────┘
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│ Binance API   │    │ Polymarket    │    │ Polymarket    │
│ WebSocket     │    │ WebSocket     │    │ CLOB REST API │
└───────────────┘    └───────────────┘    └───────────────┘
```

## Module Structure

```
trading/
├── __init__.py      # Package exports
├── config.py        # Configuration & constants
├── logger.py        # Logging utilities
├── rsi.py           # RSI calculation & Binance WebSocket
├── monitor.py       # Polymarket position monitor WebSocket
├── client.py        # Polymarket trading client (order execution)
├── market.py        # Market discovery & momentum analysis
└── strategy.py      # Trading decision logic

real_trader.py       # Main entry point
```

## Data Flow

### 1. Startup Flow

```
main()
  │
  ├─► Parse CLI arguments
  ├─► Update CONFIG
  ├─► Initialize PolymarketTrader (client.py)
  │     └─► Derive API credentials
  │     └─► Reinitialize with credentials
  ├─► Check USDC balance
  └─► run_main_loop()
```

### 2. Main Loop Flow

```
run_main_loop()
  │
  ├─► Initialize WebSocket connections:
  │     ├─► BinanceRSIStream (rsi.py)
  │     │     └─► Fetch 20 historical candles
  │     │     └─► Calculate initial RSI
  │     │     └─► Start WebSocket for real-time updates
  │     │
  │     └─► PolymarketPositionMonitor (monitor.py)
  │           └─► Start WebSocket for price updates
  │
  └─► LOOP (every 5 minutes):
        │
        ├─► Calculate sleep until next 5-min interval
        │
        └─► INNER LOOP (every 5 seconds):
              │
              ├─► run_trading_iteration()
              │     ├─► discover_current_market()
              │     ├─► Get RSI data from stream
              │     ├─► make_trading_decision()
              │     └─► execute_trade() if signal
              │
              ├─► update_position_prices()
              │     └─► Sync from WebSocket monitor
              │     └─► Check exit conditions
              │
              └─► log_position_status() (every 30s)
```

## Trading Decision Flow

### make_trading_decision() in strategy.py

```
┌─────────────────────────────────────────────────────────────┐
│                  TRADING DECISION FLOW                       │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │ Check 1: Market Status │
              │ - Is market active?    │
              │ - Not closed/resolved? │
              └───────────────────────┘
                          │ PASS
                          ▼
              ┌───────────────────────┐
              │ Check 2: Position Limit│
              │ - < max_open_positions │
              └───────────────────────┘
                          │ PASS
                          ▼
              ┌───────────────────────┐
              │ Check 3: Momentum      │
              │ - Fetch from Binance   │
              │ - |momentum| >= 0.1%   │
              │ - Direction: up/down   │
              └───────────────────────┘
                          │ PASS
                          ▼
              ┌───────────────────────┐
              │ Check 4: RSI Signal    │
              │ - 3 consecutive green  │
              │   → BUY signal         │
              │ - 3 consecutive red    │
              │   → SELL signal        │
              │ - Must confirm momentum│
              └───────────────────────┘
                          │ PASS
                          ▼
              ┌───────────────────────┐
              │ Fetch Market Price     │
              │ - /price endpoint      │
              │ - Real orderbook price │
              └───────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │ Check 5: Position Size │
              │ - Calculate shares     │
              │ - Cap exit at $0.99    │
              │ - Check min profit     │
              └───────────────────────┘
                          │ PASS
                          ▼
              ┌───────────────────────┐
              │    TRADE SIGNAL        │
              │ Return decision dict   │
              └───────────────────────┘
```

## RSI Signal Logic

### Signal Classification (rsi.py)

```python
def classify_signal(rsi_current, rsi_prev, rsi_prev2):
    # GREEN: RSI increasing for 2 consecutive periods
    if rsi_current > rsi_prev and rsi_prev > rsi_prev2:
        return 'green'
    
    # RED: RSI decreasing for 2 consecutive periods
    if rsi_current < rsi_prev and rsi_prev < rsi_prev2:
        return 'red'
    
    return 'neutral'
```

### Entry Signal (RSISignalMemory)

```
Signal Memory: [signal_1, signal_2, ..., signal_n]

BUY Signal:
  - signal[-2] = 'green'
  - signal[-1] = 'green'  
  - current   = 'green'
  → 3 consecutive green = BUY

SELL Signal:
  - signal[-2] = 'red'
  - signal[-1] = 'red'
  - current   = 'red'
  → 3 consecutive red = SELL

NEUTRAL:
  - Any other combination
  → SKIP trade (when rsi_require_confirmation=True)
```

### RSI + Momentum Confirmation

```
Momentum UP + RSI BUY   → ✅ Trade YES token
Momentum UP + RSI SELL  → ❌ Skip (conflict)
Momentum UP + RSI NEUTRAL → ❌ Skip

Momentum DOWN + RSI SELL → ✅ Trade NO token
Momentum DOWN + RSI BUY  → ❌ Skip (conflict)
Momentum DOWN + RSI NEUTRAL → ❌ Skip
```

## Order Execution Flow

### execute_trade() in real_trader.py

```
execute_trade(decision)
  │
  ├─► Check USDC balance
  │
  ├─► place_market_order(token_id, BUY, position_size)
  │     │
  │     ├─► Create MarketOrderArgs
  │     ├─► client.create_market_order()
  │     └─► client.post_order(orderType=FOK)
  │
  ├─► Get shares from response.takingAmount
  │
  ├─► Track position in _open_positions
  │
  └─► Add to PolymarketPositionMonitor
        └─► Subscribe to WebSocket for price updates
```

## Position Monitoring Flow

### PolymarketPositionMonitor (monitor.py)

```
WebSocket Connection: wss://ws-subscriptions-clob.polymarket.com/ws/market

Message Types:
  │
  ├─► 'book' - Full orderbook snapshot
  │     └─► Extract best_bid, best_ask
  │
  ├─► 'price_change' - Price level updates
  │     └─► Extract best_bid, best_ask
  │
  └─► 'market_resolved' - Market resolution
        └─► Close all positions for market

_process_price_update(asset_id, best_bid, best_ask):
  │
  ├─► Calculate P&L:
  │     current_price = best_bid (sell price)
  │     gross_profit = (current_price - entry_price) × shares
  │     fee = gross_profit × 0.10 (if profit > 0)
  │     net_profit = gross_profit - fee
  │
  └─► If net_profit >= target_profit:
        └─► Trigger exit_callback(position, 'profit_target')
```

## Exit Execution Flow

### execute_exit() in real_trader.py

```
execute_exit(position, reason)
  │
  ├─► Extract asset_id, shares from position
  │
  ├─► Log exit details:
  │     - Token ID
  │     - Entry price → Current price
  │     - P&L
  │
  ├─► wait_for_token_balance(asset_id, shares)
  │     └─► Retry up to 5 times (3s delay)
  │
  ├─► place_market_order(asset_id, SELL, actual_shares)
  │
  └─► Remove from tracking:
        ├─► _open_positions.pop(asset_id)
        └─► _polymarket_monitor.remove_position(asset_id)
```

## Configuration

### Default CONFIG (config.py)

```python
CONFIG = {
    # Trading parameters
    'target_profit_per_trade': 15.0,   # Target $15 profit
    'min_profit_per_share': 0.05,      # Min 5¢ per share
    'max_position_size': 100.0,        # Max $100 position
    'target_sell_spread': 0.06,        # Target 6¢ spread
    
    # RSI settings
    'rsi_enabled': True,
    'rsi_period': 7,
    'rsi_signal_memory_size': 10,
    'rsi_require_confirmation': True,  # RSI must confirm momentum
    
    # Momentum settings
    'min_momentum_pct': 0.1,           # Min 0.1% momentum
    'lookback_minutes': 5,
    
    # Execution
    'dry_run': False,
    'tick_size': "0.01",
    'neg_risk': False,
    'max_open_positions': 1,
}
```

### CLI Arguments

```bash
python real_trader.py [options]

Options:
  --dry-run              Simulate without executing
  --target-profit FLOAT  Target profit per trade (default: 15.0)
  --max-position FLOAT   Max position size (default: 100.0)
  --no-rsi               Disable RSI confirmation
  --min-momentum FLOAT   Min momentum percent (default: 0.1)
```

## API Endpoints Used

### Polymarket CLOB API

| Endpoint | Purpose |
|----------|---------|
| `/price?token_id=X&side=BUY` | Get market buy price |
| `/price?token_id=X&side=SELL` | Get market sell price |
| `/book?token_id=X` | Get full orderbook |
| POST order | Execute market order |

### Polymarket Gamma API

| Endpoint | Purpose |
|----------|---------|
| `/markets?slug=X` | Discover market by slug |

### Binance API

| Endpoint | Purpose |
|----------|---------|
| `/api/v3/klines` | Historical candles for RSI |
| WebSocket `btcusdt@kline_1m` | Real-time 1-min candles |

## Position Sizing Formula

```
entry_price = market ask price (from /price endpoint)
exit_price = min(entry_price + target_spread, 0.99)  # Cap at $0.99
actual_spread = exit_price - entry_price

gross_profit_per_share = actual_spread
fee_per_share = gross_profit_per_share × 0.10
net_profit_per_share = gross_profit_per_share - fee_per_share

shares_needed = target_profit / net_profit_per_share
position_size = shares_needed × entry_price

# Apply caps
if position_size > max_position_size:
    position_size = max_position_size
    shares_needed = position_size / entry_price
```

## Error Handling

- WebSocket auto-reconnect with exponential backoff
- API request retries
- Balance verification before trade
- Token balance wait with retries before sell
- Graceful shutdown on Ctrl+C

## Example Trade Flow

```
1. Bot starts, connects to WebSockets
2. Every 5 seconds, checks entry conditions
3. Momentum: BTC +0.15% (UP direction)
4. RSI: 3 consecutive green signals → BUY
5. Fetch YES token price: $0.45 (ask)
6. Calculate: need 370 shares for $15 profit
7. Execute BUY: $166.50 position
8. Monitor via WebSocket
9. Price rises to $0.51 (bid)
10. P&L = (0.51 - 0.45) × 370 - fee = $19.98
11. Target hit! Execute SELL
12. Position closed with profit
```
