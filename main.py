# main.py

import time
from datetime import datetime
import argparse

# Import all modules
import kraken_api
import strategy
from multi_timeframe import fetch_multi_timeframe_data, validate_trend_alignment, get_trend_strength
from risk_manager import RiskManager
from trade_analytics import TradeAnalytics
from config import (
    TRADING_PAIR_API, TRADING_PAIR_DISPLAY, QUOTE_CURRENCY, 
    ASSET_CURRENCY, MIN_ASSET_VOLUME, ATR_PERIOD, SMA_PERIOD,
    MAX_RISK_PERCENT, ATR_STOP_MULTIPLIER, TRADE_INTERVAL_SECONDS,
    MAX_CANDLES_IN_TRADE, ENABLE_TRADE_LOGGING, PERFORMANCE_LOG_INTERVAL,
    PRIMARY_TIMEFRAME, TREND_TIMEFRAME, MAX_CONCURRENT_TRADES
)

# --- GLOBAL STATE ---
risk_manager = None
trade_analytics = None
candles_in_position = 0
position_entry_time = 0
last_performance_log = 0


def print_status(data_points=None, indicators=None, balance=None, risk_stats=None):
    """Prints the current state of the bot with enhanced information."""
    now = datetime.now()
    timestamp_str = now.strftime("%a %b %d %H:%M:%S %Y")
    
    price = kraken_api.get_current_price(TRADING_PAIR_API)
    
    # Prepare output
    print("="*80)
    print(f"TIMESTAMP: {timestamp_str} | MODE: LIVE TRADING ({PRIMARY_TIMEFRAME}min/{TREND_TIMEFRAME}min)")
    
    if balance and price:
        quote_bal = float(balance.get(QUOTE_CURRENCY, 0))
        asset_bal = float(balance.get(ASSET_CURRENCY, 0))
        total_equity = quote_bal + asset_bal * price
        print(f"EQUITY: {total_equity:.2f} {QUOTE_CURRENCY} | BAL: {quote_bal:.2f} {QUOTE_CURRENCY} / {asset_bal:.8f} {ASSET_CURRENCY}")
    elif balance:
        print(f"BALANCE: {balance.get(QUOTE_CURRENCY, 'N/A')} {QUOTE_CURRENCY} / {balance.get(ASSET_CURRENCY, 'N/A')} {ASSET_CURRENCY}")
    else:
        print("BALANCE: Could not retrieve balance.")
        
    print(f"CURRENT PRICE ({TRADING_PAIR_DISPLAY}): {price:.8f} {QUOTE_CURRENCY}")
    
    if data_points is not None:
        print("\n--- SIGNAL DATA POINTS (1=Bullish, -1=Bearish) ---")
        print(" | ".join([f"{k}:{v}" for k, v in data_points.items()]))
        
        # Calculate signal sum excluding long-term filters
        filtered_sum = sum(v for k, v in data_points.items() if k not in ['HR_TREND', 'HL'])
        print(f"Signal Sum: {filtered_sum:.1f} | Trend: {data_points.get('HR_TREND', 0)}")
    
    if indicators:
        print("\n--- INDICATORS ---")
        atr = indicators.get('ATR')
        sma = indicators.get('SMA')
        rsi = indicators.get('RSI')
        macd_hist = indicators.get('MACD_HIST')
        regime = indicators.get('REGIME')
        adx = indicators.get('ADX')
        
        if atr: print(f"ATR({ATR_PERIOD}): {atr:.2f}", end=" | ")
        if sma: print(f"SMA({SMA_PERIOD}): {sma:.2f}", end=" | ")
        if rsi: print(f"RSI: {rsi:.1f}", end=" | ")
        if macd_hist is not None: print(f"MACD Hist: {macd_hist:.4f}", end=" | ")
        if regime: print(f"Regime: {regime}", end=" | ")
        if adx: print(f"ADX: {adx:.1f}", end="")
        print()
    
    if risk_stats:
        print("\n--- RISK MANAGEMENT ---")
        print(f"Active Positions: {len(risk_manager.active_positions)}/{MAX_CONCURRENT_TRADES}")
        print(f"Max Drawdown: {risk_stats['max_drawdown']*100:.2f}%")
        print(f"Circuit Breaker: {'ACTIVE' if risk_manager.circuit_breaker_active else 'OK'}")
        if risk_stats['total_trades'] > 0:
            print(f"Win Rate: {risk_stats['win_rate']*100:.1f}% | Total Trades: {risk_stats['total_trades']}")

    print("="*80)


