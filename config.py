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
MAX_RISK_PERCENT = 0.05   # Max 5% of total equity to risk per trade.
ATR_STOP_MULTIPLIER = 2.0 # Stop Loss distance = 2.0 * ATR.

# --- EXECUTION PARAMETERS ---
TRADE_INTERVAL_SECONDS = 60 # How often the bot checks for a signal (e.g., 60 seconds for 1-minute candles)
