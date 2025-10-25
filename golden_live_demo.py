#!/usr/bin/env python3
"""
🏆 Golden Trend Live Demo
Live Demo Trading ด้วย Golden Trend System
"""

import time
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from config import SYMBOL, TIMEFRAME, DAILY_PROFIT_TARGET, DAILY_DRAWDOWN_LIMIT, MAX_POSITIONS, RISK_PERCENT
from strategy import golden_trend_system
from utils.logger import get_logger
import signal
import sys

log = get_logger("golden_live_demo")

class GoldenTrendLiveDemo:
    def __init__(self, initial_balance=10000):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.daily_start_balance = initial_balance
        self.equity = initial_balance
        self.open_positions = []
        self.closed_trades = []
        self.running = True
        self.last_signal_time = None
        self.consecutive_losses = 0
        
        # Stats
        self.total_trades = 0
        self.winning_trades = 0
        self.daily_pnl = 0.0
        
        # กำหนดชื่อ symbol ที่แสดง
        symbol_display = {
            "XAUUSD": "💰 XAUUSD (Gold)",
            "BTCUSD": "₿ BTCUSD (Bitcoin)",
            "EURUSD": "💶 EURUSD (Euro)",
            "GBPUSD": "💷 GBPUSD (Pound)",
            "USDJPY": "💴 USDJPY (Yen)"
        }.get(SYMBOL, f"📊 {SYMBOL}")
        
        print(f"""
╔══════════════════════════════════════════════════════════════╗
║              🏆 Golden Trend Live Demo System                ║
║                                                              ║
║               {symbol_display:^46}                ║
╚══════════════════════════════════════════════════════════════╝
💰 Initial Balance: ${self.initial_balance:,.2f}
📊 Symbol: {SYMBOL}
⏰ Timeframe: {TIMEFRAME}
🎯 Daily Target: +{DAILY_PROFIT_TARGET}% | Limit: -{DAILY_DRAWDOWN_LIMIT}%
🛡️ Risk per Trade: {RISK_PERCENT}%
📦 Max Positions: {MAX_POSITIONS}
        """)

    def get_live_data(self, days_back=60):
        """ดึงข้อมูลล่าสุด"""
        try:
            if SYMBOL == "XAUUSD":
                yahoo_symbol = "GC=F"
            elif SYMBOL == "BTCUSD":
                yahoo_symbol = "BTC-USD"  # Bitcoin symbol for Yahoo Finance
            elif SYMBOL == "EURUSD":
                yahoo_symbol = "EURUSD=X"
            else:
                yahoo_symbol = f"{SYMBOL}=X"

            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            # ใช้ interval ตาม TIMEFRAME
            if TIMEFRAME in ["M1", "M5", "M15", "M30"]:
                interval = "5m" if TIMEFRAME in ["M1", "M5"] else "15m" if TIMEFRAME == "M15" else "30m"
            elif TIMEFRAME == "H1":
                interval = "1h"
            elif TIMEFRAME == "H4":
                interval = "1h"  # จะ resample เป็น 4h
            else:  # D1
                interval = "1d"
            
            data = yf.download(yahoo_symbol, start=start_date, end=end_date, interval=interval)
            
            if data.empty:
                return None
            
            df = data.reset_index()
            df.columns = ['time', 'open', 'high', 'low', 'close', 'volume']
            
            # Resample เป็น H4 ถ้าจำเป็น
            if TIMEFRAME == "H4" and interval == "1h":
                df = df.set_index('time')
                df_4h = df.resample('4H').agg({
                    'open': 'first',
                    'high': 'max',
                    'low': 'min',
                    'close': 'last',
                    'volume': 'sum'
                }).dropna().reset_index()
                df = df_4h
            
            return df.dropna()
        
        except Exception as e:
            log.error(f"Error getting data: {e}")
            return None

    def simulate_trade(self, signal_data):
        """จำลองการเทรด"""
        if signal_data['signal'] == 'HOLD':
            return
            
        # ตรวจสอบ max positions
        if len(self.open_positions) >= MAX_POSITIONS:
            log.info(f"Max positions reached ({MAX_POSITIONS})")
            return
            
        # ตรวจสอบ consecutive losses
        if self.consecutive_losses >= 3:
            log.warning("3 consecutive losses - pausing trading")
            return
        
        # สร้าง position ใหม่
        position = {
            'id': f"GT_{len(self.closed_trades) + 1}",
            'type': signal_data['signal'],
            'entry_price': signal_data['entry_price'],
            'sl_price': signal_data['sl_price'],
            'tp_price': signal_data['tp_price'],
            'lot_size': signal_data['lot_size'],
            'entry_time': datetime.now(),
            'current_price': signal_data['entry_price']
        }
        
        self.open_positions.append(position)
        log.info(f"📈 {signal_data['signal']} @ ${signal_data['entry_price']:.2f} | Lot: {signal_data['lot_size']}")
        log.info(f"🛑 SL: ${signal_data['sl_price']:.2f} | 💰 TP: ${signal_data['tp_price']:.2f}")

    def update_positions(self, current_price):
        """อัปเดต positions และปิดที่ถึง SL/TP"""
        closed_positions = []
        
        for position in self.open_positions[:]:
            position['current_price'] = current_price
            
            # คำนวณ P&L
            if position['type'] == 'BUY':
                pnl = (current_price - position['entry_price']) * position['lot_size'] * 100
                # ตรวจสอบ SL/TP
                if current_price <= position['sl_price']:
                    # Hit SL
                    self.close_position(position, position['sl_price'], "Stop Loss")
                    closed_positions.append(position)
                elif current_price >= position['tp_price']:
                    # Hit TP
                    self.close_position(position, position['tp_price'], "Take Profit")
                    closed_positions.append(position)
            else:  # SELL
                pnl = (position['entry_price'] - current_price) * position['lot_size'] * 100
                # ตรวจสอบ SL/TP
                if current_price >= position['sl_price']:
                    # Hit SL
                    self.close_position(position, position['sl_price'], "Stop Loss")
                    closed_positions.append(position)
                elif current_price <= position['tp_price']:
                    # Hit TP
                    self.close_position(position, position['tp_price'], "Take Profit")
                    closed_positions.append(position)
        
        # ลบ positions ที่ปิดแล้ว
        for pos in closed_positions:
            if pos in self.open_positions:
                self.open_positions.remove(pos)

    def close_position(self, position, close_price, reason):
        """ปิด position"""
        if position['type'] == 'BUY':
            pnl = (close_price - position['entry_price']) * position['lot_size'] * 100
        else:
            pnl = (position['entry_price'] - close_price) * position['lot_size'] * 100
        
        self.balance += pnl
        self.daily_pnl += pnl
        
        trade_record = {
            'id': position['id'],
            'type': position['type'],
            'entry_price': position['entry_price'],
            'close_price': close_price,
            'lot_size': position['lot_size'],
            'pnl': pnl,
            'entry_time': position['entry_time'],
            'close_time': datetime.now(),
            'reason': reason
        }
        
        self.closed_trades.append(trade_record)
        self.total_trades += 1
        
        if pnl > 0:
            self.winning_trades += 1
            self.consecutive_losses = 0
            log.info(f"✅ {reason} - Profit: ${pnl:.2f}")
        else:
            self.consecutive_losses += 1
            log.info(f"❌ {reason} - Loss: ${pnl:.2f}")

    def show_status(self, current_price, signal_info):
        """แสดงสถานะปัจจุบัน"""
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0
        daily_pnl_pct = (self.daily_pnl / self.daily_start_balance * 100)
        
        print(f"""
⏰ {datetime.now().strftime('%H:%M:%S')} | 💰 ${current_price:.2f}
💼 Balance: ${self.balance:,.2f} | 📊 Daily P&L: {daily_pnl_pct:+.2f}%
📈 Trades: {self.total_trades} | 🎯 Win Rate: {win_rate:.1f}%
📦 Open: {len(self.open_positions)} | 🔄 Consecutive Losses: {self.consecutive_losses}
🎯 Signal: {signal_info['signal']} | 💭 {signal_info['reason']}
        """)

    def run(self):
        """เริ่มการทำงาน"""
        print("🚀 เริ่ม Golden Trend Live Demo...")
        
        # Setup signal handler
        def signal_handler(sig, frame):
            print("\n🛑 กำลังหยุด Golden Trend Demo...")
            self.running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        
        try:
            while self.running:
                # ดึงข้อมูลล่าสุด
                df = self.get_live_data(days_back=90)
                if df is None or len(df) < 200:
                    log.error("ไม่สามารถดึงข้อมูลได้")
                    time.sleep(60)
                    continue
                
                current_price = df.iloc[-1]['close']
                
                # วิเคราะห์ Golden Trend System
                signal_result = golden_trend_system(df, risk_pct=RISK_PERCENT, account_balance=self.balance)
                
                # อัปเดต positions
                self.update_positions(current_price)
                
                # ตรวจสอบสัญญาณใหม่
                current_time = datetime.now()
                if (signal_result['signal'] in ['BUY', 'SELL'] and 
                    (self.last_signal_time is None or 
                     (current_time - self.last_signal_time).total_seconds() > 3600)):  # 1 ชั่วโมง
                    
                    self.simulate_trade(signal_result)
                    self.last_signal_time = current_time
                
                # แสดงสถานะ
                self.show_status(current_price, signal_result)
                
                # ตรวจสอบ daily limits
                daily_pnl_pct = (self.daily_pnl / self.daily_start_balance * 100)
                if daily_pnl_pct >= DAILY_PROFIT_TARGET:
                    print(f"🎯 ถึงเป้าหมายกำไรรายวัน! (+{daily_pnl_pct:.2f}%)")
                    break
                elif daily_pnl_pct <= -DAILY_DRAWDOWN_LIMIT:
                    print(f"🛑 ถึงขีดจำกัดการขาดทุนรายวัน! ({daily_pnl_pct:.2f}%)")
                    break
                
                time.sleep(30)  # รอ 30 วินาที
                
        except Exception as e:
            log.error(f"Error in main loop: {e}")
        finally:
            print(f"""
📊 Golden Trend Demo สิ้นสุด
===============================
💰 Final Balance: ${self.balance:,.2f}
📈 Total P&L: ${self.balance - self.initial_balance:,.2f}
🎯 Total Trades: {self.total_trades}
✅ Winning Trades: {self.winning_trades}
📊 Win Rate: {(self.winning_trades/self.total_trades*100) if self.total_trades > 0 else 0:.1f}%
            """)

def main():
    demo = GoldenTrendLiveDemo(initial_balance=10000)
    demo.run()

if __name__ == "__main__":
    main()