# Implementation Tasks - RSI Signal Enhancement

## Overview
Implementation tasks for building a mock trading bot with RSI signals, WebSocket integration, and early exit functionality.

## Task List

- [ ] 1. Setup and Dependencies
  - [x] 1.1 Install required packages (websocket-client, numpy, requests)
  - [x] 1.2 Create mock_trader.py main file
  - [x] 1.3 Setup configuration management (config dict with defaults)

- [ ] 2. RSI Calculation Module
  - [x] 2.1 Implement calculate_rsi() function with standard RSI formula
  - [x] 2.2 Implement classify_signal() function (green/red/neutral)
  - [x] 2.3 Implement check_rsi_entry_signal() function
  - [x] 2.4 Add unit tests for RSI calculation edge cases

- [ ] 3. Binance WebSocket Integration
  - [x] 3.1 Create BinanceRSIStream class with WebSocket connection
  - [x] 3.2 Implement _fetch_initial_data() to get 20 historical candles
  - [x] 3.3 Implement _on_message() to process kline updates
  - [x] 3.4 Implement _recalculate_rsi() for rolling RSI calculation
  - [x] 3.5 Implement get_current_rsi_data() to return RSI values and classification
  - [x] 3.6 Add auto-reconnect logic for WebSocket disconnections
  - [x] 3.7 Test WebSocket connection and RSI updates

- [ ] 4. RSI Signal Memory
  - [x] 4.1 Create global _rsi_signal_memory list
  - [x] 4.2 Implement add_signal_to_memory() function
  - [x] 4.3 Implement FIFO logic (max 10 signals)
  - [x] 4.4 Test signal memory storage and retrieval

- [ ] 5. Market Discovery Functions
  - [x] 5.1 Implement round_to_5min() to round timestamps
  - [x] 5.2 Implement generate_market_slug() to create slug from timestamp
  - [x] 5.3 Implement fetch_market_by_slug() to query Gamma API
  - [x] 5.4 Implement discover_and_subscribe_market() main discovery function
  - [x] 5.5 Test market discovery with current timestamp

- [ ] 6. Polymarket WebSocket Integration
  - [x] 6.1 Create PolymarketPositionMonitor class
  - [x] 6.2 Implement _on_message() to handle book and price_change events
  - [x] 6.3 Implement _process_price_update() to calculate P&L
  - [x] 6.4 Implement _handle_market_resolution() for resolved markets
  - [x] 6.5 Implement _send_subscription() to subscribe to asset_ids
  - [x] 6.6 Implement _send_heartbeat() (PING every 10 seconds)
  - [x] 6.7 Implement add_position() to start monitoring a position
  - [x] 6.8 Implement remove_position() to stop monitoring
  - [x] 6.9 Test WebSocket connection and price updates

- [ ] 7. Mock Trading Engine
  - [x] 7.1 Create mock trading state variables (balance, positions, history, stats)
  - [x] 7.2 Implement get_mock_balance() function
  - [x] 7.3 Implement execute_mock_trade() for entry
  - [x] 7.4 Implement execute_mock_exit() for exit
  - [x] 7.5 Implement show_mock_stats() to display performance
  - [x] 7.6 Implement reset_mock_trading() to reset state
  - [x] 7.7 Implement save_mock_history() to save trades to JSON
  - [x] 7.8 Test mock trading with simulated trades

- [ ] 8. Profit Calculation Functions
  - [x] 8.1 Implement calculate_profit_and_position() for entry analysis
  - [x] 8.2 Implement check_balance_and_adjust_position() for balance checks
  - [x] 8.3 Test profit calculations with various scenarios

- [x] 9. Entry Logic Integration
  - [x] 9.1 Implement main trading decision function
  - [x] 9.2 Integrate momentum check (from existing code)
  - [x] 9.3 Integrate RSI check (optional, configurable)
  - [x] 9.4 Implement spread check using Polymarket spread API
  - [x] 9.5 Implement profit requirement check
  - [x] 9.6 Implement balance check
  - [x] 9.7 Implement market status check
  - [x] 9.8 Test entry logic with all conditions

