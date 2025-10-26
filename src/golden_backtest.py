#!/usr/bin/env python3
"""
🏆 Golden Trend Backtest Engine
ทดสอบ Golden Trend System แบบ comprehensive
"""

import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import numpy as np
from .config import SYMBOL, RISK_PERCENT, BACKTEST_DAYS
from .strategy import golden_trend_system
from .utils.logger import get_logger

log = get_logger("golden_backtest")

class GoldenTrendBacktest:
    def __init__(self, initial_balance=10000):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.equity = initial_balance
        self.trades = []
        self.daily_balance = []
        self.consecutive_losses = 0
        self.max_consecutive_losses = 0
        
        # Drawdown tracking
        self.peak_balance = initial_balance
        self.max_drawdown = 0.0
        self.current_drawdown = 0.0
        self.balance_history = [initial_balance]
        
    def get_historical_data(self, symbol: str, days: int):
        """ดึงข้อมูลย้อนหลัง"""
        try:
            if symbol == "XAUUSD":
                yahoo_symbol = "GC=F"  # Gold Futures
            elif symbol == "BTCUSD":
                yahoo_symbol = "BTC-USD"  # Bitcoin vs USD
            else:
                yahoo_symbol = f"{symbol}=X"
            
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days + 50)  # Buffer สำหรับ indicators
            
            data = yf.download(yahoo_symbol, start=start_date, end=end_date, interval="1h")
            
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
            log.error(f"Error getting data: {e}")
            return None

    def execute_trade(self, action, entry_price, sl_price, tp_price, lot_size, entry_time, reason="Golden Trend Signal"):
        """บันทึกการเทรด พร้อมจำลอง Slippage และ Commission"""
        multiplier = 1 if action == "BUY" else -1

        # ค่า Spread, Commission และ Slippage
        spread = 0.0  # Zero spread account
        commission_per_lot = 7.0  # $7 per lot per side
        commission = commission_per_lot * lot_size * 2  # ค่าคอมมิชชั่นทั้งเปิดและปิด
        slippage = np.random.uniform(-0.5, 0.5)  # Slippage ±0.5

        # คำนวณ P&L เมื่อปิดที่ TP
        if action == "BUY":
            exit_price = tp_price - spread + slippage  # หัก Spread และเพิ่ม Slippage สำหรับ BUY
        else:
            exit_price = tp_price + spread + slippage  # บวก Spread และเพิ่ม Slippage สำหรับ SELL

        # คำนวณ P&L สำหรับ XAUUSD
        pnl = ((exit_price - entry_price) * multiplier * lot_size * 100) - commission

        # อัปเดต balance
        old_balance = self.balance
        self.balance += pnl

        # จัดการ consecutive losses
        if pnl > 0:
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
            self.max_consecutive_losses = max(self.max_consecutive_losses, self.consecutive_losses)

        # บันทึก trade
        trade = {
            'time': entry_time,
            'action': action,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'sl_price': sl_price,
            'tp_price': tp_price,
            'lot_size': lot_size,
            'pnl': pnl,
            'balance': self.balance,
            'result': 'WIN' if pnl > 0 else 'LOSS',
            'commission': commission,
            'slippage': slippage,
            'drawdown': self.current_drawdown,
            'reason': reason
        }

        self.trades.append(trade)

        return trade

    def run_backtest(self):
        """รัน backtest"""
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
║              🏆 Golden Trend System Backtest                ║
║                                                              ║
║               {symbol_display:^46}                ║
╚══════════════════════════════════════════════════════════════╝
📊 Symbol: {SYMBOL}
📅 Period: {BACKTEST_DAYS} days
💰 Initial Balance: ${self.initial_balance:,.2f}
🛡️ Risk per Trade: {RISK_PERCENT}%
        """)
        
        # ดึงข้อมูล
        print("📥 ดาวน์โหลดข้อมูล...")
        df = self.get_historical_data(SYMBOL, BACKTEST_DAYS)
        
        if df is None or len(df) < 200:
            print("❌ ไม่สามารถดึงข้อมูลได้หรือข้อมูลไม่เพียงพอ")
            return
        
        print(f"✅ ข้อมูล: {len(df)} candles ({df['time'].iloc[0].strftime('%Y-%m-%d')} ถึง {df['time'].iloc[-1].strftime('%Y-%m-%d')})")
        
        # Backtest loop
        print("\n🔍 กำลังวิเคราะห์...")
        signals = 0
        
        for i in range(200, len(df)):  # เริ่มจากตำแหน่งที่มี indicator ครบ
            # ตรวจสอบ consecutive losses limit
            if self.consecutive_losses >= 3:
                continue  # หยุดเทรดหลังขาดทุน 3 ครั้งติด
                
            current_data = df.iloc[:i+1].copy()
            current_price = current_data.iloc[-1]['close']
            current_time = current_data.iloc[-1]['time']
            
            # วิเคราะห์ Golden Trend System
            result = golden_trend_system(current_data, risk_pct=RISK_PERCENT, account_balance=self.balance)
            
            if result['signal'] in ['BUY', 'SELL']:
                signals += 1
                
                # ตรวจสอบขนาด lot ไม่เกิน 0.05
                max_lot_size = 0.05
                lot_size = min(result['lot_size'], max_lot_size)

                # ปรับ SL/TP ตามค่าจาก .env
                sl_pips = 70  # Stop Loss
                tp_pips = 210  # Take Profit
                sl_price = current_price - (sl_pips * 0.01) if result['signal'] == 'BUY' else current_price + (sl_pips * 0.01)
                tp_price = current_price + (tp_pips * 0.01) if result['signal'] == 'BUY' else current_price - (tp_pips * 0.01)

                # Execute trade with adjusted values
                trade = self.execute_trade(
                    action=result['signal'],
                    entry_price=result['entry_price'],
                    sl_price=sl_price,
                    tp_price=tp_price,
                    lot_size=lot_size,
                    entry_time=current_time,
                    reason=result.get('reason', 'Golden Trend Signal')
                )
                
                # แสดง log รายละเอียด trade พร้อมหมายเลข (log to file)
                order_no = len(self.trades)
                log_msg = f"#{order_no:04d} 🎯 {trade['action']} @ ${trade['entry_price']:.2f} | P&L: ${trade['pnl']:.2f} | Balance: ${trade['balance']:.2f} | Reason: {trade['reason']}"
                log.info(log_msg)
                print(log_msg)
        
        # แสดงผลลัพธ์
        self.show_results()

    def show_results(self):
        """แสดงผลลัพธ์"""
        if not self.trades:
            print("\n❌ ไม่มี Trade ใน Golden Trend System")
            return

        # คำนวณสถิติ
        total_trades = len(self.trades)
        winning_trades = len([t for t in self.trades if t['pnl'] > 0])
        losing_trades = total_trades - winning_trades
        win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0

        total_profit = sum([t['pnl'] for t in self.trades if t['pnl'] > 0])
        total_loss = sum([t['pnl'] for t in self.trades if t['pnl'] < 0])
        net_profit = self.balance - self.initial_balance

        # คำนวณจำนวนการเทรดเฉลี่ยต่อวัน
        backtest_days = BACKTEST_DAYS
        avg_trades_per_day = total_trades / backtest_days if backtest_days > 0 else 0

        print(f"""
