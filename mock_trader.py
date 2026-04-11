#!/usr/bin/env python3
"""
Mock Trading Bot for RSI Signal Enhancement

A mock trading bot that tests RSI signals with WebSocket integration
for Polymarket BTC 5-minute fast markets.

Usage:
    python mock_trader.py [options]

Options:
    --mock / --no-mock          Enable/disable mock trading mode (default: True)
    --rsi-enabled / --no-rsi    Enable/disable RSI signal confirmation (default: False)
    --target-profit FLOAT       Target profit per trade in dollars (default: 15.0)
    --mock-balance FLOAT        Starting balance for mock trading (default: 1000.0)
    --rsi-period INT            RSI calculation period (default: 7)
    --min-profit-per-share FLOAT  Minimum profit per share after fees (default: 0.05)
    --max-position-size FLOAT   Maximum position size cap (default: None)
    --config FILE               Load configuration from JSON file
    --help                      Show this help message
"""

import sys
import time
import json
import argparse
import threading
from datetime import datetime, timezone
from collections import deque
import numpy as np
import websocket
import requests


# ============================================================================
# API Constants
# ============================================================================

CLOB_HOST = "https://clob.polymarket.com"


# ============================================================================
# Retry Utility with Exponential Backoff
# ============================================================================

def retry_with_backoff(func, max_retries=3, base_delay=1.0, max_delay=30.0, 
                       exceptions=(requests.exceptions.RequestException,)):
    """
    Retry a function with exponential backoff on failure.
    
    This utility wraps any function and retries it on specified exceptions
    using exponential backoff to avoid overwhelming the server.
    
    Args:
        func: Callable to execute (should be a lambda or function with no args)
        max_retries: Maximum number of retry attempts (default: 3)
        base_delay: Base delay in seconds (default: 1.0)
        max_delay: Maximum delay in seconds (default: 30.0)
        exceptions: Tuple of exception types to catch and retry (default: RequestException)
    
    Returns:
        The return value of func if successful
    
    Raises:
        The last exception if all retries fail
    
    Examples:
        >>> # Retry an API call
        >>> result = retry_with_backoff(
        ...     lambda: requests.get("https://api.example.com/data", timeout=10),
        ...     max_retries=3
        ... )
        
        >>> # Retry with custom exceptions
        >>> result = retry_with_backoff(
        ...     lambda: some_function(),
        ...     exceptions=(ValueError, ConnectionError)
        ... )
    """
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            return func()
        except exceptions as e:
            last_exception = e
            
            if attempt < max_retries:
                # Calculate delay with exponential backoff
                delay = min(base_delay * (2 ** attempt), max_delay)
                print(f"[Retry] Attempt {attempt + 1}/{max_retries + 1} failed: {e}")
                print(f"[Retry] Retrying in {delay:.1f} seconds...")
                time.sleep(delay)
            else:
                print(f"[Retry] All {max_retries + 1} attempts failed. Last error: {e}")
    
    # Re-raise the last exception if all retries failed
    raise last_exception


def api_request_with_retry(url, params=None, timeout=10, max_retries=3):
    """
    Make an API GET request with automatic retry on failure.
    
    Convenience wrapper around retry_with_backoff for HTTP GET requests.
    
    Args:
        url: URL to request
        params: Optional query parameters dict
        timeout: Request timeout in seconds (default: 10)
        max_retries: Maximum number of retry attempts (default: 3)
    
    Returns:
        requests.Response object if successful
    
    Raises:
        requests.exceptions.RequestException: If all retries fail
    
    Examples:
        >>> response = api_request_with_retry(
        ...     "https://api.binance.com/api/v3/klines",
        ...     params={'symbol': 'BTCUSDT', 'interval': '1m', 'limit': 20}
        ... )
        >>> data = response.json()
    """
    def make_request():
        response = requests.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        return response
    
    return retry_with_backoff(
        make_request,
        max_retries=max_retries,
        exceptions=(requests.exceptions.RequestException,)
    )


# ============================================================================
# Configuration Schema and Defaults
# ============================================================================

# Configuration schema with type information and validation
CONFIG_SCHEMA = {
    # RSI Configuration
    'rsi_enabled': {
        'type': bool,
        'default': False,
        'description': 'Enable RSI signal confirmation',
        'cli_flag': '--rsi-enabled',
        'cli_flag_negative': '--no-rsi',
    },
    'rsi_period': {
        'type': int,
        'default': 7,
        'description': 'RSI calculation period (number of bars)',
        'cli_flag': '--rsi-period',
        'min': 2,
        'max': 50,
    },
    'rsi_signal_memory_size': {
        'type': int,
        'default': 10,
        'description': 'Number of RSI signals to store in memory',
        'cli_flag': '--rsi-memory-size',
        'min': 2,
        'max': 100,
    },
    'rsi_require_confirmation': {
        'type': bool,
        'default': True,
        'description': 'Require RSI to confirm momentum signals',
        'cli_flag': '--rsi-require-confirmation',
        'cli_flag_negative': '--no-rsi-confirmation',
    },
    
    # Momentum Configuration
    'min_momentum_pct': {
        'type': float,
        'default': 0.1,
        'description': 'Minimum momentum percentage to trigger trade',
        'cli_flag': '--min-momentum',
        'min': 0.0,
        'max': 10.0,
    },
    
    # Profit Configuration
    'min_profit_per_share': {
        'type': float,
        'default': 0.05,
        'description': 'Minimum net profit per share after fees (in dollars)',
        'cli_flag': '--min-profit-per-share',
        'min': 0.01,
        'max': 1.0,
    },
    'target_profit_per_trade': {
        'type': float,
        'default': 15.0,
        'description': 'Target net profit per trade (in dollars)',
        'cli_flag': '--target-profit',
        'min': 1.0,
        'max': 1000.0,
    },
    'max_position_size': {
        'type': float,
        'default': None,
        'description': 'Maximum position size cap (None = no cap)',
        'cli_flag': '--max-position-size',
        'min': 0.5,
        'max': 100000.0,
        'nullable': True,
    },
    'target_sell_spread': {
        'type': float,
        'default': 0.06,
        'description': 'Target spread for exit (need 5.56¢+ for 5¢ net after 10% fee)',
        'cli_flag': '--target-spread',
        'min': 0.01,
        'max': 0.50,
    },
    
    # Mock Trading Configuration
    'mock_trading': {
        'type': bool,
        'default': True,
        'description': 'Enable mock trading mode (no real trades)',
        'cli_flag': '--mock',
        'cli_flag_negative': '--no-mock',
    },
    'mock_balance': {
        'type': float,
        'default': 1000.0,
        'description': 'Starting balance for mock trading (in dollars)',
        'cli_flag': '--mock-balance',
        'min': 1.0,
        'max': 1000000.0,
    },
}


def get_default_config():
    """
    Get default configuration values from schema.
    
    Returns:
        dict: Configuration dictionary with default values
    """
    return {key: schema['default'] for key, schema in CONFIG_SCHEMA.items()}


def validate_config_value(key, value):
    """
    Validate a configuration value against its schema.
    
    Args:
        key: Configuration key
        value: Value to validate
    
    Returns:
        tuple: (is_valid, error_message or None)
    
    Raises:
        KeyError: If key is not in schema
    """
    if key not in CONFIG_SCHEMA:
        return False, f"Unknown configuration key: {key}"
    
    schema = CONFIG_SCHEMA[key]
    expected_type = schema['type']
    
    # Handle None values for nullable fields
    if value is None:
        if schema.get('nullable', False):
            return True, None
        else:
            return False, f"{key} cannot be None"
    
    # Type check
    if not isinstance(value, expected_type):
        # Allow int for float fields
        if expected_type == float and isinstance(value, int):
            value = float(value)
        else:
            return False, f"{key} must be {expected_type.__name__}, got {type(value).__name__}"
    
    # Range check for numeric types
    if expected_type in (int, float):
        if 'min' in schema and value < schema['min']:
            return False, f"{key} must be >= {schema['min']}, got {value}"
        if 'max' in schema and value > schema['max']:
            return False, f"{key} must be <= {schema['max']}, got {value}"
    
    return True, None


def validate_config(config):
    """
    Validate entire configuration dictionary.
    
    Args:
        config: Configuration dictionary to validate
    
    Returns:
        tuple: (is_valid, list of error messages)
    """
    errors = []
    
    for key, value in config.items():
        is_valid, error = validate_config_value(key, value)
        if not is_valid:
            errors.append(error)
    
    return len(errors) == 0, errors


def load_config_from_file(filepath):
    """
    Load configuration from a JSON file.
    
    Args:
        filepath: Path to JSON configuration file
    
    Returns:
        dict: Configuration dictionary
    
    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file is not valid JSON
        ValueError: If configuration values are invalid
    """
    with open(filepath, 'r') as f:
        file_config = json.load(f)
    
    # Start with defaults
    config = get_default_config()
    
    # Override with file values
    for key, value in file_config.items():
        if key in CONFIG_SCHEMA:
            config[key] = value
        else:
            print(f"Warning: Unknown config key '{key}' in {filepath}, ignoring")
    
    # Validate
    is_valid, errors = validate_config(config)
    if not is_valid:
        raise ValueError(f"Invalid configuration: {'; '.join(errors)}")
    
    return config


def save_config_to_file(config, filepath):
    """
    Save configuration to a JSON file.
    
    Args:
        config: Configuration dictionary
        filepath: Path to save JSON file
    """
    with open(filepath, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"Configuration saved to {filepath}")


