# Risk Management for macOS Demo (MT5-free version)
from datetime import datetime, timezone
from config import DAILY_PROFIT_TARGET, DAILY_DRAWDOWN_LIMIT, MAX_OPEN_TRADES
from utils.logger import get_logger

log = get_logger("risk")

def today_bounds_utc():
    """Get today's start and end time in UTC"""
    now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = now.replace(hour=23, minute=59, second=59, microsecond=0)
    return start, end

def get_today_pnl():
    """Get today's P&L - Demo version always returns 0"""
    # In demo mode, we don't have real trading history
    # This will be overridden by the trading bot's internal tracking
    return 0.0

def get_account_balance():
    """Get account balance - Demo version returns default"""
    # In demo mode, return default demo balance
    return 10000.0

def can_trade():
    """Check if trading is allowed based on risk parameters"""
    # For demo mode, always allow trading
    # Real risk management is handled within live_demo.py
    return True, "OK"

# Demo-specific risk functions (used by live_demo.py)
def check_daily_limits(current_pnl, initial_balance):
    """Check daily P&L limits for demo trading"""
    pnl_pct = (current_pnl / initial_balance) * 100
    
    if pnl_pct >= DAILY_PROFIT_TARGET:
        return False, f"Daily profit target reached: {pnl_pct:.2f}%"
    
    if pnl_pct <= -DAILY_DRAWDOWN_LIMIT:
        return False, f"Daily drawdown limit reached: {pnl_pct:.2f}%"
    
    return True, "OK"