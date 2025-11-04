import os
from dotenv import load_dotenv

load_dotenv()

SYMBOL = os.getenv("SYMBOL", "XAUUSD")

TF_MAP = {
    "M1": 1,
    "M5": 5,
    "M15": 15,
    "M30": 30,
    "H1": 60,
    "H4": 240,
    "D1": 1440,
}
TIMEFRAME = os.getenv("TIMEFRAME", "M5")
LOT = float(os.getenv("LOT", "0.1"))
SL_PIPS = float(os.getenv("SL_PIPS", "20"))
TP_PIPS = float(os.getenv("TP_PIPS", "30"))
MAGIC = int(os.getenv("MAGIC", "234000"))
MAX_SLIPPAGE = int(os.getenv("MAX_SLIPPAGE", "10"))

DAILY_PROFIT_TARGET = float(os.getenv("DAILY_PROFIT_TARGET", "2.0"))
DAILY_DRAWDOWN_LIMIT = float(os.getenv("DAILY_DRAWDOWN_LIMIT", "2.0"))
MAX_OPEN_TRADES = int(os.getenv("MAX_OPEN_TRADES", "1"))

# Risk Management
RISK_PERCENT = float(os.getenv("RISK_PERCENT", "1.5"))
# Allow more concurrent positions to increase chance of fills
MAX_POSITIONS = int(os.getenv("MAX_POSITIONS", "5"))
MAX_CONSECUTIVE_LOSSES = int(os.getenv("MAX_CONSECUTIVE_LOSSES", "3"))

BACKTEST_DAYS = int(os.getenv("BACKTEST_DAYS", "180"))

# MT5 Connection
MT5_LOGIN = os.getenv("MT5_LOGIN")
MT5_PASSWORD = os.getenv("MT5_PASSWORD")
MT5_SERVER = os.getenv("MT5_SERVER")

# Instrument sizing (for backtest / lot calculation)
POINT_SIZE = float(os.getenv("POINT_SIZE", "0.01"))
VALUE_PER_PIP_PER_LOT = float(os.getenv("VALUE_PER_PIP_PER_LOT", "1.0"))
INSTRUMENT_TYPE = os.getenv("INSTRUMENT_TYPE", "XAU")

# Notifications
NOTIFICATIONS_ENABLE = os.getenv("NOTIFICATIONS_ENABLE", "false").lower() in ("1", "true", "yes")
NOTIFICATIONS_LOG_PATH = os.getenv("NOTIFICATIONS_LOG_PATH", "logs/notifications.log")

# Aggregate close (close all positions when combined profit reaches this USD amount)
AGGREGATE_CLOSE_ENABLED = os.getenv("AGGREGATE_CLOSE_ENABLED", "true").lower() in ("1", "true", "yes")
AGGREGATE_CLOSE_PROFIT_USD = float(os.getenv("AGGREGATE_CLOSE_PROFIT_USD", "5.0"))
AGGREGATE_CLOSE_RETRY_ATTEMPTS = int(os.getenv("AGGREGATE_CLOSE_RETRY_ATTEMPTS", "3"))
AGGREGATE_CLOSE_RETRY_BACKOFF_SECONDS = float(os.getenv("AGGREGATE_CLOSE_RETRY_BACKOFF_SECONDS", "2.0"))

# --- Sculpting / M1 mode settings ---
SCULPT_MODE = os.getenv("SCULPT_MODE", "false").lower() in ("1", "true", "yes")
SCULPT_PER_TRADE_LOT = float(os.getenv("SCULPT_PER_TRADE_LOT", "0.01"))
SCULPT_MAX_TRADES = int(os.getenv("SCULPT_MAX_TRADES", "3"))
SCULPT_SL_MULT = float(os.getenv("SCULPT_SL_MULT", "0.8"))
SCULPT_TP_MULT = float(os.getenv("SCULPT_TP_MULT", "1.6"))
# Lower MACD threshold for sculpt to be less strict (more signals)
SCULPT_MACD_THRESHOLD = float(os.getenv("SCULPT_MACD_THRESHOLD", "0.15"))
SCULPT_HOLD_BARS = int(os.getenv("SCULPT_HOLD_BARS", "60"))
# Reduce cooldown so sculpt sets can run more frequently
SCULPT_COOLDOWN_SECONDS = int(os.getenv("SCULPT_COOLDOWN_SECONDS", "60"))
SCULPT_MIN_ATR = float(os.getenv("SCULPT_MIN_ATR", "0.0"))
# Allow larger spread to avoid skipping entries due to transient spread
SCULPT_MAX_SPREAD = float(os.getenv("SCULPT_MAX_SPREAD", "50.0"))
# active hours for sculpt mode (local hour ranges). Format: "start-end" e.g. "0-23"
SCULPT_ACTIVE_HOURS = os.getenv("SCULPT_ACTIVE_HOURS", "0-23")
# breakeven trigger as fraction of R (e.g. 0.5 = 0.5R)
SCULPT_BREAKEVEN_R_MULT = float(os.getenv("SCULPT_BREAKEVEN_R_MULT", "0.5"))
SCULPT_TRAILING_ATR_STEP_MULT = float(os.getenv("SCULPT_TRAILING_ATR_STEP_MULT", "0.5"))

# M5-specific MACD threshold (allow easier M5 entries)
M5_MACD_THRESHOLD = float(os.getenv("M5_MACD_THRESHOLD", "0.2"))

# --- Scalping / Grid settings (for mt5_scalping.py) ---
# Force scalping to only open BUY orders
SCALP_FORCE_BUY_ONLY = os.getenv("SCALP_FORCE_BUY_ONLY", "true").lower() in ("1", "true", "yes")
# Enable grid mode for scalping (open multiple legs per signal)
SCALP_GRID_ENABLED = os.getenv("SCALP_GRID_ENABLED", "true").lower() in ("1", "true", "yes")
SCALP_GRID_LEGS = int(os.getenv("SCALP_GRID_LEGS", "3"))
# distance between legs in pips (points units depend on POINT_SIZE)
SCALP_GRID_DISTANCE_PIPS = float(os.getenv("SCALP_GRID_DISTANCE_PIPS", "5"))
# lot multiplier per subsequent grid leg (1.0 = same lot)
SCALP_GRID_LOT_MULTIPLIER = float(os.getenv("SCALP_GRID_LOT_MULTIPLIER", "1.0"))
# shared TP for all grid legs (in pips)
SCALP_GRID_SHARED_TP_PIPS = float(os.getenv("SCALP_GRID_SHARED_TP_PIPS", "15"))

