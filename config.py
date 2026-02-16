import os
from dotenv import load_dotenv

# --- Load environment variables from .env file ---
# NOTE: Ensure your .env file only contains key=value pairs without leading comments/blanks.
load_dotenv()

# --- API CREDENTIALS (Loaded from .env) ---
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
API_URL = os.getenv("API_URL", "https://api.kraken.com")

# --- CREDENTIAL VALIDATION ---
if not API_KEY or API_KEY == "YOUR_KRAKEN_API_KEY_HERE":
    raise EnvironmentError(
        "FATAL ERROR: API_KEY is missing or the default placeholder. "
        "Please check your .env file structure and ensure keys are set."
    )
if not API_SECRET or API_SECRET == "YOUR_KRAKEN_API_SECRET_HERE":
    raise EnvironmentError(
        "FATAL ERROR: API_SECRET is missing or the default placeholder. "
        "Please check your .env file structure and ensure secret is set."
    )

# --- TRADING PAIR & CURRENCY INFO ---
TRADING_PAIR_API = "XRPUSDT"
TRADING_PAIR_DISPLAY = "XRP/USDT"
QUOTE_CURRENCY = "USDT" # The currency used to buy the asset (e.g., USD, USDT)
ASSET_CURRENCY = "XRP"  # The asset being traded (e.g., BTC, ETH)
MIN_ASSET_VOLUME = 0.0000000000000000001 # Minimum volume for the asset (BTC).

# --- INDICATOR PERIODS (Optimized for 5-min timeframes) ---
ATR_PERIOD = 14
SMA_PERIOD = 20
RSI_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# --- MULTI-TIMEFRAME SETTINGS ---
PRIMARY_TIMEFRAME = 5      # Primary trading timeframe in minutes
TREND_TIMEFRAME = 15       # Higher timeframe for trend validation
MIN_CANDLES_PRIMARY = 30   # Minimum candles needed for primary timeframe
MIN_CANDLES_TREND = 20     # Minimum candles needed for trend timeframe

# --- RISK & STRATEGY PARAMETERS ---
MAX_RISK_PERCENT = 0.08   # Max 8% of total equity to risk per trade (increased for profitability).
ATR_STOP_MULTIPLIER = 1.5 # Stop Loss distance = 1.5 * ATR (tighter stops for better exits).
PROFIT_TARGET_MULTIPLIER = 3.0  # Take profit at 3.0 * ATR above entry (Risk 1.5 ATR to gain 3.0 ATR = 1:2 risk:reward).
MIN_PROFIT_PERCENT_FOR_WEAK_SIGNAL = 1.0  # Take profit if we have 1%+ gain and signals turn negative.

# --- EXECUTION PARAMETERS ---
TRADE_INTERVAL_SECONDS = 300 # How often the bot checks for a signal (5 minutes for better signal quality)
MAX_RISK_PERCENT = 0.05   # Max 5% of total equity to risk per trade.
ATR_STOP_MULTIPLIER = 2.0 # Stop Loss distance = 2.0 * ATR.
MAX_DRAWDOWN_PERCENT = 0.05  # Maximum 5% drawdown before halting
MAX_CONCURRENT_TRADES = 2  # Maximum number of concurrent positions
TRAILING_STOP_ACTIVATION = 0.015  # Activate trailing stop after 1.5% profit
TRAILING_STOP_DISTANCE = 0.01     # Trailing stop 1% below highest price

# --- PROFIT TAKING (Three-tier system) ---
PROFIT_TARGET_1 = 0.02    # First target: 2% profit
PROFIT_TARGET_1_SIZE = 0.50  # Exit 50% of position
PROFIT_TARGET_2 = 0.04    # Second target: 4% profit
PROFIT_TARGET_2_SIZE = 0.30  # Exit 30% of remaining position
PROFIT_TARGET_3 = 0.06    # Third target: 6% profit
PROFIT_TARGET_3_SIZE = 0.20  # Exit 20% of remaining position

# --- EXIT PARAMETERS ---
MAX_CANDLES_IN_TRADE = 10  # Maximum time in trade (10 candles)
BREAKEVEN_STOP_TRIGGER = 0.015  # Move stop to breakeven after 1.5% profit

# --- VOLUME ANALYSIS ---
VOLUME_SPIKE_THRESHOLD = 1.5  # Volume must be 1.5x average to confirm
MIN_VOLUME_PERCENTILE = 30    # Only trade when volume > 30th percentile

# --- SUPPORT/RESISTANCE ---
SR_LOOKBACK_CANDLES = 50      # Candles to look back for S/R levels
SR_TOUCH_THRESHOLD = 0.002    # 0.2% threshold for price touching S/R

# --- MARKET REGIME ---
REGIME_ADX_PERIOD = 14        # Period for ADX (trend strength)
REGIME_TREND_THRESHOLD = 25   # ADX > 25 = trending, < 25 = ranging

# --- EXECUTION PARAMETERS ---
TRADE_INTERVAL_SECONDS = 300  # Check every 5 minutes (300 seconds)
ORDER_TIMEOUT_SECONDS = 30    # Order timeout
MAX_ORDER_RETRIES = 3         # Maximum retries for failed orders
SLIPPAGE_TOLERANCE = 0.001    # 0.1% maximum slippage tolerance

# --- ANALYTICS & LOGGING ---
ENABLE_TRADE_LOGGING = True   # Enable trade analytics
LOG_FILE_PATH = "trade_logs/trades.log"
PERFORMANCE_LOG_INTERVAL = 86400  # Daily performance summary (24 hours)
