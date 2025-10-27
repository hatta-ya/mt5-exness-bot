import pandas as pd
import numpy as np
from datetime import datetime, time as dt_time

def calculate_indicators(df: pd.DataFrame):
    """
    คำนวณ indicators ทั้งหมดสำหรับ Golden Trend System
    (ปรับปรุงโดยเพิ่ม ATR และแก้ไข MACD)
    """
    df = df.copy()
    
    # --- EMA 20, 50, 200 (เหมือนเดิม) ---
    df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    # --- MACD (12, 26, 9) (แก้ไขโค้ดที่ error) ---
    exp12 = df['close'].ewm(span=12, adjust=False).mean()
    exp26 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = exp12 - exp26
    
    # แก้ไขบรรทัดนี้: .mean() หายไป และ adjust=False
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean() 
    df['macd_hist'] = df['macd'] - df['macd_signal'] # เพิ่ม histogram
    
    # --- ⭐️ เพิ่ม ATR (ตามคำแนะนำ) ---
    # ATR (Average True Range) จะใช้สำหรับตั้ง Stop Loss แบบไดนามิก
    
    # 1. คำนวณ True Range (TR)
    prev_close = df['close'].shift(1)
    tr1 = df['high'] - df['low']
    tr2 = abs(df['high'] - prev_close)
    tr3 = abs(df['low'] - prev_close)
    
    # ใช้ .max(axis=1) เพื่อหาค่าที่มากที่สุดใน 3 คอลัมน์
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # 2. คำนวณ ATR (Standard period = 14)
    # ใช้ ewm (RMA) เหมือนตัวอื่นๆ เพื่อความสอดคล้อง
    df['atr'] = tr.ewm(span=14, adjust=False).mean()

    # จัดการค่า NaN ที่เกิดจาก indicator ในช่วงแรก
    df.fillna(0, inplace=True) # หรือ .dropna() ก็ได้
    
    return df

# --- ตัวอย่างการใช้งาน (ถ้าคุณมีข้อมูล) ---
# สมมติคุณมี 'data' เป็น DataFrame ที่มี 'open', 'high', 'low', 'close', 'volume'
# df_with_indicators = calculate_indicators(data)
# print(df_with_indicators[['close', 'ema200', 'macd', 'atr']].tail())


def golden_trend_system(
    df: pd.DataFrame,
    risk_pct: float = 1.0,
    account_balance: float = 10000.0,
    macd_hist_threshold: float = 0.5,
    adx_threshold: float = 25.0,
    rsi_buy_max: float = 65.0,
    rsi_sell_min: float = 35.0,
    sl_multiplier: float = 1.5,
    tp_multiplier: float = 2.5,
    require_pullback_to_ema20: bool = False,
    point_size: float = 0.0001,
    value_per_point_per_lot: float = 10.0,
    min_lot: float = 0.01,
    max_lot: float = 0.05,
):
    """Lightweight Golden Trend decision function used by the backtester.

    Returns a dict with keys: 'signal' ('BUY'|'SELL'|'NONE'), 'entry_price',
    'sl_price', 'tp_price', 'lot_size'. This implementation is conservative and
    designed to be deterministic for backtests.
    """
    if df is None or len(df) < 50:
        return {'signal': 'NONE'}

    df_ind = calculate_indicators(df.copy())
    last = df_ind.iloc[-1]

    # Default return
    res = {'signal': 'NONE'}

    # Basic trend filter using EMAs
    bullish = last['ema20'] > last['ema50'] and last['ema50'] > last['ema200']
    bearish = last['ema20'] < last['ema50'] and last['ema50'] < last['ema200']

    macd_hist = last.get('macd_hist', 0.0)
    atr = last.get('atr', 0.0)
    entry_price = last['close']

    if atr is None or atr == 0:
        # cannot size or set SL without ATR
        return res

    # BUY signal
    if bullish and macd_hist >= macd_hist_threshold:
        sl_price = entry_price - (sl_multiplier * atr)
        tp_price = entry_price + (tp_multiplier * atr)
        # compute risk-based lot sizing
        risk_amount = max(0.0, account_balance * (risk_pct / 100.0))
        sl_points = abs(entry_price - sl_price) / point_size if point_size > 0 else 0
        if sl_points <= 0:
            return res
        lot_size = risk_amount / (sl_points * value_per_point_per_lot) if value_per_point_per_lot > 0 else min_lot
        lot_size = max(min_lot, min(max_lot, round(lot_size, 4)))

        res.update({
            'signal': 'BUY',
            'entry_price': entry_price,
            'sl_price': sl_price,
            'tp_price': tp_price,
            'lot_size': lot_size,
        })
        return res

    # SELL signal
    if bearish and macd_hist <= -macd_hist_threshold:
        sl_price = entry_price + (sl_multiplier * atr)
        tp_price = entry_price - (tp_multiplier * atr)
        risk_amount = max(0.0, account_balance * (risk_pct / 100.0))
        sl_points = abs(entry_price - sl_price) / point_size if point_size > 0 else 0
        if sl_points <= 0:
            return res
        lot_size = risk_amount / (sl_points * value_per_point_per_lot) if value_per_point_per_lot > 0 else min_lot
        lot_size = max(min_lot, min(max_lot, round(lot_size, 4)))

        res.update({
            'signal': 'SELL',
            'entry_price': entry_price,
            'sl_price': sl_price,
            'tp_price': tp_price,
            'lot_size': lot_size,
        })
        return res

    return res