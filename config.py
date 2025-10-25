import os
from dotenv import load_dotenv

load_dotenv()

SYMBOL = os.getenv("SYMBOL", "EURUSD")

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

# Golden Trend System Parameters
EMA_SHORT = int(os.getenv("EMA_SHORT", "20"))
EMA_LONG = int(os.getenv("EMA_LONG", "50"))
EMA_VERY_LONG = int(os.getenv("EMA_VERY_LONG", "200"))

# Risk Management
RISK_PERCENT = float(os.getenv("RISK_PERCENT", "1.5"))
MAX_POSITIONS = int(os.getenv("MAX_POSITIONS", "3"))
MAX_CONSECUTIVE_LOSSES = int(os.getenv("MAX_CONSECUTIVE_LOSSES", "3"))

BACKTEST_DAYS = int(os.getenv("BACKTEST_DAYS", "180"))

# MT5 Connection
MT5_LOGIN = os.getenv("MT5_LOGIN")
MT5_PASSWORD = os.getenv("MT5_PASSWORD")
MT5_SERVER = os.getenv("MT5_SERVER")
