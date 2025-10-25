import pandas as pd
import numpy as np
from config import EMA_SHORT, EMA_LONG
from datetime import datetime, time as dt_time

def calculate_indicators(df: pd.DataFrame):
    """คำนวณ indicators ทั้งหมดสำหรับ Golden Trend System"""
    df = df.copy()
    
    # EMA 20, 50, 200
    df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    # MACD (12, 26, 9)
    exp12 = df['close'].ewm(span=12, adjust=False).mean()
    exp26 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = exp12 - exp26
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_histogram'] = df['macd'] - df['macd_signal']
    
    # RSI (14)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # ADX (14) - Simplified version
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift(1))
    low_close = np.abs(df['low'] - df['close'].shift(1))
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    
    plus_dm = df['high'].diff()
    minus_dm = df['low'].diff() * -1
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    
    plus_di = 100 * (plus_dm.rolling(14).mean() / true_range.rolling(14).mean())
    minus_di = 100 * (minus_dm.rolling(14).mean() / true_range.rolling(14).mean())
    
    dx = (np.abs(plus_di - minus_di) / np.abs(plus_di + minus_di)) * 100
    df['adx'] = dx.rolling(14).mean()
    
    # ATR (14)
    df['atr'] = true_range.rolling(window=14).mean()
    
    return df

def is_london_or_ny_session():
    """ตรวจสอบว่าอยู่ในช่วงเวลา London หรือ NY session หรือไม่"""
    # สำหรับ Backtest - อนุญาตทุกเวลา (คืน True เสมอ)
    return True
    
    # Code เดิมสำหรับ Live Trading
    # now = datetime.now().time()
    # london_start = dt_time(15, 0)
    # london_end = dt_time(23, 59)
    # ny_start = dt_time(20, 0)
    # ny_end = dt_time(5, 0)
    # return (london_start <= now <= london_end) or (now >= ny_start or now <= ny_end)

