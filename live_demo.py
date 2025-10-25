#!/usr/bin/env python3
"""
Live Demo Trading Bot สำหรับ XAUUSD
จำลองการเทรดแบบ real-time
"""
import time
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from config import SYMBOL, TIMEFRAME, LOT, SL_PIPS, TP_PIPS, DAILY_PROFIT_TARGET, DAILY_DRAWDOWN_LIMIT, MAX_OPEN_TRADES
from strategy import ema_strategy
from utils.logger import get_logger
import signal
import sys

log = get_logger("live_demo")

class LiveDemoTrader:
    def __init__(self, initial_balance=10000):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.daily_start_balance = initial_balance
        self.equity = initial_balance
        self.open_positions = []
        self.closed_trades = []
        self.running = True
        self.last_signal_time = None
        
        # Stats
        self.total_trades = 0
        self.winning_trades = 0
        self.daily_pnl = 0.0
        
        print(f"""
🚀 Live Demo Trading Bot เริ่มทำงาน
💰 Initial Balance: ${self.initial_balance:,.2f}
📊 Symbol: {SYMBOL}
⏰ Timeframe: {TIMEFRAME}
🎯 Daily Target: +{DAILY_PROFIT_TARGET}% | Limit: -{DAILY_DRAWDOWN_LIMIT}%
        """)
    
    def get_live_data(self, days_back=60):
        """ดึงข้อมูลล่าสุด"""
        try:
            if SYMBOL == "XAUUSD":
                yahoo_symbol = "GC=F"
            elif SYMBOL == "EURUSD":
                yahoo_symbol = "EURUSD=X"
            else:
                yahoo_symbol = f"{SYMBOL}=X"
            
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            # ดึงข้อมูล daily
            data = yf.download(yahoo_symbol, start=start_date, end=end_date, interval="1d")
            
            if data.empty:
                return None
            
            df = pd.DataFrame()
            df['time'] = data.index
            df['open'] = data['Open'].values
            df['high'] = data['High'].values
            df['low'] = data['Low'].values
            df['close'] = data['Close'].values
            df['volume'] = data['Volume'].values if 'Volume' in data.columns else [0] * len(data)
            
            return df.dropna().reset_index(drop=True)
            
        except Exception as e:
            log.error(f"Error fetching live data: {e}")
            return None
    
    def calculate_position_value(self, price):
        """คำนวณมูลค่า position"""
        if SYMBOL == "XAUUSD":
            return LOT * 100 * price  # 1 lot gold = 100 oz
        else:
            return LOT * 100000  # 1 lot forex = 100,000 units
    
    def open_position(self, action, entry_price):
        """เปิด position ใหม่"""
        if len(self.open_positions) >= MAX_OPEN_TRADES:
            log.warning("Reached max open trades limit")
            return False
        
        # คำนวณ SL และ TP
        if SYMBOL == "XAUUSD":
            pip_value = 0.1  # Gold: 1 pip = $0.1
        else:
            pip_value = 0.0001  # Forex: 1 pip = 0.0001
        
        if action == "BUY":
            sl_price = entry_price - (SL_PIPS * pip_value)
            tp_price = entry_price + (TP_PIPS * pip_value)
        else:  # SELL
            sl_price = entry_price + (SL_PIPS * pip_value)
            tp_price = entry_price - (TP_PIPS * pip_value)
        
        position = {
            'id': len(self.closed_trades) + len(self.open_positions) + 1,
            'symbol': SYMBOL,
            'action': action,
            'lot': LOT,
            'entry_price': entry_price,
            'sl_price': sl_price,
            'tp_price': tp_price,
            'entry_time': datetime.now(),
            'unrealized_pnl': 0.0
        }
        
        self.open_positions.append(position)
        
        log.info(f"""
🎯 NEW {action} POSITION OPENED
   ID: #{position['id']}
   Entry: ${entry_price:.2f}
   SL: ${sl_price:.2f} ({SL_PIPS} pips)
   TP: ${tp_price:.2f} ({TP_PIPS} pips)
   Lot: {LOT}
        """)
        
        return True
    
    def close_position(self, position, exit_price, exit_reason):
        """ปิด position"""
        if SYMBOL == "XAUUSD":
            # Gold: P&L = (Exit - Entry) * Lot * 100 * Direction
            if position['action'] == "BUY":
                pnl = (exit_price - position['entry_price']) * LOT * 100
            else:  # SELL
                pnl = (position['entry_price'] - exit_price) * LOT * 100
        else:
            # Forex: P&L = (Exit - Entry) * Position Size * Direction / Entry Price
            position_size = LOT * 100000
            if position['action'] == "BUY":
                pnl = (exit_price - position['entry_price']) * position_size / position['entry_price']
            else:  # SELL
                pnl = (position['entry_price'] - exit_price) * position_size / position['entry_price']
        
        # อัปเดต balance
        self.balance += pnl
        self.equity = self.balance
        self.daily_pnl += pnl
        
        # สถิติ
        self.total_trades += 1
        if pnl > 0:
            self.winning_trades += 1
        
        # บันทึก trade
        closed_trade = position.copy()
        closed_trade.update({
            'exit_price': exit_price,
            'exit_time': datetime.now(),
            'exit_reason': exit_reason,
            'pnl': pnl
        })
        
        self.closed_trades.append(closed_trade)
        
        # ลบจาก open positions
        self.open_positions.remove(position)
        
        pnl_str = f"+${pnl:.2f}" if pnl > 0 else f"${pnl:.2f}"
        emoji = "🟢" if pnl > 0 else "🔴"
        
        log.info(f"""
{emoji} POSITION CLOSED - {exit_reason}
   ID: #{closed_trade['id']} {position['action']}
   Entry: ${position['entry_price']:.2f} → Exit: ${exit_price:.2f}
   P&L: {pnl_str}
   Balance: ${self.balance:.2f}
        """)
        
        return closed_trade
    
    def update_positions(self, current_price):
        """อัปเดตและตรวจสอบ positions"""
        positions_to_close = []
        
        for pos in self.open_positions[:]:  # copy list to avoid modification during iteration
            action = pos['action']
            
            # ตรวจสอบ SL/TP
            if action == "BUY":
                if current_price <= pos['sl_price']:
                    positions_to_close.append((pos, current_price, "STOP LOSS"))
                elif current_price >= pos['tp_price']:
                    positions_to_close.append((pos, current_price, "TAKE PROFIT"))
                else:
                    # อัปเดต unrealized P&L
                    if SYMBOL == "XAUUSD":
                        pos['unrealized_pnl'] = (current_price - pos['entry_price']) * LOT * 100
                    else:
                        position_size = LOT * 100000
                        pos['unrealized_pnl'] = (current_price - pos['entry_price']) * position_size / pos['entry_price']
            
            else:  # SELL
                if current_price >= pos['sl_price']:
                    positions_to_close.append((pos, current_price, "STOP LOSS"))
                elif current_price <= pos['tp_price']:
                    positions_to_close.append((pos, current_price, "TAKE PROFIT"))
                else:
                    # อัปเดต unrealized P&L
                    if SYMBOL == "XAUUSD":
                        pos['unrealized_pnl'] = (pos['entry_price'] - current_price) * LOT * 100
                    else:
                        position_size = LOT * 100000
                        pos['unrealized_pnl'] = (pos['entry_price'] - current_price) * position_size / pos['entry_price']
        
        # ปิด positions ที่โดน SL/TP
        for pos, price, reason in positions_to_close:
            self.close_position(pos, price, reason)
    
    def check_daily_limits(self):
        """ตรวจสอบขีดจำกัดรายวัน"""
        daily_pnl_pct = (self.daily_pnl / self.daily_start_balance) * 100
        
        # ตรวจสอบเป้าหมายกำไร
        if daily_pnl_pct >= DAILY_PROFIT_TARGET:
            log.info(f"🎯 Daily profit target reached: +{daily_pnl_pct:.2f}%")
            return "PROFIT_TARGET"
        
        # ตรวจสอบขีดจำกัดขาดทุน
        if daily_pnl_pct <= -DAILY_DRAWDOWN_LIMIT:
            log.warning(f"🚫 Daily drawdown limit reached: {daily_pnl_pct:.2f}%")
            return "DRAWDOWN_LIMIT"
        
        return "OK"
    
    def show_status(self, current_price, signal):
        """แสดงสถานะปัจจุบัน"""
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0
        daily_pnl_pct = (self.daily_pnl / self.daily_start_balance) * 100
        
        # คำนวณ unrealized P&L
        total_unrealized = sum(pos['unrealized_pnl'] for pos in self.open_positions)
        
        print(f"""
{'='*60}
⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 💰 {SYMBOL}: ${current_price:.2f}
📊 Signal: {signal} | Open Positions: {len(self.open_positions)}
💰 Balance: ${self.balance:.2f} | Daily P&L: {self.daily_pnl:+.2f} ({daily_pnl_pct:+.2f}%)
📈 Unrealized: {total_unrealized:+.2f} | Equity: ${self.balance + total_unrealized:.2f}
🎯 Trades: {self.total_trades} | Win Rate: {win_rate:.1f}%
{'='*60}
        """)
        
        # แสดง open positions
        if self.open_positions:
            print("📋 Open Positions:")
            for pos in self.open_positions:
                pnl_str = f"{pos['unrealized_pnl']:+.2f}"
                print(f"   #{pos['id']} {pos['action']} | Entry: ${pos['entry_price']:.2f} | P&L: {pnl_str}")
    
    def run(self):
        """รันเทรดเดโม"""
        log.info("🚀 Starting Live Demo Trading...")
        
        # Setup signal handler สำหรับ Ctrl+C
        def signal_handler(sig, frame):
            print("\n🛑 Stopping trading bot...")
            self.running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        
        try:
            while self.running:
                # ดึงข้อมูลล่าสุด
                df = self.get_live_data()
                
                if df is None or len(df) < 30:
                    log.warning("Insufficient data, retrying...")
                    time.sleep(30)
                    continue
                
                current_price = df.iloc[-1]['close']
                
                # อัปเดต positions
                self.update_positions(current_price)
                
                # ตรวจสอบขีดจำกัดรายวัน
                limit_status = self.check_daily_limits()
                if limit_status != "OK":
                    log.info(f"Trading stopped due to: {limit_status}")
                    break
                
                # หา signal
                signal_result = ema_strategy(df)
                current_time = datetime.now()
                
                # เปิด position ใหม่ (ถ้ามี signal และไม่ได้เปิดไปแล้วในช่วงเวลาใกล้เคียง)
                if signal_result in ["BUY", "SELL"]:
                    # ป้องกันการเปิด position ซ้ำในช่วงเวลาใกล้เคียงกัน
                    if (self.last_signal_time is None or 
                        (current_time - self.last_signal_time).total_seconds() > 300):  # 5 minutes for demo
                        
                        if self.open_position(signal_result, current_price):
                            self.last_signal_time = current_time
                
                # แสดงสถานะ
                self.show_status(current_price, signal_result)
                
                # รอ 10 วินาที ก่อนอัปเดตครั้งถัดไป (เร็วขึ้นสำหรับ demo)
                time.sleep(10)
                
        except KeyboardInterrupt:
            print("\n🛑 Trading stopped by user")
        except Exception as e:
            log.error(f"Error in trading loop: {e}")
        finally:
            self.stop_trading()
    
    def stop_trading(self):
        """หยุดการเทรดและแสดงสรุป"""
        print(f"\n🏁 Trading Session Ended - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # ปิด positions ที่เหลือ
        if self.open_positions:
            print("🔄 Closing remaining positions...")
            df = self.get_live_data()
            if df is not None:
                current_price = df.iloc[-1]['close']
                for pos in self.open_positions[:]:
                    self.close_position(pos, current_price, "SESSION_END")
        
        # แสดงสรุปผลลัพธ์
        self.show_final_summary()
    
    def show_final_summary(self):
        """แสดงสรุปผลลัพธ์สุดท้าย"""
        total_pnl = self.balance - self.initial_balance
        roi = (total_pnl / self.initial_balance) * 100
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0
        
        print(f"""
{'='*60}
📊 TRADING SESSION SUMMARY
{'='*60}
💰 Initial Balance:    ${self.initial_balance:,.2f}
💰 Final Balance:      ${self.balance:,.2f}
📈 Total P&L:          {total_pnl:+,.2f}
📊 ROI:               {roi:+.2f}%
🎯 Total Trades:       {self.total_trades}
✅ Winning Trades:     {self.winning_trades} ({win_rate:.1f}%)
❌ Losing Trades:      {self.total_trades - self.winning_trades}
{'='*60}
        """)
        
        if self.closed_trades:
            print("🔄 Recent Trades:")
            for trade in self.closed_trades[-5:]:
                pnl_str = f"+${trade['pnl']:.2f}" if trade['pnl'] > 0 else f"${trade['pnl']:.2f}"
                print(f"   #{trade['id']} {trade['action']} | {trade['exit_reason']} | P&L: {pnl_str}")

def main():
    """รันเทรดเดโมหลัก"""
    trader = LiveDemoTrader(initial_balance=10000)
    trader.run()

if __name__ == "__main__":
    main()