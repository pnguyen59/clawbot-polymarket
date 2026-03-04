# Auto-Reconnect Documentation

## Overview

The `BinanceRSIStream` class now includes automatic reconnection logic for handling WebSocket disconnections gracefully. This feature ensures continuous RSI data streaming even when network issues or server disconnections occur.

## Features

### 1. Automatic Reconnection
- Automatically attempts to reconnect when the WebSocket connection is lost
- Works for both expected and unexpected disconnections
- Preserves data buffers (close prices and RSI values) across reconnections

### 2. Exponential Backoff
- Uses exponential backoff strategy to avoid overwhelming the server
- Formula: `delay = min(max_delay, base_delay * 2^attempts)`
- Default configuration:
  - Base delay: 1 second
  - Max delay: 60 seconds
  - Max attempts: 10 (configurable, can be set to `None` for infinite)

### 3. Connection Status Monitoring
- `is_connected()`: Check if WebSocket is currently connected
- `get_connection_status()`: Get detailed connection information including:
  - Connection state
  - Number of reconnection attempts
  - Buffer sizes
  - Symbol and period information

### 4. Graceful Shutdown
- `stop()` method disables auto-reconnect to prevent reconnection after manual stop
- Cancels any pending reconnection attempts
- Properly closes WebSocket connection

## Configuration

The auto-reconnect behavior can be configured through instance attributes:

```python
stream = BinanceRSIStream(symbol="BTCUSDT", period=7, buffer_size=20)

# Configure reconnection behavior
stream.reconnect_enabled = True           # Enable/disable auto-reconnect
stream.max_reconnect_attempts = 10        # Max attempts (None = infinite)
stream.base_reconnect_delay = 1.0         # Base delay in seconds
stream.max_reconnect_delay = 60.0         # Maximum delay in seconds
```

## Reconnection Delays

The exponential backoff produces the following delays:

| Attempt | Delay (seconds) |
|---------|----------------|
| 1       | 1.0            |
| 2       | 2.0            |
| 3       | 4.0            |
| 4       | 8.0            |
| 5       | 16.0           |
| 6       | 32.0           |
| 7+      | 60.0 (capped)  |

## Usage Examples

### Basic Usage

```python
from mock_trader import BinanceRSIStream

# Create stream with auto-reconnect enabled by default
stream = BinanceRSIStream(symbol="BTCUSDT", period=7, buffer_size=20)

# Start WebSocket connection
stream.start()

# Check connection status
if stream.is_connected():
    print("Connected!")
    
# Get detailed status
status = stream.get_connection_status()
print(f"Reconnect attempts: {status['reconnect_attempts']}")
print(f"Buffer size: {status['buffer_size']}")

# Stop when done (disables auto-reconnect)
stream.stop()
```

### Monitoring Reconnection Attempts

```python
import time

stream = BinanceRSIStream(symbol="BTCUSDT", period=7, buffer_size=20)
stream.start()

# Monitor connection status
while True:
    status = stream.get_connection_status()
    
    if not status['connected']:
        print(f"Disconnected. Reconnection attempts: {status['reconnect_attempts']}")
    else:
        print("Connected and streaming data")
    
    time.sleep(5)
```

### Custom Reconnection Configuration

```python
# Create stream with custom reconnection settings
stream = BinanceRSIStream(symbol="BTCUSDT", period=7, buffer_size=20)

# Configure for more aggressive reconnection
stream.base_reconnect_delay = 0.5      # Start with 0.5 second delay
stream.max_reconnect_delay = 30.0      # Cap at 30 seconds
stream.max_reconnect_attempts = None   # Infinite attempts

stream.start()
```

### Disable Auto-Reconnect

```python
# Create stream without auto-reconnect
stream = BinanceRSIStream(symbol="BTCUSDT", period=7, buffer_size=20)
stream.reconnect_enabled = False  # Disable before starting

stream.start()
```

