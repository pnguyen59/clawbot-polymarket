#!/usr/bin/env python3
"""
Test script to execute a market BUY then SELL order on Polymarket.

This test:
1. Finds the current BTC 5-minute market
2. Buys $10 worth of YES tokens (market order)
3. Waits a few seconds
4. Sells all tokens back (market order)

Usage:
    export POLYMARKET_PRIVATE_KEY=0x...
    python test_market_order.py
    
    # Dry run (no real trades)
    python test_market_order.py --dry-run
"""

import os
import sys
import time
import json
import argparse
import requests

try:
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import (
        BalanceAllowanceParams,
        MarketOrderArgs,
        PartialCreateOrderOptions,
        OrderType,
    )
    from eth_account import Account
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("   Run: pip install py-clob-client")
    sys.exit(1)


CLOB_HOST = "https://clob.polymarket.com"
GAMMA_API_HOST = "https://gamma-api.polymarket.com"
CHAIN_ID = 137
SIGNATURE_TYPE = 1  # POLY_PROXY

# Side constants
BUY = "BUY"
SELL = "SELL"

# Test amount
TEST_AMOUNT = 2  # $10


def get_current_btc_market():
    """Get current BTC 5-minute market with YES and NO token IDs."""
    now = int(time.time())
    rounded_ts = (now // 300) * 300
    slug = f"btc-updown-5m-{rounded_ts}"
    
    print(f"   Looking for market: {slug}")
    
    try:
        url = f"{GAMMA_API_HOST}/markets?slug={slug}"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        if not data or len(data) == 0:
            print(f"   Market not found: {slug}")
            return None
        
        market = data[0]
        
        # Extract token information (same as mock_trader.py)
        clob_token_ids = market.get('clobTokenIds', [])
        outcomes = market.get('outcomes', [])
        outcome_prices = market.get('outcomePrices', [])
        
        # Handle JSON strings
        if isinstance(clob_token_ids, str):
            clob_token_ids = json.loads(clob_token_ids)
        if isinstance(outcomes, str):
            outcomes = json.loads(outcomes)
        if isinstance(outcome_prices, str):
            outcome_prices = json.loads(outcome_prices)
        
        # Build tokens list
        tokens = []
        yes_token = None
        no_token = None
        
        print(f"   Raw outcomes: {outcomes}")
        
        for i, (token_id, outcome) in enumerate(zip(clob_token_ids, outcomes)):
            price = 0.0
            if i < len(outcome_prices):
                try:
                    price = float(outcome_prices[i])
                except (ValueError, TypeError):
                    price = 0.0
            
            token_info = {
                'asset_id': token_id,  # Use asset_id like mock_trader
                'outcome': outcome,
                'price': price
            }
            tokens.append(token_info)
            
            # Track YES/Up and NO/Down tokens (handle different naming)
            outcome_upper = outcome.upper()
            if outcome_upper in ('YES', 'UP'):
                yes_token = token_info
            elif outcome_upper in ('NO', 'DOWN'):
                no_token = token_info
        
        # Fallback: if no match, use first token as YES, second as NO
        if not yes_token and len(tokens) >= 1:
            yes_token = tokens[0]
            print(f"   Using first token as YES: {yes_token['outcome']}")
        if not no_token and len(tokens) >= 2:
            no_token = tokens[1]
            print(f"   Using second token as NO: {no_token['outcome']}")
        
        return {
            'market_id': market.get('conditionId'),
            'slug': slug,
            'question': market.get('question', 'N/A'),
            'tokens': tokens,
            'yes_token': yes_token,
            'no_token': no_token,
        }
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    return None


def run_test(private_key: str, dry_run: bool = False):
    """Run the market order test."""
    
    if not private_key.startswith('0x'):
        private_key = '0x' + private_key
    
    print()
    print("="*60)
    print("🧪 Market Order Test")
    print("="*60)
    print(f"   Test amount: ${TEST_AMOUNT:.2f}")
    print(f"   Dry run: {dry_run}")
    
    # Get wallet address
    try:
        account = Account.from_key(private_key)
        # wallet_address = account.address
        wallet_address="0x02d2364332eC53a5D8439d660558C02170b10C12"
        print(f"   Wallet: {wallet_address}")
    except Exception as e:
        print(f"❌ Invalid private key: {e}")
        return
    
    # Step 1: Initialize client
    print("\n" + "-"*40)
    print("1️⃣ Initializing client...")
    print("-"*40)
    
    try:
        # First create client to derive credentials
        client = ClobClient(
            CLOB_HOST,
            key=private_key,
            chain_id=CHAIN_ID,
            signature_type=SIGNATURE_TYPE,
            funder=wallet_address,
        )
        
        # Derive API credentials
        print("   Deriving API credentials...")
        creds = client.create_or_derive_api_creds()
        if not creds:
            print("   ❌ Failed to get API credentials")
            return
        
        print(f"   ✅ API Key: {creds.api_key[:12]}...")
        print(f"   ✅ Secret: {creds.api_secret[:12]}...")
        print(f"   ✅ Passphrase: {creds.api_passphrase[:12]}...")
        
        # Reinitialize client with credentials for authenticated requests
        from py_clob_client.clob_types import ApiCreds
        api_creds = ApiCreds(
            api_key=creds.api_key,
            api_secret=creds.api_secret,
            api_passphrase=creds.api_passphrase,
        )
        
        client = ClobClient(
            CLOB_HOST,
            key=private_key,
            chain_id=CHAIN_ID,
            signature_type=SIGNATURE_TYPE,
            funder=wallet_address,
            creds=api_creds,
        )
        
        print(f"   ✅ Client ready with credentials")
        
    except Exception as e:
        print(f"   ❌ Init error: {e}")
        return
    
    # Step 2: Check USDC balance
    print("\n" + "-"*40)
    print("2️⃣ Checking USDC balance...")
    print("-"*40)
    
    try:
        params = BalanceAllowanceParams(asset_type="COLLATERAL")
        balance_info = client.get_balance_allowance(params)
        
        if balance_info:
            balance = int(balance_info.get('balance', '0')) / 1_000_000
            print(f"   💵 USDC Balance: ${balance:,.2f}")
            
            if balance < TEST_AMOUNT:
                print(f"   ❌ Insufficient balance (need ${TEST_AMOUNT:.2f})")
                return
        else:
            print("   ⚠️ Could not get balance")
            
    except Exception as e:
        print(f"   ❌ Balance error: {e}")
        return
    
    # Step 3: Find current BTC market
    print("\n" + "-"*40)
    print("3️⃣ Finding BTC market...")
    print("-"*40)
    
    market = get_current_btc_market()
    
    if not market or not market.get('tokens'):
        print("   ❌ No active market found")
        return
    
    print(f"   ✅ Market: {market['slug']}")
    print(f"   Question: {market['question'][:50]}...")
    
    # Get YES and NO tokens
    yes_token = market.get('yes_token')
    no_token = market.get('no_token')
    
    if not yes_token:
        print("   ❌ No YES token found")
        return
    
    if not no_token:
        print("   ❌ No NO token found")
        return
    
    # Display both tokens
    print()
    print(f"   YES Token:")
    print(f"      ID: {yes_token['asset_id'][:30]}...")
    print(f"      Price: ${yes_token['price']:.3f}")
    print()
    print(f"   NO Token:")
    print(f"      ID: {no_token['asset_id'][:30]}...")
    print(f"      Price: ${no_token['price']:.3f}")
    
    # Use YES token for the test
    token_id = yes_token['asset_id']
    token_price = yes_token['price']
    
    # Variable to store shares bought
    shares_bought = 0
    
    # Step 4: Place market BUY order
    print("\n" + "-"*40)
    print("4️⃣ Placing market BUY order...")
    print("-"*40)
    print(f"   Amount: ${TEST_AMOUNT:.2f}")
    print(f"   Token: YES ({token_id[:16]}...)")
    
    if dry_run:
        print("   🔸 DRY RUN - Skipping actual order")
        shares_bought = TEST_AMOUNT / token_price
        print(f"   Would buy ~{shares_bought:.2f} shares @ ${token_price:.3f}")
    else:
        try:
            print("   Submitting order...")
            
            # Create market order args
            order_args = MarketOrderArgs(
                token_id=token_id,
                amount=TEST_AMOUNT,
                side=BUY,
            )
            
            options = PartialCreateOrderOptions(
                tick_size="0.01",
                neg_risk=False,
            )
            
            # Create and sign the order
            signed_order = client.create_market_order(order_args, options)
            
            # Post the order
            response = client.post_order(signed_order, orderType=OrderType.FOK)
            
            if response:
                print(f"   ✅ BUY order executed!")
                print(f"   Response: {json.dumps(response, indent=2)[:200]}...")
                
                # Get shares bought from takingAmount
                taking_amount = response.get('takingAmount', '0')
                shares_bought = float(taking_amount)
                print(f"   📊 Shares bought (takingAmount): {shares_bought:.6f}")
            else:
                print("   ❌ BUY order failed - no response")
                return
                
        except Exception as e:
            print(f"   ❌ BUY order error: {e}")
            return
    
    # Step 5: Wait for settlement
    print("\n" + "-"*40)
    print("5️⃣ Waiting for settlement (10 seconds)...")
    print("-"*40)
    time.sleep(10)
    
    # Step 6: Verify token balance before selling
    print("\n" + "-"*40)
    print("6️⃣ Verifying token balance...")
    print("-"*40)
    
    # Use shares_bought from BUY response (takingAmount)
    shares_to_sell = shares_bought
    
    if dry_run:
        shares_to_sell = TEST_AMOUNT / token_price
        print(f"   🔸 DRY RUN - Assuming {shares_to_sell:.2f} shares")
    else:
        print(f"   📊 Expected shares (from BUY takingAmount): {shares_to_sell:.6f}")
        
        # Check actual token balance with retries
        actual_balance = 0
        max_retries = 5
        for attempt in range(max_retries):
            try:
                params = BalanceAllowanceParams(
                    asset_type="CONDITIONAL",
                    token_id=token_id
                )
                token_balance = client.get_balance_allowance(params)
                
                if token_balance:
                    actual_balance = int(token_balance.get('balance', '0')) / 1_000_000
                    print(f"   📊 Actual token balance: {actual_balance:.6f} shares")
                    
                    if actual_balance > 0:
                        shares_to_sell = actual_balance
                        break
                    else:
                        print(f"   ⏳ Balance not settled yet, waiting... ({attempt + 1}/{max_retries})")
                        time.sleep(3)
                        
            except Exception as e:
                print(f"   ⚠️ Balance check error: {e}")
                time.sleep(3)
        
        if actual_balance <= 0:
            print("   ❌ Token balance still 0 after waiting. Settlement may take longer.")
            print("   💡 Try running the script again in a minute to sell the tokens.")
            return
    
    if shares_to_sell <= 0:
        print("   ⚠️ No shares to sell")
        return
    
    # Step 7: Place market SELL order
    print("\n" + "-"*40)
    print("7️⃣ Placing market SELL order...")
    print("-"*40)
    print(f"   Shares: {shares_to_sell:.6f}")
    print(f"   Token: YES ({token_id[:16]}...)")
    
    if dry_run:
        print("   🔸 DRY RUN - Skipping actual order")
        estimated_return = shares_to_sell * token_price
        print(f"   Would sell {shares_to_sell:.2f} shares @ ~${token_price:.3f}")
        print(f"   Estimated return: ~${estimated_return:.2f}")
    else:
        try:
            print("   Submitting order...")
            
            # Create market order args
            order_args = MarketOrderArgs(
                token_id=token_id,
                amount=shares_to_sell,
                side=SELL
                # price=token_price,
            )
            
            options = PartialCreateOrderOptions(
                tick_size="0.01",
                neg_risk=False,
            )
            
            # Create and sign the order
            signed_order = client.create_market_order(order_args, options)
            
            # Post the order
            response = client.post_order(signed_order, orderType=OrderType.FOK)
            
            if response:
                print(f"   ✅ SELL order executed!")
                print(f"   Response: {json.dumps(response, indent=2)[:200]}...")
            else:
                print("   ❌ SELL order failed - no response")
                
        except Exception as e:
            print(f"   ❌ SELL order error: {e}")
    
    # Step 8: Final balance check
    print("\n" + "-"*40)
    print("8️⃣ Final balance check...")
    print("-"*40)
    
    if not dry_run:
        try:
            time.sleep(2)  # Wait for settlement
            
            params = BalanceAllowanceParams(asset_type="COLLATERAL")
            balance_info = client.get_balance_allowance(params)
            
            if balance_info:
                final_balance = int(balance_info.get('balance', '0')) / 1_000_000
                print(f"   💵 Final USDC: ${final_balance:,.2f}")
                print(f"   📊 Change: ${final_balance - balance:+.2f}")
                
        except Exception as e:
            print(f"   ⚠️ Final balance error: {e}")
    
    print()
    print("="*60)
    print("✅ Test complete!")
    print("="*60)
    print()


def main():
    parser = argparse.ArgumentParser(description='Test market orders')
    parser.add_argument('--private-key', type=str, default=None)
    parser.add_argument('--dry-run', action='store_true', help='Simulate without executing')
    args = parser.parse_args()
    
    private_key = args.private_key or os.environ.get('POLYMARKET_PRIVATE_KEY')
    
    if not private_key:
        print("❌ Private key required")
        print()
        print("Usage:")
        print("  export POLYMARKET_PRIVATE_KEY=0x...")
        print("  python test_market_order.py")
        print()
        print("  # Dry run:")
        print("  python test_market_order.py --dry-run")
        sys.exit(1)
    
    run_test(private_key, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
