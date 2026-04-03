"""
Trading Bot Components for Polymarket

Modules:
- config: Configuration management
- logger: Logging utilities
- rsi: RSI calculation and Binance stream
- monitor: Polymarket position monitoring
- client: Polymarket trading client
- market: Market discovery and momentum
- strategy: Trading decision logic
"""

from .config import CONFIG, load_config
from .logger import log
from .client import PolymarketTrader
from .rsi import BinanceRSIStream, calculate_rsi, get_rsi_signal
from .monitor import PolymarketPositionMonitor
from .market import discover_current_market, check_momentum
from .strategy import make_trading_decision, calculate_position_size

__all__ = [
    'CONFIG',
    'load_config',
    'log',
    'PolymarketTrader',
    'BinanceRSIStream',
    'calculate_rsi',
    'get_rsi_signal',
    'PolymarketPositionMonitor',
    'discover_current_market',
    'check_momentum',
    'make_trading_decision',
    'calculate_position_size',
]