def create_argument_parser():
    """
    Create argument parser with all configuration options.
    
    Returns:
        argparse.ArgumentParser: Configured argument parser
    """
    parser = argparse.ArgumentParser(
        description='Mock Trading Bot for RSI Signal Enhancement',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default settings (mock trading enabled)
  python mock_trader.py

  # Run with RSI enabled and custom target profit
  python mock_trader.py --rsi-enabled --target-profit 20.0

  # Run with custom mock balance
  python mock_trader.py --mock-balance 5000.0

  # Load configuration from file
  python mock_trader.py --config my_config.json

  # Disable mock trading (CAUTION: real trades!)
  python mock_trader.py --no-mock
        """
    )
    
    # Mock trading flags (mutually exclusive)
    mock_group = parser.add_mutually_exclusive_group()
    mock_group.add_argument(
        '--mock',
        action='store_true',
        dest='mock_trading',
        default=None,
        help='Enable mock trading mode (default: True)'
    )
    mock_group.add_argument(
        '--no-mock',
        action='store_false',
        dest='mock_trading',
        help='Disable mock trading mode (CAUTION: real trades!)'
    )
    
    # RSI enabled flags (mutually exclusive)
    rsi_group = parser.add_mutually_exclusive_group()
    rsi_group.add_argument(
        '--rsi-enabled',
        action='store_true',
        dest='rsi_enabled',
        default=None,
        help='Enable RSI signal confirmation (default: False)'
    )
    rsi_group.add_argument(
        '--no-rsi',
        action='store_false',
        dest='rsi_enabled',
        help='Disable RSI signal confirmation'
    )
    
    # Target profit
    parser.add_argument(
        '--target-profit',
        type=float,
        dest='target_profit_per_trade',
        default=None,
        metavar='DOLLARS',
        help='Target profit per trade in dollars (default: 15.0)'
    )
    
    # Mock balance
    parser.add_argument(
        '--mock-balance',
        type=float,
        dest='mock_balance',
        default=None,
        metavar='DOLLARS',
        help='Starting balance for mock trading (default: 1000.0)'
    )
    
    # RSI period
    parser.add_argument(
        '--rsi-period',
        type=int,
        dest='rsi_period',
        default=None,
        metavar='BARS',
        help='RSI calculation period (default: 7)'
    )
    
    # Min profit per share
    parser.add_argument(
        '--min-profit-per-share',
        type=float,
        dest='min_profit_per_share',
        default=None,
        metavar='DOLLARS',
        help='Minimum profit per share after fees (default: 0.05)'
    )
    
    # Max position size
    parser.add_argument(
        '--max-position-size',
        type=float,
        dest='max_position_size',
        default=None,
        metavar='DOLLARS',
        help='Maximum position size cap (default: None/unlimited)'
    )
    
    # Target spread
    parser.add_argument(
        '--target-spread',
        type=float,
        dest='target_sell_spread',
        default=None,
        metavar='DOLLARS',
        help='Target spread for exit (default: 0.06)'
    )
    
    # RSI memory size
    parser.add_argument(
        '--rsi-memory-size',
        type=int,
        dest='rsi_signal_memory_size',
        default=None,
        metavar='COUNT',
        help='Number of RSI signals to store in memory (default: 10)'
    )
    
    # Min momentum
    parser.add_argument(
        '--min-momentum',
        type=float,
        dest='min_momentum_pct',
        default=None,
        metavar='PERCENT',
        help='Minimum momentum percentage to trigger trade (default: 0.1)'
    )
    
    # RSI confirmation flags (mutually exclusive)
    rsi_conf_group = parser.add_mutually_exclusive_group()
    rsi_conf_group.add_argument(
        '--rsi-require-confirmation',
        action='store_true',
        dest='rsi_require_confirmation',
        default=None,
        help='Require RSI to confirm momentum signals (default: True)'
    )
    rsi_conf_group.add_argument(
        '--no-rsi-confirmation',
        action='store_false',
        dest='rsi_require_confirmation',
        help='Do not require RSI to confirm momentum signals'
    )
    
    # Config file
    parser.add_argument(
        '--config',
        type=str,
        dest='config_file',
        default=None,
        metavar='FILE',
        help='Load configuration from JSON file'
    )
    
    # Save config
    parser.add_argument(
        '--save-config',
        type=str,
        dest='save_config_file',
        default=None,
        metavar='FILE',
        help='Save current configuration to JSON file and exit'
    )
    
    return parser


def parse_args_to_config(args=None):
    """
    Parse command-line arguments and return configuration dictionary.
    
    Args:
        args: List of arguments (default: sys.argv[1:])
    
    Returns:
        dict: Configuration dictionary
    """
    parser = create_argument_parser()
    parsed = parser.parse_args(args)
    
    # Start with defaults
    config = get_default_config()
    
    # Load from config file if specified
    if parsed.config_file:
        try:
            config = load_config_from_file(parsed.config_file)
            print(f"Loaded configuration from {parsed.config_file}")
        except FileNotFoundError:
            print(f"Error: Config file not found: {parsed.config_file}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in config file: {e}")
            sys.exit(1)
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)
    
    # Override with command-line arguments (only if explicitly set)
    cli_overrides = {
        'mock_trading': parsed.mock_trading,
        'rsi_enabled': parsed.rsi_enabled,
        'target_profit_per_trade': parsed.target_profit_per_trade,
        'mock_balance': parsed.mock_balance,
        'rsi_period': parsed.rsi_period,
        'min_profit_per_share': parsed.min_profit_per_share,
        'max_position_size': parsed.max_position_size,
        'target_sell_spread': parsed.target_sell_spread,
        'rsi_signal_memory_size': parsed.rsi_signal_memory_size,
        'min_momentum_pct': parsed.min_momentum_pct,
        'rsi_require_confirmation': parsed.rsi_require_confirmation,
    }
    
    for key, value in cli_overrides.items():
        if value is not None:
            config[key] = value
    
    # Validate final configuration
    is_valid, errors = validate_config(config)
    if not is_valid:
        print(f"Error: Invalid configuration:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
    
    # Handle save-config option
    if parsed.save_config_file:
        save_config_to_file(config, parsed.save_config_file)
        print("Configuration saved. Exiting.")
        sys.exit(0)
    
    return config


# Configuration dictionary with defaults (initialized at module load)
CONFIG = get_default_config()


# ============================================================================
# Logging Module
# ============================================================================

# Logging configuration
_log_config = {
    'quiet': False,           # Suppress non-essential output
    'verbose': False,         # Enable verbose/debug output
    'log_to_file': False,     # Enable file logging
    'log_file': None,         # File handle for logging
    'log_filename': None,     # Log filename
}


def log(message, level='info', force=False, mock_prefix=True):
    """
    Log a message with optional [MOCK] prefix and level formatting.
    
    This is the central logging function for the mock trading bot.
    All output should go through this function for consistent formatting.
    
    Features:
    - Automatic [MOCK] prefix when mock trading is enabled
    - Timestamp prefix for all messages
    - Level-based formatting (info, warn, error, debug, trade, exit, signal)
    - Quiet mode support (suppresses non-essential output)
    - Force flag to override quiet mode
    
    Args:
        message: The message to log
        level: Log level - 'info', 'warn', 'error', 'debug', 'trade', 'exit', 'signal'
        force: If True, print even in quiet mode
        mock_prefix: If True and mock trading enabled, add [MOCK] prefix
    
    Returns:
        str: The formatted message that was logged
    
    Examples:
        >>> log("Trade executed successfully", level='trade')
        [2024-01-15 10:30:00] [MOCK] [TRADE] Trade executed successfully
        
        >>> log("WebSocket disconnected", level='warn')
        [2024-01-15 10:30:00] [MOCK] [WARN] WebSocket disconnected
        
        >>> log("Debug info", level='debug')  # Only shown in verbose mode
        [2024-01-15 10:30:00] [MOCK] [DEBUG] Debug info
    """
    global _log_config
    
    # Skip debug messages unless verbose mode is enabled
    if level == 'debug' and not _log_config.get('verbose', False):
        return None
    
    # Skip non-essential messages in quiet mode (unless forced)
    if _log_config.get('quiet', False) and not force:
        if level in ('info', 'debug'):
            return None
    
    # Build timestamp
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    
    # Build prefix parts
    prefix_parts = [f"[{timestamp}]"]
    
    # Add [MOCK] prefix if mock trading is enabled
    if mock_prefix and CONFIG.get('mock_trading', True):
        prefix_parts.append("[MOCK]")
    
    # Add level tag
    level_tags = {
        'info': '',
        'warn': '[WARN]',
        'error': '[ERROR]',
        'debug': '[DEBUG]',
        'trade': '[TRADE]',
        'exit': '[EXIT]',
        'signal': '[SIGNAL]',
        'position': '[POSITION]',
        'rsi': '[RSI]',
        'websocket': '[WS]',
    }
    level_tag = level_tags.get(level, '')
    if level_tag:
        prefix_parts.append(level_tag)
    
    # Build final message
    prefix = ' '.join(prefix_parts)
    formatted_message = f"{prefix} {message}"
    
    # Print to console
    print(formatted_message)
    
    # Log to file if enabled
    if _log_config.get('log_to_file', False) and _log_config.get('log_file'):
        try:
            _log_config['log_file'].write(formatted_message + '\n')
            _log_config['log_file'].flush()
        except Exception:
            pass  # Silently ignore file write errors
    
    return formatted_message


def log_trade(message, force=True):
    """Log a trade-related message. Always shown (force=True by default)."""
    return log(message, level='trade', force=force)


def log_exit(message, force=True):
    """Log an exit-related message. Always shown (force=True by default)."""
    return log(message, level='exit', force=force)


def log_signal(message, force=False):
    """Log a signal-related message (RSI, momentum, etc.)."""
    return log(message, level='signal', force=force)


def log_position(message, force=False):
    """Log a position status message."""
    return log(message, level='position', force=force)


def log_rsi(message, force=False):
    """Log an RSI-related message."""
    return log(message, level='rsi', force=force)


def log_websocket(message, force=False):
    """Log a WebSocket-related message."""
    return log(message, level='websocket', force=force)


def log_warn(message, force=True):
    """Log a warning message. Always shown (force=True by default)."""
    return log(message, level='warn', force=force)


def log_error(message, force=True):
    """Log an error message. Always shown (force=True by default)."""
    return log(message, level='error', force=force)


def log_debug(message):
    """Log a debug message. Only shown in verbose mode."""
    return log(message, level='debug', force=False)


def log_info(message, force=False):
    """Log an info message."""
    return log(message, level='info', force=force)


def set_log_quiet(quiet=True):
    """Enable or disable quiet mode."""
    global _log_config
    _log_config['quiet'] = quiet


def set_log_verbose(verbose=True):
    """Enable or disable verbose/debug mode."""
    global _log_config
    _log_config['verbose'] = verbose


def enable_file_logging(filename=None):
    """
    Enable logging to a file.
    
    Args:
        filename: Log filename (default: mock_trader_YYYYMMDD_HHMMSS.log)
    """
    global _log_config
    
    if filename is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"mock_trader_{timestamp}.log"
    
    try:
        _log_config['log_file'] = open(filename, 'a')
        _log_config['log_filename'] = filename
        _log_config['log_to_file'] = True
        log(f"File logging enabled: {filename}", level='info', force=True)
    except Exception as e:
        log(f"Failed to enable file logging: {e}", level='error', force=True)


def disable_file_logging():
    """Disable file logging and close the log file."""
    global _log_config
    
    if _log_config.get('log_file'):
        try:
            _log_config['log_file'].close()
        except Exception:
            pass
    
    _log_config['log_file'] = None
    _log_config['log_filename'] = None
    _log_config['log_to_file'] = False


# ============================================================================
# RSI Signal Memory
# ============================================================================

# Global signal memory list (FIFO, max 10 signals)
# Each signal is a dict with: timestamp, rsi_value, classification
_rsi_signal_memory = []


def add_signal_to_memory(rsi_value, classification, timestamp=None, max_size=None):
    """
    Add a new RSI signal to memory with FIFO logic.
    
    Stores RSI signals in a global memory list for pattern analysis.
    When the memory reaches max_size, the oldest signal is removed (FIFO).
    
    Signal Structure:
        {
            'timestamp': datetime object (UTC),
            'rsi_value': float (0-100),
            'classification': str ('green', 'red', or 'neutral')
        }
    
    Args:
        rsi_value: RSI value (0-100)
        classification: Signal classification ('green', 'red', or 'neutral')
        timestamp: Optional timestamp (defaults to current UTC time)
        max_size: Optional max memory size (defaults to CONFIG['rsi_signal_memory_size'])
    
    Returns:
        dict: The signal that was added to memory
    
    Examples:
        >>> add_signal_to_memory(55.2, 'green')
        {'timestamp': datetime(...), 'rsi_value': 55.2, 'classification': 'green'}
        
        >>> # Add signal with custom timestamp
        >>> from datetime import datetime, timezone
        >>> ts = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        >>> add_signal_to_memory(45.8, 'red', timestamp=ts)
        {'timestamp': datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc), 'rsi_value': 45.8, 'classification': 'red'}
    """
    global _rsi_signal_memory
    
    # Use default max_size from config if not provided
    if max_size is None:
        max_size = CONFIG['rsi_signal_memory_size']
    
    # Use current UTC time if timestamp not provided
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)
    
    # Validate inputs
    if not isinstance(rsi_value, (int, float)):
        raise ValueError(f"rsi_value must be a number, got {type(rsi_value)}")
    
    if not 0 <= rsi_value <= 100:
        raise ValueError(f"rsi_value must be between 0 and 100, got {rsi_value}")
    
    if classification not in ['green', 'red', 'neutral']:
        raise ValueError(f"classification must be 'green', 'red', or 'neutral', got '{classification}'")
    
    # Create signal dict
    signal = {
        'timestamp': timestamp,
        'rsi_value': rsi_value,
        'classification': classification
    }
    
    # Add signal to memory
    _rsi_signal_memory.append(signal)
    
    # Implement FIFO: Remove oldest signal if memory exceeds max_size
    if len(_rsi_signal_memory) > max_size:
        removed_signal = _rsi_signal_memory.pop(0)  # Remove first (oldest) element
        log_signal(f"FIFO: Removed oldest signal (RSI: {removed_signal['rsi_value']:.2f}, {removed_signal['classification']})")
    
    # Log the addition
    log_signal(f"Added signal: RSI={rsi_value:.2f}, classification={classification}, memory_size={len(_rsi_signal_memory)}/{max_size}")
    
    return signal


def get_signal_memory():
    """
    Get the current signal memory.
    
    Returns:
        list: Copy of the signal memory list
    
    Examples:
        >>> memory = get_signal_memory()
        >>> print(f"Memory has {len(memory)} signals")
        >>> for signal in memory:
        ...     print(f"RSI: {signal['rsi_value']:.2f}, {signal['classification']}")
    """
    global _rsi_signal_memory
    return _rsi_signal_memory.copy()


def clear_signal_memory():
    """
    Clear all signals from memory.
    
    Useful for testing or resetting the bot state.
    
    Examples:
        >>> clear_signal_memory()
        >>> memory = get_signal_memory()
        >>> len(memory)
        0
    """
    global _rsi_signal_memory
    _rsi_signal_memory.clear()
    log_signal("Cleared all signals from memory")


def get_signal_memory_size():
    """
    Get the current number of signals in memory.
    
    Returns:
        int: Number of signals currently stored
    
    Examples:
        >>> size = get_signal_memory_size()
        >>> print(f"Memory contains {size} signals")
    """
    global _rsi_signal_memory
    return len(_rsi_signal_memory)


def calculate_rsi(prices, period=7):
    """
    Calculate RSI (Relative Strength Index) using standard formula.
    
    Formula: RSI = 100 - (100 / (1 + RS))
    Where RS = Average Gain / Average Loss
    
    Args:
        prices: List or numpy array of price values (need at least period+1 values)
        period: RSI calculation period (default: 7)
    
    Returns:
        float: RSI value (0-100), or None if insufficient data
    
    Raises:
        ValueError: If prices is empty or period is invalid
    
    Examples:
        >>> prices = [100, 102, 101, 103, 105, 104, 106, 108]
        >>> rsi = calculate_rsi(prices, period=7)
        >>> print(f"RSI: {rsi:.2f}")
    """
    # Input validation
    if prices is None or len(prices) == 0:
        raise ValueError("prices cannot be empty")
    
    if period <= 0:
        raise ValueError(f"period must be positive, got {period}")
    
    # Need at least period+1 prices to calculate RSI
    if len(prices) < period + 1:
        return None
    
    # Convert to numpy array for efficient calculation
    prices = np.array(prices, dtype=float)
    
    # Calculate price deltas (changes between consecutive prices)
    deltas = np.diff(prices)
    
    # Separate gains and losses
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    
    # Calculate initial average gain and loss (simple average of first 'period' values)
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    
    # Apply smoothing for remaining periods using Wilder's smoothing method
    # This is the standard RSI calculation approach
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    
    # Handle division by zero case
    if avg_loss == 0:
        # If there are no losses, RSI is 100 (maximum bullish)
        if avg_gain == 0:
            # No gains and no losses = neutral = 50
            return 50.0
        else:
            # Only gains, no losses = maximum RSI
            return 100.0
    
    # Calculate RS (Relative Strength)
    rs = avg_gain / avg_loss
    
    # Calculate RSI using standard formula
    rsi = 100 - (100 / (1 + rs))
    
    return rsi


def classify_signal(rsi_current, rsi_prev, rsi_prev2):
    """
    Classify RSI signal as green, red, or neutral based on momentum.
    
    Classification Rules:
    - Green: RSI increasing for 2 consecutive periods (bullish momentum)
      → current_rsi > previous_rsi AND previous_rsi > rsi_before_previous
    
    - Red: RSI decreasing for 2 consecutive periods (bearish momentum)
      → current_rsi < previous_rsi AND previous_rsi < rsi_before_previous
    
    - Neutral: Mixed signals (no clear trend)
      → Neither green nor red conditions are met
    
    Args:
        rsi_current: Most recent RSI value
        rsi_prev: Previous RSI value (1 bar ago)
        rsi_prev2: RSI value from 2 bars ago
    
    Returns:
        str: "green", "red", or "neutral"
    
    Examples:
        >>> classify_signal(55, 50, 45)  # Increasing RSI
        'green'
        >>> classify_signal(45, 50, 55)  # Decreasing RSI
        'red'
        >>> classify_signal(50, 45, 50)  # Mixed signals
        'neutral'
    """
    # Green: RSI increasing for 2 consecutive periods
    if rsi_current > rsi_prev and rsi_prev > rsi_prev2:
        return "green"
    
    # Red: RSI decreasing for 2 consecutive periods
    if rsi_current < rsi_prev and rsi_prev < rsi_prev2:
        return "red"
    
    # Neutral: mixed signals
    return "neutral"


def check_rsi_entry_signal(signal_memory, current_rsi_values):
    """
    Check if RSI signals indicate entry (BUY or SELL).
    
    CRITICAL: current_signal is calculated from FRESH RSI data (last 3 bars),
    NOT from memory. This ensures we're using the most recent RSI values.
    
    Entry Logic:
    - BUY: Last 2 signals in memory are "green" AND current signal is "green"
      → 3 consecutive green signals indicate strong bullish momentum
    
    - SELL: Last 2 signals in memory are "red" AND current signal is "red"
      → 3 consecutive red signals indicate strong bearish momentum
    
    - None: No clear signal (mixed signals or insufficient data)
    
    Args:
        signal_memory: List of past signals from memory (for historical context)
                      Each signal is a dict with 'classification' key
                      Example: [{'classification': 'green', ...}, ...]
        
        current_rsi_values: Fresh RSI calculation - list of RSI values
                           Need at least last 3 values: [rsi_n-2, rsi_n-1, rsi_n]
                           These are the most recent RSI values, not from memory
    
    Returns:
        str or None: "BUY", "SELL", or None
    
    Examples:
        >>> memory = [
        ...     {'classification': 'green'},
        ...     {'classification': 'green'}
        ... ]
        >>> rsi_values = [45.0, 50.0, 55.0]  # Increasing RSI
        >>> check_rsi_entry_signal(memory, rsi_values)
        'BUY'
        
        >>> memory = [
        ...     {'classification': 'red'},
        ...     {'classification': 'red'}
        ... ]
        >>> rsi_values = [55.0, 50.0, 45.0]  # Decreasing RSI
        >>> check_rsi_entry_signal(memory, rsi_values)
        'SELL'
        
        >>> memory = [
        ...     {'classification': 'green'},
        ...     {'classification': 'red'}
        ... ]
        >>> rsi_values = [45.0, 50.0, 55.0]
        >>> check_rsi_entry_signal(memory, rsi_values)
        None
    """
    # Validate inputs
    if signal_memory is None or current_rsi_values is None:
        return None
    
    # Need at least 2 signals in memory for pattern matching
    if len(signal_memory) < 2:
        return None
    
    # Need at least 3 fresh RSI values to calculate current signal
    if len(current_rsi_values) < 3:
        return None
    
    # Get last 2 signals from memory (for historical pattern)
    signal_1 = signal_memory[-2]  # 2nd most recent (older)
    signal_2 = signal_memory[-1]  # Most recent
    
    # Validate signal structure
    if not isinstance(signal_1, dict) or 'classification' not in signal_1:
        return None
    if not isinstance(signal_2, dict) or 'classification' not in signal_2:
        return None
    
    # Get last 3 RSI values from FRESH data (not from memory!)
    # This is the key: we calculate current signal from fresh RSI data
    rsi_2_bars_ago = current_rsi_values[-3]  # 3rd from end
    rsi_1_bar_ago = current_rsi_values[-2]   # 2nd from end
    rsi_current = current_rsi_values[-1]     # Most recent
    
    # Calculate current signal using FRESH RSI data
    # This ensures we're using the most up-to-date RSI values
    current_signal = classify_signal(rsi_current, rsi_1_bar_ago, rsi_2_bars_ago)
    
    # Check for BUY: Last 2 memory signals + current = all green
    # This indicates 3 consecutive periods of increasing RSI (strong bullish momentum)
    if (signal_1['classification'] == 'green' and 
        signal_2['classification'] == 'green' and 
        current_signal == 'green'):
        return "BUY"
    
    # Check for SELL: Last 2 memory signals + current = all red
    # This indicates 3 consecutive periods of decreasing RSI (strong bearish momentum)
    if (signal_1['classification'] == 'red' and 
        signal_2['classification'] == 'red' and 
        current_signal == 'red'):
        return "SELL"
    
    # No clear signal (mixed signals or neutral)
    return None


# ============================================================================
# Binance WebSocket Integration
# ============================================================================

class BinanceRSIStream:
    """
    Manages Binance WebSocket connection for real-time RSI calculation.
    
    This class connects to Binance's WebSocket API to receive real-time 1-minute
    kline (candlestick) data for a specified symbol. It maintains a rolling buffer
    of close prices and calculates RSI automatically when each candle closes.
    
    The WebSocket runs in a background thread (non-blocking) and handles
    disconnections with automatic reconnection.
    
    Attributes:
        symbol: Trading pair symbol (e.g., "BTCUSDT")
        period: RSI calculation period (default: 7)
        buffer_size: Number of prices to keep in rolling buffer (default: 20)
        close_prices: Deque of recent close prices
        rsi_values: Deque of calculated RSI values
        ws: WebSocket connection object
        thread: Background thread for WebSocket
        running: Flag indicating if WebSocket is active
    
    Example:
        >>> stream = BinanceRSIStream(symbol="BTCUSDT", period=7, buffer_size=20)
        >>> stream.start()
        >>> # Wait for data...
        >>> rsi_data = stream.get_current_rsi_data()
        >>> print(f"Current RSI: {rsi_data['current_rsi']:.2f}")
        >>> stream.stop()
    """
    
    def __init__(self, symbol="BTCUSDT", period=7, buffer_size=20):
        """
        Initialize BinanceRSIStream.
        
        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT")
            period: RSI calculation period (default: 7)
            buffer_size: Number of prices to keep in rolling buffer (default: 20)
        """
        self.symbol = symbol.lower()
        self.period = period
        self.buffer_size = buffer_size
        
        # Rolling buffers for prices and RSI values
        self.close_prices = deque(maxlen=buffer_size)
        self.rsi_values = deque(maxlen=buffer_size)
        
        # WebSocket connection and thread management
        self.ws = None
        self.thread = None
        self.running = False
        
        # Auto-reconnect configuration
        self.reconnect_enabled = True
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10  # Maximum reconnection attempts (None = infinite)
        self.base_reconnect_delay = 1.0   # Base delay in seconds
        self.max_reconnect_delay = 60.0   # Maximum delay in seconds
        self.reconnect_thread = None
        
        # Initialize with historical data
        self._fetch_initial_data()
    
    def _fetch_initial_data(self):
        """
        Fetch historical candles to initialize buffer.
        
        This method fetches the last N candles from Binance REST API to populate
        the initial buffer before starting the WebSocket stream.
        
        API Endpoint: GET /api/v3/klines
        Parameters:
            - symbol: Trading pair (e.g., BTCUSDT)
            - interval: Candle interval (1m for 1-minute)
            - limit: Number of candles to fetch (default: 20)
        
        Response Format: Array of arrays
            [
                [
                    1499040000000,      // 0: Open time
                    "0.01634000",       // 1: Open
                    "0.80000000",       // 2: High
                    "0.01575800",       // 3: Low
                    "0.01577100",       // 4: Close
                    "148976.11427815",  // 5: Volume
                    1499644799999,      // 6: Close time
                    "2434.19055334",    // 7: Quote asset volume
                    308,                // 8: Number of trades
                    "1756.87402397",    // 9: Taker buy base asset volume
                    "28.46694368",      // 10: Taker buy quote asset volume
                    "17928899.62484339" // 11: Ignore
                ]
            ]
        
        Raises:
            Exception: If API request fails or returns invalid data after retries
        """
        try:
            # Construct API URL
            url = f"https://api.binance.com/api/v3/klines"
            params = {
                'symbol': self.symbol.upper(),
                'interval': '1m',
                'limit': self.buffer_size
            }
            
            print(f"[Binance API] Fetching {self.buffer_size} historical candles for {self.symbol.upper()}...")
            
            # Make API request with retry
            response = api_request_with_retry(url, params=params, timeout=10, max_retries=3)
            
            # Parse JSON response
            candles = response.json()
            
            # Validate response
            if not isinstance(candles, list) or len(candles) == 0:
                raise ValueError(f"Invalid API response: expected non-empty list, got {type(candles)}")
            
            # Extract close prices from candles
            # Close price is at index 4 in each candle array
            for candle in candles:
                if not isinstance(candle, list) or len(candle) < 5:
                    print(f"[Binance API] Warning: Skipping invalid candle: {candle}")
                    continue
                
                close_price = float(candle[4])
                self.close_prices.append(close_price)
            
            print(f"[Binance API] Fetched {len(self.close_prices)} candles successfully")
            print(f"[Binance API] Price range: ${min(self.close_prices):.2f} - ${max(self.close_prices):.2f}")
            
            # Calculate initial RSI values
            self._recalculate_rsi()
            
        except requests.exceptions.RequestException as e:
            print(f"[Binance API] Error fetching historical data after retries: {e}")
            raise
        except (ValueError, KeyError, IndexError) as e:
            print(f"[Binance API] Error parsing API response: {e}")
            raise
        except Exception as e:
            print(f"[Binance API] Unexpected error: {e}")
            raise
    
    def _recalculate_rsi(self):
        """
        Recalculate RSI for all prices in buffer.
        
        This method recalculates RSI values for the entire price buffer.
        Used during initialization and when the buffer is updated.
        
        The method calculates RSI for each possible window in the buffer,
        starting from the minimum required prices (period + 1).
        
        Example:
            If buffer has 20 prices and period is 7, this will calculate
            RSI for positions 7, 8, 9, ..., 19 (13 RSI values total).
        """
        # Need at least period+1 prices to calculate RSI
        if len(self.close_prices) < self.period + 1:
            print(f"[Binance RSI] Insufficient data for RSI calculation: {len(self.close_prices)} prices (need {self.period + 1})")
            return
        
        # Convert deque to list for easier indexing
        prices = list(self.close_prices)
        
        # Clear existing RSI values
        self.rsi_values.clear()
        
        # Calculate RSI for each window in the buffer
        # Start from period (need period+1 prices for first RSI)
        for i in range(self.period, len(prices)):
            # Get price window up to current position
            price_window = prices[:i+1]
            
            # Calculate RSI for this window
            rsi = calculate_rsi(price_window, self.period)
            
            if rsi is not None:
                self.rsi_values.append(rsi)
        
        print(f"[Binance RSI] Calculated {len(self.rsi_values)} RSI values")
        if len(self.rsi_values) > 0:
            print(f"[Binance RSI] Latest RSI: {self.rsi_values[-1]:.2f}")
    
    def _on_message(self, ws, message):
        """
        Handle incoming WebSocket messages.
        
        Processes kline (candlestick) updates from Binance WebSocket.
        Only processes closed candles (k.x = true) to calculate RSI.
        
        Message Format:
        {
            "e": "kline",
            "E": 1638747660000,
            "s": "BTCUSDT",
            "k": {
                "t": 1638747600000,  // Kline start time
                "T": 1638747659999,  // Kline close time
                "s": "BTCUSDT",      // Symbol
                "i": "1m",           // Interval
                "o": "48000.00",     // Open price
                "c": "48100.00",     // Close price (current)
                "h": "48200.00",     // High price
                "l": "47900.00",     // Low price
                "v": "10.5",         // Base asset volume
                "n": 100,            // Number of trades
                "x": false,          // Is this kline closed?
                ...
            }
        }
        
        Args:
            ws: WebSocket connection object
            message: JSON message from Binance WebSocket
        """
        try:
            # Parse JSON message
            data = json.loads(message)
            
            # Only process kline events
            if data.get('e') != 'kline':
                return
            
            # Extract kline data
            kline = data.get('k')
            if not kline:
                return
            
            # Only process closed candles (k.x = true)
            # This ensures we only calculate RSI when a candle is finalized
            if not kline.get('x'):
                return
            
            # Extract close price from kline data
            close_price = float(kline['c'])
            
            # Add to close_prices buffer
            # The deque automatically removes oldest price when maxlen is reached
            self.close_prices.append(close_price)
            
            # Calculate new RSI when sufficient data available
            if len(self.close_prices) >= self.period + 1:
                # Convert deque to list for RSI calculation
                prices = list(self.close_prices)
                
                # Calculate RSI for the current price window
                rsi = calculate_rsi(prices, self.period)
                
                if rsi is not None:
                    # Add to RSI values buffer
                    self.rsi_values.append(rsi)
                    
                    # Log new RSI value
                    log_rsi(f"New RSI: {rsi:.2f} (close: ${close_price:.2f})")
            else:
                # Not enough data yet
                log_rsi(f"Candle closed at ${close_price:.2f} (need {self.period + 1 - len(self.close_prices)} more for RSI)")
        
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            log_websocket(f"Binance error processing message: {e}")
        except Exception as e:
            log_websocket(f"Binance unexpected error in _on_message: {e}")
    
    def _on_error(self, ws, error):
        """
        Handle WebSocket errors.
        
        Args:
            ws: WebSocket connection object
            error: Error object or message
        """
        log_websocket(f"Binance error: {error}")
        # Note: Reconnection will be handled in _on_close
    
    def _on_close(self, ws, close_status_code, close_msg):
        """
        Handle WebSocket close event.
        
        Triggers auto-reconnect logic if enabled.
        
        Args:
            ws: WebSocket connection object
            close_status_code: Close status code
            close_msg: Close message
        """
        log_websocket(f"Binance connection closed (code: {close_status_code}, msg: {close_msg})")
        self.running = False
        
        # Attempt to reconnect if enabled and not manually stopped
        if self.reconnect_enabled:
            self._schedule_reconnect()
    
    def _on_open(self, ws):
        """
        Handle WebSocket open event.
        
        Args:
            ws: WebSocket connection object
        """
        log_websocket(f"Binance connected: {self.symbol}@kline_1m")
        self.running = True
        
        # Reset reconnection counter on successful connection
        self.reconnect_attempts = 0
    
    def _calculate_reconnect_delay(self):
        """
        Calculate exponential backoff delay for reconnection.
        
        Uses exponential backoff with jitter to avoid thundering herd problem.
        Formula: min(max_delay, base_delay * 2^attempts)
        
        Returns:
            float: Delay in seconds before next reconnection attempt
        """
        # Exponential backoff: base_delay * 2^attempts
        delay = self.base_reconnect_delay * (2 ** self.reconnect_attempts)
        
        # Cap at maximum delay
        delay = min(delay, self.max_reconnect_delay)
        
        return delay
    
    def _schedule_reconnect(self):
        """
        Schedule a reconnection attempt with exponential backoff.
        
        This method is called when the WebSocket connection is closed.
        It schedules a reconnection attempt after a calculated delay.
        """
        # Check if we've exceeded max reconnection attempts
        if self.max_reconnect_attempts is not None and self.reconnect_attempts >= self.max_reconnect_attempts:
            log_websocket(f"Binance max reconnection attempts ({self.max_reconnect_attempts}) reached. Giving up.")
            return
        
        # Calculate delay with exponential backoff
        delay = self._calculate_reconnect_delay()
        
        # Increment reconnection counter
        self.reconnect_attempts += 1
        
        log_websocket(f"Binance scheduling reconnection attempt {self.reconnect_attempts} in {delay:.1f} seconds...")
        
        # Schedule reconnection in a separate thread
        self.reconnect_thread = threading.Timer(delay, self._reconnect)
        self.reconnect_thread.daemon = True
        self.reconnect_thread.start()
    
    def _reconnect(self):
        """
        Attempt to reconnect to the WebSocket.
        
        This method is called by the reconnection timer.
        It attempts to re-establish the WebSocket connection.
        """
        log_websocket(f"Binance attempting to reconnect (attempt {self.reconnect_attempts})...")
        
        try:
            # Close existing connection if any
            if self.ws:
                try:
                    self.ws.close()
                except:
                    pass
            
            # Create new WebSocket connection
            self.start()
            
        except Exception as e:
            log_websocket(f"Binance reconnection failed: {e}")
            # Schedule another reconnection attempt
            if self.reconnect_enabled:
                self._schedule_reconnect()
    
    def start(self):
        """
        Start WebSocket connection in background thread.
        
        Creates a WebSocket connection to Binance and runs it in a daemon thread.
        The thread is non-blocking and will automatically terminate when the main
        program exits.
        """
        # Construct WebSocket URL for 1-minute kline stream
        ws_url = f"wss://stream.binance.com:9443/ws/{self.symbol}@kline_1m"
        
        # Create WebSocket app with event handlers
        self.ws = websocket.WebSocketApp(
            ws_url,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
            on_open=self._on_open
        )
        
        # Start WebSocket in background thread
        # Use run_forever with sslopt to handle SSL certificates
        self.thread = threading.Thread(
            target=lambda: self.ws.run_forever(sslopt={"cert_reqs": 0})
        )
        self.thread.daemon = True  # Daemon thread exits when main program exits
        self.thread.start()
    
    def stop(self):
        """
        Stop WebSocket connection.
        
        Gracefully closes the WebSocket connection and stops the background thread.
        Disables auto-reconnect to prevent reconnection after manual stop.
        """
        log_websocket("Binance stopping connection...")
        
        # Disable auto-reconnect
        self.reconnect_enabled = False
        self.running = False
        
        # Cancel any pending reconnection attempts
        if self.reconnect_thread and self.reconnect_thread.is_alive():
            self.reconnect_thread.cancel()
        
        # Close WebSocket connection
        if self.ws:
            try:
                self.ws.close()
            except Exception as e:
                log_websocket(f"Binance error closing connection: {e}")
        
        log_websocket("Binance connection stopped")
    
    def get_current_rsi_data(self):
        """
        Get current RSI data for signal classification.
        
        Returns RSI values and classification for the most recent candles.
        Requires at least 3 RSI values to calculate classification.
        
        Returns:
            dict with RSI values and classification, or None if insufficient data
            
            Example return value:
            {
                'rsi_values': [45.2, 48.1, 52.3, ...],
                'current_rsi': 52.3,
                'rsi_1_bar_ago': 48.1,
                'rsi_2_bars_ago': 45.2,
                'classification': 'green',
                'timestamp': datetime(...),
                'data_status': 'sufficient'
            }
            
            When insufficient data:
            {
                'data_status': 'insufficient',
                'rsi_values_count': 2,
                'required_count': 3,
                'reason': 'Need at least 3 RSI values for classification'
            }
        """
        # Need at least 3 RSI values to calculate classification
        if len(self.rsi_values) < 3:
            log_rsi(f"Insufficient RSI data: {len(self.rsi_values)}/3 values available")
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
            'timestamp': datetime.now(timezone.utc),
            'data_status': 'sufficient'
        }
    
    def get_rsi_data_status(self):
        """
        Get detailed status of RSI data availability.
        
        Returns:
            dict: Status information including:
                - has_sufficient_data: bool
                - rsi_values_count: int
                - close_prices_count: int
                - required_rsi_values: int (3)
                - required_close_prices: int (period + 1)
        """
        return {
            'has_sufficient_data': len(self.rsi_values) >= 3,
            'rsi_values_count': len(self.rsi_values),
            'close_prices_count': len(self.close_prices),
            'required_rsi_values': 3,
            'required_close_prices': self.period + 1
        }
    
    def is_connected(self):
        """
        Check if WebSocket is currently connected and running.
        
        Returns:
            bool: True if connected, False otherwise
        """
        return self.running and self.ws is not None
    
    def get_connection_status(self):
        """
        Get detailed connection status information.
        
        Returns:
            dict: Connection status details including:
                - connected: bool indicating if WebSocket is connected
                - reconnect_attempts: number of reconnection attempts
                - buffer_size: number of prices in buffer
                - rsi_values_count: number of RSI values calculated
        """
        return {
            'connected': self.is_connected(),
            'reconnect_attempts': self.reconnect_attempts,
            'buffer_size': len(self.close_prices),
            'rsi_values_count': len(self.rsi_values),
            'symbol': self.symbol.upper(),
            'period': self.period
        }


# ============================================================================
# Polymarket WebSocket Integration
# ============================================================================

class PolymarketPositionMonitor:
    """
    Manages Polymarket WebSocket connection for position monitoring and early exit.
    
    This class connects to Polymarket's WebSocket API to receive real-time market
    data for position monitoring. It tracks open positions and automatically
    triggers exit callbacks when profit targets are reached or markets are resolved.
    
    WebSocket URL: wss://ws-subscriptions-clob.polymarket.com/ws/market
    
    Message Types:
    - book: Full orderbook snapshot (on subscribe and after trades)
    - price_change: Price level updates (includes best_bid/best_ask)
    - market_resolved: Market resolution notification
    
    Attributes:
        ws: WebSocket connection object
        thread: Background thread for WebSocket
        running: Flag indicating if WebSocket is active
        positions: Dict of open positions {asset_id: position_data}
        callbacks: Dict of exit callbacks {asset_id: callback_function}
        subscribed_assets: Set of asset_ids currently subscribed
    
    Example:
        >>> monitor = PolymarketPositionMonitor()
        >>> monitor.start()
        >>> 
        >>> def on_exit(position, reason):
        ...     print(f"Exit: {reason}, P&L: ${position['net_profit']:.2f}")
        >>> 
        >>> monitor.add_position(
        ...     market_id="0x5f65...",
        ...     asset_id="71321...",
        ...     side="BUY",
        ...     shares=333,
        ...     entry_price=0.40,
        ...     target_profit=15.0,
        ...     exit_callback=on_exit
        ... )
        >>> 
        >>> # Monitor will automatically call on_exit when target is reached
        >>> monitor.stop()
    """
    
    def __init__(self):
        """Initialize PolymarketPositionMonitor."""
        # WebSocket connection and thread management
        self.ws = None
        self.thread = None
        self.running = False
        
        # Position tracking
        self.positions = {}  # {asset_id: position_data}
        self.callbacks = {}  # {asset_id: callback_function}
        self.subscribed_assets = set()  # Set of asset_ids currently subscribed
        
        # Heartbeat thread
        self.heartbeat_thread = None
        
        # Auto-reconnect configuration
        self.reconnect_enabled = True
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10  # Maximum reconnection attempts (None = infinite)
        self.base_reconnect_delay = 1.0   # Base delay in seconds
        self.max_reconnect_delay = 60.0   # Maximum delay in seconds
        self.reconnect_thread = None
    
    def _on_message(self, ws, message):
        """
        Handle incoming WebSocket messages.
        
        Processes different message types:
        - price_change: Price level updates with side (BUY/SELL) and price
        - market_resolved: Market resolution notification
        
        Args:
            ws: WebSocket connection object
            message: JSON message from Polymarket WebSocket
        """
        try:
            # Handle empty messages
            if not message or message.strip() == "":
                return
            
            # Handle PONG response to PING heartbeat
            if message == "PONG" or message.strip() == "PONG":
                return
            
            # Parse JSON message
            data = json.loads(message)
            event_type = data.get('event_type')
            
            if event_type == 'price_change':
                # Price level updates
                price_changes = data.get('price_changes', [])
                
                for change in price_changes:
                    asset_id = change.get('asset_id')
                    side = change.get('side')  # 'BUY' or 'SELL'
                    price = change.get('price')
                    
                    if price is not None:
                        price = float(price)
                    
                    self._process_price_update(asset_id, side, price)
            
            elif event_type == 'market_resolved':
                # Market resolved - close all positions for this market
                market_id = data.get('market')
                winning_outcome = data.get('winning_outcome')
                
                log_websocket(f"Polymarket market resolved: {market_id} → {winning_outcome}")
                self._handle_market_resolution(market_id, winning_outcome)
        
        except json.JSONDecodeError as e:
            # Only log if it's not an empty message issue
            if message and message.strip():
                log_websocket(f"Polymarket error parsing message: {e}")
        except (KeyError, ValueError, TypeError) as e:
            log_websocket(f"Polymarket error processing message: {e}")
        except Exception as e:
            log_websocket(f"Polymarket unexpected error in _on_message: {e}")
    
    def _process_price_update(self, asset_id, side, price):
        """
        Process price update and check exit conditions.
        
        Only updates price if the side matches the position's side.
        - If position side is 'BUY' (YES token), use BUY side price
        - If position side is 'SELL' (NO token), use SELL side price
        
        Args:
            asset_id: Token ID (asset_id)
            side: Price side ('BUY' or 'SELL')
            price: Current price for that side
        """
        global _mock_positions
        
        # Check if we're monitoring this asset
        if asset_id not in self.positions:
            return
        
        position = self.positions[asset_id]
        
        # Check if exit signal already triggered
        if position.get('exit_triggered', False):
            return
        
        # Only update if side matches position side
        position_side = position.get('side', 'BUY')
        if side != position_side:
            return
        
        if price is None:
            return
        
        current_price = price
        
        # Calculate current P&L
        entry_price = position['entry_price']
        shares = position['shares']
        
        # Simple P&L: (current_price - entry_price) × shares
        gross_profit = (current_price - entry_price) * shares
        
        # Fee is 10% of gross profit (only on profits)
        fee = gross_profit * 0.10 if gross_profit > 0 else 0
        
        # Net profit (after fees)
        net_profit = gross_profit - fee
        
        # Update position with current data
        position['current_price'] = current_price
        position['gross_profit'] = gross_profit
        position['fee'] = fee
        position['net_profit'] = net_profit
        
        # Also update global _mock_positions for mock trading
        if asset_id in _mock_positions:
            _mock_positions[asset_id]['current_price'] = current_price
            _mock_positions[asset_id]['gross_profit'] = gross_profit
            _mock_positions[asset_id]['fee'] = fee
            _mock_positions[asset_id]['net_profit'] = net_profit
        
        # Check exit condition
        target_profit = position.get('target_profit', 15.0)
        
        if net_profit >= target_profit:
            log_exit(f"Exit signal: Asset {asset_id[:16]}... reached target profit ${net_profit:.2f}")
            
            # Mark exit as triggered to prevent duplicate callbacks
            position['exit_triggered'] = True
            
            # Call exit callback if registered
            if asset_id in self.callbacks:
                try:
                    self.callbacks[asset_id](position, 'profit_target')
                except Exception as e:
                    log_error(f"Polymarket error in exit callback: {e}")
    
    def _handle_market_resolution(self, market_id, winning_outcome):
        """
        Handle market resolution event.
        
        When a market is resolved, all positions for that market are closed
        and their exit callbacks are triggered with reason 'market_resolved'.
        
        Args:
            market_id: Polymarket market ID
            winning_outcome: Winning outcome (e.g., "YES" or "NO")
        """
        # Find all positions for this market
        positions_to_close = []
        
        for asset_id, position in self.positions.items():
            if position['market_id'] == market_id:
                positions_to_close.append((asset_id, position))
        
        # Close each position
        for asset_id, position in positions_to_close:
            log_position(f"Position closed by resolution: {asset_id[:16]}...")
            
            # Call exit callback
            if asset_id in self.callbacks:
                try:
                    self.callbacks[asset_id](position, 'market_resolved')
                except Exception as e:
                    log_error(f"Polymarket error in exit callback: {e}")
            
            # Remove position from tracking
            if asset_id in self.positions:
                del self.positions[asset_id]
            if asset_id in self.callbacks:
                del self.callbacks[asset_id]
    
    def _on_error(self, ws, error):
        """
        Handle WebSocket errors.
        
        Args:
            ws: WebSocket connection object
            error: Error object or message
        """
        log_websocket(f"Polymarket error: {error}")
    
    def _on_close(self, ws, close_status_code, close_msg):
        """
        Handle WebSocket close event.
        
        Triggers auto-reconnect logic if enabled.
        
        Args:
            ws: WebSocket connection object
            close_status_code: Close status code
            close_msg: Close message
        """
        log_websocket(f"Polymarket connection closed (code: {close_status_code}, msg: {close_msg})")
        self.running = False
        
        # Attempt to reconnect if enabled and not manually stopped
        if self.reconnect_enabled:
            self._schedule_reconnect()
    
    def _on_open(self, ws):
        """
        Handle WebSocket open event.
        
        Subscribes to all assets in subscribed_assets set when connection opens.
        
        Args:
            ws: WebSocket connection object
        """
        log_websocket("Polymarket connected")
        self.running = True
        
        # Reset reconnection counter on successful connection
        self.reconnect_attempts = 0
        
        # Subscribe to assets if any
        if self.subscribed_assets:
            self._send_subscription(list(self.subscribed_assets))
    
    def _calculate_reconnect_delay(self):
        """
        Calculate exponential backoff delay for reconnection.
        
        Uses exponential backoff with jitter to avoid thundering herd problem.
        Formula: min(max_delay, base_delay * 2^attempts)
        
        Returns:
            float: Delay in seconds before next reconnection attempt
        """
        # Exponential backoff: base_delay * 2^attempts
        delay = self.base_reconnect_delay * (2 ** self.reconnect_attempts)
        
        # Cap at maximum delay
        delay = min(delay, self.max_reconnect_delay)
        
        return delay
    
    def _schedule_reconnect(self):
        """
        Schedule a reconnection attempt with exponential backoff.
        
        This method is called when the WebSocket connection is closed.
        It schedules a reconnection attempt after a calculated delay.
        """
        # Check if we've exceeded max reconnection attempts
        if self.max_reconnect_attempts is not None and self.reconnect_attempts >= self.max_reconnect_attempts:
            log_websocket(f"Polymarket max reconnection attempts ({self.max_reconnect_attempts}) reached. Giving up.")
            return
        
        # Calculate delay with exponential backoff
        delay = self._calculate_reconnect_delay()
        
        # Increment reconnection counter
        self.reconnect_attempts += 1
        
        log_websocket(f"Polymarket scheduling reconnection attempt {self.reconnect_attempts} in {delay:.1f} seconds...")
        
        # Schedule reconnection in a separate thread
        self.reconnect_thread = threading.Timer(delay, self._reconnect)
        self.reconnect_thread.daemon = True
        self.reconnect_thread.start()
    
    def _reconnect(self):
        """
        Attempt to reconnect to the WebSocket.
        
        This method is called by the reconnection timer.
        It attempts to re-establish the WebSocket connection.
        """
        log_websocket(f"Polymarket attempting to reconnect (attempt {self.reconnect_attempts})...")
        
        try:
            # Close existing connection if any
            if self.ws:
                try:
                    self.ws.close()
                except:
                    pass
            
            # Create new WebSocket connection
            self.start()
            
        except Exception as e:
            log_websocket(f"Polymarket reconnection failed: {e}")
            # Schedule another reconnection attempt
            if self.reconnect_enabled:
                self._schedule_reconnect()
    
    def _send_subscription(self, asset_ids):
        """
        Send subscription message to WebSocket.
        
        Subscribes to market data for the specified asset_ids.
        Enables custom features for best_bid_ask and market_resolved events.
        
        Subscription Format:
        {
            "assets_ids": ["71321...", "65818..."],
            "type": "market",
            "custom_feature_enabled": true
        }
        
        Args:
            asset_ids: List of asset_ids (token IDs) to subscribe to
        """
        if not self.ws or not self.running:
            log_websocket("Polymarket cannot send subscription: not connected")
            return
        
        subscription = {
            "assets_ids": asset_ids,
            "type": "market",
            "custom_feature_enabled": True  # Enable best_bid_ask, market_resolved
        }
        
        try:
            self.ws.send(json.dumps(subscription))
            log_websocket(f"Polymarket subscribed to {len(asset_ids)} assets")
        except Exception as e:
            log_websocket(f"Polymarket error sending subscription: {e}")
    
    def _send_heartbeat(self):
        """
        Send PING heartbeat every 10 seconds.
        
        Keeps the WebSocket connection alive by sending periodic PING messages.
        The server responds with PONG messages.
        
        Runs in a separate daemon thread.
        """
        while self.running:
            time.sleep(10)
            if self.ws and self.running:
                try:
                    self.ws.send("PING")
                except Exception as e:
                    log_websocket(f"Polymarket heartbeat error: {e}")
    
    def start(self):
        """
        Start WebSocket connection in background thread.
        
        Creates a WebSocket connection to Polymarket and runs it in a daemon thread.
        Also starts a heartbeat thread to keep the connection alive.
        """
        ws_url = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
        
        # Create WebSocket app with event handlers
        self.ws = websocket.WebSocketApp(
            ws_url,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
            on_open=self._on_open
        )
        
        # Start WebSocket in background thread with SSL options
        # Use sslopt to disable certificate verification (for development/testing)
        self.thread = threading.Thread(
            target=lambda: self.ws.run_forever(sslopt={"cert_reqs": 0})
        )
        self.thread.daemon = True
        self.thread.start()
        
        # Start heartbeat thread
        self.heartbeat_thread = threading.Thread(target=self._send_heartbeat)
        self.heartbeat_thread.daemon = True
        self.heartbeat_thread.start()
    
    def stop(self):
        """
        Stop WebSocket connection.
        
        Gracefully closes the WebSocket connection and stops background threads.
        Disables auto-reconnect to prevent reconnection after manual stop.
        """
        log_websocket("Polymarket stopping connection...")
        
        # Disable auto-reconnect
        self.reconnect_enabled = False
        self.running = False
        
        # Cancel any pending reconnection attempts
        if self.reconnect_thread and self.reconnect_thread.is_alive():
            self.reconnect_thread.cancel()
        
        # Close WebSocket connection
        if self.ws:
            try:
                self.ws.close()
            except Exception as e:
                log_websocket(f"Polymarket error closing connection: {e}")
        
        log_websocket("Polymarket connection stopped")
    
    def add_position(self, market_id, asset_id, side, shares, entry_price, target_profit=15.0, exit_callback=None):
        """
        Add a position to monitor.
        
        Starts monitoring a position for price updates and exit conditions.
        Subscribes to the asset_id on the WebSocket if not already subscribed.
        
        Args:
            market_id: Polymarket market ID
            asset_id: Token ID to monitor
            side: 'BUY' or 'SELL'
            shares: Number of shares
            entry_price: Entry price per share
            target_profit: Target net profit in dollars (default: 15.0)
            exit_callback: Function to call when exit condition is met
                          Signature: callback(position, reason)
        
        Example:
            >>> def on_exit(position, reason):
            ...     print(f"Exit: {reason}, P&L: ${position['net_profit']:.2f}")
            >>> 
            >>> monitor.add_position(
            ...     market_id="0x5f65...",
            ...     asset_id="71321...",
            ...     side="BUY",
            ...     shares=333,
            ...     entry_price=0.40,
            ...     target_profit=15.0,
            ...     exit_callback=on_exit
            ... )
        """
        # Create position record
        self.positions[asset_id] = {
            'market_id': market_id,
            'asset_id': asset_id,
            'side': side,
            'shares': shares,
            'entry_price': entry_price,
            'target_profit': target_profit,
            'entry_time': time.time(),
            'current_price': None,
            'gross_profit': 0,
            'fee': 0,
            'net_profit': 0
        }
        
        # Register exit callback
        if exit_callback:
            self.callbacks[asset_id] = exit_callback
        
        # Add to subscribed assets
        was_new = asset_id not in self.subscribed_assets
        self.subscribed_assets.add(asset_id)
        
        # Subscribe to this asset if WebSocket is running and this is a new asset
        if self.running and was_new:
            self._send_subscription([asset_id])
        
        log_position(f"Position added: {asset_id[:16]}... ({side}, {shares} shares @ ${entry_price:.3f})")
    
    def remove_position(self, asset_id):
        """
        Remove a position from monitoring and unsubscribe from WebSocket.
        
        Stops monitoring a position, removes it from tracking, and
        unsubscribes from the WebSocket to stop receiving price updates.
        
        Args:
            asset_id: Token ID to stop monitoring
        """
        # Remove position
        if asset_id in self.positions:
            del self.positions[asset_id]
            log_position(f"Position removed: {asset_id[:16]}...")
        
        # Remove callback
        if asset_id in self.callbacks:
            del self.callbacks[asset_id]
        
        # Unsubscribe from WebSocket
        if asset_id in self.subscribed_assets:
            self.subscribed_assets.remove(asset_id)
            
            # Send unsubscribe message if connected
            if self.running and self.ws:
                try:
                    unsubscribe_msg = {
                        "type": "unsubscribe",
                        "assets_ids": [asset_id]
                    }
                    self.ws.send(json.dumps(unsubscribe_msg))
                except Exception as e:
                    log_error(f"Error unsubscribing from asset: {e}")
    
    def get_position_status(self, asset_id):
        """
        Get current status of a position.
        
        Args:
            asset_id: Token ID
        
        Returns:
            dict: Position data or None if not found
        
        Example:
            >>> status = monitor.get_position_status("71321...")
            >>> if status:
            ...     print(f"Current P&L: ${status['net_profit']:.2f}")
        """
        return self.positions.get(asset_id)
    
    def is_connected(self):
        """
        Check if WebSocket is currently connected and running.
        
        Returns:
            bool: True if connected, False otherwise
        """
        return self.running and self.ws is not None
    
    def get_connection_status(self):
        """
        Get detailed connection status information.
        
        Returns:
            dict: Connection status details including:
                - connected: bool indicating if WebSocket is connected
                - reconnect_attempts: number of reconnection attempts
                - positions_count: number of positions being monitored
                - subscribed_assets_count: number of assets subscribed
        """
        return {
            'connected': self.is_connected(),
            'reconnect_attempts': self.reconnect_attempts,
            'positions_count': len(self.positions),
            'subscribed_assets_count': len(self.subscribed_assets)
        }


# Global instance
_polymarket_monitor = None


def get_polymarket_monitor():
    """
    Get or create Polymarket position monitor.
    
    Returns the global PolymarketPositionMonitor instance, creating it
    if it doesn't exist yet.
    
    Returns:
        PolymarketPositionMonitor: Global monitor instance
    
    Example:
        >>> monitor = get_polymarket_monitor()
        >>> monitor.add_position(...)
    """
    global _polymarket_monitor
    
    if _polymarket_monitor is None:
        _polymarket_monitor = PolymarketPositionMonitor()
        _polymarket_monitor.start()
        time.sleep(1)  # Wait for connection
    
    return _polymarket_monitor


# ============================================================================
# Market Discovery Functions
# ============================================================================

def round_to_5min(timestamp=None):
    """
    Round timestamp to nearest 5-minute interval.
    
    Rounds DOWN to the nearest 5-minute boundary. For example:
    - 8:26 → 8:25
    - 8:29 → 8:25
    - 8:30 → 8:30
    - 8:31 → 8:30
    
    This is used to generate market slugs for Polymarket's 5-minute BTC markets,
    which are created at 5-minute intervals (e.g., 8:25, 8:30, 8:35, etc.).
    
    Args:
        timestamp: Unix timestamp in seconds (default: current time)
    
    Returns:
        int: Rounded unix timestamp (rounded down to nearest 5 minutes)
    
    Examples:
        >>> # Round current time
        >>> rounded = round_to_5min()
        >>> print(f"Rounded timestamp: {rounded}")
        
        >>> # Round specific timestamp (2024-01-15 08:26:30)
        >>> ts = 1705308390
        >>> rounded = round_to_5min(ts)
        >>> # Result: 1705308300 (2024-01-15 08:25:00)
        
        >>> # Verify rounding
        >>> from datetime import datetime, timezone
        >>> dt = datetime.fromtimestamp(rounded, tz=timezone.utc)
        >>> print(dt.strftime('%H:%M'))  # Should be 08:25
    """
    # Use current time if timestamp not provided
    if timestamp is None:
        timestamp = int(time.time())
    
    # Round down to nearest 5 minutes (300 seconds)
    # Integer division by 300, then multiply back
    rounded = (timestamp // 300) * 300
    
    return rounded


def generate_market_slug(timestamp=None):
    """
    Generate BTC 5-minute market slug from timestamp.
    
    Creates a market slug in the format: "btc-updown-5m-{rounded_timestamp}"
    where the timestamp is rounded to the nearest 5-minute interval.
    
    This slug format matches Polymarket's naming convention for BTC 5-minute
    fast markets. The slug can be used to query the Gamma API for market details.
    
    Args:
        timestamp: Unix timestamp in seconds (default: current time)
    
    Returns:
        tuple: (slug, rounded_timestamp)
            - slug: Market slug string (e.g., "btc-updown-5m-1705308300")
            - rounded_timestamp: Rounded unix timestamp used in slug
    
    Examples:
        >>> # Generate slug for current time
        >>> slug, ts = generate_market_slug()
        >>> print(f"Market slug: {slug}")
        >>> print(f"Timestamp: {ts}")
        
        >>> # Generate slug for specific time (2024-01-15 08:26:30)
        >>> slug, ts = generate_market_slug(1705308390)
        >>> # Result: ("btc-updown-5m-1705308300", 1705308300)
        >>> # Timestamp 1705308300 = 2024-01-15 08:25:00 (rounded down)
        
        >>> # Verify the slug format
        >>> assert slug.startswith("btc-updown-5m-")
        >>> assert slug.endswith(str(ts))
    """
    # Round timestamp to nearest 5-minute interval
    rounded_ts = round_to_5min(timestamp)
    
    # Generate slug using Polymarket's naming convention
    slug = f"btc-updown-5m-{rounded_ts}"
    
    return slug, rounded_ts


def fetch_current_price_for_asset(asset_id, market_slug=None, outcome=None):
    """
    Fetch current price for an asset from Polymarket API.
    
    This function is used in mock trading mode to get real-time prices
    for calculating P&L on simulated positions.
    
    Args:
        asset_id: Token ID (asset_id) to get price for
        market_slug: Optional market slug to fetch market data
        outcome: Optional outcome ('Yes' or 'No') to match token by outcome
    
    Returns:
        float or None: Current price for the asset, or None if not found
    """
    try:
        # If we have a market slug, fetch market data
        if market_slug:
            market_info = fetch_market_by_slug(market_slug)
            if market_info and market_info.get('tokens'):
                # First try to match by outcome (more reliable)
                if outcome:
                    for token in market_info['tokens']:
                        if token.get('outcome', '').lower() == outcome.lower():
                            price = token.get('price')
                            if price is not None:
                                return price
                
                # Then try to match by asset_id
                for token in market_info['tokens']:
                    if token.get('asset_id') == asset_id:
                        price = token.get('price')
                        if price is not None:
                            return price
                
                # If we have tokens but no match, use first token for BUY (Yes)
                if len(market_info['tokens']) >= 1:
                    price = market_info['tokens'][0].get('price')
                    if price is not None:
                        return price
        
        # Try to get price from CLOB API using token_id
        url = f"https://clob.polymarket.com/price?token_id={asset_id}&side=sell"
        response = requests.get(url, timeout=10, verify=False)
        
        if response.status_code == 200:
            data = response.json()
            price = data.get('price')
            if price is not None:
                return float(price)
        
        return None
        
    except Exception as e:
        log_error(f"Error fetching price for asset {asset_id[:16]}...: {e}")
        return None


def update_mock_position_prices():
    """
    Update prices for all mock positions by fetching from API.
    
    This function fetches the current market price from the Gamma API
    and calculates P&L for each position.
    
    Mock Trading Logic:
    - Entry: Buy at current token price
    - Exit: Sell at current token price  
    - P&L = (current_price - entry_price) × shares
    
    Also checks if any position has reached target profit and triggers exit.
    """
    global _mock_positions
    
    if not _mock_positions:
        return
    
    positions_to_exit = []
    
    for asset_id, position in list(_mock_positions.items()):
        # Skip if already exiting
        if position.get('exit_triggered'):
            continue
        
        # Get market slug from position
        market_slug = position.get('market_slug')
        
        # Determine which token we're holding (BUY = Yes token, SELL = No token)
        side = position.get('side', 'BUY')
        outcome = 'Yes' if side == 'BUY' else 'No'
        
        # Fetch current price from API
        current_price = fetch_current_price_for_asset(asset_id, market_slug, outcome)
        
        if current_price is not None:
            entry_price = position.get('entry_price', 0)
            shares = position.get('shares', 0)
            
            # Simple P&L: (current_price - entry_price) × shares
            gross_profit = (current_price - entry_price) * shares
            fee = gross_profit * 0.10 if gross_profit > 0 else 0
            net_profit = gross_profit - fee
            
            # Update position
            position['current_price'] = current_price
            position['gross_profit'] = gross_profit
            position['fee'] = fee
            position['net_profit'] = net_profit
            
            # Also update in Polymarket monitor if it exists
            monitor = get_polymarket_monitor()
            if monitor:
                monitor_position = monitor.get_position_status(asset_id)
                if monitor_position:
                    monitor_position['current_price'] = current_price
                    monitor_position['gross_profit'] = gross_profit
                    monitor_position['fee'] = fee
                    monitor_position['net_profit'] = net_profit
            
            # Check if target profit reached
            target_profit = CONFIG.get('target_profit_per_trade', 15.0)
            if net_profit >= target_profit:
                log_exit(f"🎯 Target profit reached for {asset_id[:16]}...")
                log_exit(f"   Entry: ${entry_price:.3f} -> Current: ${current_price:.3f}")
                log_exit(f"   Net profit: ${net_profit:.2f} >= target ${target_profit:.2f}")
                position['exit_triggered'] = True
                positions_to_exit.append((asset_id, position, current_price))
    
    # Execute exits for positions that reached target
    for asset_id, position, exit_price in positions_to_exit:
        execute_mock_exit(position, exit_price)


def fetch_market_by_slug(slug):
    """
    Fetch market details from Polymarket Gamma API by slug.
    
    Queries the Polymarket Gamma API to retrieve market information for a given
    market slug. The API returns market details including market_id, asset_ids
    (token IDs for YES/NO outcomes), prices, and market status.
    
    API Endpoint: GET https://gamma-api.polymarket.com/markets?slug={slug}
    
    Response includes:
    - condition_id: Market ID (used for trading)
    - market_slug: Market slug
    - question: Market question text
    - end_date_iso: Market end time
    - closed: Whether market is closed for trading
    - resolved: Whether market has been resolved
    - tokens: Array of token objects with token_id, outcome, and price
    
    Args:
        slug: Market slug (e.g., "btc-updown-5m-1705308300")
    
    Returns:
        dict or None: Market information dict if found, None if not found or error
        
        Example return value:
        {
            'market_id': '0x5f65177b394277fd294cd75650044e32ba009a95022d88a0c1d565897d72f8f1',
            'slug': 'btc-updown-5m-1705308300',
            'question': 'Will BTC price go up in the next 5 minutes?',
            'end_date': '2024-01-15T08:30:00Z',
            'closed': False,
            'resolved': False,
            'tokens': [
                {
                    'asset_id': '71321045679252212594626385532706912750332728571942532289631379312455583992563',
                    'outcome': 'YES',
                    'price': 0.52
                },
                {
                    'asset_id': '65818619657568813474341868652308942079804919287380422192892211131408793125422',
                    'outcome': 'NO',
                    'price': 0.48
                }
            ]
        }
    
    Examples:
        >>> # Fetch market by slug
        >>> market = fetch_market_by_slug("btc-updown-5m-1705308300")
        >>> if market:
        ...     print(f"Market ID: {market['market_id']}")
        ...     print(f"Question: {market['question']}")
        ...     for token in market['tokens']:
        ...         print(f"  {token['outcome']}: ${token['price']:.3f}")
        ... else:
        ...     print("Market not found")
    """
    # Construct API URL
    url = f"https://gamma-api.polymarket.com/markets?slug={slug}"
    
    try:
        print(f"[Gamma API] Fetching market: {slug}")
        
        # Make API request with retry
        response = api_request_with_retry(url, timeout=10, max_retries=3)
        
        # Parse JSON response
        data = response.json()
        
        # Check if market was found
        if not data or len(data) == 0:
            print(f"[Gamma API] Market not found: {slug}")
            return None
        
        # Extract first result (should only be one match for exact slug)
        market = data[0]
        
        # Debug: Print raw market data to understand structure
        print(f"[Gamma API] Raw market keys: {list(market.keys())[:10]}...")  # Show first 10 keys
        
        # Extract key fields (API uses camelCase)
        market_info = {
            'market_id': market.get('conditionId'),  # Market ID for trading
            'slug': market.get('slug'),
            'question': market.get('question'),
            'end_date': market.get('endDateIso'),
            'closed': market.get('closed', False),
            'resolved': market.get('archived', False),  # 'archived' might indicate resolved
            'tokens': []
        }
        
        # Extract token information from clobTokenIds and outcomes
        clob_token_ids = market.get('clobTokenIds', [])
        outcomes = market.get('outcomes', [])
        outcome_prices = market.get('outcomePrices', [])
        
        # Handle case where these fields might be JSON strings instead of arrays
        if isinstance(clob_token_ids, str):
            try:
                clob_token_ids = json.loads(clob_token_ids)
            except json.JSONDecodeError:
                clob_token_ids = []
        
        if isinstance(outcomes, str):
            try:
                outcomes = json.loads(outcomes)
            except json.JSONDecodeError:
                outcomes = []
        
        if isinstance(outcome_prices, str):
            try:
                outcome_prices = json.loads(outcome_prices)
            except json.JSONDecodeError:
                outcome_prices = []
        
        # Build tokens list by combining data from multiple fields
        if clob_token_ids and outcomes:
            for i, (token_id, outcome) in enumerate(zip(clob_token_ids, outcomes)):
                # Get price for this outcome (if available)
                price = 0.0
                if i < len(outcome_prices):
                    try:
                        price = float(outcome_prices[i])
                    except (ValueError, TypeError):
                        price = 0.0
                
                token_info = {
                    'asset_id': token_id,
                    'outcome': outcome,
                    'price': price
                }
                market_info['tokens'].append(token_info)
        
        print(f"[Gamma API] Market found: {market_info['market_id']}")
        print(f"[Gamma API]   Question: {market_info['question']}")
        print(f"[Gamma API]   Tokens: {len(market_info['tokens'])}")
        
        return market_info
        
    except requests.exceptions.Timeout:
        print(f"[Gamma API] Request timeout for slug: {slug}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"[Gamma API] Request error: {e}")
        return None
    except (ValueError, KeyError, TypeError) as e:
        print(f"[Gamma API] Error parsing response: {e}")
        return None
    except Exception as e:
        print(f"[Gamma API] Unexpected error: {e}")
        return None


def fetch_market_price(token_id, side):
    """
    Fetch market price from Polymarket CLOB API /price endpoint.
    
    Args:
        token_id: Token ID (asset_id)
        side: 'BUY' or 'SELL'
    
    Returns:
        Market price or None on error
    """
    url = f"{CLOB_HOST}/price"
    params = {'token_id': token_id, 'side': side}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        price = data.get('price')
        if price is not None:
            return float(price)
        return None
        
    except Exception as e:
        log_error(f"Market price fetch error: {e}")
        return None


# ============================================================================
# Profit Calculation Functions
# ============================================================================

def calculate_profit_and_position(buy_price, sell_price, target_profit=None, max_position_size=None):
    """
    Calculate if trade is profitable and determine position size for target profit.
    
    This function analyzes a potential trade to determine:
    1. If the spread is sufficient to meet minimum profit requirements
    2. How many shares are needed to achieve the target profit
    3. What the total position cost would be
    
    Profit Calculation:
    - Gross profit per share: sell_price - buy_price
    - Fee per share: gross_profit × 0.10 (10% on profit)
    - Net profit per share: gross_profit - fee
    - Minimum required: $0.05 (5¢) net profit per share
    
    Position Sizing:
    - Required shares: target_profit / net_profit_per_share
    - Position cost: shares × buy_price
    - Capped at max_position_size if provided
    
    Args:
        buy_price: Entry price per share (e.g., 0.40)
        sell_price: Target exit price per share (e.g., 0.45)
        target_profit: Target net profit in dollars (default: from CONFIG)
        max_position_size: Optional cap on position size (default: from CONFIG)
    
    Returns:
        dict: Analysis result with the following keys:
        
        Success case:
        {
            'profitable': True,
            'spread': 0.05,                    # sell_price - buy_price
            'gross_profit_per_share': 0.05,    # spread
            'fee_per_share': 0.005,            # 10% of gross profit
            'net_profit_per_share': 0.045,     # gross - fee
            'required_shares': 333.33,         # shares needed for target profit
            'position_size': 133.33,           # cost in dollars
            'expected_net_profit': 15.00,      # expected profit if target hit
            'expected_fee': 1.67               # expected fee
        }
        
        Failure case (insufficient spread):
        {
            'profitable': False,
            'reason': 'Spread too small: $0.04 < $0.055 minimum',
            'spread': 0.04,
            'net_profit_per_share': 0.036,
            'min_required': 0.05
        }
    
    Examples:
        >>> # Good trade: 5¢ spread
        >>> result = calculate_profit_and_position(0.40, 0.45)
        >>> print(f"Profitable: {result['profitable']}")
        >>> print(f"Position size: ${result['position_size']:.2f}")
        Profitable: True
        Position size: $133.33
        
        >>> # Bad trade: spread too small
        >>> result = calculate_profit_and_position(0.40, 0.405)
        >>> print(f"Profitable: {result['profitable']}")
        >>> print(f"Reason: {result['reason']}")
        Profitable: False
        Reason: Spread too small: $0.005 < $0.055 minimum
        
        >>> # Custom target profit
        >>> result = calculate_profit_and_position(0.40, 0.50, target_profit=20.0)
        >>> print(f"Position size: ${result['position_size']:.2f}")
        Position size: $88.89
    """
    # Use defaults from CONFIG if not provided
    if target_profit is None:
        target_profit = CONFIG['target_profit_per_trade']
    
    if max_position_size is None:
        max_position_size = CONFIG.get('max_position_size')
    
    min_profit_per_share = CONFIG['min_profit_per_share']
    
    # Calculate spread (difference between sell and buy price)
    spread = sell_price - buy_price
    
    # Calculate profit per share
    gross_profit_per_share = spread
    fee_per_share = gross_profit_per_share * 0.10  # 10% fee on profit
    net_profit_per_share = gross_profit_per_share - fee_per_share
    
    # Check if spread meets minimum profit requirement
    # Need at least 5¢ net profit per share after 10% fee
    # This means we need 5.5¢+ spread (5¢ / 0.9 = 5.56¢)
    if net_profit_per_share < min_profit_per_share:
        return {
            'profitable': False,
            'reason': f'Spread too small: ${spread:.3f} < ${min_profit_per_share / 0.9:.3f} minimum',
            'spread': spread,
            'net_profit_per_share': net_profit_per_share,
            'min_required': min_profit_per_share
        }
    
    # Calculate position size to achieve target profit
    # shares = target_profit / net_profit_per_share
    required_shares = target_profit / net_profit_per_share
    
    # Calculate position cost (total dollars needed)
    position_size = required_shares * buy_price
    
    # Apply max position size cap if configured
    if max_position_size is not None and position_size > max_position_size:
        position_size = max_position_size
        required_shares = position_size / buy_price
    
    # Calculate expected profit and fee for this position
    expected_gross_profit = required_shares * gross_profit_per_share
    expected_fee = expected_gross_profit * 0.10
    expected_net_profit = expected_gross_profit - expected_fee
    
    return {
        'profitable': True,
        'spread': spread,
        'gross_profit_per_share': gross_profit_per_share,
        'fee_per_share': fee_per_share,
        'net_profit_per_share': net_profit_per_share,
        'required_shares': required_shares,
        'position_size': position_size,
        'expected_net_profit': expected_net_profit,
        'expected_fee': expected_fee
    }


def check_balance_and_adjust_position(position_size, balance=None, min_position=0.50):
    """
    Check if sufficient balance is available and adjust position size if needed.
    
    This function validates that:
    1. Balance is sufficient for the trade
    2. Position size meets minimum requirements
    3. Position size is adjusted down if balance is insufficient
    
    Balance Check Logic:
    - If balance < min_position → Trade not possible
    - If balance < position_size → Reduce position to available balance
    - If balance >= position_size → Use full calculated position
    
    Args:
        position_size: Desired position size in dollars
        balance: Available balance (default: get from mock balance)
        min_position: Minimum position size in dollars (default: $0.50)
    
    Returns:
        dict: Balance check result with the following keys:
        
        Success case (sufficient balance):
        {
            'sufficient': True,
            'balance': 1000.0,
            'requested_position': 133.33,
            'adjusted_position': 133.33,
            'adjustment_made': False
        }
        
        Success case (balance adjusted):
        {
            'sufficient': True,
            'balance': 100.0,
            'requested_position': 133.33,
            'adjusted_position': 100.0,
            'adjustment_made': True,
            'adjustment_reason': 'Reduced position to available balance'
        }
        
        Failure case (insufficient balance):
        {
            'sufficient': False,
            'balance': 0.30,
            'requested_position': 133.33,
            'reason': 'Insufficient balance: $0.30 < $0.50 minimum'
        }
    
    Examples:
        >>> # Sufficient balance
        >>> result = check_balance_and_adjust_position(133.33, balance=1000.0)
        >>> print(f"Can trade: {result['sufficient']}")
        >>> print(f"Position: ${result['adjusted_position']:.2f}")
        Can trade: True
        Position: $133.33
        
        >>> # Insufficient balance - adjust down
        >>> result = check_balance_and_adjust_position(133.33, balance=100.0)
        >>> print(f"Can trade: {result['sufficient']}")
        >>> print(f"Adjusted to: ${result['adjusted_position']:.2f}")
        Can trade: True
        Adjusted to: $100.00
        
        >>> # Balance too low
        >>> result = check_balance_and_adjust_position(133.33, balance=0.30)
        >>> print(f"Can trade: {result['sufficient']}")
        >>> print(f"Reason: {result['reason']}")
        Can trade: False
        Reason: Insufficient balance: $0.30 < $0.50 minimum
    """
    # Get current balance if not provided
    if balance is None:
        balance = get_mock_balance()
    
    # Check if balance meets minimum requirement
    if balance < min_position:
        return {
            'sufficient': False,
            'balance': balance,
            'requested_position': position_size,
            'reason': f'Insufficient balance: ${balance:.2f} < ${min_position:.2f} minimum'
        }
    
    # Check if balance is sufficient for requested position
    if balance >= position_size:
        # Sufficient balance - use full position
        return {
            'sufficient': True,
            'balance': balance,
            'requested_position': position_size,
            'adjusted_position': position_size,
            'adjustment_made': False
        }
    else:
        # Insufficient balance - reduce position to available balance
        return {
            'sufficient': True,
            'balance': balance,
            'requested_position': position_size,
            'adjusted_position': balance,
            'adjustment_made': True,
            'adjustment_reason': 'Reduced position to available balance'
        }


# ============================================================================
# Mock Trading Engine
# ============================================================================

# Mock trading state variables
_mock_balance = CONFIG['mock_balance']  # Starting balance
_mock_positions = {}  # {asset_id: position_data}
_mock_trade_history = []  # List of all trades (open and closed)
_mock_stats = {
    'total_trades': 0,
    'wins': 0,
    'losses': 0,
    'total_pnl': 0.0,
    'total_fees': 0.0
}


def get_mock_balance():
    """
    Get current mock balance.
    
    Returns the current mock trading balance. This balance is updated
    when mock trades are executed (entry and exit).
    
    Returns:
        float: Current mock balance in dollars
    
    Examples:
        >>> balance = get_mock_balance()
        >>> print(f"Mock balance: ${balance:.2f}")
    """
    global _mock_balance
    return _mock_balance


def execute_mock_trade(market_id, asset_id, side, position_size, entry_price, market_slug=None):
    """
    Execute a mock trade (no real API call).
    
    Simulates entering a position by:
    1. Calculating shares from position size and entry price
    2. Checking if sufficient mock balance is available
    3. Deducting cost from mock balance
    4. Creating position record
    5. Adding to trade history
    
    Args:
        market_id: Market ID
        asset_id: Token ID (asset_id)
        side: 'BUY' or 'SELL'
        position_size: Dollar amount to trade
        entry_price: Price per share
        market_slug: Market slug for fetching price updates
    
    Returns:
        dict: Result with success status, asset_id, shares, price, position_id
        
        Success example:
        {
            'success': True,
            'asset_id': '71321...',
            'shares': 333.33,
            'price': 0.40,
            'position_id': 'mock_0'
        }
        
        Failure example:
        {
            'success': False,
            'error': 'Insufficient mock balance: $50.00 < $133.33'
        }
    
    Examples:
        >>> # Execute mock BUY trade
        >>> result = execute_mock_trade(
        ...     market_id="0x5f65...",
        ...     asset_id="71321...",
        ...     side="BUY",
        ...     position_size=133.33,
        ...     entry_price=0.40
        ... )
        >>> if result['success']:
        ...     print(f"Mock trade executed: {result['shares']:.2f} shares")
        ... else:
        ...     print(f"Mock trade failed: {result['error']}")
    """
    global _mock_balance, _mock_positions, _mock_trade_history, _mock_stats
    
    # Calculate shares from position size and entry price
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
    
    # Create position ID
    position_id = f"mock_{len(_mock_trade_history)}"
    
    # Create trade record
    trade_record = {
        'id': position_id,
        'market_id': market_id,
        'asset_id': asset_id,
        'side': side,
        'shares': shares,
        'entry_price': entry_price,
        'current_price': entry_price,  # Initialize with entry price
        'cost': cost,
        'entry_time': time.time(),
        'status': 'open',
        'exit_price': None,
        'exit_time': None,
        'gross_profit': 0,
        'fee': 0,
        'net_profit': 0,
        'market_slug': market_slug  # Store for price updates
    }
    
    # Add to open positions
    _mock_positions[asset_id] = trade_record
    
    # Add to trade history
    _mock_trade_history.append(trade_record)
    
    # Update stats
    _mock_stats['total_trades'] += 1
    
    # Log mock trade using new logging system
    log_trade(f"Trade executed: {side} {shares:.2f} shares @ ${entry_price:.3f}")
    log_trade(f"  Position ID: {position_id}")
    log_trade(f"  Cost: ${cost:.2f}")
    log_trade(f"  Mock balance: ${_mock_balance:.2f}")
    
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
    
    Simulates exiting a position by:
    1. Calculating P&L (gross profit, fees, net profit)
    2. Calculating proceeds from selling shares
    3. Adding proceeds to mock balance
    4. Updating trade record with exit details
    5. Updating mock stats (wins/losses, total P&L)
    6. Removing from open positions
    
    P&L Calculation:
    - gross_profit = (exit_price - entry_price) × shares
    - fee = 10% of gross_profit (only if profit > 0)
    - net_profit = gross_profit - fee
    
    Args:
        position: Position dict from monitor (contains entry details)
        exit_price: Exit price per share
    
    Returns:
        dict: Result with success status and net profit
    """
    global _mock_balance, _mock_positions, _mock_stats
    
    asset_id = position['asset_id']
    
    # Check if position exists in mock positions
    if asset_id not in _mock_positions:
        return {
            'success': False,
            'error': 'Position not found in mock positions'
        }
    
    # Get trade record
    trade_record = _mock_positions[asset_id]
    
    # Calculate P&L
    entry_price = trade_record['entry_price']
    shares = trade_record['shares']
    
    # Simple P&L: (exit_price - entry_price) × shares
    gross_profit = (exit_price - entry_price) * shares
    
    # Fee is 10% of gross profit (only on profits, not losses)
    fee = gross_profit * 0.10 if gross_profit > 0 else 0
    
    # Net profit (after fees)
    net_profit = gross_profit - fee
    
    # Calculate proceeds (amount to add back to balance)
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
    
    # Log mock exit
    profit_emoji = "✅" if net_profit > 0 else "❌"
    log_exit(f"{profit_emoji} Exit executed: ${net_profit:.2f} net profit")
    log_exit(f"  Position ID: {trade_record['id']}")
    log_exit(f"  Entry: ${entry_price:.3f} -> Exit: ${exit_price:.3f}")
    log_exit(f"  Gross profit: ${gross_profit:.2f}")
    log_exit(f"  Fee (10%): ${fee:.2f}")
    log_exit(f"  Proceeds: ${proceeds:.2f}")
    log_exit(f"  Mock balance: ${_mock_balance:.2f}")
    
    # Show stats every 5 trades
    total_closed = _mock_stats['wins'] + _mock_stats['losses']
    if total_closed > 0 and total_closed % 5 == 0:
        show_mock_stats()
    
    return {
        'success': True,
        'net_profit': net_profit
    }


