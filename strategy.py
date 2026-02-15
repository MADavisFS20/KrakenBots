# strategy.py

from config import (ATR_PERIOD, SMA_PERIOD, RSI_PERIOD, 
                    VOLUME_SPIKE_THRESHOLD, MIN_VOLUME_PERCENTILE)
from indicators import (calculate_sma, calculate_atr, calculate_rsi, calculate_macd,
                       detect_support_resistance, check_near_support_resistance,
                       analyze_volume, detect_market_regime,
                       get_candle_info, evaluate_candlestick_signal, check_hourly_trend)
import math

def evaluate_data_points_verbose(ohlc_data, order_book, ticker_data, hourly_ohlc):
    """
    Evaluates market conditions using a rule-based system with advanced indicators.
    Returns: data_points, decisions, indicators
    """
    data_points = {}
    decisions = []
    indicators = {}
    current_price = float(ohlc_data[-1][4]) if ohlc_data else 0

    # 1. Indicator Calculations
    current_candle = get_candle_info(ohlc_data[-1]) if ohlc_data else None

    indicators['ATR'] = calculate_atr(ohlc_data, ATR_PERIOD)
    indicators['SMA'] = calculate_sma(ohlc_data, SMA_PERIOD)
    indicators['RSI'] = calculate_rsi(ohlc_data, RSI_PERIOD)
    
    # MACD calculation
    macd_line, signal_line, histogram = calculate_macd(ohlc_data)
    indicators['MACD'] = macd_line
    indicators['MACD_SIGNAL'] = signal_line
    indicators['MACD_HIST'] = histogram
    
    # Support/Resistance
    support_levels, resistance_levels = detect_support_resistance(ohlc_data)
    indicators['SUPPORT'] = support_levels
    indicators['RESISTANCE'] = resistance_levels
    
    # Volume analysis
    vol_signal, avg_vol, current_vol = analyze_volume(ohlc_data)
    indicators['AVG_VOLUME'] = avg_vol
    indicators['CURRENT_VOLUME'] = current_vol
    
    # Market regime
    regime, adx = detect_market_regime(ohlc_data)
    indicators['REGIME'] = regime
    indicators['ADX'] = adx
    
    # --- Decision Point Evaluation ---

    # CND (Candlesticks): Detailed Manual Patterns
    cnd_decision = evaluate_candlestick_signal(ohlc_data)
    data_points['CND'] = cnd_decision
    decisions.append(cnd_decision)

    # HR_TREND (Multi-Timeframe Trend): Latest Hourly Candle
    hr_trend_decision = check_hourly_trend(hourly_ohlc)
    data_points['HR_TREND'] = hr_trend_decision
    decisions.append(hr_trend_decision)
    
    # RSI (Momentum): Overbought/Oversold
    rsi_decision = 0
    if indicators['RSI'] is not None:
        if indicators['RSI'] < 30:
            rsi_decision = 1  # Oversold, bullish
        elif indicators['RSI'] > 70:
            rsi_decision = -1  # Overbought, bearish
        elif indicators['RSI'] < 45:
            rsi_decision = 0.5  # Slightly bullish
        elif indicators['RSI'] > 55:
            rsi_decision = -0.5  # Slightly bearish
    data_points['RSI'] = rsi_decision
    decisions.append(rsi_decision)
    
    # MACD (Trend Direction)
    macd_decision = 0
    if indicators['MACD_HIST'] is not None:
        if indicators['MACD_HIST'] > 0:
            macd_decision = 1  # Bullish
        elif indicators['MACD_HIST'] < 0:
            macd_decision = -1  # Bearish
    data_points['MACD'] = macd_decision
    decisions.append(macd_decision)
    
    # S/R (Support/Resistance): Price near levels
    sr_decision = check_near_support_resistance(
        current_price, support_levels, resistance_levels
    )
    data_points['SR'] = sr_decision
    decisions.append(sr_decision)

    # ODB (Order book Spread): Top Bid vs. Top Ask Spread (Proximity)
    odb_decision = 0
    try:
        bids = order_book.get('bids', [])
        asks = order_book.get('asks', [])
        if bids and asks:
            top_bid = float(bids[0][0])
            top_ask = float(asks[0][0])
            if top_ask > top_bid and (top_ask - top_bid) / top_bid < 0.001: # Small spread is good
                odb_decision = 1
            elif top_ask == top_bid: 
                odb_decision = 0
            else: # Wide spread is bad/bearish
                odb_decision = -1
    except Exception:
        pass 
    data_points['ODB'] = odb_decision
    decisions.append(odb_decision)

    # VOL (Volume & Candle Alignment with spike confirmation)
    vol_decision = 0
    if vol_signal != 0 and current_candle:
        # Volume spike with directional candle
        if vol_signal == 1 and current_candle['is_bullish']:
            vol_decision = 1 
        elif vol_signal == 1 and current_candle['is_bearish']:
            vol_decision = -1 
    data_points['VOL'] = vol_decision
    decisions.append(vol_decision)

    # DPM (Depth of Market): Bid vs Ask Depth Ratio
    dpm_decision = 0
    try:
        bid_depth = sum(float(b[1]) for b in order_book.get('bids', []))
        ask_depth = sum(float(a[1]) for a in order_book.get('asks', []))
        if bid_depth > ask_depth * 1.2: 
            dpm_decision = 1 # More bid depth (support)
        elif ask_depth > bid_depth * 1.2:
            dpm_decision = -1 # More ask depth (resistance)
    except Exception:
        pass 
    data_points['DPM'] = dpm_decision
    decisions.append(dpm_decision)

    # HL (Proximity to 24hr extreme prices)
    try:
        high_24 = float(ticker_data['h'][1])
        low_24 = float(ticker_data['l'][1])
        if current_price >= high_24 * 0.995: # 0.5% proximity to 24hr high is a warning
            hl_decision = -1
        elif current_price <= low_24 * 1.005: # 0.5% proximity to 24hr low is a warning
            hl_decision = 1
        else:
            hl_decision = 0
        data_points['HL'] = hl_decision
        decisions.append(hl_decision)
    except Exception:
        data_points['HL'] = 0
        decisions.append(0)
        
    # SMA_POS (Price relative to 20-period SMA)
    sma_pos_decision = 0
    if indicators['SMA'] is not None and current_candle:
        if current_candle['c'] > indicators['SMA']:
            sma_pos_decision = 1
        elif current_candle['c'] < indicators['SMA']:
            sma_pos_decision = -1
    data_points['SMA_POS'] = sma_pos_decision
    decisions.append(sma_pos_decision)
    
    # REGIME (Market Regime): Trending vs Ranging
    regime_decision = 0
    if regime == 'trending':
        # In trending market, favor trend-following
        if macd_decision > 0:
            regime_decision = 0.5
        elif macd_decision < 0:
            regime_decision = -0.5
    data_points['REGIME'] = regime_decision
    decisions.append(regime_decision)

    return data_points, decisions, indicators

def calculate_position_size(total_equity, current_price, atr_value, max_risk_percent, atr_stop_multiplier):
    """
    Calculates the asset volume to buy based on risk parameters.
    Returns: (buy_volume, stop_loss_price)
    """
    if atr_value <= 0 or current_price <= 0:
        return 0.0, 0.0

    risk_amount_usdt = total_equity * max_risk_percent
    stop_loss_distance = atr_value * atr_stop_multiplier
    
    # Volume = Risk Amount / Stop Loss Distance (in quote currency terms)
    buy_volume = risk_amount_usdt / stop_loss_distance
    
    # Stop loss price is calculated as current price minus the distance
    stop_loss_price = current_price - stop_loss_distance
    
    # Cap volume to maximum affordable amount
    max_affordable_volume = total_equity / current_price
    buy_volume = min(buy_volume, max_affordable_volume)

    return buy_volume, stop_loss_price
