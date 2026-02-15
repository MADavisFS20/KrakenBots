# indicators.py

import math
import numpy as np
from config import (ATR_PERIOD, SMA_PERIOD, RSI_PERIOD, MACD_FAST, MACD_SLOW, 
                    MACD_SIGNAL, SR_LOOKBACK_CANDLES, SR_TOUCH_THRESHOLD,
                    REGIME_ADX_PERIOD, VOLUME_SPIKE_THRESHOLD)

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

# --- ADVANCED INDICATORS ---

def calculate_rsi(ohlc_data, period=RSI_PERIOD):
    """
    Calculates the Relative Strength Index (RSI).
    Returns RSI value between 0-100, or None if insufficient data.
    """
    if len(ohlc_data) < period + 1:
        return None
    
    closes = [float(c[4]) for c in ohlc_data]
    
    # Calculate price changes
    deltas = np.diff(closes)
    
    # Separate gains and losses
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    
    # Calculate average gains and losses
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi

def calculate_macd(ohlc_data, fast=MACD_FAST, slow=MACD_SLOW, signal=MACD_SIGNAL):
    """
    Calculates MACD (Moving Average Convergence Divergence).
    Returns: (macd_line, signal_line, histogram) or (None, None, None) if insufficient data.
    """
    if len(ohlc_data) < slow + signal:
        return None, None, None
    
    closes = np.array([float(c[4]) for c in ohlc_data])
    
    # Calculate EMA arrays
    ema_fast_array = _calculate_ema_array(closes, fast)
    ema_slow_array = _calculate_ema_array(closes, slow)
    
    # MACD line = Fast EMA - Slow EMA
    macd_array = ema_fast_array - ema_slow_array
    
    # Signal line = EMA of MACD line
    signal_array = _calculate_ema_array(macd_array, signal)
    
    # Histogram = MACD - Signal
    histogram = macd_array[-1] - signal_array[-1]
    
    return macd_array[-1], signal_array[-1], histogram

def _calculate_ema(data, period):
    """Helper function to calculate Exponential Moving Average (returns single value)."""
    if len(data) < period:
        return data[-1] if len(data) > 0 else 0
    
    multiplier = 2 / (period + 1)
    ema = data[0]
    
    for value in data[1:]:
        ema = (value * multiplier) + (ema * (1 - multiplier))
    
    return ema

def _calculate_ema_array(data, period):
    """Helper function to calculate EMA array from data array."""
    multiplier = 2 / (period + 1)
    ema = np.zeros(len(data))
    ema[0] = data[0]
    
    for i in range(1, len(data)):
        ema[i] = (data[i] * multiplier) + (ema[i-1] * (1 - multiplier))
    
    return ema

def detect_support_resistance(ohlc_data, lookback=SR_LOOKBACK_CANDLES):
    """
    Detects support and resistance levels based on pivot points.
    Returns: (support_levels, resistance_levels) as lists of prices.
    """
    if len(ohlc_data) < lookback:
        return [], []
    
    recent_data = ohlc_data[-lookback:]
    highs = [float(c[2]) for c in recent_data]
    lows = [float(c[3]) for c in recent_data]
    
    support_levels = []
    resistance_levels = []
    
    # Find local minima (support) and maxima (resistance)
    for i in range(2, len(recent_data) - 2):
        # Support: local minimum
        if lows[i] < lows[i-1] and lows[i] < lows[i-2] and \
           lows[i] < lows[i+1] and lows[i] < lows[i+2]:
            support_levels.append(lows[i])
        
        # Resistance: local maximum
        if highs[i] > highs[i-1] and highs[i] > highs[i-2] and \
           highs[i] > highs[i+1] and highs[i] > highs[i+2]:
            resistance_levels.append(highs[i])
    
    # Cluster nearby levels (within 0.5%)
    support_levels = _cluster_levels(support_levels, 0.005)
    resistance_levels = _cluster_levels(resistance_levels, 0.005)
    
    return support_levels, resistance_levels

