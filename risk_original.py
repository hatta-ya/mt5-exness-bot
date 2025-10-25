# MT5 import disabled for macOS compatibility
# import MetaTrader5 as mt5
from datetime import datetime, timezone
from config import DAILY_PROFIT_TARGET, DAILY_DRAWDOWN_LIMIT, MAX_OPEN_TRADES
from utils.logger import get_logger

log = get_logger("risk")

def today_bounds_utc():
    now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = now.replace(hour=23, minute=59, second=59, microsecond=0)
    return start, end

def get_today_pnl():
    start, end = today_bounds_utc()
    deals = mt5.history_deals_get(start, end) or []
    profit = sum(d.profit for d in deals)
    commission = sum(d.commission for d in deals)
    swap = sum(d.swap for d in deals)
    return profit + commission + swap

def can_trade():
    acc = mt5.account_info()
    if acc is None:
        log.error("account_info() is None")
        return False, "NO_ACCOUNT"
    balance = acc.balance
    open_positions = mt5.positions_total()
    if open_positions >= MAX_OPEN_TRADES:
        return False, "MAX_OPEN_TRADES"
    pnl = get_today_pnl()
    # เป้า/จำกัด เป็น % ของ balance
    if pnl >= (DAILY_PROFIT_TARGET/100.0) * balance:
        return False, "DAILY_TARGET_REACHED"
    if pnl <= - (DAILY_DRAWDOWN_LIMIT/100.0) * balance:
        return False, "DAILY_DRAWDOWN_HIT"
    return True, "OK"
