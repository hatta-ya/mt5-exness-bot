#!/usr/bin/env python3
"""
🏆 Golden Trend System - Tester
ทดสอบ Golden Trend System สำหรับ XAUUSD
"""

import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from strategy import golden_trend_system, calculate_indicators
from config import SYMBOL

def test_golden_trend():
    """ทดสอบ Golden Trend System"""
    print("""
🏆 Golden Trend System - Live Test
================================
📊 Indicators: EMA(20,50,200) + MACD + RSI + ADX + ATR
🎯 Target: XAUUSD Trend Following Strategy
⚡ Dynamic SL/TP based on ATR
🛡️ Advanced Risk Management
    """)
    
    # ดึงข้อมูล XAUUSD
    print("📥 ดึงข้อมูลตลาด...")
    try:
        if SYMBOL == "XAUUSD":
            yahoo_symbol = "GC=F"  # Gold Futures
        else:
            yahoo_symbol = f"{SYMBOL}=X"
        
        # ดึงข้อมูล 6 เดือนล่าสุด
        end_date = datetime.now()
        start_date = end_date - timedelta(days=180)
        
        data = yf.download(yahoo_symbol, start=start_date, end=end_date, interval="1h")
        
        if data.empty:
            print("❌ ไม่สามารถดึงข้อมูลได้")
            return
        
        # เตรียมข้อมูล
        df = data.reset_index()
        df.columns = ['time', 'open', 'high', 'low', 'close', 'volume']
        df = df.dropna()
        
        print(f"✅ ข้อมูล: {len(df)} candles ({df['time'].iloc[0].strftime('%Y-%m-%d')} ถึง {df['time'].iloc[-1].strftime('%Y-%m-%d')})")
        
        # คำนวณ indicators
        print("\n🔍 คำนวณ Technical Indicators...")
        df = calculate_indicators(df)
        
        # แสดงข้อมูลล่าสุด
        latest = df.iloc[-1]
        print(f"""
📊 ข้อมูลล่าสุด ({latest['time'].strftime('%Y-%m-%d %H:%M')}):
----------------------------------------
💰 ราคา: ${latest['close']:.2f}
📈 EMA20: ${latest['ema20']:.2f}
📈 EMA50: ${latest['ema50']:.2f} 
📈 EMA200: ${latest['ema200']:.2f}
🔄 MACD: {latest['macd']:.4f}
⚡ RSI: {latest['rsi']:.1f}
💪 ADX: {latest['adx']:.1f} {'(Strong Trend)' if latest['adx'] > 25 else '(Weak Trend)'}
📊 ATR: {latest['atr']:.2f}
        """)
        
        # EMA Stack Analysis
        if latest['ema20'] > latest['ema50'] > latest['ema200']:
            ema_trend = "🟢 Bullish Stack (EMA20>50>200)"
        elif latest['ema20'] < latest['ema50'] < latest['ema200']:
            ema_trend = "🔴 Bearish Stack (EMA20<50<200)"
        else:
            ema_trend = "🟡 Mixed/Sideways"
        
        print(f"📊 EMA Trend: {ema_trend}")
        
        # ทดสอบ Golden Trend System
        print("\n🏆 Golden Trend System Analysis:")
        print("=" * 50)
        
        result = golden_trend_system(df, risk_pct=1.5, account_balance=10000)
        
        print(f"🎯 Signal: {result['signal']}")
        print(f"💭 Reason: {result['reason']}")
        
        if result['signal'] in ['BUY', 'SELL']:
            print(f"""
📋 Trade Setup:
--------------
🎯 Entry: ${result['entry_price']:.2f}
🛑 Stop Loss: ${result['sl_price']:.2f}
💰 Take Profit: ${result['tp_price']:.2f}
📦 Lot Size: {result['lot_size']}
📊 ATR: {result['atr']:.2f}

📈 Risk/Reward:
- Risk: ${abs(result['entry_price'] - result['sl_price']):.2f}
- Reward: ${abs(result['tp_price'] - result['entry_price']):.2f}
- R:R Ratio: 1:{abs(result['tp_price'] - result['entry_price']) / abs(result['entry_price'] - result['sl_price']):.1f}
            """)
        
        # สถิติย้อนหลัง 30 วัน
        print("\n📈 Quick Backtest (30 วันล่าสุด):")
        print("=" * 40)
        
        recent_data = df.tail(720)  # 30 วัน × 24 ชั่วโมง
        signals = []
        
        for i in range(200, len(recent_data)):  # เริ่มจากตำแหน่งที่มี indicator ครบ
            test_df = recent_data.iloc[:i+1].copy()
            signal_result = golden_trend_system(test_df, risk_pct=1.5, account_balance=10000)
            if signal_result['signal'] in ['BUY', 'SELL']:
                signals.append({
                    'time': test_df.iloc[-1]['time'],
                    'signal': signal_result['signal'],
                    'price': signal_result['entry_price'],
                    'sl': signal_result['sl_price'],
                    'tp': signal_result['tp_price']
                })
        
        print(f"🎯 Total Signals: {len(signals)}")
        buy_signals = [s for s in signals if s['signal'] == 'BUY']
        sell_signals = [s for s in signals if s['signal'] == 'SELL']
        print(f"🟢 BUY Signals: {len(buy_signals)}")
        print(f"🔴 SELL Signals: {len(sell_signals)}")
        
        if signals:
            print(f"\n📅 ล่าสุด 3 สัญญาณ:")
            for signal in signals[-3:]:
                print(f"   {signal['time'].strftime('%m-%d %H:%M')} - {signal['signal']} @ ${signal['price']:.2f}")
        
        print(f"""
🎯 Golden Trend System พร้อมใช้งาน!
- เงื่อนไขเข้มงวดสำหรับ XAUUSD
- Dynamic SL/TP จาก ATR
- Risk Management 1.5% per trade
- เฉพาะ London/NY sessions
        """)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_golden_trend()