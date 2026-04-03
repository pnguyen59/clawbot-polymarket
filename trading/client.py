"""
Polymarket trading client for order execution.
"""

import os
import time
from typing import Optional, Dict

from .config import CLOB_HOST, CHAIN_ID, SIGNATURE_TYPE, CONFIG
from .logger import log, log_trade, log_error
from .market import fetch_market_price

# Polymarket CLOB Client
try:
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import (
        ApiCreds,
        MarketOrderArgs,
        PartialCreateOrderOptions,
        BalanceAllowanceParams,
        OrderType,
    )
    from eth_account import Account
    CLOB_CLIENT_AVAILABLE = True
except ImportError:
    CLOB_CLIENT_AVAILABLE = False


class PolymarketTrader:
    """Real trading client for Polymarket."""
    
    def __init__(self, private_key: str = None, dry_run: bool = False):
        """
        Initialize Polymarket trader.
        
        Args:
            private_key: Ethereum private key (hex string)
            dry_run: If True, simulate trades without executing
        """
        self.private_key = private_key or os.environ.get('POLYMARKET_PRIVATE_KEY')
        self.dry_run = dry_run
        
        if not self.private_key:
            raise ValueError("Private key required. Set POLYMARKET_PRIVATE_KEY env var")
        
        if not self.private_key.startswith('0x'):
            self.private_key = '0x' + self.private_key
        
        account = Account.from_key(self.private_key)
        self.wallet_address = "0x02d2364332eC53a5D8439d660558C02170b10C12"
        
        self.client = None
        self.api_creds = None
        self.initialized = False
        
        self.stats = {
            'total_trades': 0,
            'successful_trades': 0,
            'failed_trades': 0,
            'total_volume': 0.0,
        }
    
    def initialize(self) -> bool:
        """Initialize the Polymarket client with authentication."""
        if not CLOB_CLIENT_AVAILABLE:
            log_error("py-clob-client not installed")
            return False
        
        log(f"Initializing Polymarket client...")
        log(f"  Wallet: {self.wallet_address}")
        
        try:
            # Create initial client
            self.client = ClobClient(
                host=CLOB_HOST,
                chain_id=CHAIN_ID,
                key=self.private_key,
                signature_type=SIGNATURE_TYPE,
                funder=self.wallet_address,
            )
            
            # Derive API credentials
            log("  Deriving API credentials...")
            creds = self.client.create_or_derive_api_creds()
            
            if not creds:
                log_error("Failed to derive API credentials")
                return False
            
            self.api_creds = ApiCreds(
                api_key=creds.api_key,
                api_secret=creds.api_secret,
                api_passphrase=creds.api_passphrase,
            )
            
            # Reinitialize client with credentials
            self.client = ClobClient(
                host=CLOB_HOST,
                chain_id=CHAIN_ID,
                key=self.private_key,
                signature_type=SIGNATURE_TYPE,
                funder=self.wallet_address,
                creds=self.api_creds,
            )
            
            self.initialized = True
            log("  ✅ Client initialized", 'success')
            return True
            
        except Exception as e:
            log_error(f"Initialization error: {e}")
            return False
    
    def get_usdc_balance(self) -> Optional[float]:
        """Get USDC balance."""
        if not self.initialized:
            return None
        try:
            params = BalanceAllowanceParams(asset_type="COLLATERAL")
            balance_info = self.client.get_balance_allowance(params)
            if balance_info:
                return int(balance_info.get('balance', '0')) / 1_000_000
            return None
        except Exception as e:
            log_error(f"Balance error: {e}")
            return None
    
    def get_token_balance(self, token_id: str) -> Optional[float]:
        """Get token balance."""
        if not self.initialized:
            return None
        try:
            params = BalanceAllowanceParams(asset_type="CONDITIONAL", token_id=token_id)
            balance_info = self.client.get_balance_allowance(params)
            if balance_info:
                return int(balance_info.get('balance', '0')) / 1_000_000
            return None
        except Exception as e:
            log_error(f"Token balance error: {e}")
            return None
    
    def place_market_order(self, token_id: str, side: str, amount: float) -> Optional[Dict]:
        """
        Place a market order.
        
        Args:
            token_id: Token ID to trade
            side: 'BUY' or 'SELL'
            amount: Dollar amount (for BUY) or shares (for SELL)
        
        Returns:
            Order response dict or None on error
        """
        if not self.initialized:
            log_error("Client not initialized")
            return None
        
        log_trade(f"Placing {side} order: ${amount:.2f} on {token_id[:16]}...")
        
        if self.dry_run:
            log_trade("  DRY RUN - Order not executed")
            return {
                'orderID': f'dry_run_{int(time.time())}',
                'status': 'simulated',
                'takingAmount': str(amount * 2),
            }
        
        try:
            # Fetch current market price for worst-price limit
            market_price = fetch_market_price(token_id, side)
            
            if market_price is None:
                log_error("  Failed to fetch market price for worst-price limit")
                return None
            
            # Calculate worst-price limit (0.1% slippage tolerance)
            if side == 'BUY':
                worst_price = round(market_price * 1.001, 4)  # Pay up to 0.1% more
            else:
                worst_price = round(market_price * 0.999, 4)  # Receive at least 0.1% less
            
            log_trade(f"  Market price: ${market_price:.4f}, Worst-price limit: ${worst_price:.4f}")
            
            order_args = MarketOrderArgs(
                token_id=token_id,
                amount=amount,
                side=side,
                price=worst_price,
            )
            
            options = PartialCreateOrderOptions(
                tick_size=CONFIG['tick_size'],
                neg_risk=CONFIG['neg_risk'],
            )
            
            signed_order = self.client.create_market_order(order_args, options)
            response = self.client.post_order(signed_order, orderType=OrderType.FOK)
            
            if response:
                order_id = response.get('orderID', 'unknown')
                taking_amount = response.get('takingAmount', '0')
                log_trade(f"  ✅ Order executed: {order_id[:20]}...")
                log_trade(f"  Taking amount: {taking_amount}")
                
                self.stats['total_trades'] += 1
                self.stats['successful_trades'] += 1
                self.stats['total_volume'] += amount
                
                return response
            else:
                log_error("  Order failed - no response")
                self.stats['failed_trades'] += 1
                return None
                
        except Exception as e:
            log_error(f"  Order error: {e}")
            self.stats['failed_trades'] += 1
            return None
    
    def wait_for_token_balance(self, token_id: str, expected_shares: float, 
                                max_retries: int = 5, delay: int = 3) -> float:
        """
        Wait for token balance to settle after buy.
        
        Args:
            token_id: Token ID to check
            expected_shares: Expected number of shares
            max_retries: Maximum retry attempts
            delay: Delay between retries in seconds
        
        Returns:
            Actual balance or 0 if not settled
        """
        for attempt in range(max_retries):
            balance = self.get_token_balance(token_id)
            if balance and balance > 0:
                return balance
            log(f"  Waiting for settlement... ({attempt + 1}/{max_retries})")
            time.sleep(delay)
        return 0
    
    def get_stats(self) -> Dict:
        """Get trading statistics."""
        return self.stats.copy()