def show_mock_stats():
    """
    Display mock trading performance summary.
    
    Shows comprehensive statistics including:
    - Total trades executed
    - Wins and losses
    - Win rate percentage
    - Total P&L (profit and loss)
    - Total fees paid
    - Current balance
    - Net change from starting balance
    
    This function is automatically called every 10 trades, but can also
    be called manually to check performance at any time.
    
    Examples:
        >>> # Show current mock trading stats
        >>> show_mock_stats()
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
    """
    global _mock_stats, _mock_balance
    
    total = _mock_stats['total_trades']
    wins = _mock_stats['wins']
    losses = _mock_stats['losses']
    win_rate = (wins / total * 100) if total > 0 else 0
    
    starting_balance = CONFIG['mock_balance']
    net_change = _mock_balance - starting_balance
    net_change_pct = (net_change / starting_balance * 100) if starting_balance > 0 else 0
    
    # Calculate average profit per trade
    avg_profit = (_mock_stats['total_pnl'] / total) if total > 0 else 0
    
    # Calculate profit factor (gross wins / gross losses)
    # Note: This is a simplified version since we track net P&L
    
    log_trade("="*60, force=True)
    log_trade("📊 Trading Performance Summary", force=True)
    log_trade("="*60, force=True)
    log_trade(f"Total trades: {total}", force=True)
    log_trade(f"Wins: {wins} | Losses: {losses}", force=True)
    log_trade(f"Win rate: {win_rate:.1f}%", force=True)
    log_trade(f"Total P&L: ${_mock_stats['total_pnl']:.2f}", force=True)
    log_trade(f"Average profit per trade: ${avg_profit:.2f}", force=True)
    log_trade(f"Total fees: ${_mock_stats['total_fees']:.2f}", force=True)
    log_trade(f"Current balance: ${_mock_balance:.2f}", force=True)
    log_trade(f"Starting balance: ${starting_balance:.2f}", force=True)
    
    # Format net change with + or - sign and emoji
    change_sign = "+" if net_change >= 0 else ""
    change_emoji = "📈" if net_change >= 0 else "📉"
    log_trade(f"Net change: {change_emoji} {change_sign}${net_change:.2f} ({change_sign}{net_change_pct:.1f}%)", force=True)
    log_trade("="*60, force=True)


