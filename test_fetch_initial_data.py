#!/usr/bin/env python3
"""
Test script for _fetch_initial_data() implementation.

This script tests the BinanceRSIStream class initialization and
verifies that historical data is fetched correctly.
"""

import sys
from mock_trader import BinanceRSIStream

def test_fetch_initial_data():
    """Test fetching initial historical data from Binance API."""
    print("="*60)
    print("Testing _fetch_initial_data() Implementation")
    print("="*60)
    print()
    
    try:
        # Create BinanceRSIStream instance
        # This should automatically fetch initial data
        print("Creating BinanceRSIStream instance...")
        stream = BinanceRSIStream(symbol="BTCUSDT", period=7, buffer_size=20)
        
        print()
        print("="*60)
        print("Test Results")
        print("="*60)
        
        # Verify close_prices buffer
        print(f"\n1. Close Prices Buffer:")
        print(f"   - Length: {len(stream.close_prices)}")
        print(f"   - Expected: 20")
        print(f"   - Status: {'✓ PASS' if len(stream.close_prices) == 20 else '✗ FAIL'}")
        
        if len(stream.close_prices) > 0:
            print(f"   - First price: ${stream.close_prices[0]:.2f}")
            print(f"   - Last price: ${stream.close_prices[-1]:.2f}")
            print(f"   - Min price: ${min(stream.close_prices):.2f}")
            print(f"   - Max price: ${max(stream.close_prices):.2f}")
        
        # Verify RSI values
        print(f"\n2. RSI Values:")
        print(f"   - Length: {len(stream.rsi_values)}")
        print(f"   - Expected: ~13 (20 prices - 7 period)")
        print(f"   - Status: {'✓ PASS' if len(stream.rsi_values) >= 10 else '✗ FAIL'}")
        
        if len(stream.rsi_values) > 0:
            print(f"   - First RSI: {stream.rsi_values[0]:.2f}")
            print(f"   - Last RSI: {stream.rsi_values[-1]:.2f}")
            print(f"   - Min RSI: {min(stream.rsi_values):.2f}")
            print(f"   - Max RSI: {max(stream.rsi_values):.2f}")
        
        # Verify RSI values are in valid range (0-100)
        print(f"\n3. RSI Value Range:")
        if len(stream.rsi_values) > 0:
            all_valid = all(0 <= rsi <= 100 for rsi in stream.rsi_values)
            print(f"   - All RSI values in range [0, 100]: {'✓ PASS' if all_valid else '✗ FAIL'}")
        else:
            print(f"   - No RSI values to validate: ✗ FAIL")
        
        # Overall test result
        print()
        print("="*60)
        success = (
            len(stream.close_prices) == 20 and
            len(stream.rsi_values) >= 10 and
            all(0 <= rsi <= 100 for rsi in stream.rsi_values)
        )
        
        if success:
            print("✓ ALL TESTS PASSED")
            print("_fetch_initial_data() is working correctly!")
        else:
            print("✗ SOME TESTS FAILED")
            print("Please review the implementation.")
        
        print("="*60)
        
        return success
        
    except Exception as e:
        print()
        print("="*60)
        print("✗ TEST FAILED WITH EXCEPTION")
        print("="*60)
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_fetch_initial_data()
    sys.exit(0 if success else 1)
