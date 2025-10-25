import pandas as pd
from config import EMA_SHORT, EMA_LONG

def ema_strategy(df: pd.DataFrame):
    # df ควรมีคอลัมน์: time, open, high, low, close, tick_volume
    df = df.copy()
    df['ema_short'] = df['close'].ewm(span=EMA_SHORT, adjust=False).mean()
    df['ema_long'] = df['close'].ewm(span=EMA_LONG, adjust=False).mean()
    if len(df) < max(EMA_SHORT, EMA_LONG) + 1:
        return "HOLD"
    last_short = df['ema_short'].iloc[-1]
    last_long = df['ema_long'].iloc[-1]
    prev_short = df['ema_short'].iloc[-2]
    prev_long = df['ema_long'].iloc[-2]
    # สัญญาณเมื่อมีการ cross ล่าสุด
    if prev_short <= prev_long and last_short > last_long:
        return "BUY"
    elif prev_short >= prev_long and last_short < last_long:
        return "SELL"
    return "HOLD"