def show_detailed_performance_report():
    """
    Show a detailed performance report with trade-by-trade analysis.
    
    This function provides a comprehensive breakdown of trading performance:
    - Summary statistics (same as show_mock_stats)
    - Best and worst trades
    - Average trade duration
    - Trade distribution by side (BUY/SELL)
    - Recent trade history
    
    Useful for end-of-session analysis or debugging.
    
    Examples:
        >>> show_detailed_performance_report()
        ============================================================
        📊 DETAILED PERFORMANCE REPORT
        ============================================================
        ...
    """
    global _mock_stats, _mock_balance, _mock_trade_history
    
    log_trade("="*60, force=True)
    log_trade("📊 DETAILED PERFORMANCE REPORT", force=True)
    log_trade("="*60, force=True)
    
    # Basic stats
    total = _mock_stats['total_trades']
    wins = _mock_stats['wins']
    losses = _mock_stats['losses']
    win_rate = (wins / total * 100) if total > 0 else 0
    
    starting_balance = CONFIG['mock_balance']
    net_change = _mock_balance - starting_balance
    net_change_pct = (net_change / starting_balance * 100) if starting_balance > 0 else 0
    
    log_trade(f"📈 SUMMARY", force=True)
    log_trade(f"  Total trades: {total}", force=True)
    log_trade(f"  Win rate: {win_rate:.1f}% ({wins}W / {losses}L)", force=True)
    log_trade(f"  Total P&L: ${_mock_stats['total_pnl']:.2f}", force=True)
    log_trade(f"  Total fees: ${_mock_stats['total_fees']:.2f}", force=True)
    
    change_sign = "+" if net_change >= 0 else ""
    log_trade(f"  Net change: {change_sign}${net_change:.2f} ({change_sign}{net_change_pct:.1f}%)", force=True)
    
    if total == 0:
        log_trade("  No trades to analyze.", force=True)
        log_trade("="*60, force=True)
        return
    
    # Analyze trade history
    closed_trades = [t for t in _mock_trade_history if t.get('status') == 'closed']
    
    if closed_trades:
        # Best and worst trades
        profits = [t.get('net_profit', 0) for t in closed_trades]
        best_profit = max(profits)
        worst_profit = min(profits)
        avg_profit = sum(profits) / len(profits)
        
        log_trade(f"", force=True)
        log_trade(f"💰 TRADE ANALYSIS", force=True)
        log_trade(f"  Best trade: ${best_profit:.2f}", force=True)
        log_trade(f"  Worst trade: ${worst_profit:.2f}", force=True)
        log_trade(f"  Average profit: ${avg_profit:.2f}", force=True)
        
        # Trade distribution by side
        buy_trades = [t for t in closed_trades if t.get('side') == 'BUY']
        sell_trades = [t for t in closed_trades if t.get('side') == 'SELL']
        
        log_trade(f"", force=True)
        log_trade(f"📊 TRADE DISTRIBUTION", force=True)
        log_trade(f"  BUY trades: {len(buy_trades)}", force=True)
        log_trade(f"  SELL trades: {len(sell_trades)}", force=True)
        
        # Average trade duration
        durations = []
        for t in closed_trades:
            if t.get('entry_time') and t.get('exit_time'):
                duration = t['exit_time'] - t['entry_time']
                durations.append(duration)
        
        if durations:
            avg_duration = sum(durations) / len(durations)
            log_trade(f"  Avg trade duration: {avg_duration:.1f} seconds", force=True)
        
        # Recent trades (last 5)
        log_trade(f"", force=True)
        log_trade(f"📜 RECENT TRADES (last 5)", force=True)
        recent = closed_trades[-5:]
        for i, trade in enumerate(reversed(recent), 1):
            side = trade.get('side', 'N/A')
            entry = trade.get('entry_price', 0)
            exit_p = trade.get('exit_price', 0)
            profit = trade.get('net_profit', 0)
            emoji = "✅" if profit > 0 else "❌"
            log_trade(f"  {i}. {emoji} {side} @ ${entry:.3f} → ${exit_p:.3f} = ${profit:.2f}", force=True)
    
    log_trade("="*60, force=True)