def main():
    global risk_manager, trade_analytics, candles_in_position, position_entry_time, last_performance_log
    
    print("="*80)
    print("ADVANCED CRYPTO TRADING BOT - Multi-Timeframe with Risk Management")
    print("="*80)
    print(f"TRADING PAIR: {TRADING_PAIR_DISPLAY}")
    print(f"TIMEFRAMES: Primary {PRIMARY_TIMEFRAME}min / Trend {TREND_TIMEFRAME}min")
    print(f"RISK: {MAX_RISK_PERCENT*100}% per trade | Stop: {ATR_STOP_MULTIPLIER}x ATR")
    print("="*80 + "\n")
    
    # Initialize systems
    initial_balance = kraken_api.get_balance(ASSET_CURRENCY, QUOTE_CURRENCY)
    if initial_balance:
        quote_bal = float(initial_balance.get(QUOTE_CURRENCY, 0))
        asset_bal = float(initial_balance.get(ASSET_CURRENCY, 0))
        price = kraken_api.get_current_price(TRADING_PAIR_API)
        initial_equity = quote_bal + (asset_bal * price if price else 0)
    else:
        initial_equity = 1000.0  # Default if can't get balance
        print("[WARNING] Could not get initial balance. Using default equity.")
    
    risk_manager = RiskManager(initial_equity)
    trade_analytics = TradeAnalytics()
    
    print(f"[INIT] Risk Manager initialized with {initial_equity:.2f} {QUOTE_CURRENCY} equity")
    print(f"[INIT] Trade Analytics enabled: {ENABLE_TRADE_LOGGING}\n")
    
    last_check_time = 0
    
    while True:
        try:
            current_time = time.time()
            
            # Check at defined intervals
            if current_time - last_check_time >= TRADE_INTERVAL_SECONDS:
                last_check_time = current_time
                
                # 1. Fetch multi-timeframe data
                primary_data, trend_data = fetch_multi_timeframe_data(TRADING_PAIR_API)
                
                if not primary_data or not trend_data:
                    print("[ERROR] Could not fetch multi-timeframe data. Retrying...")
                    time.sleep(TRADE_INTERVAL_SECONDS)
                    continue
                
                # 2. Fetch other market data
                ticker_data = kraken_api.get_current_price_and_ticker(TRADING_PAIR_API)
                depth_raw = kraken_api.get_order_book(TRADING_PAIR_API, depth=5)
                
                if not ticker_data or not depth_raw:
                    print("[ERROR] Could not fetch market data. Retrying...")
                    time.sleep(TRADE_INTERVAL_SECONDS)
                    continue
                
                # 3. Evaluate signals with all new indicators
                data_points, _, indicators = strategy.evaluate_data_points_verbose(
                    primary_data, depth_raw, ticker_data, trend_data
                )
                
                # 4. Get current price and balance
                price = float(ticker_data['c'][0])
                balance = kraken_api.get_balance(ASSET_CURRENCY, QUOTE_CURRENCY)
                
                if not balance:
                    print("[ERROR] Could not retrieve balance. Retrying...")
                    time.sleep(TRADE_INTERVAL_SECONDS)
                    continue
                
                asset_bal = float(balance.get(ASSET_CURRENCY, 0))
                quote_bal = float(balance.get(QUOTE_CURRENCY, 0))
                total_equity = quote_bal + asset_bal * price
                
                # 5. Update risk manager
                current_drawdown = risk_manager.update_equity(total_equity)
                risk_stats = risk_manager.get_statistics()
                
                # 6. Log equity point
                trade_analytics.log_equity_point(total_equity, current_time)
                
                # 7. Print status
                print_status(data_points, indicators, balance, risk_stats)
                
                # 8. Calculate primary signal
                signal_sum = sum(v for k, v in data_points.items() 
                               if k not in ['HR_TREND', 'HL', 'REGIME'])
                hr_trend = data_points.get('HR_TREND', 0)
                atr_value = indicators.get('ATR', 0.0)
                
                # 9. Handle existing positions
                if len(risk_manager.active_positions) > 0:
                    candles_in_position += 1
                    
                    for idx, position in enumerate(risk_manager.active_positions):
                        action, exit_volume, reason = risk_manager.update_position(idx, price)
                        
                        # Handle position updates
                        if action == 'full_exit':
                            print(f"\n[EXIT] {reason}: Selling {exit_volume:.4f} {ASSET_CURRENCY}")
                            result = kraken_api.place_order(TRADING_PAIR_API, 'sell', exit_volume)
                            
                            if result:
                                trade_record = risk_manager.remove_position(idx, price, reason)
                                trade_analytics.log_trade(trade_record)
                                candles_in_position = 0
                            
                        elif action == 'partial_exit':
                            print(f"\n[PARTIAL EXIT] {reason}: Selling {exit_volume:.4f} {ASSET_CURRENCY}")
                            kraken_api.place_order(TRADING_PAIR_API, 'sell', exit_volume)
                            
                        elif action == 'update_stop':
                            print(f"[STOP UPDATE] {reason}: New stop at {position['stop_loss']:.8f}")
                    
                    # Time-based exit
                    if candles_in_position >= MAX_CANDLES_IN_TRADE:
                        print(f"\n[TIME EXIT] Max {MAX_CANDLES_IN_TRADE} candles reached. Exiting all positions.")
                        for idx, position in enumerate(risk_manager.active_positions[:]):
                            kraken_api.place_order(TRADING_PAIR_API, 'sell', position['volume'])
                            trade_record = risk_manager.remove_position(idx, price, 'time_exit')
                            trade_analytics.log_trade(trade_record)
                        candles_in_position = 0
                
                # 10. Entry logic - check if we can open new positions
                can_trade, reason = risk_manager.can_open_position()
                
                if can_trade and asset_bal < MIN_ASSET_VOLUME:  # Not in position
                    # Strong bullish signal with trend confirmation
                    if signal_sum > 2 and validate_trend_alignment(1, trend_data) and atr_value > 0:
                        
                        # Calculate position size with volatility adjustment
                        volatility_factor = 1.0
                        regime = indicators.get('REGIME')
                        if regime == 'ranging':
                            volatility_factor = 0.7  # Reduce size in ranging markets
                        
                        position_size, stop_loss = risk_manager.calculate_position_size(
                            price, atr_value, volatility_factor
                        )
                        
                        # Cap by available funds
                        max_affordable = quote_bal / price
                        position_size = min(position_size, max_affordable * 0.95)
                        
                        if position_size >= MIN_ASSET_VOLUME:
                            print(f"\n[BUY SIGNAL] Sum: {signal_sum:.1f} | Regime: {regime}")
                            print(f"[BUY] Executing buy of {position_size:.4f} {ASSET_CURRENCY} @ {price:.8f}")
                            
                            result = kraken_api.place_order(TRADING_PAIR_API, 'buy', position_size)
                            
                            if result:
                                risk_manager.add_position(price, position_size, stop_loss)
                                candles_in_position = 0
                                position_entry_time = current_time
                                print(f"[POSITION] Entry @ {price:.8f} | Stop @ {stop_loss:.8f}")
                    
                    # Strong bearish signal (if already holding assets)
                    elif signal_sum < -2 and asset_bal >= MIN_ASSET_VOLUME:
                        print(f"\n[SELL SIGNAL] Sum: {signal_sum:.1f}")
                        print(f"[SELL] Executing sell of {asset_bal:.4f} {ASSET_CURRENCY}")
                        kraken_api.place_order(TRADING_PAIR_API, 'sell', asset_bal)
                
                elif not can_trade:
                    print(f"\n[TRADING HALTED] {reason}")
                
                # 11. Performance logging
                if current_time - last_performance_log >= PERFORMANCE_LOG_INTERVAL:
                    print("\n" + "="*80)
                    trade_analytics.print_performance_summary()
                    last_performance_log = current_time
                    print("="*80 + "\n")
            
            # Wait for next interval
            time_to_sleep = max(1, TRADE_INTERVAL_SECONDS - (time.time() - current_time))
            time.sleep(time_to_sleep)
        
        except KeyboardInterrupt:
            print("\n\n[SHUTDOWN] Bot stopped by user.")
            trade_analytics.print_performance_summary()
            break
        
        except Exception as e:
            print(f"\n[FATAL ERROR] {e}")
            import traceback
            traceback.print_exc()
            print("Restarting in 60 seconds...")
            time.sleep(60)


if __name__ == '__main__':
    main()