- [x] 10. Exit Logic Integration
  - [x] 10.1 Implement exit callback function
  - [x] 10.2 Integrate with PolymarketPositionMonitor
  - [x] 10.3 Execute mock exit when target profit reached
  - [x] 10.4 Handle market resolution events
  - [x] 10.5 Test exit logic with price updates

- [x] 11. Main Trading Loop
  - [x] 11.1 Implement continuous loop (every 5 minutes)
  - [x] 11.2 Integrate market discovery
  - [x] 11.3 Integrate entry logic
  - [x] 11.4 Integrate position monitoring
  - [x] 11.5 Add keyboard interrupt handling (Ctrl+C)
  - [x] 11.6 Add error handling for failed markets
  - [x] 11.7 Test full trading loop

- [-] 12. Configuration and CLI
  - [x] 12.1 Define configuration schema with all parameters
  - [x] 12.2 Implement command-line argument parsing
  - [x] 12.3 Add --mock flag (default True)
  - [x] 12.4 Add --rsi-enabled flag (default False)
  - [x] 12.5 Add --target-profit flag (default 15.0)
  - [x] 12.6 Add --mock-balance flag (default 1000.0)
  - [x] 12.7 Test configuration loading

- [x] 13. Logging and Output
  - [x] 13.1 Implement log() function with [MOCK] prefix
  - [x] 13.2 Add detailed logging for all operations
  - [x] 13.3 Add performance summary output
  - [x] 13.4 Add position status logging (every 30 seconds)
  - [x] 13.5 Test logging output

- [x] 14. Error Handling and Edge Cases
  - [x] 14.1 Handle WebSocket disconnections (auto-reconnect)
  - [x] 14.2 Handle API failures (retry with backoff)
  - [x] 14.3 Handle insufficient RSI data
  - [x] 14.4 Handle market not found
  - [x] 14.5 Handle insufficient mock balance
  - [x] 14.6 Test error scenarios

- [x] 15. Testing and Validation
  - [x] 15.1 Test RSI calculation accuracy
  - [x] 15.2 Test signal classification logic
  - [x] 15.3 Test mock trading P&L calculations
  - [x] 15.4 Test WebSocket connections (Binance + Polymarket)
  - [x] 15.5 Test market discovery with various timestamps
  - [x] 15.6 Test full end-to-end flow with mock trades
  - [x] 15.7 Run bot for 1 hour and verify behavior

- [ ] 16. Documentation
  - [ ] 16.1 Add docstrings to all functions
  - [ ] 16.2 Create README with usage instructions
  - [ ] 16.3 Document configuration options
  - [ ] 16.4 Add example output screenshots
  - [ ] 16.5 Document how to switch from mock to real trading

## Notes

- Start with tasks 1-2 (setup and RSI calculation) as they're foundational
- Tasks 3-4 (Binance WebSocket) can be done in parallel with task 5 (market discovery)
- Task 6 (Polymarket WebSocket) depends on task 5 (need asset_ids)
- Task 7 (mock trading) is independent and can be done early
- Tasks 9-10 (entry/exit logic) depend on tasks 2-8
- Task 11 (main loop) integrates everything
- Tasks 12-16 are polish and can be done last

## Priority Order

1. **Phase 1 - Core Functionality** (Tasks 1-5): Setup, RSI, market discovery
2. **Phase 2 - Mock Trading** (Task 7): Get mock trading working standalone
3. **Phase 3 - WebSockets** (Tasks 3, 6): Real-time data streams
4. **Phase 4 - Integration** (Tasks 8-11): Connect all pieces
5. **Phase 5 - Polish** (Tasks 12-16): CLI, logging, testing, docs
