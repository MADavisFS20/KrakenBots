# main.py

import time
from datetime import datetime
import argparse

# Import all modules
import kraken_api
import strategy
from config import (
    TRADING_PAIR_API, TRADING_PAIR_DISPLAY, QUOTE_CURRENCY, 
    ASSET_CURRENCY, MIN_ASSET_VOLUME, ATR_PERIOD, SMA_PERIOD,
    MAX_RISK_PERCENT, ATR_STOP_MULTIPLIER, TRADE_INTERVAL_SECONDS,
    PROFIT_TARGET_MULTIPLIER, MIN_PROFIT_PERCENT_FOR_WEAK_SIGNAL
)

# --- GLOBAL STATE ---
in_position = False
last_trade_price = 0.0
position_volume = 0.0
waiting_for_buy_signal = False
current_stop_loss = 0.0
profit_target = 0.0  # Track profit target for take-profit exits 

# --- EXECUTION HELPERS ---

def print_status(data_points=None, indicators=None, balance=None):
    """Prints the current state of the bot."""
    global in_position, last_trade_price, current_stop_loss, profit_target
    
    now = datetime.now()
    timestamp_str = now.strftime("%a %b %d %H:%M:%S %Y")
    
    price = kraken_api.get_current_price(TRADING_PAIR_API)
    
    # Prepare output
    print("="*70)
    print(f"TIMESTAMP: {timestamp_str} | MODE: LIVE TRADING")
    
    if balance and price:
        quote_bal = float(balance.get(QUOTE_CURRENCY, 0))
        asset_bal = float(balance.get(ASSET_CURRENCY, 0))
        total_equity = quote_bal + asset_bal * price
        print(f"EQUITY: {total_equity:.2f} {QUOTE_CURRENCY} | BAL: {quote_bal:.2f} {QUOTE_CURRENCY} / {asset_bal:.8f} {ASSET_CURRENCY}")
    elif balance:
        print(f"BALANCE: {balance.get(QUOTE_CURRENCY, 'N/A')} {QUOTE_CURRENCY} / {balance.get(ASSET_CURRENCY, 'N/A')} {ASSET_CURRENCY} | Price unavailable.")
    else:
        print("BALANCE: Could not retrieve balance.")
        
    print(f"CURRENT PRICE ({TRADING_PAIR_DISPLAY}): {price:.8f} {QUOTE_CURRENCY}")
    
    if data_points is not None:
        print("\n--- SIGNAL DATA POINTS (1=Bullish, -1=Bearish) ---")
        print(" | ".join([f"{k}:{v}" for k, v in data_points.items()]))
        
        # Calculate signal sum excluding trend and HL (long-term/proximity filters)
        filtered_sum = sum(v for k, v in data_points.items() if k not in ['HR_TREND', 'HL'])
        print(f"Signal Sum (Short-Term): {filtered_sum:.1f} | HR_TREND: {data_points.get('HR_TREND', 0)}")
    
    if indicators and indicators.get('ATR') is not None:
        print(f"INDICATORS: ATR({ATR_PERIOD}): {indicators['ATR']:.2f} | SMA({SMA_PERIOD}): {indicators['SMA']:.8f}")

    print("\n--- POSITION STATUS ---")
    print(f"STATUS: {'IN POSITION' if in_position else 'OUT OF POSITION'}")
    if in_position:
        print(f"LAST BUY PRICE: {last_trade_price:.8f} | Stop Loss: {current_stop_loss:.8f} (Stop Multiplier: {ATR_STOP_MULTIPLIER}x ATR)")
        print(f"PROFIT TARGET: {profit_target:.8f} (Target Multiplier: {PROFIT_TARGET_MULTIPLIER}x ATR)")
        if price:
            current_pnl_pct = ((price - last_trade_price) / last_trade_price) * 100 if last_trade_price > 0 else 0
            print(f"CURRENT P/L: {current_pnl_pct:+.2f}%")
    
    print("="*70)


# --- MAIN EXECUTION ---

