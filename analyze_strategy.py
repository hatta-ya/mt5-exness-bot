#!/usr/bin/env python3
"""
ทดสอบ Strategy และดูข้อมูล EMA
"""
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from config import SYMBOL, EMA_SHORT, EMA_LONG
from strategy import ema_strategy

def get_data_and_analyze():
    """ดึงข้อมูลและวิเคราะห์ strategy"""
    print(f"🔍 วิเคราะห์ Strategy - {SYMBOL}")
    print(f"📊 EMA Short: {EMA_SHORT}, EMA Long: {EMA_LONG}")
    
    # ดึงข้อมูล
    if SYMBOL == "XAUUSD":
        yahoo_symbol = "GC=F"
    else:
        yahoo_symbol = f"{SYMBOL}=X"
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=120)
    
    data = yf.download(yahoo_symbol, start=start_date, end=end_date, interval="1d")
    
    if data.empty:
        print("❌ ไม่สามารถดึงข้อมูลได้")
        return
    
    # แปลงข้อมูล
    df = pd.DataFrame()
    df['time'] = data.index
    df['close'] = data['Close'].values
    df = df.reset_index(drop=True)
    
    print(f"✅ ข้อมูล: {len(df)} วัน")
    
    # คำนวณ EMA
    df['ema_short'] = df['close'].ewm(span=EMA_SHORT).mean()
    df['ema_long'] = df['close'].ewm(span=EMA_LONG).mean()
    
    # หา signals ย้อนหลัง 10 วัน
    print("\n📈 Signals ล่าสุด 10 วัน:")
    print("วันที่\t\tราคา\tEMA20\tEMA50\tSignal")
    print("-" * 70)
    
    signals_found = 0
    
    for i in range(max(len(df) - 10, EMA_LONG), len(df)):
        if i < EMA_LONG:
            continue
            
        # ดึงข้อมูลถึงวันที่ i
        current_data = df.iloc[:i+1].copy()
        signal = ema_strategy(current_data)
        
        if signal != "HOLD":
            signals_found += 1
        
        date_str = str(df.iloc[i]['time'])[:10]
        price = df.iloc[i]['close']
        ema_s = df.iloc[i]['ema_short']
        ema_l = df.iloc[i]['ema_long']
        
        # เพิ่ม emoji สำหรับ signal
        signal_emoji = "🔴" if signal == "SELL" else "🟢" if signal == "BUY" else "⚪"
        
        print(f"{date_str}\t${price:.2f}\t${ema_s:.2f}\t${ema_l:.2f}\t{signal_emoji} {signal}")
    
    print(f"\n📊 สรุป: พบ {signals_found} signals ใน 10 วันล่าสุด")
    
    # แสดงสถานะปัจจุบัน
    current_signal = ema_strategy(df)
    last_price = df.iloc[-1]['close']
    last_ema_short = df.iloc[-1]['ema_short']
    last_ema_long = df.iloc[-1]['ema_long']
    
    print(f"""
🎯 สถานะปัจจุบัน:
   ราคา: ${last_price:.2f}
   EMA {EMA_SHORT}: ${last_ema_short:.2f}
   EMA {EMA_LONG}: ${last_ema_long:.2f}
   Trend: {'Bullish' if last_ema_short > last_ema_long else 'Bearish'}
   Signal: {current_signal}
    """)
    
    # ดูว่ามี crossover ล่าสุดเมื่อไหร่
    print("\n🔄 หา EMA Crossover ล่าสุด...")
    
    for i in range(len(df) - 1, EMA_LONG, -1):
        prev_short = df.iloc[i-1]['ema_short']
        prev_long = df.iloc[i-1]['ema_long']
        curr_short = df.iloc[i]['ema_short']
        curr_long = df.iloc[i]['ema_long']
        
        # Golden Cross (bullish)
        if prev_short <= prev_long and curr_short > curr_long:
            date_str = str(df.iloc[i]['time'])[:10]
            print(f"🟢 Golden Cross (BUY): {date_str} - {len(df) - i} วันก่อน")
            break
        
        # Death Cross (bearish)
        elif prev_short >= prev_long and curr_short < curr_long:
            date_str = str(df.iloc[i]['time'])[:10]
            print(f"🔴 Death Cross (SELL): {date_str} - {len(df) - i} วันก่อน")
            break
    else:
        print("❌ ไม่พบ EMA Crossover ในช่วงเวลานี้")

if __name__ == "__main__":
    get_data_and_analyze()