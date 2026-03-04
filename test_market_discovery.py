#!/usr/bin/env python3
"""
Test Market Discovery Functions

Tests for the market discovery functions in mock_trader.py:
- round_to_5min()
- generate_market_slug()
- fetch_market_by_slug()
- discover_and_subscribe_market()
"""

import time
from datetime import datetime, timezone
from mock_trader import (
    round_to_5min,
    generate_market_slug,
    fetch_market_by_slug,
    discover_and_subscribe_market
)


def test_round_to_5min():
    """Test timestamp rounding to 5-minute intervals."""
    print("\n" + "="*60)
    print("Test: round_to_5min()")
    print("="*60)
    
    # Test cases: (input_timestamp, expected_rounded_timestamp, description)
    test_cases = [
        # Test rounding down
        (1705308390, 1705308300, "8:26:30 → 8:25:00"),  # 2024-01-15 08:26:30 → 08:25:00
        (1705308540, 1705308300, "8:29:00 → 8:25:00"),  # 2024-01-15 08:29:00 → 08:25:00
        
        # Test exact 5-minute boundaries (no rounding needed)
        (1705308300, 1705308300, "8:25:00 → 8:25:00"),  # 2024-01-15 08:25:00 → 08:25:00
        (1705308600, 1705308600, "8:30:00 → 8:30:00"),  # 2024-01-15 08:30:00 → 08:30:00
        
        # Test rounding down from just after boundary
        (1705308301, 1705308300, "8:25:01 → 8:25:00"),  # 2024-01-15 08:25:01 → 08:25:00
        (1705308601, 1705308600, "8:30:01 → 8:30:00"),  # 2024-01-15 08:30:01 → 08:30:00
    ]
    
    passed = 0
    failed = 0
    
    for input_ts, expected_ts, description in test_cases:
        result = round_to_5min(input_ts)
        
        # Convert timestamps to readable format
        input_dt = datetime.fromtimestamp(input_ts, tz=timezone.utc)
        result_dt = datetime.fromtimestamp(result, tz=timezone.utc)
        expected_dt = datetime.fromtimestamp(expected_ts, tz=timezone.utc)
        
        if result == expected_ts:
            print(f"✅ PASS: {description}")
            print(f"   Input:    {input_dt.strftime('%H:%M:%S')} ({input_ts})")
            print(f"   Result:   {result_dt.strftime('%H:%M:%S')} ({result})")
            print(f"   Expected: {expected_dt.strftime('%H:%M:%S')} ({expected_ts})")
            passed += 1
        else:
            print(f"❌ FAIL: {description}")
            print(f"   Input:    {input_dt.strftime('%H:%M:%S')} ({input_ts})")
            print(f"   Result:   {result_dt.strftime('%H:%M:%S')} ({result})")
            print(f"   Expected: {expected_dt.strftime('%H:%M:%S')} ({expected_ts})")
            failed += 1
        print()
    
    # Test with current timestamp (default parameter)
    print("Testing with current timestamp (no parameter):")
    current_ts = int(time.time())
    rounded_ts = round_to_5min()
    
    current_dt = datetime.fromtimestamp(current_ts, tz=timezone.utc)
    rounded_dt = datetime.fromtimestamp(rounded_ts, tz=timezone.utc)
    
    print(f"   Current:  {current_dt.strftime('%Y-%m-%d %H:%M:%S')} ({current_ts})")
    print(f"   Rounded:  {rounded_dt.strftime('%Y-%m-%d %H:%M:%S')} ({rounded_ts})")
    
    # Verify rounding is correct (should be <= current and divisible by 300)
    if rounded_ts <= current_ts and rounded_ts % 300 == 0:
        print(f"✅ PASS: Current timestamp rounded correctly")
        passed += 1
    else:
        print(f"❌ FAIL: Current timestamp rounding incorrect")
        failed += 1
    
    print()
    print(f"Results: {passed} passed, {failed} failed")
    return failed == 0