def reset_mock_trading(starting_balance=None):
    """
    Reset mock trading state.
    
    Resets all mock trading variables to their initial state:
    - Balance reset to starting_balance (or CONFIG default)
    - All open positions cleared
    - Trade history cleared
    - Stats reset to zero
    
    This is useful for:
    - Starting a new mock trading session
    - Testing different strategies from scratch
    - Resetting after configuration changes
    
    Args:
        starting_balance: Starting balance in dollars (default: CONFIG['mock_balance'])
    
    Examples:
        >>> # Reset with default balance
        >>> reset_mock_trading()
        [MOCK] Trading reset - Starting balance: $1000.00
        
        >>> # Reset with custom balance
        >>> reset_mock_trading(starting_balance=5000.0)
        [MOCK] Trading reset - Starting balance: $5000.00
    """
    global _mock_balance, _mock_positions, _mock_trade_history, _mock_stats
    
    # Use provided starting balance or default from config
    if starting_balance is None:
        starting_balance = CONFIG['mock_balance']
    
    # Reset all state variables
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
    
    log_trade(f"Trading reset - Starting balance: ${starting_balance:.2f}")


def save_mock_history(filename="mock_trades.json"):
    """
    Save mock trade history to JSON file.
    
    Saves all mock trading data to a JSON file for later analysis:
    - Current balance
    - Performance stats (wins, losses, P&L, fees)
    - Complete trade history (all trades with entry/exit details)
    
    The saved file can be used for:
    - Performance analysis
    - Strategy backtesting
    - Record keeping
    - Sharing results
    
    Args:
        filename: Output filename (default: "mock_trades.json")
    
    Examples:
        >>> # Save to default file
        >>> save_mock_history()
        [MOCK] Trade history saved to mock_trades.json
        
        >>> # Save to custom file
        >>> save_mock_history("my_trades_2024.json")
        [MOCK] Trade history saved to my_trades_2024.json
    """
    global _mock_balance, _mock_stats, _mock_trade_history
    
    # Prepare data for JSON serialization
    # Convert trade records to serializable format (timestamps to ISO format)
    serializable_history = []
    for trade in _mock_trade_history:
        trade_copy = trade.copy()
        
        # Convert timestamps to ISO format strings
        if trade_copy['entry_time']:
            trade_copy['entry_time'] = datetime.fromtimestamp(
                trade_copy['entry_time'], tz=timezone.utc
            ).isoformat()
        
        if trade_copy['exit_time']:
            trade_copy['exit_time'] = datetime.fromtimestamp(
                trade_copy['exit_time'], tz=timezone.utc
            ).isoformat()
        
        serializable_history.append(trade_copy)
    
    # Create data structure
    data = {
        'balance': _mock_balance,
        'starting_balance': CONFIG['mock_balance'],
        'stats': _mock_stats,
        'history': serializable_history,
        'saved_at': datetime.now(timezone.utc).isoformat()
    }
    
    # Write to file
    try:
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        log_trade(f"Trade history saved to {filename}")
        log_trade(f"  Total trades: {len(serializable_history)}")
        log_trade(f"  Current balance: ${_mock_balance:.2f}")
    except Exception as e:
        log_error(f"Error saving trade history: {e}")


