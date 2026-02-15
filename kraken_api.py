# kraken_api.py

import time
import hmac
import hashlib
import base64
import urllib.parse
import json
import requests
from config import API_KEY, API_SECRET, API_URL, MIN_ASSET_VOLUME

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

def place_order(pair, order_type, volume):
    """Places a market order."""
    if volume is None or volume < MIN_ASSET_VOLUME: 
        print(f"[FAILURE] Order not placed: volume {volume:.4f} below minimum {MIN_ASSET_VOLUME:.4f}.")
        return None
        
    if API_KEY and API_SECRET:
        uri_path = '/0/private/AddOrder'
        data = {
            'nonce': str(int(1000 * time.time())),
            'pair': pair,
            'type': order_type,
            'ordertype': 'market',
            'volume': f"{volume:.4f}",
        }
        print(f"\n[REAL TRADE] Attempting to place a {order_type} order for {volume:.4f} of {pair}...")
        res = kraken_request(uri_path, data)
        if res and not res.get('error'):
            print(f"[SUCCESS] Order placed successfully: {res['result']['descr']['order']}")
            return res['result']
        print(f"[FAILURE] Order could not be placed: {res.get('error') if res else 'No response'}")
        
    return None