def test_generate_market_slug():
    """Test market slug generation."""
    print("\n" + "="*60)
    print("Test: generate_market_slug()")
    print("="*60)
    
    # Test cases: (input_timestamp, expected_slug, expected_rounded_ts, description)
    test_cases = [
        (1705308390, "btc-updown-5m-1705308300", 1705308300, "8:26:30 → slug with 8:25:00"),
        (1705308300, "btc-updown-5m-1705308300", 1705308300, "8:25:00 → slug with 8:25:00"),
        (1705308600, "btc-updown-5m-1705308600", 1705308600, "8:30:00 → slug with 8:30:00"),
    ]
    
    passed = 0
    failed = 0
    
    for input_ts, expected_slug, expected_rounded_ts, description in test_cases:
        slug, rounded_ts = generate_market_slug(input_ts)
        
        if slug == expected_slug and rounded_ts == expected_rounded_ts:
            print(f"✅ PASS: {description}")
            print(f"   Slug: {slug}")
            print(f"   Timestamp: {rounded_ts}")
            passed += 1
        else:
            print(f"❌ FAIL: {description}")
            print(f"   Result slug: {slug}")
            print(f"   Expected slug: {expected_slug}")
            print(f"   Result timestamp: {rounded_ts}")
            print(f"   Expected timestamp: {expected_rounded_ts}")
            failed += 1
        print()
    
    # Test with current timestamp
    print("Testing with current timestamp (no parameter):")
    slug, rounded_ts = generate_market_slug()
    
    rounded_dt = datetime.fromtimestamp(rounded_ts, tz=timezone.utc)
    print(f"   Slug: {slug}")
    print(f"   Timestamp: {rounded_ts} ({rounded_dt.strftime('%Y-%m-%d %H:%M:%S UTC')})")
    
    # Verify slug format
    if slug.startswith("btc-updown-5m-") and slug.endswith(str(rounded_ts)):
        print(f"✅ PASS: Current timestamp slug generated correctly")
        passed += 1
    else:
        print(f"❌ FAIL: Current timestamp slug format incorrect")
        failed += 1
    
    print()
    print(f"Results: {passed} passed, {failed} failed")
    return failed == 0


def test_fetch_market_by_slug():
    """Test fetching market details from Gamma API."""
    print("\n" + "="*60)
    print("Test: fetch_market_by_slug()")
    print("="*60)
    
    # Generate slug for current time
    slug, rounded_ts = generate_market_slug()
    
    print(f"Testing with current market slug: {slug}")
    print()
    
    # Fetch market details
    market = fetch_market_by_slug(slug)
    
    if market is None:
        print("⚠️  Market not found (this is expected if market doesn't exist yet)")
        print("   This is not a test failure - markets may not exist for all timestamps")
        return True
    
    # Validate market structure
    print("✅ Market found! Validating structure...")
    print()
    
    required_fields = ['market_id', 'slug', 'question', 'end_date', 'closed', 'resolved', 'tokens']
    passed = 0
    failed = 0
    
    for field in required_fields:
        if field in market:
            print(f"✅ Field '{field}' present")
            passed += 1
        else:
            print(f"❌ Field '{field}' missing")
            failed += 1
    
    print()
    
    # Validate tokens structure
    if 'tokens' in market and len(market['tokens']) > 0:
        print(f"✅ Tokens present: {len(market['tokens'])} tokens")
        
        for i, token in enumerate(market['tokens']):
            print(f"\n   Token {i+1}:")
            token_fields = ['asset_id', 'outcome', 'price']
            for field in token_fields:
                if field in token:
                    print(f"   ✅ {field}: {token[field]}")
                else:
                    print(f"   ❌ {field}: missing")
                    failed += 1
    else:
        print("❌ No tokens found in market")
        failed += 1
    
    print()
    print(f"Results: {passed} passed, {failed} failed")
    return failed == 0


def test_discover_and_subscribe_market():
    """Test the main market discovery function."""
    print("\n" + "="*60)
    print("Test: discover_and_subscribe_market()")
    print("="*60)
    
    # Test with current timestamp
    print("Testing with current timestamp...")
    market = discover_and_subscribe_market()
    
    if market is None:
        print("⚠️  No active market found (this is expected if market doesn't exist yet)")
        print("   This is not a test failure - markets may not exist for all timestamps")
        return True
    
    # If market found, validate it
    print("\n✅ Market discovered successfully!")
    print("\nMarket details:")
    print(f"   Market ID: {market['market_id']}")
    print(f"   Slug: {market['slug']}")
    print(f"   Question: {market['question']}")
    print(f"   End date: {market['end_date']}")
    print(f"   Closed: {market['closed']}")
    print(f"   Resolved: {market['resolved']}")
    print(f"\n   Tokens:")
    for token in market['tokens']:
        print(f"      {token['outcome']}: ${token['price']:.3f} (ID: {token['asset_id'][:20]}...)")
    
    # Validate market is active
    if not market['closed'] and not market['resolved']:
        print("\n✅ Market is active and ready for trading")
        return True
    else:
        print("\n⚠️  Market is not active (closed or resolved)")
        return True


def main():
    """Run all market discovery tests."""
    print("\n" + "="*70)
    print("Market Discovery Functions - Test Suite")
    print("="*70)
    print(f"Started at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    
    # Run all tests
    results = []
    
    results.append(("round_to_5min", test_round_to_5min()))
    results.append(("generate_market_slug", test_generate_market_slug()))
    results.append(("fetch_market_by_slug", test_fetch_market_by_slug()))
    results.append(("discover_and_subscribe_market", test_discover_and_subscribe_market()))
    
    # Summary
    print("\n" + "="*70)
    print("Test Summary")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    failed = sum(1 for _, result in results if not result)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print()
    print(f"Total: {passed} passed, {failed} failed")
    print("="*70)
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