## Implementation Details

### Reconnection Flow

1. **Connection Lost**: WebSocket `_on_close()` is triggered
2. **Check Enabled**: Verify `reconnect_enabled` is `True`
3. **Check Max Attempts**: Verify we haven't exceeded `max_reconnect_attempts`
4. **Calculate Delay**: Use exponential backoff formula
5. **Schedule Reconnect**: Create timer thread to reconnect after delay
6. **Increment Counter**: Increase `reconnect_attempts`
7. **Attempt Reconnect**: Call `_reconnect()` method after delay
8. **On Success**: Reset `reconnect_attempts` to 0 in `_on_open()`
9. **On Failure**: Repeat from step 3

### Buffer Preservation

Data buffers are preserved across reconnections:
- `close_prices`: Rolling buffer of recent close prices
- `rsi_values`: Rolling buffer of calculated RSI values

This ensures continuity of RSI calculations even after reconnection.

### Thread Safety

The reconnection logic uses daemon threads that:
- Run in the background without blocking the main thread
- Automatically terminate when the main program exits
- Can be cancelled via the `stop()` method

## Logging

The auto-reconnect feature provides detailed logging:

```
[Binance WebSocket] Connection closed (code: 1006, msg: Connection lost)
[Binance WebSocket] Scheduling reconnection attempt 1 in 1.0 seconds...
[Binance WebSocket] Attempting to reconnect (attempt 1)...
[Binance WebSocket] Connected: btcusdt@kline_1m
```

## Error Handling

### Connection Errors
- Logged via `_on_error()` handler
- Reconnection triggered by `_on_close()`

### Reconnection Failures
- If reconnection fails, another attempt is scheduled
- Continues until max attempts reached or connection succeeds

### Max Attempts Reached
```
[Binance WebSocket] Max reconnection attempts (10) reached. Giving up.
```

### Manual Stop
```
[Binance WebSocket] Stopping connection...
[Binance WebSocket] Connection stopped
```

## Testing

Comprehensive tests are provided in `test_auto_reconnect.py`:

```bash
python3 test_auto_reconnect.py
```

Test coverage includes:
- Exponential backoff calculation
- Reconnection counter reset on success
- Max attempts limit enforcement
- Reconnection scheduling
- Buffer preservation
- Connection status methods
- Stop functionality
- Integration scenarios

## Best Practices

1. **Always use `stop()` when done**: This ensures clean shutdown and prevents reconnection attempts after you're done with the stream.

2. **Monitor connection status**: Use `get_connection_status()` to track reconnection attempts and detect persistent connection issues.

3. **Set reasonable max attempts**: For production use, set `max_reconnect_attempts` to a reasonable value (e.g., 10-20) to avoid infinite reconnection loops.

4. **Handle persistent failures**: If reconnection attempts are consistently failing, investigate network issues or API availability.

5. **Preserve buffers**: The auto-reconnect feature preserves data buffers, so RSI calculations continue seamlessly after reconnection.

## Troubleshooting

### Connection keeps disconnecting
- Check network stability
- Verify Binance API is accessible
- Check for rate limiting issues

### Reconnection not working
- Verify `reconnect_enabled` is `True`
- Check if max attempts has been reached
- Review logs for error messages

### Slow reconnection
- Adjust `base_reconnect_delay` for faster initial attempts
- Reduce `max_reconnect_delay` if needed
- Note: Too aggressive reconnection may trigger rate limits

## Requirements

The auto-reconnect feature requires:
- Python 3.7+
- `websocket-client` library
- `threading` module (standard library)

## Acceptance Criteria (Task 3.6)

✅ Handle WebSocket disconnections gracefully
✅ Automatically reconnect when connection is lost
✅ Implement exponential backoff for reconnection attempts
✅ Preserve data buffers across reconnections
✅ Log reconnection attempts

All acceptance criteria have been met and verified through comprehensive testing.
