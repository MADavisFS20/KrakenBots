# kraken_api.py

import time
import hmac
import hashlib
import base64
import urllib.parse
import json
import requests
from config import (API_KEY, API_SECRET, API_URL, MIN_ASSET_VOLUME,
                    ORDER_TIMEOUT_SECONDS, MAX_ORDER_RETRIES, SLIPPAGE_TOLERANCE)

# --- AUTHENTICATION HELPERS ---

def get_kraken_signature(urlpath, data, secret):
    """Generates the HMAC-SHA512 signature for private endpoints."""
    postdata = urllib.parse.urlencode(data)
    encoded = (str(data['nonce']) + postdata).encode()
    message = urlpath.encode() + hashlib.sha256(encoded).digest()
    mac = hmac.new(base64.b64decode(secret), message, hashlib.sha512)
    sigdigest = base64.b64encode(mac.digest())
    return sigdigest.decode()

def kraken_request(uri_path, data):
    """Performs a private API request."""
    headers = {
        'API-Key': API_KEY,
        'API-Sign': get_kraken_signature(uri_path, data, API_SECRET)
    }
    try:
        response = requests.post((API_URL + uri_path), headers=headers, data=data)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        # print(f"[ERROR] API request failed: {e}")
        return None

# --- PUBLIC DATA FETCHING ---

def get_current_price_and_ticker(pair):
    """Fetches Ticker data (current price, 24hr high/low, volume)."""
    uri_path = '/0/public/Ticker'
    params = {'pair': pair}
    try:
        response = requests.get(API_URL + uri_path, params=params)
        response.raise_for_status()
        ticker_json = response.json()
        if ticker_json.get('error'):
            return None
        pair_key = list(ticker_json['result'].keys())[0]
        return ticker_json['result'][pair_key]
    except Exception as e:
        return None

def get_current_price(pair):
    """Returns the current closing price."""
    ticker_data = get_current_price_and_ticker(pair)
    if ticker_data:
        return float(ticker_data['c'][0])
    return None

def get_historical_ohlc(pair, interval=1, limit=100):
    """Fetches historical OHLC data for live mode."""
    url = API_URL + "/0/public/OHLC"
    params = {'pair': pair, 'interval': interval, 'limit': limit}
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        if data.get('error'):
            return None
        pair_key = list(data['result'].keys())[0]
        return data['result'][pair_key]
    except Exception as e:
        return None

def get_order_book(pair, depth=5):
    """Fetches market depth/order book data."""
    url = API_URL + "/0/public/Depth"
    params = {"pair": pair, "count": depth}
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        if data.get('error'):
            return None
        pair_key = list(data['result'].keys())[0]
        return data['result'][pair_key]
    except Exception as e:
        return None

# --- PRIVATE DATA & EXECUTION ---

def get_balance(asset_curr='BTC', quote_curr='USDT'):
    """Fetches the account balance."""
    if API_KEY and API_SECRET:
        uri_path = '/0/private/Balance'
        data = {'nonce': str(int(1000 * time.time()))}
        res = kraken_request(uri_path, data)
        if res and not res.get('error'):
            # Filter for the needed assets
            return {
                quote_curr: res['result'].get(quote_curr, '0'),
                asset_curr: res['result'].get(asset_curr, '0')
            }
        # print(f"[ERROR] Getting balance: {res.get('error') if res else 'No response'}")
        
    return None

def place_order(pair, order_type, volume, retry=True):
    """
    Places a market order with retry logic and better error handling.
    
    Args:
        pair: Trading pair
        order_type: 'buy' or 'sell'
        volume: Order volume
        retry: Enable retry logic for failed orders
    
    Returns:
        Order result or None
    """
    if volume is None or volume < MIN_ASSET_VOLUME: 
        print(f"[FAILURE] Order not placed: volume {volume:.4f} below minimum {MIN_ASSET_VOLUME:.4f}.")
        return None
        
    if not API_KEY or not API_SECRET:
        print("[FAILURE] API credentials not configured.")
        return None
    
    # Try with retries
    attempts = MAX_ORDER_RETRIES if retry else 1
    
    for attempt in range(attempts):
        try:
            uri_path = '/0/private/AddOrder'
            data = {
                'nonce': str(int(1000 * time.time())),
                'pair': pair,
                'type': order_type,
                'ordertype': 'market',
                'volume': f"{volume:.4f}",
            }
            
            if attempt == 0:
                print(f"\n[ORDER] Placing {order_type} order for {volume:.4f} of {pair}...")
            else:
                print(f"[RETRY] Attempt {attempt + 1}/{attempts}...")
            
            res = kraken_request(uri_path, data)
            
            if res and not res.get('error'):
                print(f"[SUCCESS] Order placed: {res['result']['descr']['order']}")
                return res['result']
            
            error_msg = res.get('error') if res else 'No response'
            print(f"[FAILURE] Order failed: {error_msg}")
            
            # Check if error is retryable
            if res and res.get('error'):
                error_str = str(res.get('error'))
                # Don't retry for insufficient funds or invalid parameters
                if 'Insufficient' in error_str or 'Invalid' in error_str:
                    print("[FAILURE] Non-retryable error detected.")
                    return None
            
            # Wait before retry
            if attempt < attempts - 1:
                time.sleep(2)
        
        except Exception as e:
            print(f"[ERROR] Exception during order placement: {e}")
            if attempt < attempts - 1:
                time.sleep(2)
    
    return None