def discover_and_subscribe_market(timestamp=None, max_retries=3, retry_delay=5):
    """
    Discover current 5-minute BTC market and prepare for trading.
    
    This is the main market discovery function that:
    1. Generates market slug from timestamp (rounded to 5-minute interval)
    2. Fetches market details from Polymarket Gamma API
    3. Validates market is active (not closed or resolved)
    4. Extracts market_id and asset_ids for trading
    5. Logs market information for debugging
    
    If the market is not found, it will retry a few times with a delay,
    as the market might not be created yet.
    
    This function should be called at the start of each trading cycle to
    discover the current 5-minute market and prepare for entry.
    
    Args:
        timestamp: Unix timestamp in seconds (default: current time)
        max_retries: Maximum number of retries if market not found (default: 3)
        retry_delay: Delay in seconds between retries (default: 5)
    
    Returns:
        dict or None: Market information if found and active, None otherwise
        
        Example return value:
        {
            'market_id': '0x5f65177b394277fd294cd75650044e32ba009a95022d88a0c1d565897d72f8f1',
            'slug': 'btc-updown-5m-1705308300',
            'question': 'Will BTC price go up in the next 5 minutes?',
            'end_date': '2024-01-15T08:30:00Z',
            'closed': False,
            'resolved': False,
            'tokens': [
                {
                    'asset_id': '71321045679252212594626385532706912750332728571942532289631379312455583992563',
                    'outcome': 'YES',
                    'price': 0.52
                },
                {
                    'asset_id': '65818619657568813474341868652308942079804919287380422192892211131408793125422',
                    'outcome': 'NO',
                    'price': 0.48
                }
            ],
            'discovery_status': 'found'
        }
    
    Examples:
        >>> # Discover current market
        >>> market = discover_and_subscribe_market()
        >>> if market:
        ...     print(f"Trading market: {market['slug']}")
        ...     print(f"Market ID: {market['market_id']}")
        ...     yes_token = next(t for t in market['tokens'] if t['outcome'] == 'YES')
        ...     print(f"YES price: ${yes_token['price']:.3f}")
        ... else:
        ...     print("No active market found")
        
        >>> # Discover market for specific time
        >>> market = discover_and_subscribe_market(timestamp=1705308390)
    """
    # Generate market slug from timestamp
    slug, rounded_ts = generate_market_slug(timestamp)
    
    # Convert timestamp to human-readable format for logging
    dt = datetime.fromtimestamp(rounded_ts, tz=timezone.utc)
    dt_str = dt.strftime('%Y-%m-%d %H:%M:%S UTC')
    
    print()
    print("="*60)
    print("🔍 Market Discovery")
    print("="*60)
    print(f"Market slug: {slug}")
    print(f"Timestamp: {rounded_ts} ({dt_str})")
    print()
    
    # Fetch market details from Gamma API with retry
    market_info = None
    for attempt in range(max_retries + 1):
        market_info = fetch_market_by_slug(slug)
        
        if market_info:
            break
        
        if attempt < max_retries:
            print(f"⏳ Market not found, retrying in {retry_delay} seconds... (attempt {attempt + 1}/{max_retries + 1})")
            time.sleep(retry_delay)
        else:
            print(f"❌ Market not found after {max_retries + 1} attempts")
            print("   Possible reasons:")
            print("   - Market hasn't been created yet")
            print("   - Market slug format has changed")
            print("   - API is temporarily unavailable")
            print("="*60)
            return None
    
    # Display market information
    print("✅ Market found:")
    print(f"   Market ID: {market_info['market_id']}")
    print(f"   Question: {market_info['question']}")
    print(f"   End date: {market_info['end_date']}")
    print(f"   Closed: {market_info['closed']}")
    print(f"   Resolved: {market_info['resolved']}")
    print()
    
    # Check if market is still active
    if market_info['closed']:
        print("⚠️  Market is closed for trading")
        print("="*60)
        return None
    
    if market_info['resolved']:
        print("⚠️  Market is already resolved")
        print("="*60)
        return None
    
    # Check if tokens are available
    if not market_info.get('tokens') or len(market_info['tokens']) == 0:
        print("⚠️  Market has no tokens available")
        print("="*60)
        return None
    
    # Display token information
    print(f"📊 Tokens ({len(market_info['tokens'])}):")
    for token in market_info['tokens']:
        print(f"   {token['outcome']:3s}: ${token['price']:.3f} (ID: {token['asset_id'][:16]}...)")
    
    print("="*60)
    print()
    
    # Add discovery status
    market_info['discovery_status'] = 'found'
    
    return market_info


# ============================================================================
# Entry Logic Integration
# ============================================================================

# Global Binance RSI stream instance
_binance_rsi_stream = None


def get_binance_rsi(symbol="BTCUSDT", period=7):
    """
    Get current RSI data from WebSocket stream.
    
    Initializes the Binance RSI stream on first call and returns
    current RSI data for signal classification.
    
    Args:
        symbol: Trading pair symbol (default: "BTCUSDT")
        period: RSI calculation period (default: 7)
    
    Returns:
        dict: RSI data with values and classification, or None if insufficient data
    """
    global _binance_rsi_stream
    
    # Initialize stream on first call
    if _binance_rsi_stream is None:
        try:
            _binance_rsi_stream = BinanceRSIStream(symbol, period)
            _binance_rsi_stream.start()
            
            # Wait for initial data
            time.sleep(2)
        except Exception as e:
            log_error(f"Failed to initialize Binance RSI stream: {e}")
            return None
    
    # Check if stream is connected
    if not _binance_rsi_stream.is_connected():
        log_warn("Binance RSI stream is not connected")
        # Try to get data anyway (might have buffered data)
    
    rsi_data = _binance_rsi_stream.get_current_rsi_data()
    
    if rsi_data is None:
        # Get detailed status for debugging
        status = _binance_rsi_stream.get_rsi_data_status()
        log_rsi(f"RSI data unavailable: {status['rsi_values_count']}/{status['required_rsi_values']} values")
    
    return rsi_data


def check_momentum(asset="BTC", lookback_minutes=5):
    """
    Get price momentum from Binance API.
    
    Fetches recent candles and calculates price momentum (percentage change)
    over the lookback period.
    
    Args:
        asset: Asset symbol (default: "BTC")
        lookback_minutes: Number of minutes to look back (default: 5)
    
    Returns:
        dict: Momentum data with direction and percentage, or None on error
        
        Example return:
        {
            'momentum_pct': 0.5,
            'direction': 'up',
            'price_now': 50000.0,
            'price_then': 49750.0
        }
    """
    symbol = f"{asset}USDT"
    
    try:
        url = f"https://api.binance.com/api/v3/klines"
        params = {
            'symbol': symbol,
            'interval': '1m',
            'limit': lookback_minutes + 1
        }
        
        # Make API request with retry
        response = api_request_with_retry(url, params=params, timeout=10, max_retries=3)
        
        candles = response.json()
        
        if not candles or len(candles) < 2:
            return None
        
        # Get price from oldest and newest candle
        price_then = float(candles[0][1])   # Open of oldest candle
        price_now = float(candles[-1][4])   # Close of newest candle
        
        # Calculate momentum percentage
        momentum_pct = ((price_now - price_then) / price_then) * 100
        direction = "up" if momentum_pct > 0 else "down"
        
        return {
            'momentum_pct': momentum_pct,
            'direction': direction,
            'price_now': price_now,
            'price_then': price_then
        }
        
    except Exception as e:
        print(f"[Momentum] Error fetching data after retries: {e}")
        return None


def check_rsi_confirmation(momentum_direction, rsi_signal):
    """
    Check if RSI signal confirms momentum direction.
    
    When RSI confirmation is required, both momentum and RSI must agree
    on the trade direction. This provides additional confirmation before
    entering a trade.
    
    Args:
        momentum_direction: 'up' or 'down' from momentum check
        rsi_signal: 'BUY', 'SELL', or None from RSI check
    
    Returns:
        tuple: (confirmed, reason)
            - confirmed: True if RSI confirms momentum
            - reason: Explanation string
    
    Note:
        When rsi_require_confirmation is True:
        - RSI must actively confirm (BUY for up, SELL for down)
        - Neutral RSI (None) will SKIP the trade
        
        Per requirements 4.4 and 5.4:
        - BUY signal works alongside existing momentum checks (both must pass)
        - SELL signal works alongside existing momentum checks (both must pass)
        
        Per requirements 6.3-6.4:
        - If momentum UP but RSI SELL → SKIP (contradiction)
        - If momentum DOWN but RSI BUY → SKIP (contradiction)
    """
    # If no RSI signal (neutral), skip trade when confirmation is required
    # Requirement 4 & 5: Need 3 consecutive green/red signals for BUY/SELL
    # When RSI is enabled with confirmation, we need a clear signal
    if rsi_signal is None:
        return False, "RSI neutral - no clear signal (need 3 consecutive green/red)"
    
    # Check for contradiction: momentum UP but RSI says SELL
    # Requirement 6.3: If momentum says UP but RSI says SELL → SKIP trade
    if momentum_direction == 'up' and rsi_signal == 'SELL':
        return False, "RSI contradicts momentum (momentum UP, RSI SELL)"
    
    # Check for contradiction: momentum DOWN but RSI says BUY
    # Requirement 6.4: If momentum says DOWN but RSI says BUY → SKIP trade
    if momentum_direction == 'down' and rsi_signal == 'BUY':
        return False, "RSI contradicts momentum (momentum DOWN, RSI BUY)"
    
    # RSI confirms momentum
    if momentum_direction == 'up' and rsi_signal == 'BUY':
        return True, "RSI confirms momentum (both UP/BUY)"
    
    if momentum_direction == 'down' and rsi_signal == 'SELL':
        return True, "RSI confirms momentum (both DOWN/SELL)"
    
    # Default: skip trade (shouldn't reach here)
    return False, "RSI and momentum not aligned"


def check_profit_requirement(buy_price, target_sell_spread=None):
    """
    Check if potential profit meets minimum requirements.
    
    Calculates expected profit based on buy price and target sell spread,
    then verifies it meets the minimum profit per share requirement.
    
    Args:
        buy_price: Entry price per share
        target_sell_spread: Target spread for exit (default: from CONFIG)
    
    Returns:
        tuple: (meets_requirement, result_dict)
            - meets_requirement: True if profit requirement is met
            - result_dict: Details including sell_price, profit calculations
    """
    if target_sell_spread is None:
        target_sell_spread = CONFIG['target_sell_spread']
    
    # Calculate target sell price
    sell_price = buy_price + target_sell_spread
    
    # Use existing profit calculation function
    result = calculate_profit_and_position(buy_price, sell_price)
    
    return result.get('profitable', False), result


def check_balance_for_trade(position_size, min_position=0.50):
    """
    Check if sufficient balance is available for the trade.
    
    Verifies mock balance is sufficient and adjusts position size
    if needed to fit available balance.
    
    Args:
        position_size: Desired position size in dollars
        min_position: Minimum position size (default: $0.50)
    
    Returns:
        tuple: (can_trade, adjusted_position, balance, reason)
    """
    balance = get_mock_balance()
    
    # Check minimum balance
    if balance < min_position:
        log_warn(f"Insufficient mock balance: ${balance:.2f} < ${min_position:.2f} minimum")
        return False, 0, balance, f"Insufficient balance: ${balance:.2f} < ${min_position:.2f} minimum"
    
    # Check if balance covers position
    if balance >= position_size:
        return True, position_size, balance, "Sufficient balance"
    else:
        # Adjust position to available balance
        log_info(f"Position adjusted from ${position_size:.2f} to ${balance:.2f} (available balance)")
        return True, balance, balance, f"Position adjusted to available balance: ${balance:.2f}"


