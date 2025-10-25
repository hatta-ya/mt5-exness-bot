#!/usr/bin/env python3
"""
Backtest Engine สำหรับ macOS (ใช้ข้อมูลจาก Yahoo Finance)
"""
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import numpy as np
from config import SYMBOL, LOT, SL_PIPS, TP_PIPS, BACKTEST_DAYS, EMA_SHORT, EMA_LONG
from strategy import ema_strategy
from utils.logger import get_logger

log = get_logger("backtest")

class BacktestEngine:
    def __init__(self, initial_balance=10000):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.equity = initial_balance
        self.trades = []
        self.daily_balance = []
        
    def get_historical_data(self, symbol: str, days: int):
        """ดึงข้อมูลย้อนหลัง"""
        try:
            # แปลง symbol
            if symbol == "XAUUSD":
                yahoo_symbol = "GC=F"
            elif symbol == "EURUSD":
                yahoo_symbol = "EURUSD=X"
            else:
                yahoo_symbol = f"{symbol}=X"
            
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days + 30)  # เพิ่ม buffer สำหรับ EMA
            
            data = yf.download(yahoo_symbol, start=start_date, end=end_date, interval="1d")
            
            if data.empty:
                return None
            
            df = pd.DataFrame()
            df['time'] = data.index
            df['open'] = data['Open'].values
            df['high'] = data['High'].values
            df['low'] = data['Low'].values
            df['close'] = data['Close'].values
            df['volume'] = data.get('Volume', [0] * len(data)).values
            
            return df.dropna().reset_index(drop=True)
            
        except Exception as e:
            log.error(f"Error fetching data: {e}")
            return None
    
    def calculate_position_size(self, price: float):
        """คำนวณขนาดของ position (แปลงจาก lot เป็น value)"""
        if SYMBOL == "XAUUSD":
            # ทองคำ 1 lot = 100 oz
            return LOT * 100 * price
        else:
            # Forex 1 lot = 100,000 units
            return LOT * 100000
    
    def simulate_trade(self, entry_price: float, action: str, exit_price: float = None, exit_reason: str = "Market"):
        """จำลองการเทรด"""
        position_size = self.calculate_position_size(entry_price)
        
        # คำนวณ SL และ TP
        if action == "BUY":
            sl_price = entry_price - (SL_PIPS * 0.1)  # สำหรับทองคำ 1 pip = 0.1
            tp_price = entry_price + (TP_PIPS * 0.1)
            multiplier = 1
        else:  # SELL
            sl_price = entry_price + (SL_PIPS * 0.1)
            tp_price = entry_price - (TP_PIPS * 0.1)
            multiplier = -1
        
        # ถ้าไม่ระบุ exit_price ใช้ TP
        if exit_price is None:
            exit_price = tp_price
            exit_reason = "TP"
        
        # คำนวณ P&L
        if SYMBOL == "XAUUSD":
            # ทองคำ: P&L = (Exit - Entry) * Volume * Multiplier
            pnl = (exit_price - entry_price) * (LOT * 100) * multiplier
        else:
            # Forex: P&L = (Exit - Entry) * Position Size * Multiplier / Entry Price
            pnl = (exit_price - entry_price) * position_size * multiplier / entry_price
        
        # อัปเดต balance
        self.balance += pnl
        self.equity = self.balance
        
        # บันทึก trade
        trade = {
            'time': datetime.now(),
            'symbol': SYMBOL,
            'action': action,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'exit_reason': exit_reason,
            'lot': LOT,
            'pnl': pnl,
            'balance': self.balance
        }
        
        self.trades.append(trade)
        return trade
    
    def run_backtest(self, df: pd.DataFrame):
        """รัน backtest"""
        print(f"🚀 เริ่ม Backtest - {SYMBOL}")
        print(f"💰 Balance เริ่มต้น: ${self.initial_balance:,.2f}")
        print(f"📊 ข้อมูล: {len(df)} วัน")
        print("=" * 50)
        
        # ต้องมีข้อมูลเพียงพอสำหรับ EMA
        if len(df) < EMA_LONG + 10:
            print(f"❌ ข้อมูลไม่เพียงพอ (ต้องการอย่างน้อย {EMA_LONG + 10} วัน)")
            return
        
        open_position = None
        
        # วนลูปทุกวัน
        for i in range(EMA_LONG, len(df)):
            # ดึงข้อมูลจนถึงวันปัจจุบัน
            current_data = df.iloc[:i+1].copy()
            current_price = current_data.iloc[-1]['close']
            
            # บันทึก balance รายวัน
            self.daily_balance.append({
                'date': current_data.iloc[-1]['time'],
                'balance': self.balance
            })
            
            # ถ้ามี position เปิด ตรวจสอบ SL/TP
            if open_position:
                action = open_position['action']
                entry_price = open_position['entry_price']
                
                hit_sl = False
                hit_tp = False
                
                if action == "BUY":
                    sl_price = entry_price - (SL_PIPS * 0.1)
                    tp_price = entry_price + (TP_PIPS * 0.1)
                    
                    if current_price <= sl_price:
                        hit_sl = True
                        exit_price = sl_price
                    elif current_price >= tp_price:
                        hit_tp = True
                        exit_price = tp_price
                        
                else:  # SELL
                    sl_price = entry_price + (SL_PIPS * 0.1)
                    tp_price = entry_price - (TP_PIPS * 0.1)
                    
                    if current_price >= sl_price:
                        hit_sl = True
                        exit_price = sl_price
                    elif current_price <= tp_price:
                        hit_tp = True
                        exit_price = tp_price
                
                # ปิด position ถ้าโดน SL/TP
                if hit_sl or hit_tp:
                    exit_reason = "SL" if hit_sl else "TP"
                    trade = self.simulate_trade(entry_price, action, exit_price, exit_reason)
                    
                    pnl_str = f"+${trade['pnl']:.2f}" if trade['pnl'] > 0 else f"${trade['pnl']:.2f}"
                    print(f"📈 {action} {exit_reason} | Entry: ${entry_price:.2f} | Exit: ${exit_price:.2f} | P&L: {pnl_str}")
                    
                    open_position = None
                    continue
            
            # ถ้าไม่มี position หา signal ใหม่
            if not open_position:
                signal = ema_strategy(current_data)
                
                if signal in ["BUY", "SELL"]:
                    open_position = {
                        'action': signal,
                        'entry_price': current_price,
                        'entry_time': current_data.iloc[-1]['time']
                    }
                    print(f"🔔 New {signal} Signal | Price: ${current_price:.2f}")
        
        # ปิด position ที่เหลือ (ถ้ามี)
        if open_position:
            final_price = df.iloc[-1]['close']
            trade = self.simulate_trade(
                open_position['entry_price'], 
                open_position['action'], 
                final_price, 
                "Market Close"
            )
            pnl_str = f"+${trade['pnl']:.2f}" if trade['pnl'] > 0 else f"${trade['pnl']:.2f}"
            print(f"📈 {open_position['action']} Market Close | P&L: {pnl_str}")
    
    def show_results(self):
        """แสดงผลลัพธ์"""
        if not self.trades:
            print("\n❌ ไม่มี Trade")
            return
        
        # คำนวณสถิติ
        total_trades = len(self.trades)
        winning_trades = sum(1 for t in self.trades if t['pnl'] > 0)
        losing_trades = total_trades - winning_trades
        win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
        
        total_pnl = sum(t['pnl'] for t in self.trades)
        avg_win = np.mean([t['pnl'] for t in self.trades if t['pnl'] > 0]) if winning_trades > 0 else 0
        avg_loss = np.mean([t['pnl'] for t in self.trades if t['pnl'] < 0]) if losing_trades > 0 else 0
        
        max_win = max([t['pnl'] for t in self.trades]) if self.trades else 0
        max_loss = min([t['pnl'] for t in self.trades]) if self.trades else 0
        
        roi = ((self.balance - self.initial_balance) / self.initial_balance) * 100
        
        print(f"""
{'='*60}
📊 ผลลัพธ์ Backtest
{'='*60}
💰 Balance เริ่มต้น:     ${self.initial_balance:,.2f}
💰 Balance สุดท้าย:      ${self.balance:,.2f}
📈 Total P&L:           ${total_pnl:+,.2f}
📊 ROI:                 {roi:+.2f}%

🎯 จำนวน Trades:        {total_trades}
✅ Win Trades:          {winning_trades} ({win_rate:.1f}%)
❌ Loss Trades:         {losing_trades} ({100-win_rate:.1f}%)

💹 Average Win:         ${avg_win:.2f}
📉 Average Loss:        ${avg_loss:.2f}
🏆 Max Win:             ${max_win:.2f}
💔 Max Loss:            ${max_loss:.2f}

⚖️ Risk/Reward Ratio:   {abs(avg_win/avg_loss):.2f} (ถ้า avg_loss ≠ 0)
{'='*60}
        """)
        
        # แสดง trades ล่าสุด 5 รายการ
        print("🔄 Trades ล่าสุด:")
        for trade in self.trades[-5:]:
            pnl_str = f"+${trade['pnl']:.2f}" if trade['pnl'] > 0 else f"${trade['pnl']:.2f}"
            print(f"   {trade['action']} | Entry: ${trade['entry_price']:.2f} | Exit: ${trade['exit_price']:.2f} | {trade['exit_reason']} | P&L: {pnl_str}")

def run_backtest():
    """รัน backtest หลัก"""
    print("🚀 เริ่ม Backtesting...")
    
    # สร้าง backtest engine
    bt = BacktestEngine(initial_balance=10000)
    
    # ดึงข้อมูล
    print("📈 กำลังดึงข้อมูลย้อนหลัง...")
    df = bt.get_historical_data(SYMBOL, BACKTEST_DAYS)
    
    if df is None or df.empty:
        print("❌ ไม่สามารถดึงข้อมูลได้")
        return
    
    print(f"✅ ดึงข้อมูลสำเร็จ: {len(df)} วัน")
    
    # รัน backtest
    bt.run_backtest(df)
    
    # แสดงผลลัพธ์
    bt.show_results()

if __name__ == "__main__":
    run_backtest()