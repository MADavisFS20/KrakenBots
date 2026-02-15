import hmac
import hashlib
import base64
import urllib.parse
import requests
import time
from config import API_URL, API_KEY, API_SECRET, MIN_ASSET_VOLUME
from config import SHORT_SMA_PERIOD, LONG_SMA_PERIOD, ATR_PERIOD, GRAVITY_LOOKBACK


# --- KRAKEN API HELPERS ---

def get_kraken_signature(urlpath, data, secret):
    postdata = urllib.parse.urlencode(data)
    encoded = (str(data['nonce']) + postdata).encode()
    message = urlpath.encode() + hashlib.sha256(encoded).digest()
    mac = hmac.new(base64.b64decode(secret), message, hashlib.sha512)
    sigdigest = base64.b64encode(mac.digest())
    return sigdigest.decode()

def kraken_request(uri_path, data):
    headers = {
        'API-Key': API_KEY,
        'API-Sign': get_kraken_signature(uri_path, data, API_SECRET)
    }
    try:
        response = requests.post((API_URL + uri_path), headers=headers, data=data)
        response.raise_for_status()
        return response.json()
    except Exception:
        return None

def get_current_price_and_ticker(pair):
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
    except Exception:
        return None

def get_current_price(pair):
    ticker_data = get_current_price_and_ticker(pair)
    return float(ticker_data['c'][0]) if ticker_data else None

def get_balance():
    # TODO: Implement actual Kraken balance check here using kraken_request
    # For now, return a DUMMY BALANCE for logic testing
    return {'USDT': 1000.0, 'BTC': 0.0} 

def get_historical_ohlc(pair, interval=1, since=None):
    url = API_URL + "/0/public/OHLC"
    params = {'pair': pair, 'interval': interval}
    if since:
        params['since'] = since
    
    # Calculate required limit for all indicators
    required_limit = max(SHORT_SMA_PERIOD, LONG_SMA_PERIOD, ATR_PERIOD, GRAVITY_LOOKBACK) + 2
    if interval == 1:
        params['limit'] = required_limit
    else:
        params['limit'] = 2
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        if data.get('error'):
            return None
        pair_key = list(data['result'].keys())[0]
        return data['result'][pair_key]
    except Exception:
        return None

def place_order(pair, order_type, volume):
    if volume < MIN_ASSET_VOLUME: 
        print(f"[ERROR] Order volume {volume:.4f} is below minimum {MIN_ASSET_VOLUME}.")
        return None
    
    # TODO: Implement actual order placement via kraken_request here
    print(f"[WARNING] Live order placement skipped for {order_type} {volume:.4f} {pair}.")
    return True # Simulate success