def _cluster_levels(levels, threshold=0.005):
    """Clusters price levels that are close together."""
    if not levels:
        return []
    
    levels = sorted(levels)
    clustered = []
    current_cluster = [levels[0]]
    
    for level in levels[1:]:
        if abs(level - current_cluster[-1]) / current_cluster[-1] < threshold:
            current_cluster.append(level)
        else:
            # Average the cluster
            clustered.append(sum(current_cluster) / len(current_cluster))
            current_cluster = [level]
    
    # Add the last cluster
    if current_cluster:
        clustered.append(sum(current_cluster) / len(current_cluster))
    
    return clustered

def check_near_support_resistance(price, support_levels, resistance_levels, threshold=SR_TOUCH_THRESHOLD):
    """
    Checks if price is near support or resistance.
    Returns: 1 (near support/bullish), -1 (near resistance/bearish), 0 (neutral)
    """
    for support in support_levels:
        if abs(price - support) / support < threshold:
            return 1  # Near support, potential bounce
    
    for resistance in resistance_levels:
        if abs(price - resistance) / resistance < threshold:
            return -1  # Near resistance, potential rejection
    
    return 0

def analyze_volume(ohlc_data, lookback=20):
    """
    Analyzes volume patterns to detect spikes or abnormalities.
    Returns: volume_signal (1=spike, -1=drop, 0=normal), avg_volume, current_volume
    """
    if len(ohlc_data) < lookback + 1:
        return 0, None, None
    
    volumes = [float(c[6]) for c in ohlc_data]
    avg_volume = np.mean(volumes[-lookback-1:-1])  # Exclude current candle
    current_volume = volumes[-1]
    
    if current_volume > avg_volume * VOLUME_SPIKE_THRESHOLD:
        return 1, avg_volume, current_volume  # Volume spike
    elif current_volume < avg_volume / VOLUME_SPIKE_THRESHOLD:
        return -1, avg_volume, current_volume  # Volume drop
    
    return 0, avg_volume, current_volume

def detect_market_regime(ohlc_data, adx_period=REGIME_ADX_PERIOD):
    """
    Detects market regime: trending vs ranging.
    Returns: 'trending', 'ranging', or None if insufficient data
    Also returns ADX value.
    """
    if len(ohlc_data) < adx_period * 2:
        return None, None
    
    # Calculate +DI and -DI
    highs = np.array([float(c[2]) for c in ohlc_data])
    lows = np.array([float(c[3]) for c in ohlc_data])
    closes = np.array([float(c[4]) for c in ohlc_data])
    
    # True Range
    high_low = highs[1:] - lows[1:]
    high_close = np.abs(highs[1:] - closes[:-1])
    low_close = np.abs(lows[1:] - closes[:-1])
    true_range = np.maximum(high_low, np.maximum(high_close, low_close))
    
    # Directional Movement
    up_move = highs[1:] - highs[:-1]
    down_move = lows[:-1] - lows[1:]
    
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
    
    # Smooth using EMA-like calculation
    atr = _smooth_array(true_range, adx_period)
    plus_di = 100 * _smooth_array(plus_dm, adx_period) / atr
    minus_di = 100 * _smooth_array(minus_dm, adx_period) / atr
    
    # Calculate DX and ADX
    dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
    adx = _smooth_array(dx, adx_period)
    
    current_adx = adx[-1] if len(adx) > 0 else 0
    
    # Threshold for trending vs ranging
    from config import REGIME_TREND_THRESHOLD
    regime = 'trending' if current_adx > REGIME_TREND_THRESHOLD else 'ranging'
    
    return regime, current_adx

def _smooth_array(data, period):
    """Smooths an array using EMA-like calculation."""
    if len(data) < period:
        return data
    
    smoothed = np.zeros(len(data))
    smoothed[0] = data[0]
    multiplier = 2 / (period + 1)
    
    for i in range(1, len(data)):
        smoothed[i] = (data[i] * multiplier) + (smoothed[i-1] * (1 - multiplier))
    
    return smoothed