def golden_trend_system(df: pd.DataFrame, risk_pct=1.5, account_balance=10000):
    """
    Golden Trend System สำหรับ XAUUSD
    
    Args:
        df: DataFrame with OHLC data
        risk_pct: Risk percentage per trade (1-2%)
        account_balance: Account balance for position sizing
    
    Returns:
        dict: {
            'signal': 'BUY'/'SELL'/'HOLD',
            'entry_price': float,
            'sl_price': float, 
            'tp_price': float,
            'lot_size': float,
            'reason': str
        }
    """
    
    # ตรวจสอบข้อมูลเพียงพอ
    if len(df) < 200:
        return {'signal': 'HOLD', 'reason': 'ข้อมูลไม่เพียงพอ (ต้อง >= 200 candles)'}
    
    # คำนวณ indicators
    df = calculate_indicators(df)
    
    # ใช้ข้อมูล candle ล่าสุด (closed candle)
    current = df.iloc[-1]
    
    # ตรวจสอบเวลา trading
    if not is_london_or_ny_session():
        return {'signal': 'HOLD', 'reason': 'นอกเวลา London/NY session'}
    
    # เงื่อนไข BUY Setup (ปรับให้อ่อนลง)
    buy_conditions = [
        current['ema20'] > current['ema50'],           # EMA20 > EMA50
        current['ema50'] > current['ema200'],          # EMA50 > EMA200  
        current['macd'] > -0.5,                        # MACD > -0.5 (อ่อนลง)
        40 <= current['rsi'] <= 70,                    # RSI between 40-70 (กว้างขึ้น)
        current['adx'] > 20                            # ADX > 20 (อ่อนลง)
    ]
    
    # เงื่อนไข SELL Setup (ปรับให้อ่อนลง)  
    sell_conditions = [
        current['ema20'] < current['ema50'],           # EMA20 < EMA50
        current['ema50'] < current['ema200'],          # EMA50 < EMA200
        current['macd'] < 0.5,                         # MACD < 0.5 (อ่อนลง)
        30 <= current['rsi'] <= 60,                    # RSI between 30-60 (กว้างขึ้น)
        current['adx'] > 20                            # ADX > 20 (อ่อนลง)
    ]
    
    entry_price = current['close']
    atr = current['atr']
    
    # BUY Signal
    if all(buy_conditions):
        sl_price = entry_price - (1.5 * atr)
        tp_price = entry_price + (2.5 * atr)
        
        # คำนวณ lot size based on risk
        sl_distance_points = (entry_price - sl_price) * 100  # XAUUSD: 1 point = $0.01
        risk_amount = account_balance * (risk_pct / 100)
        lot_size = min(0.1, max(0.01, risk_amount / sl_distance_points))
        
        return {
            'signal': 'BUY',
            'entry_price': entry_price,
            'sl_price': sl_price,
            'tp_price': tp_price,
            'lot_size': round(lot_size, 2),
            'atr': atr,
            'reason': f'Golden Trend BUY: EMA Stack✅ MACD+✅ RSI:{current["rsi"]:.1f}✅ ADX:{current["adx"]:.1f}✅'
        }
    
    # SELL Signal
    elif all(sell_conditions):
        sl_price = entry_price + (1.5 * atr)
        tp_price = entry_price - (2.5 * atr)
        
        # คำนวณ lot size based on risk
        sl_distance_points = (sl_price - entry_price) * 100  # XAUUSD: 1 point = $0.01
        risk_amount = account_balance * (risk_pct / 100)
        lot_size = min(0.1, max(0.01, risk_amount / sl_distance_points))
        
        return {
            'signal': 'SELL',
            'entry_price': entry_price,
            'sl_price': sl_price,
            'tp_price': tp_price,
            'lot_size': round(lot_size, 2),
            'atr': atr,
            'reason': f'Golden Trend SELL: EMA Stack✅ MACD-✅ RSI:{current["rsi"]:.1f}✅ ADX:{current["adx"]:.1f}✅'
        }
    
    # Alternative Strategy - เมื่อ Golden Trend ไม่ได้สัญญาณ
    else:
        # ลองใช้ Simple EMA Cross + RSI
        if (current['ema20'] > current['ema50'] and 
            current['rsi'] > 50 and current['rsi'] < 80 and
            current['macd'] > -1.0):
            
            sl_price = entry_price - (1.2 * atr)
            tp_price = entry_price + (2.0 * atr)
            
            sl_distance_points = (entry_price - sl_price) * 100
            risk_amount = account_balance * (risk_pct / 100)
            lot_size = min(0.1, max(0.01, risk_amount / sl_distance_points))
            
            return {
                'signal': 'BUY',
                'entry_price': entry_price,
                'sl_price': sl_price,
                'tp_price': tp_price,
                'lot_size': round(lot_size, 2),
                'atr': atr,
                'reason': f'Alternative BUY: EMA Cross + RSI:{current["rsi"]:.1f}'
            }
            
        elif (current['ema20'] < current['ema50'] and 
              current['rsi'] < 50 and current['rsi'] > 20 and
              current['macd'] < 1.0):
            
            sl_price = entry_price + (1.2 * atr)
            tp_price = entry_price - (2.0 * atr)
            
            sl_distance_points = (sl_price - entry_price) * 100
            risk_amount = account_balance * (risk_pct / 100)
            lot_size = min(0.1, max(0.01, risk_amount / sl_distance_points))
            
            return {
                'signal': 'SELL',
                'entry_price': entry_price,
                'sl_price': sl_price,
                'tp_price': tp_price,
                'lot_size': round(lot_size, 2),
                'atr': atr,
                'reason': f'Alternative SELL: EMA Cross + RSI:{current["rsi"]:.1f}'
            }
        
        # วิเคราะห์เงื่อนไขที่ไม่ผ่าน
        failed_conditions = []
        if not (current['ema20'] > current['ema50'] > current['ema200']) and not (current['ema20'] < current['ema50'] < current['ema200']):
            failed_conditions.append("EMA Stack")
        if abs(current['macd']) > 2:
            failed_conditions.append("MACD ผันผวนมาก")
        if current['rsi'] < 30 or current['rsi'] > 70:
            failed_conditions.append(f"RSI:{current['rsi']:.1f} extreme")
        if current['adx'] <= 15:
            failed_conditions.append(f"ADX:{current['adx']:.1f} ไม่มี trend")
            
        return {
            'signal': 'HOLD',
            'reason': f'รอสัญญาณ: {", ".join(failed_conditions) if failed_conditions else "ตรวจสอบเงื่อนไข"}'
        }

# Backward compatibility - เก็บ function เก่าไว้
def ema_strategy(df: pd.DataFrame):
    """Legacy EMA strategy - ใช้ Golden Trend แทน"""
    result = golden_trend_system(df)
    return result['signal']