def check_mock_balance_health():
    """
    Check the health of the mock balance.
    
    Returns a status dict indicating if the balance is healthy,
    low, or critically low.
    
    Returns:
        dict: Balance health status
            - balance: Current balance
            - status: 'healthy', 'low', or 'critical'
            - can_trade: bool
            - message: Human-readable status message
    """
    balance = get_mock_balance()
    starting_balance = CONFIG.get('mock_balance', 1000.0)
    min_position = 0.50
    
    # Calculate percentage of starting balance
    balance_pct = (balance / starting_balance * 100) if starting_balance > 0 else 0
    
    if balance < min_position:
        return {
            'balance': balance,
            'status': 'critical',
            'can_trade': False,
            'balance_pct': balance_pct,
            'message': f'Critical: Balance ${balance:.2f} is below minimum ${min_position:.2f}'
        }
    elif balance < starting_balance * 0.1:  # Less than 10% of starting balance
        return {
            'balance': balance,
            'status': 'low',
            'can_trade': True,
            'balance_pct': balance_pct,
            'message': f'Low balance warning: ${balance:.2f} ({balance_pct:.1f}% of starting)'
        }
    else:
        return {
            'balance': balance,
            'status': 'healthy',
            'can_trade': True,
            'balance_pct': balance_pct,
            'message': f'Balance healthy: ${balance:.2f} ({balance_pct:.1f}% of starting)'
        }


def check_market_status(market_info):
    """
    Verify market is active and not resolved.
    
    Checks if the market is still open for trading by verifying
    it's not closed or resolved.
    
    Args:
        market_info: Market information dict from discover_and_subscribe_market()
    
    Returns:
        tuple: (is_active, reason)
    """
    if market_info is None:
        return False, "Market not found"
    
    if market_info.get('closed', False):
        return False, "Market is closed for trading"
    
    if market_info.get('resolved', False):
        return False, "Market already resolved"
    
    return True, "Market is active"


def make_trading_decision(market_info, momentum_data=None, rsi_data=None):
    """
    Main trading decision function that integrates all entry checks.
    
    This function orchestrates all entry condition checks:
    1. Market status check
    2. Momentum check
    3. RSI check (optional, configurable)
    4. Profit requirement check
    5. Balance check
    
    Args:
        market_info: Market information from discover_and_subscribe_market()
        momentum_data: Pre-fetched momentum data (optional, will fetch if None)
        rsi_data: Pre-fetched RSI data (optional, will fetch if None)
    
    Returns:
        dict: Trading decision with the following structure:
        
        Success (trade):
        {
            'action': 'TRADE',
            'side': 'BUY' or 'SELL',
            'position_size': float,
            'entry_price': float,
            'target_exit_price': float,
            'expected_profit': float,
            'shares': float,
            'market_id': str,
            'asset_id': str,
            'reasons': [list of check results]
        }
        
        Skip (no trade):
        {
            'action': 'SKIP',
            'reason': str,
            'details': dict
        }
    """
    reasons = []
    
    print()
    print("="*60)
    print("🧠 Trading Decision Analysis")
    print("="*60)
    
    # -------------------------------------------------------------------------
    # Check 1: Market Status
    # -------------------------------------------------------------------------
    print("\n📋 Check 1: Market Status")
    is_active, status_reason = check_market_status(market_info)
    
    if not is_active:
        print(f"   ❌ {status_reason}")
        return {
            'action': 'SKIP',
            'reason': status_reason,
            'details': {'check': 'market_status'}
        }
    
    print(f"   ✅ {status_reason}")
    reasons.append(f"Market: {status_reason}")
    
    # Extract market details
    market_id = market_info.get('market_id')
    tokens = market_info.get('tokens', [])
    
    if not tokens:
        print("   ❌ No tokens found in market")
        return {
            'action': 'SKIP',
            'reason': 'No tokens found in market',
            'details': {'check': 'market_tokens'}
        }
    
    # -------------------------------------------------------------------------
    # Check 2: Momentum
    # -------------------------------------------------------------------------
    print("\n📈 Check 2: Momentum")
    
    if momentum_data is None:
        momentum_data = check_momentum()
    
    if momentum_data is None:
        print("   ❌ Failed to fetch momentum data")
        return {
            'action': 'SKIP',
            'reason': 'Failed to fetch momentum data',
            'details': {'check': 'momentum'}
        }
    
    momentum_pct = abs(momentum_data['momentum_pct'])
    direction = momentum_data['direction']
    min_momentum = CONFIG.get('min_momentum_pct', 0.1)
    
    print(f"   Price: ${momentum_data['price_now']:,.2f} (was ${momentum_data['price_then']:,.2f})")
    print(f"   Momentum: {momentum_data['momentum_pct']:+.3f}%")
    print(f"   Direction: {direction}")
    
    if momentum_pct < min_momentum:
        print(f"   ❌ Momentum {momentum_pct:.3f}% < minimum {min_momentum}%")
        return {
            'action': 'SKIP',
            'reason': f'Momentum too weak: {momentum_pct:.3f}% < {min_momentum}%',
            'details': {'check': 'momentum', 'momentum_pct': momentum_pct}
        }
    
    print(f"   ✅ Momentum sufficient: {momentum_pct:.3f}%")
    reasons.append(f"Momentum: {momentum_pct:.3f}% {direction}")
    
    # -------------------------------------------------------------------------
    # Check 3: RSI (Optional)
    # -------------------------------------------------------------------------
    print("\n📊 Check 3: RSI Signal")
    
    rsi_signal = None
    
    if CONFIG['rsi_enabled']:
        if rsi_data is None:
            rsi_data = get_binance_rsi()
        
        if rsi_data is None:
            print("   ⚠️  Failed to fetch RSI data, using momentum only")
            reasons.append("RSI: Data unavailable, using momentum only")
        else:
            # Store signal in memory
            add_signal_to_memory(
                rsi_value=rsi_data['current_rsi'],
                classification=rsi_data['classification']
            )
            
            # Get RSI entry signal
            signal_memory = get_signal_memory()
            rsi_signal = check_rsi_entry_signal(signal_memory, rsi_data['rsi_values'])
            
            print(f"   RSI: {rsi_data['current_rsi']:.1f} ({rsi_data['classification']})")
            print(f"   RSI Signal: {rsi_signal or 'NEUTRAL'}")
            
            # Check RSI confirmation if required
            if CONFIG['rsi_require_confirmation']:
                confirmed, confirm_reason = check_rsi_confirmation(direction, rsi_signal)
                
                if not confirmed:
                    print(f"   ❌ {confirm_reason}")
                    return {
                        'action': 'SKIP',
                        'reason': confirm_reason,
                        'details': {'check': 'rsi_confirmation', 'rsi_signal': rsi_signal, 'momentum_direction': direction}
                    }
                
                print(f"   ✅ {confirm_reason}")
            
            reasons.append(f"RSI: {rsi_data['current_rsi']:.1f} ({rsi_signal or 'NEUTRAL'})")
    else:
        print("   ⏭️  RSI check disabled")
        reasons.append("RSI: Disabled")
    
    # -------------------------------------------------------------------------
    # Determine trade side and price
    # -------------------------------------------------------------------------
    # For BTC up → buy YES token
    # For BTC down → buy NO token
    if direction == 'up':
        side = 'BUY'
        # Find YES token
        yes_token = next((t for t in tokens if t['outcome'] == 'Yes'), None)
        if not yes_token:
            yes_token = tokens[0]  # Fallback to first token
        asset_id = yes_token['asset_id']
        fallback_price = yes_token['price']
    else:
        side = 'SELL'
        # Find NO token
        no_token = next((t for t in tokens if t['outcome'] == 'No'), None)
        if not no_token:
            no_token = tokens[1] if len(tokens) > 1 else tokens[0]
        asset_id = no_token['asset_id']
        fallback_price = no_token['price']
    
    # Fetch REAL market price from CLOB API /price endpoint
    print("\n📖 Fetching market price...")
    entry_price = fetch_market_price(asset_id, 'BUY')
    
    if entry_price:
        print(f"   Market price (BUY): ${entry_price:.3f}")
    else:
        # Fallback to Gamma API price (less accurate)
        entry_price = fallback_price
        print(f"   ⚠️ Using Gamma API price (may be stale): ${entry_price:.3f}")
    
    # -------------------------------------------------------------------------
    # Check 4: Profit Requirement
    # -------------------------------------------------------------------------
    print("\n💰 Check 4: Profit Requirement")
    
    meets_profit, profit_result = check_profit_requirement(entry_price)
    
    if not meets_profit:
        reason = profit_result.get('reason', 'Profit requirement not met')
        print(f"   ❌ {reason}")
        return {
            'action': 'SKIP',
            'reason': reason,
            'details': {'check': 'profit', 'entry_price': entry_price, 'result': profit_result}
        }
    
    target_exit_price = entry_price + CONFIG['target_sell_spread']
    expected_profit = profit_result.get('expected_net_profit', 0)
    position_size = profit_result.get('position_size', 0)
    shares = profit_result.get('required_shares', 0)
    
    print(f"   Entry price: ${entry_price:.3f}")
    print(f"   Target exit: ${target_exit_price:.3f}")
    print(f"   Spread: ${CONFIG['target_sell_spread']:.3f}")
    print(f"   Expected profit: ${expected_profit:.2f}")
    print(f"   ✅ Profit requirement met")
    reasons.append(f"Profit: ${expected_profit:.2f} expected")
    
    # -------------------------------------------------------------------------
    # Check 5: Balance
    # -------------------------------------------------------------------------
    print("\n💵 Check 5: Balance")
    
    can_trade, adjusted_position, balance, balance_reason = check_balance_for_trade(position_size)
    
    if not can_trade:
        print(f"   ❌ {balance_reason}")
        return {
            'action': 'SKIP',
            'reason': balance_reason,
            'details': {'check': 'balance', 'balance': balance, 'required': position_size}
        }
    
    print(f"   Balance: ${balance:.2f}")
    print(f"   Position size: ${adjusted_position:.2f}")
    
    if adjusted_position < position_size:
        print(f"   ⚠️  Position adjusted from ${position_size:.2f} to ${adjusted_position:.2f}")
        # Recalculate shares based on adjusted position
        shares = adjusted_position / entry_price
        expected_profit = shares * profit_result.get('net_profit_per_share', 0)
    
    print(f"   ✅ {balance_reason}")
    reasons.append(f"Balance: ${balance:.2f}")
    
    # -------------------------------------------------------------------------
    # All checks passed - TRADE
    # -------------------------------------------------------------------------
    print("\n" + "="*60)
    print("✅ ALL CHECKS PASSED - TRADE SIGNAL")
    print("="*60)
    print(f"   Side: {side}")
    print(f"   Asset ID: {asset_id[:20]}...")
    print(f"   Entry price: ${entry_price:.3f}")
    print(f"   Target exit: ${target_exit_price:.3f}")
    print(f"   Shares: {shares:.2f}")
    print(f"   Position size: ${adjusted_position:.2f}")
    print(f"   Expected profit: ${expected_profit:.2f}")
    print("="*60)
    print()
    
    return {
        'action': 'TRADE',
        'side': side,
        'position_size': adjusted_position,
        'entry_price': entry_price,
        'target_exit_price': target_exit_price,
        'expected_profit': expected_profit,
        'shares': shares,
        'market_id': market_id,
        'asset_id': asset_id,
        'market_slug': market_info.get('slug'),  # Include slug for price updates
        'momentum': momentum_data,
        'rsi_signal': rsi_signal,
        'reasons': reasons
    }


# ============================================================================
# Exit Logic Integration
# ============================================================================

def create_exit_callback(market_id, asset_id):
    """
    Create an exit callback function for a position.
    
    This factory function creates a callback that will be called by the
    PolymarketPositionMonitor when exit conditions are met (profit target
    reached or market resolved).
    
    The callback:
    1. Logs the exit reason and position details
    2. Executes the mock exit trade
    3. Removes the position from monitoring
    
    Args:
        market_id: Market ID for logging
        asset_id: Asset ID for position identification
    
    Returns:
        function: Exit callback function with signature (position, reason)
    
    Example:
        >>> callback = create_exit_callback("0x5f65...", "71321...")
        >>> # Callback will be called by monitor when exit conditions met
        >>> callback(position, 'profit_target')
    """
    def exit_callback(position, reason):
        """
        Exit callback function called when exit conditions are met.
        
        Args:
            position: Position dict with entry details and current P&L
            reason: Exit reason ('profit_target' or 'market_resolved')
        """
        print()
        print("="*60)
        print(f"🚪 EXIT TRIGGERED: {reason}")
        print("="*60)
        
        # Log position details
        print(f"   Market ID: {market_id[:20]}...")
        print(f"   Asset ID: {asset_id[:20]}...")
        print(f"   Side: {position.get('side', 'N/A')}")
        print(f"   Shares: {position.get('shares', 0):.2f}")
        print(f"   Entry price: ${position.get('entry_price', 0):.3f}")
        print(f"   Current price: ${position.get('current_price', 0):.3f}")
        print(f"   Gross profit: ${position.get('gross_profit', 0):.2f}")
        print(f"   Fee: ${position.get('fee', 0):.2f}")
        print(f"   Net profit: ${position.get('net_profit', 0):.2f}")
        print("="*60)
        
        # Execute mock exit if mock trading is enabled
        if CONFIG['mock_trading']:
            exit_price = position.get('current_price', position.get('entry_price', 0))
            exit_result = execute_mock_exit(position, exit_price)
            
            if exit_result['success']:
                log_exit(f"Exit successful: Net profit ${exit_result['net_profit']:.2f}")
            else:
                log_error(f"Exit failed: {exit_result.get('error', 'Unknown error')}")
        else:
            # Real trading would execute actual exit order here
            log_info("[REAL] Exit order would be placed here (not implemented)", force=True)
        
        # Remove position from monitor
        monitor = get_polymarket_monitor()
        if monitor:
            monitor.remove_position(asset_id)
    
    return exit_callback


def handle_market_resolution_exit(position, winning_outcome):
    """
    Handle exit when market is resolved.
    
    When a market resolves, the position is automatically closed at the
    resolution price (1.0 for winning outcome, 0.0 for losing outcome).
    
    Args:
        position: Position dict with entry details
        winning_outcome: The winning outcome ('Yes' or 'No')
    
    Returns:
        dict: Exit result with success status and P&L
    """
    asset_id = position.get('asset_id')
    side = position.get('side')
    
    # Determine if position won or lost based on outcome
    # For BUY positions on YES token: win if outcome is 'Yes'
    # For SELL positions on NO token: win if outcome is 'No'
    
    # Resolution price: 1.0 for winning outcome, 0.0 for losing
    # This is simplified - actual resolution depends on which token was held
    if winning_outcome == 'Yes':
        resolution_price = 1.0 if side == 'BUY' else 0.0
    else:
        resolution_price = 0.0 if side == 'BUY' else 1.0
    
    print()
    print("="*60)
    print(f"📋 MARKET RESOLVED: {winning_outcome}")
    print("="*60)
    print(f"   Resolution price: ${resolution_price:.2f}")
    
    # Execute mock exit at resolution price
    if CONFIG['mock_trading']:
        exit_result = execute_mock_exit(position, resolution_price)
        return exit_result
    
    return {'success': True, 'net_profit': 0}


def start_position_monitoring(market_id, asset_id, side, shares, entry_price, target_profit=None):
    """
    Start monitoring a position for exit conditions.
    
    Integrates with PolymarketPositionMonitor to:
    1. Create an exit callback for the position
    2. Add the position to the monitor
    3. Subscribe to price updates via WebSocket
    
    The monitor will automatically call the exit callback when:
    - Target profit is reached (based on real-time price updates)
    - Market is resolved
    
    Args:
        market_id: Polymarket market ID
        asset_id: Token ID (asset_id) to monitor
        side: 'BUY' or 'SELL'
        shares: Number of shares in position
        entry_price: Entry price per share
        target_profit: Target net profit in dollars (default: from CONFIG)
    
    Returns:
        bool: True if monitoring started successfully, False otherwise
    
    Example:
        >>> success = start_position_monitoring(
        ...     market_id="0x5f65...",
        ...     asset_id="71321...",
        ...     side="BUY",
        ...     shares=333.33,
        ...     entry_price=0.40,
        ...     target_profit=15.0
        ... )
        >>> if success:
        ...     print("Position monitoring started")
    """
    if target_profit is None:
        target_profit = CONFIG['target_profit_per_trade']
    
    print()
    print("="*60)
    print("👁️ Starting Position Monitoring")
    print("="*60)
    print(f"   Market ID: {market_id[:20]}...")
    print(f"   Asset ID: {asset_id[:20]}...")
    print(f"   Side: {side}")
    print(f"   Shares: {shares:.2f}")
    print(f"   Entry price: ${entry_price:.3f}")
    print(f"   Target profit: ${target_profit:.2f}")
    print("="*60)
    
    try:
        # Get or create the Polymarket monitor
        monitor = get_polymarket_monitor()
        
        if not monitor:
            print("❌ Failed to get Polymarket monitor")
            return False
        
        # Create exit callback for this position
        exit_callback = create_exit_callback(market_id, asset_id)
        
        # Add position to monitor
        monitor.add_position(
            market_id=market_id,
            asset_id=asset_id,
            side=side,
            shares=shares,
            entry_price=entry_price,
            target_profit=target_profit,
            exit_callback=exit_callback
        )
        
        print("✅ Position monitoring started successfully")
        print()
        return True
        
    except Exception as e:
        print(f"❌ Error starting position monitoring: {e}")
        return False


def stop_position_monitoring(asset_id):
    """
    Stop monitoring a position.
    
    Removes the position from the PolymarketPositionMonitor and
    unregisters the exit callback.
    
    Args:
        asset_id: Token ID (asset_id) to stop monitoring
    
    Returns:
        bool: True if stopped successfully, False otherwise
    """
    try:
        monitor = get_polymarket_monitor()
        
        if monitor:
            monitor.remove_position(asset_id)
            print(f"[Exit Logic] Stopped monitoring position: {asset_id[:20]}...")
            return True
        
        return False
        
    except Exception as e:
        print(f"[Exit Logic] Error stopping position monitoring: {e}")
        return False


def get_position_pnl(asset_id):
    """
    Get current P&L for a monitored position.
    
    Retrieves the current position status from the PolymarketPositionMonitor,
    including real-time P&L calculations.
    
    Args:
        asset_id: Token ID (asset_id) of the position
    
    Returns:
        dict or None: Position status with P&L, or None if not found
        
        Example return:
        {
            'asset_id': '71321...',
            'side': 'BUY',
            'shares': 333.33,
            'entry_price': 0.40,
            'current_price': 0.43,
            'gross_profit': 10.0,
            'fee': 1.0,
            'net_profit': 9.0,
            'target_profit': 15.0
        }
    """
    try:
        monitor = get_polymarket_monitor()
        
        if monitor:
            return monitor.get_position_status(asset_id)
        
        return None
        
    except Exception as e:
        print(f"[Exit Logic] Error getting position P&L: {e}")
        return None


