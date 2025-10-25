#!/usr/bin/env python3
"""
Demo Mode สำหรับ macOS (เนื่องจาก MT5 API ไม่รองรับ macOS)
"""
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from config import SYMBOL, TIMEFRAME, LOT, SL_PIPS, TP_PIPS
from strategy import ema_strategy
from utils.logger import get_logger

log = get_logger("demo_mode")

def get_forex_data(symbol: str, days: int = 30):
    """ดึงข้อมูลจาก Yahoo Finance (สำหรับ demo)"""
    try:
        # แปลง symbol format
        if symbol == "XAUUSD":
            yahoo_symbol = "GC=F"  # Gold futures
        elif symbol == "EURUSD":
            yahoo_symbol = "EURUSD=X"
        else:
            yahoo_symbol = f"{symbol}=X"
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # ดึงข้อมูล
        data = yf.download(yahoo_symbol, start=start_date, end=end_date, interval="1d")
        
        if data.empty:
            log.error(f"No data for {symbol}")
            return None
        
        # แปลงเป็น format ที่ strategy ต้องการ
        df_clean = pd.DataFrame()
        df_clean['time'] = data.index
        df_clean['open'] = data['Open'].values
        df_clean['high'] = data['High'].values
        df_clean['low'] = data['Low'].values
        df_clean['close'] = data['Close'].values
        
        # Volume (ถ้ามี)
        if 'Volume' in data.columns:
            df_clean['volume'] = data['Volume'].values
        else:
            df_clean['volume'] = [0] * len(data)
        
        return df_clean.dropna().reset_index(drop=True)
        

        
    except Exception as e:
        log.error(f"Error fetching data: {e}")
        return None

def simulate_order(symbol: str, volume: float, action: str, current_price: float):
    """จำลองการส่ง order"""
    if action == "HOLD":
        log.info("HOLD: ไม่มีการส่ง order")
        return None
    
    # คำนวณ SL และ TP
    if action == "BUY":
        sl_price = current_price - (SL_PIPS * 0.0001)  # สมมติ 1 pip = 0.0001
        tp_price = current_price + (TP_PIPS * 0.0001)
    else:  # SELL
        sl_price = current_price + (SL_PIPS * 0.0001)
        tp_price = current_price - (TP_PIPS * 0.0001)
    
    log.info(f"""
🔄 จำลองการส่ง Order:
   Symbol: {symbol}
   Action: {action}
   Volume: {volume} lot
   Price: {current_price:.5f}
   SL: {sl_price:.5f} ({SL_PIPS} pips)
   TP: {tp_price:.5f} ({TP_PIPS} pips)
    """)
    
    return {
        'symbol': symbol,
        'action': action,
        'volume': volume,
        'price': current_price,
        'sl': sl_price,
        'tp': tp_price
    }

def run_demo():
    """รัน demo mode"""
    print("🚀 เริ่มต้น Demo Mode (macOS Compatible)")
    print(f"📊 Symbol: {SYMBOL}")
    print(f"⏰ Timeframe: {TIMEFRAME}")
    print(f"💰 Lot Size: {LOT}")
    
    # ดึงข้อมูล
    print("\n📈 กำลังดึงข้อมูลราคา...")
    df = get_forex_data(SYMBOL, days=60)
    
    if df is None or df.empty:
        print("❌ ไม่สามารถดึงข้อมูลได้")
        return
    
    print(f"✅ ดึงข้อมูลสำเร็จ: {len(df)} bars")
    print(f"📅 ข้อมูลล่าสุด: {df.iloc[-1]['time']}")
    print(f"💵 ราคาปัจจุบัน: {df.iloc[-1]['close']:.5f}")
    
    # วิเคราะห์ strategy
    print("\n🤖 วิเคราะห์ Strategy...")
    signal = ema_strategy(df)
    
    print(f"📡 Signal: {signal}")
    
    # จำลองการส่ง order
    if signal in ["BUY", "SELL"]:
        current_price = df.iloc[-1]['close']
        order = simulate_order(SYMBOL, LOT, signal, current_price)
        if order:
            print("✅ Order ถูกส่งแล้ว (จำลอง)")
    else:
        print("⏸️ ไม่มี Signal - รอสัญญาณถัดไป")
    
    # แสดงข้อมูล EMA
    try:
        from config import EMA_SHORT, EMA_LONG
        if len(df) >= EMA_LONG:
            ema_short = df['close'].ewm(span=EMA_SHORT).mean().iloc[-1]
            ema_long = df['close'].ewm(span=EMA_LONG).mean().iloc[-1]
            print(f"""
📊 ข้อมูล EMA:
   EMA {EMA_SHORT}: {ema_short:.5f}
   EMA {EMA_LONG}: {ema_long:.5f}
   Trend: {'Bullish' if ema_short > ema_long else 'Bearish'}
            """)
    except Exception as e:
        log.error(f"Error calculating EMA: {e}")

if __name__ == "__main__":
    run_demo()