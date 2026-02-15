# multi_timeframe.py
"""
Multi-timeframe data management and trend validation.
Ensures trades align with both primary (5-min) and trend (15-min) timeframes.
"""

import kraken_api
from config import (PRIMARY_TIMEFRAME, TREND_TIMEFRAME, 
                    MIN_CANDLES_PRIMARY, MIN_CANDLES_TREND,
                    SMA_PERIOD, ATR_PERIOD)
from indicators import calculate_sma, check_hourly_trend, get_candle_info


def fetch_multi_timeframe_data(trading_pair):
    """
    Fetches OHLC data for both primary and trend timeframes.
    Returns: (primary_data, trend_data) or (None, None) on error.
    """
    try:
        # Fetch primary timeframe (5-min)
        primary_data = kraken_api.get_historical_ohlc(
            trading_pair, 
            interval=PRIMARY_TIMEFRAME, 
            limit=max(MIN_CANDLES_PRIMARY, SMA_PERIOD, ATR_PERIOD) + 5
        )
        
        # Fetch trend timeframe (15-min)
        trend_data = kraken_api.get_historical_ohlc(
            trading_pair, 
            interval=TREND_TIMEFRAME, 
            limit=MIN_CANDLES_TREND
        )
        
        if not primary_data or len(primary_data) < MIN_CANDLES_PRIMARY:
            return None, None
        
        if not trend_data or len(trend_data) < MIN_CANDLES_TREND:
            return None, None
        
        return primary_data, trend_data
        
    except Exception as e:
        print(f"[ERROR] Failed to fetch multi-timeframe data: {e}")
        return None, None


def validate_trend_alignment(primary_signal, trend_data):
    """
    Validates that the primary timeframe signal aligns with the trend timeframe.
    Returns: True if aligned, False otherwise.
    
    Args:
        primary_signal: +1 (bullish), -1 (bearish), 0 (neutral)
        trend_data: OHLC data for trend timeframe
    """
    if not trend_data or len(trend_data) < 2:
        return False
    
    # Get trend direction from 15-min timeframe
    trend_direction = check_hourly_trend(trend_data)
    
    # Calculate 15-min SMA for additional confirmation
    trend_sma = calculate_sma(trend_data, min(SMA_PERIOD, len(trend_data)))
    current_trend_candle = get_candle_info(trend_data[-1])
    
    # Bullish alignment: primary signal is bullish AND trend supports it
    if primary_signal > 0:
        # Trend must be bullish or neutral, and price above SMA
        if trend_direction >= 0:
            if trend_sma is None or current_trend_candle['c'] >= trend_sma:
                return True
        return False
    
    # Bearish alignment: primary signal is bearish AND trend supports it
    elif primary_signal < 0:
        # Trend must be bearish or neutral, and price below SMA
        if trend_direction <= 0:
            if trend_sma is None or current_trend_candle['c'] <= trend_sma:
                return True
        return False
    
    # Neutral signal - no trade
    return False


def get_trend_strength(trend_data):
    """
    Calculates the strength of the trend from the trend timeframe.
    Returns: strength value between -1 (strong bearish) and +1 (strong bullish)
    """
    if not trend_data or len(trend_data) < 3:
        return 0
    
    # Analyze last 3 candles
    recent_candles = [get_candle_info(c) for c in trend_data[-3:]]
    
    bullish_count = sum(1 for c in recent_candles if c['is_bullish'])
    bearish_count = sum(1 for c in recent_candles if c['is_bearish'])
    
    # Calculate body strength
    avg_body_ratio = sum(c['body'] / c['total_range'] if c['total_range'] > 0 else 0 
                         for c in recent_candles) / len(recent_candles)
    
    if bullish_count >= 2:
        return avg_body_ratio  # Positive strength
    elif bearish_count >= 2:
        return -avg_body_ratio  # Negative strength
    
    return 0


def check_multi_timeframe_divergence(primary_data, trend_data):
    """
    Checks for divergence between primary and trend timeframes.
    Divergence can signal potential reversals.
    
    Returns: 'bullish_divergence', 'bearish_divergence', or None
    """
    if not primary_data or not trend_data:
        return None
    
    if len(primary_data) < 5 or len(trend_data) < 2:
        return None
    
    # Check if primary shows weakness while trend is strong (or vice versa)
    primary_recent = [get_candle_info(c) for c in primary_data[-5:]]
    trend_current = get_candle_info(trend_data[-1])
    
    # Count recent primary candles
    primary_bullish = sum(1 for c in primary_recent if c['is_bullish'])
    primary_bearish = sum(1 for c in primary_recent if c['is_bearish'])
    
    # Bullish divergence: trend bearish but primary showing bullish momentum
    if trend_current['is_bearish'] and primary_bullish >= 4:
        return 'bullish_divergence'
    
    # Bearish divergence: trend bullish but primary showing bearish momentum
    if trend_current['is_bullish'] and primary_bearish >= 4:
        return 'bearish_divergence'
    
    return None
