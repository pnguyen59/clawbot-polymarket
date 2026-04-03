"""
Configuration management for the trading bot.
"""

import os
import json
from typing import Dict, Any

# Default configuration
CONFIG: Dict[str, Any] = {
    # Trading parameters
    'target_profit_per_trade': 15.0,
    'min_profit_per_share': 0.05,
    'max_position_size': 100.0,
    'target_sell_spread': 0.06,
    
    # RSI settings
    'rsi_enabled': True,
    'rsi_period': 7,
    'rsi_signal_memory_size': 10,
    'rsi_require_confirmation': True,
    
    # Momentum settings
    'min_momentum_pct': 0.1,
    'lookback_minutes': 5,
    
    # Execution settings
    'dry_run': False,
    'tick_size': "0.01",
    'neg_risk': False,
    
    # Position limits
    'max_open_positions': 1,
}

# API endpoints
CLOB_HOST = "https://clob.polymarket.com"
GAMMA_API_HOST = "https://gamma-api.polymarket.com"
POLYMARKET_WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
BINANCE_WS_URL = "wss://stream.binance.com:9443/ws"

# Chain config
CHAIN_ID = 137  # Polygon
SIGNATURE_TYPE = 1  # POLY_PROXY

# Side constants
BUY = "BUY"
SELL = "SELL"


def load_config(filepath: str = None) -> Dict[str, Any]:
    """Load configuration from file or environment."""
    config = CONFIG.copy()
    
    # Load from file if provided
    if filepath and os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f:
                file_config = json.load(f)
                config.update(file_config)
        except Exception as e:
            print(f"Warning: Could not load config from {filepath}: {e}")
    
    # Override from environment
    env_mappings = {
        'TRADING_TARGET_PROFIT': ('target_profit_per_trade', float),
        'TRADING_MAX_POSITION': ('max_position_size', float),
        'TRADING_MIN_MOMENTUM': ('min_momentum_pct', float),
        'TRADING_RSI_ENABLED': ('rsi_enabled', lambda x: x.lower() == 'true'),
        'TRADING_DRY_RUN': ('dry_run', lambda x: x.lower() == 'true'),
    }
    
    for env_key, (config_key, converter) in env_mappings.items():
        if env_key in os.environ:
            try:
                config[config_key] = converter(os.environ[env_key])
            except:
                pass
    
    return config


def update_config(**kwargs):
    """Update configuration values."""
    for key, value in kwargs.items():
        if key in CONFIG:
            CONFIG[key] = value
