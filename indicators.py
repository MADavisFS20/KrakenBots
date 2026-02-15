# indicators.py

import math
from config import ATR_PERIOD, SMA_PERIOD

# --- INDICATOR CALCULATIONS ---

def calculate_sma(ohlc_data, period):
    """Calculates the Simple Moving Average (SMA) of close prices."""
    if len(ohlc_data) < period:
        return None
    
    # OHLC format: [timestamp, open, high, low, close, vwap, volume, count]
    closes = [float(c[4]) for c in ohlc_data]
    return sum(closes[-period:]) / period

def calculate_atr(ohlc_data, period):
    """Calculates the Average True Range (ATR) (using SMA for smoothing)."""
    if len(ohlc_data) < period + 1:
        return None

    true_ranges = []
    # Start from the second candle (index 1)
    for i in range(1, len(ohlc_data)):
        current_h = float(ohlc_data[i][2])
        current_l = float(ohlc_data[i][3])
        previous_c = float(ohlc_data[i-1][4])
        
        tr = max(current_h - current_l, 
                 abs(current_h - previous_c), 
                 abs(current_l - previous_c))
        true_ranges.append(tr)

    if len(true_ranges) < period:
        return None

    # Calculate SMA of the last 'period' True Ranges
    return sum(true_ranges[-period:]) / period

# --- CANDLESTICK ANALYSIS ---

def get_candle_info(candle):
    """Helper to extract and calculate key candle properties."""
    # OHLC format: [timestamp, open, high, low, close, vwap, volume, count]
    o = float(candle[1])
    h = float(candle[2])
    l = float(candle[3])
    c = float(candle[4])
    v = float(candle[6])
    is_bullish = c > o
    is_bearish = c < o
    body = abs(c - o)
    total_range = h - l
    upper_wick = h - max(o, c)
    lower_wick = min(o, c) - l
    midpoint = (o + c) / 2
    return {'o': o, 'h': h, 'l': l, 'c': c, 'v': v, 'is_bullish': is_bullish,
            'is_bearish': is_bearish, 'body': body, 'total_range': total_range,
            'upper_wick': upper_wick, 'lower_wick': lower_wick, 'midpoint': midpoint}

def evaluate_candlestick_signal(ohlc_data):
    """
    Analyzes single- and multi-candle patterns for a strong signal.
    Returns: +1 (Strong Buy), -1 (Strong Sell), or 0 (Neutral/Weak)
    """
    signal = 0.0
    if not ohlc_data: return 0
    current = get_candle_info(ohlc_data[-1])
    
    # --- 1. Single-Candle Indicators (Current Candle) ---
    
    # Marubozu Check (High conviction)
    if current['total_range'] > 0 and current['body'] / current['total_range'] > 0.8:
        signal += 1.0 if current['is_bullish'] else -1.0
    
    # Hammer / Shooting Star Check (Reversal potential)
    # Hammer (Bullish): Long lower wick (2x upper) and small body
    if current['upper_wick'] > 0 and current['lower_wick'] > 2 * current['upper_wick'] and current['body'] < 0.3 * current['total_range']:
        signal += 1.0
    # Shooting Star (Bearish): Long upper wick (2x lower) and small body
    elif current['lower_wick'] > 0 and current['upper_wick'] > 2 * current['lower_wick'] and current['body'] < 0.3 * current['total_range']:
        signal -= 1.0

    # Simple Body Check
    signal += 0.5 if current['is_bullish'] else (-0.5 if current['is_bearish'] else 0)

    # --- 2. Multi-Candle Patterns (Last two candles) ---
    if len(ohlc_data) >= 2:
        previous = get_candle_info(ohlc_data[-2])
        
        # Engulfing (Strong Reversal)
        if previous['is_bearish'] and current['is_bullish'] and current['c'] > previous['o'] and current['o'] < previous['c']:
            signal += 1.5 
        elif previous['is_bullish'] and current['is_bearish'] and current['c'] < previous['o'] and current['o'] > previous['c']:
            signal -= 1.5
            
        # Piercing Line / Dark Cloud Cover (Moderate Reversal)
        elif previous['is_bearish'] and current['is_bullish']:
            prev_midpoint = (previous['o'] + previous['c']) / 2
            if current['c'] > prev_midpoint and current['o'] < previous['c']:
                signal += 1.0
        elif previous['is_bullish'] and current['is_bearish']:
            prev_midpoint = (previous['o'] + previous['c']) / 2
            if current['c'] < prev_midpoint and current['o'] > previous['c']:
                signal -= 1.0
            
    # Normalize and return final decision
    if signal >= 1.0: return 1
    if signal <= -1.0: return -1
    return 0

def check_hourly_trend(hourly_ohlc):
    """Checks the overall trend based on the latest hourly candle body size."""
    if not hourly_ohlc or len(hourly_ohlc) < 1:
        return 0
    
    latest_candle = get_candle_info(hourly_ohlc[-1])
    
    # Strong body (> 50% of total range) indicates conviction on the higher timeframe
    if latest_candle['is_bullish'] and latest_candle['body'] / latest_candle['total_range'] > 0.5:
        return 1
    elif latest_candle['is_bearish'] and latest_candle['body'] / latest_candle['total_range'] > 0.5:
        return -1
    
    return 0
