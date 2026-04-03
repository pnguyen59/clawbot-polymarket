#!/usr/bin/env python3
"""
Test script to check Polymarket account balance.

Usage:
    export POLYMARKET_PRIVATE_KEY=0x...
    python test_polymarket_balance.py
"""

import os
import sys
import argparse
import json
import requests

try:
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import BalanceAllowanceParams
    from eth_account import Account
    CLOB_AVAILABLE = True
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("   Run: pip install py-clob-client")
    sys.exit(1)


CLOB_HOST = "https://clob.polymarket.com"
GAMMA_API_HOST = "https://gamma-api.polymarket.com"
CHAIN_ID = 137


def get_current_btc_market():
    """Get current BTC 5-minute market from Gamma API."""
    import time
    
    # Round to current 5-minute interval
    now = int(time.time())
    rounded_ts = (now // 300) * 300
    slug = f"btc-updown-5m-{rounded_ts}"
    
    print(f"   Looking for market: {slug}")
    
    try:
        url = f"{GAMMA_API_HOST}/markets?slug={slug}"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        if data and len(data) > 0:
            market = data[0]
            
            # Extract token IDs
            clob_token_ids = market.get('clobTokenIds', [])
            outcomes = market.get('outcomes', [])
            
            if isinstance(clob_token_ids, str):
                clob_token_ids = json.loads(clob_token_ids)
            if isinstance(outcomes, str):
                outcomes = json.loads(outcomes)
            
            tokens = []
            for token_id, outcome in zip(clob_token_ids, outcomes):
                tokens.append({
                    'token_id': token_id,
                    'outcome': outcome
                })
            
            return {
                'market_id': market.get('conditionId'),
                'slug': slug,
                'tokens': tokens
            }
    except Exception as e:
        print(f"   ⚠️ Could not fetch market: {e}")
    
    return None


def check_balance(private_key: str):
    """Check Polymarket account balance."""
    
    # Ensure 0x prefix
    if not private_key.startswith('0x'):
        private_key = '0x' + private_key
    
    print()
    print("="*60)
    print("🔍 Polymarket Balance Check")
    print("="*60)
    
    # Get wallet address from private key
    try:
        account = Account.from_key(private_key)
        wallet_address = account.address
        print(f"\n✅ Wallet address: {wallet_address}")
    except Exception as e:
        print(f"\n❌ Invalid private key: {e}")
        return
    
    # Step 1: Test read-only access
    print("\n" + "-"*40)
    print("1️⃣ Testing server connection...")
    print("-"*40)
    
    try:
        client = ClobClient(CLOB_HOST)
        ok = client.get_ok()
        print(f"   Server OK: {ok}")
    except Exception as e:
        print(f"   ❌ Server error: {e}")
        return
    
    # Step 2: Create authenticated client
    print("\n" + "-"*40)
    print("2️⃣ Authenticating...")
    print("-"*40)
    
    try:
        client = ClobClient(
            CLOB_HOST,
            key=private_key,
            chain_id=CHAIN_ID,
            signature_type=1,  # POLY_PROXY
            funder="0x02d2364332eC53a5D8439d660558C02170b10C12",
        )
        print("   ✅ Client created")
        
        # Derive API credentials
        print("   Deriving API credentials...")
        creds = client.create_or_derive_api_creds()
        
        if creds is None:
            print("   ⚠️ Could not derive credentials")
            print("   Trying to create new API key...")
            creds = client.create_api_key()
        
        if creds:
            print(f"   ✅ API Key: {creds.api_key[:16]}...")
            client.set_api_creds(creds)
        else:
            print("   ❌ No credentials - account may not be registered")
            print("   Visit polymarket.com and connect your wallet first")
            return
            
    except Exception as e:
        print(f"   ❌ Auth error: {e}")
        return
    
    # Step 3: Get COLLATERAL balance (USDC)
    print("\n" + "-"*40)
    print("3️⃣ Checking USDC balance (COLLATERAL)...")
    print("-"*40)
    
    try:
        # Get collateral balance (USDC)
        params = BalanceAllowanceParams(asset_type="COLLATERAL")
        balance_info = client.get_balance_allowance(params)
        
        if balance_info:
            balance = balance_info.get('balance', '0')
            allowance = balance_info.get('allowance', '0')
            
            # USDC has 6 decimals
            try:
                balance_usdc = int(balance) / 1_000_000
                allowance_usdc = int(allowance) / 1_000_000
                print(f"   💵 USDC Balance:   ${balance_usdc:,.2f}")
                print(f"   💵 USDC Allowance: ${allowance_usdc:,.2f}")
            except:
                print(f"   Balance: {balance}")
                print(f"   Allowance: {allowance}")
        else:
            print("   ❌ No balance info returned")
            
    except Exception as e:
        print(f"   ❌ Balance error: {e}")
    
    # Step 4: Get current BTC market tokens
    print("\n" + "-"*40)
    print("4️⃣ Finding current BTC market...")
    print("-"*40)
    
    market = get_current_btc_market()
    
    if market and market.get('tokens'):
        print(f"   ✅ Found market: {market['slug']}")
        
        # Step 5: Check balance for each token
        print("\n" + "-"*40)
        print("5️⃣ Checking token balances (CONDITIONAL)...")
        print("-"*40)
        
        for token in market['tokens']:
            token_id = token['token_id']
            outcome = token['outcome']
            
            try:
                params = BalanceAllowanceParams(
                    asset_type="CONDITIONAL",
                    token_id=token_id
                )
                token_balance = client.get_balance_allowance(params)
                
                if token_balance:
                    balance = token_balance.get('balance', '0')
                    # Token balances are in shares (6 decimals)
                    try:
                        balance_shares = int(balance) / 1_000_000
                        print(f"   {outcome:3s} token: {balance_shares:,.2f} shares")
                    except:
                        print(f"   {outcome:3s} token: {balance}")
                else:
                    print(f"   {outcome:3s} token: 0 shares")
                    
            except Exception as e:
                print(f"   {outcome:3s} token: Error - {e}")
    else:
        print("   ⚠️ No active BTC market found")
    
    # Step 6: Check open orders
    print("\n" + "-"*40)
    print("6️⃣ Checking open orders...")
    print("-"*40)
    
    try:
        orders = client.get_orders()
        if orders:
            print(f"   📋 Open orders: {len(orders)}")
        else:
            print("   📋 No open orders")
    except Exception as e:
        print(f"   ⚠️ Orders error: {e}")
    
    print()
    print("="*60)
    print("✅ Balance check complete!")
    print("="*60)
    print()


def main():
    parser = argparse.ArgumentParser(description='Check Polymarket balance')
    parser.add_argument('--private-key', type=str, default=None)
    args = parser.parse_args()
    
    private_key = args.private_key or os.environ.get('POLYMARKET_PRIVATE_KEY')
    
    if not private_key:
        print("❌ Private key required")
        print()
        print("Usage:")
        print("  export POLYMARKET_PRIVATE_KEY=0x...")
        print("  python test_polymarket_balance.py")
        sys.exit(1)
    
    check_balance(private_key)


if __name__ == "__main__":
    main()
