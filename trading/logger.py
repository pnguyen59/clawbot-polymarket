"""
Logging utilities for the trading bot.
"""

from datetime import datetime, timezone

# Log level prefixes
PREFIXES = {
    'info': '📋',
    'trade': '💰',
    'exit': '🚪',
    'signal': '📊',
    'position': '📈',
    'rsi': '📉',
    'websocket': '🔌',
    'warn': '⚠️',
    'error': '❌',
    'success': '✅',
}


def log(message: str, level: str = 'info'):
    """
    Log a message with timestamp and emoji prefix.
    
    Args:
        message: The message to log
        level: Log level (info, trade, exit, signal, position, rsi, websocket, warn, error, success)
    """
    timestamp = datetime.now(timezone.utc).strftime('%H:%M:%S')
    prefix = PREFIXES.get(level, '📋')
    print(f"[{timestamp}] {prefix} {message}")


def log_trade(message: str):
    """Log a trade message."""
    log(message, 'trade')


def log_exit(message: str):
    """Log an exit message."""
    log(message, 'exit')


def log_position(message: str):
    """Log a position message."""
    log(message, 'position')


def log_rsi(message: str):
    """Log an RSI message."""
    log(message, 'rsi')


def log_websocket(message: str):
    """Log a websocket message."""
    log(message, 'websocket')


def log_warn(message: str):
    """Log a warning message."""
    log(message, 'warn')


def log_error(message: str):
    """Log an error message."""
    log(message, 'error')