def execute_trade_with_monitoring(decision):
    """
    Execute a trade and start position monitoring.
    
    This is the main function that combines trade execution with exit monitoring.
    It:
    1. Executes the mock trade
    2. Starts position monitoring for automatic exit
    
    Args:
        decision: Trading decision dict from make_trading_decision()
    
    Returns:
        dict: Result with trade and monitoring status
        
        Example return:
        {
            'trade_success': True,
            'monitoring_started': True,
            'position_id': 'mock_0',
            'asset_id': '71321...',
            'shares': 333.33,
            'entry_price': 0.40
        }
    """
    if decision.get('action') != 'TRADE':
        return {
            'trade_success': False,
            'error': 'No trade signal'
        }
    
    market_id = decision['market_id']
    asset_id = decision['asset_id']
    side = decision['side']
    position_size = decision['position_size']
    entry_price = decision['entry_price']
    target_profit = CONFIG['target_profit_per_trade']
    market_slug = decision.get('market_slug')  # Get market slug for price updates
    
    # Execute the mock trade
    trade_result = execute_mock_trade(
        market_id=market_id,
        asset_id=asset_id,
        side=side,
        position_size=position_size,
        entry_price=entry_price,
        market_slug=market_slug
    )
    
    if not trade_result['success']:
        return {
            'trade_success': False,
            'error': trade_result.get('error', 'Trade execution failed')
        }
    
    shares = trade_result['shares']
    
    # Start position monitoring for automatic exit
    monitoring_started = start_position_monitoring(
        market_id=market_id,
        asset_id=asset_id,
        side=side,
        shares=shares,
        entry_price=entry_price,
        target_profit=target_profit
    )
    
    return {
        'trade_success': True,
        'monitoring_started': monitoring_started,
        'position_id': trade_result.get('position_id'),
        'asset_id': asset_id,
        'shares': shares,
        'entry_price': entry_price
    }


# ============================================================================
# Main Trading Loop
# ============================================================================

def calculate_sleep_until_next_5min():
    """
    Calculate seconds to sleep until the next 5-minute interval.
    
    Returns the number of seconds until the next 5-minute boundary
    (e.g., if current time is 8:26:30, returns ~210 seconds until 8:30:00).
    
    Returns:
        float: Seconds until next 5-minute interval
    """
    now = time.time()
    current_5min = (int(now) // 300) * 300
    next_5min = current_5min + 300
    sleep_seconds = next_5min - now
    
    # Add small buffer (5 seconds) to ensure market is available
    return sleep_seconds + 5


def run_trading_iteration():
    """
    Run a single trading iteration.
    
    This function performs one complete trading cycle:
    1. Discover current 5-minute market
    2. Check all entry conditions
    3. Execute trade if conditions are met
    4. Start position monitoring
    
    IMPORTANT: Even when entry conditions fail, the main loop continues
    monitoring existing positions. This function only handles new trade
    entry - position monitoring happens continuously in the main loop.
    
    Returns:
        dict: Result of the trading iteration with status and details
            - status: 'traded', 'skipped', 'failed', or 'error'
            - reason: Human-readable explanation
            - details: Additional context
    """
    print()
    print("="*60)
    print(f"🔄 Trading Iteration - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("="*60)
    
    try:
        # Step 1: Discover current market
        market_info = discover_and_subscribe_market()
        
        if not market_info:
            return {
                'status': 'skipped',
                'reason': 'Market not found or not active',
                'continue_monitoring': True  # Still monitor existing positions
            }
        
        # Step 2: Make trading decision (includes all entry checks)
        decision = make_trading_decision(market_info)
        
        if decision['action'] == 'SKIP':
            return {
                'status': 'skipped',
                'reason': decision.get('reason', 'Entry conditions not met'),
                'details': decision.get('details', {}),
                'continue_monitoring': True  # Still monitor existing positions
            }
        
        # Step 3: Execute trade with monitoring
        if decision['action'] == 'TRADE':
            result = execute_trade_with_monitoring(decision)
            
            if result['trade_success']:
                return {
                    'status': 'traded',
                    'position_id': result.get('position_id'),
                    'asset_id': result.get('asset_id'),
                    'shares': result.get('shares'),
                    'entry_price': result.get('entry_price'),
                    'monitoring': result.get('monitoring_started', False),
                    'continue_monitoring': True
                }
            else:
                return {
                    'status': 'failed',
                    'reason': result.get('error', 'Trade execution failed'),
                    'continue_monitoring': True  # Still monitor existing positions
                }
        
        return {
            'status': 'skipped',
            'reason': 'Unknown decision action',
            'continue_monitoring': True
        }
        
    except Exception as e:
        print(f"❌ Error in trading iteration: {e}")
        return {
            'status': 'error',
            'reason': str(e),
            'continue_monitoring': True  # Still monitor existing positions even on error
        }


def log_position_status():
    """
    Log status of all open positions.
    
    Displays current P&L and status for all monitored positions.
    Called periodically (every 30 seconds) during the main loop.
    
    This function provides real-time visibility into:
    - All open positions
    - Current price vs entry price
    - Unrealized P&L
    - Progress toward target profit
    
    Note: Prices are updated separately by update_mock_position_prices()
    which runs every 5 seconds in the main loop.
    """
    global _mock_positions
    
    if not _mock_positions:
        log_position("No open positions", force=False)
        return
    
    log_position("-"*50, force=True)
    log_position("📊 Open Positions Status", force=True)
    log_position("-"*50, force=True)
    
    total_unrealized_pnl = 0
    target_profit = CONFIG.get('target_profit_per_trade', 15.0)
    
    for asset_id, position in list(_mock_positions.items()):
        side = position.get('side', 'N/A')
        shares = position.get('shares', 0)
        entry_price = position.get('entry_price', 0)
        current_price = position.get('current_price')
        net_profit = position.get('net_profit', 0)
        
        # Handle None values - indicate waiting for price data
        if current_price is None:
            log_position(f"  ⏳ {asset_id[:12]}... | {side} {shares:.0f} @ ${entry_price:.3f} | Waiting for price...", force=True)
            continue
        
        if net_profit is None:
            net_profit = 0
        
        total_unrealized_pnl += net_profit
        
        # Calculate progress toward target
        progress_pct = (net_profit / target_profit * 100) if target_profit > 0 else 0
        progress_pct = max(-100, min(100, progress_pct))  # Clamp to -100 to 100
        
        if progress_pct >= 0:
            progress_bar = "█" * int(progress_pct / 10) + "░" * (10 - int(progress_pct / 10))
        else:
            # Show negative progress
            neg_bars = int(abs(progress_pct) / 10)
            progress_bar = "▓" * neg_bars + "░" * (10 - neg_bars)
        
        # Emoji based on P&L
        pnl_emoji = "🟢" if net_profit > 0 else "🔴" if net_profit < 0 else "⚪"
        
        # Price change indicator
        price_change = current_price - entry_price
        price_emoji = "📈" if price_change > 0 else "📉" if price_change < 0 else "➡️"
        
        log_position(f"  {pnl_emoji} {asset_id[:12]}... | {side} {shares:.0f} @ ${entry_price:.3f}", force=True)
        log_position(f"     {price_emoji} Current: ${current_price:.3f} ({price_change:+.3f}) | P&L: ${net_profit:.2f} | [{progress_bar}] {progress_pct:.0f}%", force=True)
    
    log_position("-"*50, force=True)
    
    # Summary line
    pnl_emoji = "📈" if total_unrealized_pnl > 0 else "📉" if total_unrealized_pnl < 0 else "➖"
    log_position(f"  {pnl_emoji} Total unrealized P&L: ${total_unrealized_pnl:.2f}", force=True)
    log_position("-"*50, force=True)


def close_expired_positions():
    """
    Close positions from previous iterations that didn't exit.
    
    Simple rule: If position didn't exit within 5 minutes, it's a loss.
    The bet didn't hit the target, so we lost the cost.
    """
    global _mock_positions, _mock_balance, _mock_stats
    
    if not _mock_positions:
        return
    
    current_time = time.time()
    
    positions_to_close = []
    
    for asset_id, position in _mock_positions.items():
        market_slug = position.get('market_slug', '')
        
        if not market_slug:
            entry_time = position.get('entry_time', 0)
            if current_time - entry_time > 300:
                positions_to_close.append(asset_id)
            continue
        
        try:
            slug_parts = market_slug.split('-')
            market_timestamp = int(slug_parts[-1])
            market_end_time = market_timestamp + 300
            
            if current_time > market_end_time:
                positions_to_close.append(asset_id)
        except (ValueError, IndexError):
            entry_time = position.get('entry_time', 0)
            if current_time - entry_time > 300:
                positions_to_close.append(asset_id)
    
    # Close expired positions as losses
    for asset_id in positions_to_close:
        position = _mock_positions.get(asset_id)
        if not position:
            continue
        
        entry_price = position.get('entry_price', 0)
        shares = position.get('shares', 0)
        side = position.get('side', 'BUY')
        cost = position.get('cost', entry_price * shares)
        
        # No exit = loss
        net_profit = -cost
        
        _mock_stats['losses'] += 1
        _mock_stats['total_pnl'] += net_profit
        
        position['exit_price'] = 0
        position['exit_time'] = current_time
        position['gross_profit'] = -cost
        position['fee'] = 0
        position['net_profit'] = net_profit
        position['status'] = 'expired'
        position['exit_reason'] = 'no_exit_loss'
        
        log_exit(f"❌ Position expired (no exit = loss): {asset_id[:16]}...")
        log_exit(f"   Side: {side}, Shares: {shares:.2f}, Entry: ${entry_price:.3f}")
        log_exit(f"   Loss: ${abs(net_profit):.2f}")
        log_exit(f"   Mock balance: ${_mock_balance:.2f}")
        
        del _mock_positions[asset_id]
        
        monitor = get_polymarket_monitor()
        if monitor:
            monitor.remove_position(asset_id)
    
    if positions_to_close:
        log_exit(f"📊 Closed {len(positions_to_close)} expired position(s)")
        show_mock_stats()


def run_main_loop():
    """
    Run the main continuous trading loop.
    
    This is the core trading loop that:
    1. Runs continuously (every 5 minutes)
    2. Discovers new markets
    3. Executes trades when conditions are met
    4. Monitors open positions
    5. Handles errors gracefully
    
    The loop can be stopped with Ctrl+C (KeyboardInterrupt).
    """
    global _binance_rsi_stream, _polymarket_monitor
    
    log_info("🚀 Starting Main Trading Loop", force=True)
    log_info("="*60, force=True)
    
    iteration_count = 0
    last_position_log = time.time()
    position_log_interval = 30  # Log position status every 30 seconds
    
    # Initialize WebSocket connections
    log_info("Initializing WebSocket connections...", force=True)
    
    # Initialize Binance RSI stream if RSI is enabled
    if CONFIG['rsi_enabled']:
        log_info("  Starting Binance RSI stream...", force=True)
        try:
            _binance_rsi_stream = BinanceRSIStream(
                symbol="BTCUSDT",
                period=CONFIG['rsi_period'],
                buffer_size=20
            )
            _binance_rsi_stream.start()
            time.sleep(2)  # Wait for connection
            log_info("  ✅ Binance RSI stream connected", force=True)
        except Exception as e:
            log_warn(f"  ⚠️ Failed to start Binance RSI stream: {e}")
            log_warn("  Continuing without RSI...")
            CONFIG['rsi_enabled'] = False
    else:
        log_info("  ⏭️ RSI disabled, skipping Binance stream", force=True)
    
    # Initialize Polymarket monitor
    log_info("  Starting Polymarket position monitor...", force=True)
    try:
        _polymarket_monitor = PolymarketPositionMonitor()
        _polymarket_monitor.start()
        time.sleep(1)  # Wait for connection
        log_info("  ✅ Polymarket monitor connected", force=True)
    except Exception as e:
        log_warn(f"  ⚠️ Failed to start Polymarket monitor: {e}")
    
    log_info("="*60, force=True)
    log_info("Trading loop started. Press Ctrl+C to stop.", force=True)
    log_info("="*60, force=True)
    
    while True:
        try:
            iteration_count += 1
            
            # Run trading iteration
            print(f"\n{'='*60}")
            print(f"📈 Iteration #{iteration_count}")
            print(f"{'='*60}")
            
            # Close any expired positions from previous iterations (losses)
            close_expired_positions()
            
            # Calculate time until next 5-minute interval
            sleep_seconds = calculate_sleep_until_next_5min()
            next_time = datetime.now(timezone.utc).timestamp() + sleep_seconds
            next_dt = datetime.fromtimestamp(next_time, tz=timezone.utc)
            
            print(f"⏳ Continuous monitoring until {next_dt.strftime('%H:%M:%S UTC')} ({sleep_seconds:.0f}s)")
            
            # Continuous trading check loop - keep checking entry conditions
            loop_start = time.time()
            last_trade_check = 0
            last_price_update = 0
            trade_check_interval = 5  # Check entry conditions every 5 seconds
            price_update_interval = 5  # Update prices every 5 seconds
            traded_this_iteration = False
            
            while time.time() - loop_start < sleep_seconds:
                current_time = time.time()
                
                # Check entry conditions periodically (every 5 seconds) if not already traded
                if not traded_this_iteration and (current_time - last_trade_check >= trade_check_interval):
                    last_trade_check = current_time
                    elapsed = int(current_time - loop_start)
                    
                    print(f"\n🔍 Checking entry conditions ({elapsed}s elapsed)...")
                    
                    result = run_trading_iteration()
                    status = result.get('status', 'unknown')
                    
                    if status == 'traded':
                        print(f"\n✅ Trade executed successfully")
                        print(f"   Position ID: {result.get('position_id')}")
                        shares = result.get('shares') or 0
                        entry_price = result.get('entry_price') or 0
                        print(f"   Shares: {shares:.2f}")
                        print(f"   Entry: ${entry_price:.3f}")
                        traded_this_iteration = True  # Don't try to enter again this iteration
                    elif status == 'skipped':
                        print(f"   ⏭️ No entry: {result.get('reason', 'Unknown')}")
                    elif status == 'failed':
                        print(f"   ❌ Failed: {result.get('reason', 'Unknown')}")
                    elif status == 'error':
                        print(f"   ⚠️ Error: {result.get('reason', 'Unknown')}")
                
                # Update position prices continuously (every 5 seconds)
                if len(_mock_positions) > 0 and (current_time - last_price_update >= price_update_interval):
                    last_price_update = current_time
                    # Update prices and check for exit conditions
                    update_mock_position_prices()
                
                # Log position status periodically (every 30 seconds)
                if current_time - last_position_log >= position_log_interval:
                    if len(_mock_positions) > 0:
                        elapsed = int(current_time - loop_start)
                        print(f"\n📊 Position status ({elapsed}s elapsed):")
                        log_position_status()
                    last_position_log = current_time
                
                # Sleep for 1 second at a time to stay responsive
                remaining = sleep_seconds - (time.time() - loop_start)
                if remaining > 0:
                    time.sleep(min(1, remaining))
            
            # Summary at end of iteration
            print(f"\n{'='*60}")
            if traded_this_iteration:
                print(f"✅ Iteration #{iteration_count} complete - Trade executed")
            else:
                print(f"⏭️ Iteration #{iteration_count} complete - No trade")
            print(f"   Open positions: {len(_mock_positions)}")
            print(f"{'='*60}")
            
        except Exception as e:
            print(f"\n❌ Error in main loop iteration: {e}")
            print("   Continuing to next iteration...")
            
            # Sleep before retrying to avoid rapid error loops
            time.sleep(10)


def shutdown_gracefully():
    """
    Shutdown the bot gracefully.
    
    Closes all WebSocket connections and saves mock trading history.
    Called when the bot receives a shutdown signal (Ctrl+C).
    """
    global _binance_rsi_stream, _polymarket_monitor
    
    print()
    print("="*60)
    print("🛑 Shutting down gracefully...")
    print("="*60)
    
    # Stop Binance RSI stream
    if _binance_rsi_stream:
        print("  Stopping Binance RSI stream...")
        try:
            _binance_rsi_stream.stop()
            print("  ✅ Binance RSI stream stopped")
        except Exception as e:
            print(f"  ⚠️ Error stopping Binance stream: {e}")
    
    # Stop Polymarket monitor
    if _polymarket_monitor:
        print("  Stopping Polymarket monitor...")
        try:
            _polymarket_monitor.stop()
            print("  ✅ Polymarket monitor stopped")
        except Exception as e:
            print(f"  ⚠️ Error stopping Polymarket monitor: {e}")
    
    # Save mock trading history
    if CONFIG['mock_trading']:
        print("  Saving mock trading history...")
        try:
            save_mock_history("mock_trades.json")
            print("  ✅ Mock history saved")
        except Exception as e:
            print(f"  ⚠️ Error saving mock history: {e}")
    
    # Show final stats
    print()
    show_mock_stats()
    
    print()
    print("="*60)
    print("👋 Bot stopped. Goodbye!")
    print("="*60)


def main():
    """Main entry point for the mock trading bot."""
    global CONFIG
    
    # Parse command-line arguments and update CONFIG
    CONFIG = parse_args_to_config()
    
    print()
    print("="*60)
    print("🤖 Mock Trading Bot - RSI Signal Enhancement")
    print("="*60)
    print(f"Started at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print()
    
    # Display configuration
    print("📋 Configuration:")
    print(f"  RSI Enabled: {CONFIG['rsi_enabled']}")
    print(f"  RSI Period: {CONFIG['rsi_period']}")
    print(f"  RSI Signal Memory: {CONFIG['rsi_signal_memory_size']}")
    print(f"  RSI Require Confirmation: {CONFIG['rsi_require_confirmation']}")
    print(f"  Min Momentum %: {CONFIG['min_momentum_pct']}")
    print(f"  Min Profit Per Share: ${CONFIG['min_profit_per_share']:.2f}")
    print(f"  Target Profit Per Trade: ${CONFIG['target_profit_per_trade']:.2f}")
    max_pos = CONFIG['max_position_size']
    print(f"  Max Position Size: ${max_pos:.2f}" if max_pos else "  Max Position Size: None (unlimited)")
    print(f"  Target Sell Spread: ${CONFIG['target_sell_spread']:.2f}")
    print(f"  Mock Trading: {CONFIG['mock_trading']}")
    print(f"  Mock Balance: ${CONFIG['mock_balance']:.2f}")
    print()
    
    # Safety warning for real trading
    if not CONFIG['mock_trading']:
        print("⚠️  WARNING: Mock trading is DISABLED!")
        print("⚠️  Real trades will be executed!")
        print("⚠️  Press Ctrl+C within 5 seconds to abort...")
        try:
            time.sleep(5)
        except KeyboardInterrupt:
            print("\n🛑 Aborted by user.")
            sys.exit(0)
        print("Proceeding with real trading...")
        print()
    
    # Reset mock trading state
    if CONFIG['mock_trading']:
        reset_mock_trading(CONFIG['mock_balance'])
    
    try:
        # Start main trading loop
        run_main_loop()
        
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        shutdown_gracefully()
        sys.exit(0)
    
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        shutdown_gracefully()
        sys.exit(1)


if __name__ == "__main__":
    main()
