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
from config import SYMBOL, RISK_PERCENT, BACKTEST_DAYS
from strategy import golden_trend_system
from utils.logger import get_logger

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
        
    def get_historical_data(self, symbol: str, days: int):
        """ดึงข้อมูลย้อนหลัง"""
        try:
            if symbol == "XAUUSD":
                yahoo_symbol = "GC=F"
            elif symbol == "EURUSD":
                yahoo_symbol = "EURUSD=X"
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

    def execute_trade(self, action, entry_price, sl_price, tp_price, lot_size, entry_time):
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
            'slippage': slippage
        }

        self.trades.append(trade)

        return trade

    def run_backtest(self):
        """รัน backtest"""
        print(f"""
🏆 Golden Trend System Backtest
================================
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
                
                # Execute trade
                trade = self.execute_trade(
                    action=result['signal'],
                    entry_price=result['entry_price'],
                    sl_price=result['sl_price'],
                    tp_price=result['tp_price'],
                    lot_size=result['lot_size'],
                    entry_time=current_time
                )
                
                print(f"🎯 {trade['action']} @ ${trade['entry_price']:.2f} | P&L: ${trade['pnl']:.2f} | Balance: ${trade['balance']:.2f}")
        
        # แสดงผลลัพธ์
        self.show_results()

    def show_results(self):
        """แสดงผลลัพธ์"""
        if not self.trades:
            print("\n❌ ไม่มี Trade ใน Golden Trend System")
            print("💡 เป็นไปได้ว่า:")
            print("   - เงื่อนไขเข้มงวดเกินไป (ADX > 25, EMA Stack)")
            print("   - ข้อมูลไม่อยู่ในช่วงเวลา London/NY")
            print("   - ตลาดไม่มี trend ที่ชัดเจน")
            return
        
        # คำนวณสถิติ
        total_trades = len(self.trades)
        winning_trades = len([t for t in self.trades if t['pnl'] > 0])
        losing_trades = total_trades - winning_trades
        win_rate = (winning_trades / total_trades) * 100
        
        total_profit = sum([t['pnl'] for t in self.trades if t['pnl'] > 0])
        total_loss = sum([t['pnl'] for t in self.trades if t['pnl'] < 0])
        net_profit = self.balance - self.initial_balance
        
        profit_factor = abs(total_profit / total_loss) if total_loss != 0 else float('inf')
        
        # Max Drawdown
        peak = self.initial_balance
        max_drawdown = 0
        for trade in self.trades:
            if trade['balance'] > peak:
                peak = trade['balance']
            drawdown = (peak - trade['balance']) / peak * 100
            max_drawdown = max(max_drawdown, drawdown)
        
        print(f"""
🏆 Golden Trend System Results
==============================
📊 การเทรด:
   • Total Trades: {total_trades}
   • Winning: {winning_trades} ({win_rate:.1f}%)
   • Losing: {losing_trades} ({100-win_rate:.1f}%)

💰 ผลกำไร:
   • Initial Balance: ${self.initial_balance:,.2f}
   • Final Balance: ${self.balance:,.2f}
   • Net P&L: ${net_profit:,.2f} ({(net_profit/self.initial_balance)*100:+.2f}%)
   • Profit Factor: {profit_factor:.2f}

📉 ความเสี่ยง:
   • Max Drawdown: {max_drawdown:.2f}%
   • Max Consecutive Losses: {self.max_consecutive_losses}

🎯 ประเมินผล:
        """)
        
        # ประเมินผลตามเกณฑ์
        if win_rate >= 65:
            print("   ✅ Win Rate: ผ่านเกณฑ์ (≥65%)")
        else:
            print(f"   ❌ Win Rate: ไม่ผ่านเกณฑ์ ({win_rate:.1f}% < 65%)")
            
        if profit_factor >= 1.8:
            print("   ✅ Profit Factor: ผ่านเกณฑ์ (≥1.8)")
        else:
            print(f"   ❌ Profit Factor: ไม่ผ่านเกณฑ์ ({profit_factor:.2f} < 1.8)")
            
        if max_drawdown <= 12:
            print("   ✅ Max Drawdown: ผ่านเกณฑ์ (≤12%)")
        else:
            print(f"   ❌ Max Drawdown: ไม่ผ่านเกณฑ์ ({max_drawdown:.2f}% > 12%)")
        
        # สถิติเพิ่มเติม
        if len(self.trades) > 0:
            # คำนวณสถิติ trades ต่อวัน
            first_trade_date = self.trades[0]['time']
            last_trade_date = self.trades[-1]['time']
            trading_days = (last_trade_date - first_trade_date).days + 1
            trades_per_day = total_trades / trading_days
            
            # กำไรเฉลี่ยต่อ trade
            avg_profit = net_profit / total_trades
            
            print(f"\n📊 สถิติเพิ่มเติม:")
            print(f"   • Trading Period: {trading_days} วัน")
            print(f"   • Trades per Day: {trades_per_day:.1f}")
            print(f"   • Avg Profit per Trade: ${avg_profit:.2f}")
            print(f"   • Total Profit: ${total_profit:,.2f}")
            print(f"   • Total Loss: ${abs(total_loss):,.2f}")
            
            # แสดง trades รายเดือน
            monthly_trades = {}
            for trade in self.trades:
                month_key = trade['time'].strftime('%Y-%m')
                if month_key not in monthly_trades:
                    monthly_trades[month_key] = {'count': 0, 'profit': 0}
                monthly_trades[month_key]['count'] += 1
                monthly_trades[month_key]['profit'] += trade['pnl']
            
            print(f"\n📅 สถิติรายเดือน:")
            for month, stats in sorted(monthly_trades.items()):
                print(f"   • {month}: {stats['count']} trades, ${stats['profit']:+,.2f}")
        
            print(f"\n📋 Trade ล่าสุด 5 รายการ:")
            for trade in self.trades[-5:]:
                result_emoji = "✅" if trade['pnl'] > 0 else "❌"
                print(f"   {result_emoji} {trade['time'].strftime('%m-%d %H:%M')} {trade['action']} ${trade['entry_price']:.2f} → ${trade['pnl']:+.2f}")

def main():
    backtest = GoldenTrendBacktest(initial_balance=10000)
    backtest.run_backtest()

if __name__ == "__main__":
    main()