🏆 Golden Trend System Results
==============================
📊 การเทรด:
   • Total Trades: {total_trades}
   • Winning: {winning_trades} ({win_rate:.1f}%)
   • Losing: {losing_trades} ({100-win_rate:.1f}%)
   • Avg Trades/Day: {avg_trades_per_day:.2f}

💰 ผลกำไร:
   • Initial Balance: ${self.initial_balance:,.2f}
   • Final Balance: ${self.balance:,.2f}
   • Net P&L: ${net_profit:,.2f}
   • Total Profit: ${total_profit:,.2f}
   • Total Loss: ${total_loss:,.2f}

📉 ความเสี่ยง:
   • Max Drawdown: {self.max_drawdown:.2f}%
   • Current Drawdown: {self.current_drawdown:.2f}%
   • Peak Balance: ${self.peak_balance:,.2f}
   • Max Consecutive Losses: {self.max_consecutive_losses}
        """)

        # แสดง 3 ออเดอร์ล่าสุดที่ชนะ
        recent_winning_trades = [t for t in self.trades if t['pnl'] > 0][-3:]
        print("\n📈 ตัวอย่าง 3 ออเดอร์ล่าสุดที่ชนะ:")
        for i, trade in enumerate(recent_winning_trades, 1):
            print(f"   {i}. {trade['action']} @ ${trade['entry_price']:.2f} -> ${trade['exit_price']:.2f} | Lots: {trade['lot_size']} | Reason: {'TP Hit' if trade['pnl'] > 0 else 'Other'}")

def main():
    initial_balance = float(input("💰 กรุณาใส่ทุนเริ่มต้น (เช่น 10000 USD): "))
    backtest = GoldenTrendBacktest(initial_balance=initial_balance)
    backtest.run_backtest()

if __name__ == "__main__":
    main()
