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
TRADING_PAIR_API = "BTCUSDT"
TRADING_PAIR_DISPLAY = "BTC/USDT"
QUOTE_CURRENCY = "USDT" # The currency used to buy the asset (e.g., USD, USDT)
ASSET_CURRENCY = "BTC"  # The asset being traded (e.g., BTC, ETH)
MIN_ASSET_VOLUME = 0.0001 # Minimum volume for the asset (BTC).

# --- INDICATOR PERIODS ---
ATR_PERIOD = 14
SMA_PERIOD = 20

# --- RISK & STRATEGY PARAMETERS ---
MAX_RISK_PERCENT = 0.08   # Max 8% of total equity to risk per trade (increased for profitability).
ATR_STOP_MULTIPLIER = 1.5 # Stop Loss distance = 1.5 * ATR (tighter stops for better exits).
PROFIT_TARGET_MULTIPLIER = 3.0  # Take profit at 3.0 * ATR above entry (risk:reward = 1:2).

# --- EXECUTION PARAMETERS ---
TRADE_INTERVAL_SECONDS = 300 # How often the bot checks for a signal (5 minutes for better signal quality)