def main():
    global in_position, last_trade_price, position_volume, waiting_for_buy_signal, current_stop_loss, profit_target
    
    print("Starting Rule-Based Crypto Trading Bot in LIVE Mode...")
    print(f"TRADING PAIR: {TRADING_PAIR_DISPLAY}")
    print(f"RISK: {MAX_RISK_PERCENT*100}% of equity per trade (Stop Loss: {ATR_STOP_MULTIPLIER}x ATR)")
    
    last_trade_time = 0.0 
    while True:
        try:
            current_time = time.time()
            if current_time - last_trade_time >= TRADE_INTERVAL_SECONDS:
                last_trade_time = current_time
                
                # 1. Gather Data (Need enough for SMA(20) and ATR(14) on 5-min candles)
                ohlc_data_5min = kraken_api.get_historical_ohlc(TRADING_PAIR_API, interval=5, limit=max(SMA_PERIOD, ATR_PERIOD) + 5) 
                hourly_ohlc = kraken_api.get_historical_ohlc(TRADING_PAIR_API, interval=60, limit=2)
                ticker_data = kraken_api.get_current_price_and_ticker(TRADING_PAIR_API)
                depth_raw = kraken_api.get_order_book(TRADING_PAIR_API, depth=5)
                
                required_candles = max(SMA_PERIOD, ATR_PERIOD) + 1
                if not ohlc_data_5min or len(ohlc_data_5min) < required_candles or not depth_raw or not ticker_data:
                    print(f"[ERROR] Not enough market data for signal evaluation. Need {required_candles} 5-min candles. Retrying...")
                    time.sleep(TRADE_INTERVAL_SECONDS)
                    continue
                    
                # 2. Evaluate Signals and Indicators
                data_points, _, indicators = strategy.evaluate_data_points_verbose(
                    ohlc_data_5min, depth_raw, ticker_data, hourly_ohlc
                )
                
                # 3. Get Prices and Balance
                price = float(ticker_data['c'][0])
                balance = kraken_api.get_balance(asset_curr=ASSET_CURRENCY, quote_curr=QUOTE_CURRENCY)
                asset_bal = float(balance.get(ASSET_CURRENCY, 0)) if balance and balance.get(ASSET_CURRENCY) else 0.0
                quote_bal = float(balance.get(QUOTE_CURRENCY, 0)) if balance and balance.get(QUOTE_CURRENCY) else 0.0
                total_equity = quote_bal + asset_bal * price if price else quote_bal
                
                # 4. Print Status
                print_status(data_points, indicators, balance=balance) 
                
                # Filtered sum (Short-term signal)
                signal_sum = sum(v for k, v in data_points.items() if k not in ['HR_TREND', 'HL']) 
                hr_trend = data_points['HR_TREND']
                atr_value = indicators.get('ATR', 0.0)

                # 5. Profit-Taking Logic (Check for profit target BEFORE stop loss)
                if in_position and profit_target > 0 and price >= profit_target and asset_bal > MIN_ASSET_VOLUME:
                    profit_pct = ((price - last_trade_price) / last_trade_price) * 100 if last_trade_price > 0 else 0
                    print(f"[PROFIT TARGET HIT] Price reached profit target ({profit_target:.8f}). Profit: {profit_pct:+.2f}%. Selling ALL {ASSET_CURRENCY}.")
                    sell_result = kraken_api.place_order(TRADING_PAIR_API, 'sell', asset_bal)
                    if sell_result:
                        in_position = False
                        last_trade_price = 0.0
                        current_stop_loss = 0.0
                        profit_target = 0.0
                        # Don't set waiting_for_buy_signal - allow immediate re-entry if conditions are good

                # 6. Stop Loss Logic (Dynamic)
                if in_position and current_stop_loss > 0 and price < current_stop_loss and asset_bal > MIN_ASSET_VOLUME:
                    print(f"[STOP LOSS] Price dropped below dynamic stop-loss ({current_stop_loss:.8f} -> {price:.8f}). Selling ALL {ASSET_CURRENCY}.")
                    sell_result = kraken_api.place_order(TRADING_PAIR_API, 'sell', asset_bal)
                    if sell_result:
                        in_position = False
                        last_trade_price = 0.0
                        current_stop_loss = 0.0
                        profit_target = 0.0
                        waiting_for_buy_signal = True # Wait for confirmation before re-entry

                # 7. Trade Decision Logic (Filtered and Risk-Managed)
                if not waiting_for_buy_signal:
                    # SELL Condition: Strong sell signal OR profitable position with weak trend
                    if in_position and asset_bal >= MIN_ASSET_VOLUME:
                        # Sell if: strong bearish signal OR moderate profit with weak bullish trend
                        should_sell = (signal_sum < -1 and hr_trend <= 0)
                        
                        # Also sell if we have some profit and signals are weakening
                        if not should_sell and last_trade_price > 0:
                            profit_pct = ((price - last_trade_price) / last_trade_price) * 100
                            if profit_pct > MIN_PROFIT_PERCENT_FOR_WEAK_SIGNAL and signal_sum < 0:
                                should_sell = True
                                print(f"[TRADE] Taking profit ({profit_pct:+.2f}%) on weakening signals.")
                        
                        if should_sell:
                            print(f"[TRADE] SELL signal (Sum: {signal_sum}). Executing SELL of {asset_bal:.4f} {ASSET_CURRENCY}.")
                            trade_result = kraken_api.place_order(TRADING_PAIR_API, 'sell', asset_bal)
                            if trade_result:
                                in_position = False
                                last_trade_price = 0.0
                                current_stop_loss = 0.0
                                profit_target = 0.0
                            
                    # BUY Condition: Strong buy signal AND Long-term trend is positive
                    elif not in_position and signal_sum > 1 and hr_trend == 1 and quote_bal > 0 and atr_value > 0:
                        buy_vol_calc, stop_loss_price = strategy.calculate_position_size(
                            total_equity, price, atr_value, MAX_RISK_PERCENT, ATR_STOP_MULTIPLIER
                        )
                        buy_volume = min(buy_vol_calc, quote_bal / price) # Cap by available quote currency
                        
                        if buy_volume >= MIN_ASSET_VOLUME:
                            print(f"[TRADE] BUY signal (Sum: {signal_sum}). Executing BUY of {buy_volume:.4f} {ASSET_CURRENCY}.")
                            trade_result = kraken_api.place_order(TRADING_PAIR_API, 'buy', buy_volume)
                            if trade_result:
                                in_position = True
                                last_trade_price = price
                                current_stop_loss = stop_loss_price
                                # Calculate profit target: entry + (ATR * profit_multiplier)
                                profit_target = price + (atr_value * PROFIT_TARGET_MULTIPLIER)
                                print(f"[POSITION] Entry: {price:.8f}, Stop: {stop_loss_price:.8f}, Target: {profit_target:.8f}")
                
                # Re-entry logic after a stop-loss
                elif waiting_for_buy_signal:
                    if signal_sum > 1 and hr_trend == 1 and quote_bal > 0 and atr_value > 0:
                        buy_vol_calc, stop_loss_price = strategy.calculate_position_size(
                            total_equity, price, atr_value, MAX_RISK_PERCENT, ATR_STOP_MULTIPLIER
                        )
                        buy_volume = min(buy_vol_calc, quote_bal / price)
                        
                        if buy_volume >= MIN_ASSET_VOLUME:
                            print(f"[TRADE] RE-ENTRY signal (Sum: {signal_sum}). Executing BUY of {buy_volume:.4f} {ASSET_CURRENCY}.")
                            trade_result = kraken_api.place_order(TRADING_PAIR_API, 'buy', buy_volume)
                            if trade_result:
                                in_position = True
                                last_trade_price = price
                                current_stop_loss = stop_loss_price
                                profit_target = price + (atr_value * PROFIT_TARGET_MULTIPLIER)
                                waiting_for_buy_signal = False
                                print(f"[POSITION] Entry: {price:.8f}, Stop: {stop_loss_price:.8f}, Target: {profit_target:.8f}")

            # Wait for the next trade interval
            time_to_sleep = max(0, TRADE_INTERVAL_SECONDS - (time.time() - current_time))
            time.sleep(time_to_sleep)

        except Exception as e:
            print(f"\n[FATAL ERROR IN LIVE LOOP] {e}. Restarting loop in 60 seconds.")
            time.sleep(60)

if __name__ == '__main__':
    main()