def place_limit_order(pair, order_type, volume, price, retry=True):
    """
    Places a limit order with retry logic.
    
    Args:
        pair: Trading pair
        order_type: 'buy' or 'sell'
        volume: Order volume
        price: Limit price
        retry: Enable retry logic
    
    Returns:
        Order result or None
    """
    if volume is None or volume < MIN_ASSET_VOLUME: 
        print(f"[FAILURE] Limit order not placed: volume {volume:.4f} below minimum.")
        return None
    
    if not API_KEY or not API_SECRET:
        return None
    
    attempts = MAX_ORDER_RETRIES if retry else 1
    
    for attempt in range(attempts):
        try:
            uri_path = '/0/private/AddOrder'
            data = {
                'nonce': str(int(1000 * time.time())),
                'pair': pair,
                'type': order_type,
                'ordertype': 'limit',
                'price': f"{price:.8f}",
                'volume': f"{volume:.4f}",
            }
            
            res = kraken_request(uri_path, data)
            
            if res and not res.get('error'):
                print(f"[SUCCESS] Limit order placed at {price:.8f}")
                return res['result']
            
            if attempt < attempts - 1:
                time.sleep(2)
        
        except Exception as e:
            print(f"[ERROR] Limit order exception: {e}")
            if attempt < attempts - 1:
                time.sleep(2)
    
    return None


def cancel_order(txid):
    """
    Cancels an open order.
    
    Args:
        txid: Transaction ID of the order to cancel
    
    Returns:
        True if successful, False otherwise
    """
    if not API_KEY or not API_SECRET:
        return False
    
    try:
        uri_path = '/0/private/CancelOrder'
        data = {
            'nonce': str(int(1000 * time.time())),
            'txid': txid
        }
        
        res = kraken_request(uri_path, data)
        
        if res and not res.get('error'):
            print(f"[SUCCESS] Order {txid} cancelled")
            return True
        
        print(f"[FAILURE] Could not cancel order: {res.get('error') if res else 'No response'}")
        return False
    
    except Exception as e:
        print(f"[ERROR] Exception cancelling order: {e}")
        return False


def get_open_orders():
    """
    Gets all open orders.
    
    Returns:
        Dictionary of open orders or None
    """
    if not API_KEY or not API_SECRET:
        return None
    
    try:
        uri_path = '/0/private/OpenOrders'
        data = {'nonce': str(int(1000 * time.time()))}
        
        res = kraken_request(uri_path, data)
        
        if res and not res.get('error'):
            return res['result'].get('open', {})
        
        return None
    
    except Exception as e:
        print(f"[ERROR] Exception getting open orders: {e}")
        return None


def check_order_status(txid):
    """
    Checks the status of an order.
    
    Args:
        txid: Transaction ID
    
    Returns:
        Order status dict or None
    """
    if not API_KEY or not API_SECRET:
        return None
    
    try:
        uri_path = '/0/private/QueryOrders'
        data = {
            'nonce': str(int(1000 * time.time())),
            'txid': txid
        }
        
        res = kraken_request(uri_path, data)
        
        if res and not res.get('error'):
            return res['result'].get(txid)
        
        return None
    
    except Exception as e:
        print(f"[ERROR] Exception checking order status: {e}")
        return None


def monitor_order_fill(txid, timeout=ORDER_TIMEOUT_SECONDS):
    """
    Monitors an order until it's filled or times out.
    
    Args:
        txid: Transaction ID
        timeout: Maximum time to wait in seconds
    
    Returns:
        'filled', 'partial', 'timeout', or 'error'
    """
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        status = check_order_status(txid)
        
        if status:
            order_status = status.get('status')
            
            if order_status == 'closed':
                return 'filled'
            elif order_status == 'canceled':
                return 'canceled'
        
        time.sleep(1)
    
    return 'timeout'
