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
from .config import SYMBOL, RISK_PERCENT, BACKTEST_DAYS, POINT_SIZE, VALUE_PER_PIP_PER_LOT, INSTRUMENT_TYPE
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
        # Backtest control
        self.max_hold_bars = 240  # safety horizon to force exit if TP/SL not hit
        # cooldown to avoid re-entering same direction too quickly (hours for hourly bars)
        self.cooldown_bars = 6
        # track last entry bar index per side
        self._last_entry_idx = {'BUY': -9999, 'SELL': -9999}
        # parameterizable slippage ranges (entry, exit)
        self.entry_slippage_range = (-0.1, 0.1)
        self.exit_slippage_range = (-0.1, 0.1)
        # strategy parameter defaults (can be adjusted for sweeps)
        self.macd_hist_threshold = 0.5
        self.adx_threshold = 25.0
        self.rsi_buy_max = 65.0
        self.rsi_sell_min = 35.0
        self.sl_multiplier = 1.5
        self.tp_multiplier = 2.5
        # optional pullback requirement to ema20
        self.require_pullback_to_ema20 = False
        # lot cap
        self.max_lot_size = 0.05
        
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
        """Record a trade given entry and explicit exit info.

        The caller should provide an exit price/time/reason via the `reason` parameter
        as a tuple: (exit_price, exit_time, reason_str). This keeps exit simulation
        logic in `run_backtest()` where forward bars are available.
        """
        multiplier = 1 if action == "BUY" else -1

        commission_per_lot = 7.0  # $7 per lot per side
        commission = commission_per_lot * lot_size * 2

        # Parse reason for exit data if provided as tuple
        exit_price = None
        exit_time = None
        reason_str = 'Golden Trend Signal'
        if isinstance(reason, tuple) and len(reason) >= 2:
            exit_price = reason[0]
            exit_time = reason[1]
            reason_str = reason[2] if len(reason) > 2 else reason_str
        elif isinstance(reason, (int, float)):
            exit_price = reason
        elif isinstance(reason, str):
            reason_str = reason

        if exit_price is None:
            # Fallback to tp_price if exit not provided
            exit_price = tp_price

        # Compute P&L using instrument point sizing
        # pips/points moved = (exit - entry) / point_size
        pips = (exit_price - entry_price) / POINT_SIZE
        pnl = (pips * VALUE_PER_PIP_PER_LOT * lot_size * multiplier) - commission

        # Update balance and bookkeeping
        self.balance += pnl

        if pnl > 0:
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
            self.max_consecutive_losses = max(self.max_consecutive_losses, self.consecutive_losses)

        # Update peak balance and drawdown
        self.peak_balance = max(self.peak_balance, self.balance)
        dd = (self.peak_balance - self.balance) / self.peak_balance * 100.0 if self.peak_balance > 0 else 0.0
        self.current_drawdown = dd
        self.max_drawdown = max(self.max_drawdown, self.current_drawdown)

        # record balance history
        self.balance_history.append(self.balance)

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
            'slippage': None,
            'drawdown': self.current_drawdown,
            'reason': reason_str,
            'exit_time': exit_time,
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
║               Golden Trend System Backtest                   ║
║                                                              ║
║                   {symbol_display:^46}                       ║
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
            
            # วิเคราะห์ Golden Trend System (pass tunable params)
            result = golden_trend_system(
                current_data,
                risk_pct=RISK_PERCENT,
                account_balance=self.balance,
                macd_hist_threshold=self.macd_hist_threshold,
                adx_threshold=self.adx_threshold,
                rsi_buy_max=self.rsi_buy_max,
                rsi_sell_min=self.rsi_sell_min,
                sl_multiplier=self.sl_multiplier,
                tp_multiplier=self.tp_multiplier,
                require_pullback_to_ema20=self.require_pullback_to_ema20,
                point_size=POINT_SIZE,
                value_per_point_per_lot=VALUE_PER_PIP_PER_LOT,
                min_lot=0.01,
                max_lot=self.max_lot_size,
            )
            
            if result['signal'] in ['BUY', 'SELL']:
                signals += 1
                
                # ตรวจสอบขนาด lot ไม่เกิน 0.05
                max_lot_size = 0.05
                lot_size = min(result.get('lot_size', 0.01), max_lot_size)

                # Use strategy-provided SL/TP if available, else fallback to pip values
                if 'sl_price' in result and result.get('sl_price') is not None:
                    sl_price = result['sl_price']
                else:
                    sl_pips = 70  # Stop Loss (fallback)
                    sl_price = current_price - (sl_pips * POINT_SIZE) if result['signal'] == 'BUY' else current_price + (sl_pips * POINT_SIZE)

                if 'tp_price' in result and result.get('tp_price') is not None:
                    tp_price = result['tp_price']
                else:
                    tp_pips = 210  # Take Profit (fallback)
                    tp_price = current_price + (tp_pips * POINT_SIZE) if result['signal'] == 'BUY' else current_price - (tp_pips * POINT_SIZE)

                # Simulate entry price with entry slippage/spread
                spread = 0.0
                # entry slippage from configurable range
                entry_slippage = np.random.uniform(self.entry_slippage_range[0], self.entry_slippage_range[1])
                if result.get('entry_price') is not None:
                    raw_entry = result['entry_price']
                else:
                    raw_entry = current_price

                if result['signal'] == 'BUY':
                    entry_price = raw_entry + spread / 2.0 + entry_slippage
                else:
                    entry_price = raw_entry - spread / 2.0 + entry_slippage

                # Now scan forward to find TP/SL hit
                exit_found = False
                exit_price = None
                exit_time = None
                exit_reason = None

                # enforce cooldown: avoid re-entering same direction if last entry was recent
                if i - self._last_entry_idx.get(result['signal'], -9999) < self.cooldown_bars:
                    # skip entering due to cooldown
                    continue

                for j in range(i + 1, min(len(df), i + 1 + self.max_hold_bars)):
                    bar = df.iloc[j]
                    high_j = bar['high']
                    low_j = bar['low']
                    time_j = bar['time']

                    if result['signal'] == 'BUY':
                        tp_hit = high_j >= tp_price
                        sl_hit = low_j <= sl_price
                        if tp_hit and sl_hit:
                            # Both hit same bar: conservative -> assume SL hit first
                            exit_price_raw = sl_price
                            exit_reason = 'SL Hit (intrabar tie - conservative)'
                            exit_found = True
                        elif tp_hit:
                            exit_price_raw = tp_price
                            exit_reason = 'TP Hit'
                            exit_found = True
                        elif sl_hit:
                            exit_price_raw = sl_price
                            exit_reason = 'SL Hit'
                            exit_found = True
                    else:  # SELL
                        tp_hit = low_j <= tp_price
                        sl_hit = high_j >= sl_price
                        if tp_hit and sl_hit:
                            exit_price_raw = sl_price
                            exit_reason = 'SL Hit (intrabar tie - conservative)'
                            exit_found = True
                        elif tp_hit:
                            exit_price_raw = tp_price
                            exit_reason = 'TP Hit'
                            exit_found = True
                        elif sl_hit:
                            exit_price_raw = sl_price
                            exit_reason = 'SL Hit'
                            exit_found = True

                    if exit_found:
                        # apply exit slippage
                        exit_slippage = np.random.uniform(self.exit_slippage_range[0], self.exit_slippage_range[1])
                        if result['signal'] == 'BUY':
                            # BUY exit: exit_price_raw minus spread + slippage
                            exit_price = exit_price_raw - spread / 2.0 + exit_slippage
                        else:
                            exit_price = exit_price_raw + spread / 2.0 + exit_slippage

                        exit_time = time_j
                        break

                # If no TP/SL hit within horizon, exit at next bar close (or last considered bar)
                if not exit_found:
                    j = min(len(df) - 1, i + self.max_hold_bars)
                    exit_price_raw = df.iloc[j]['close']
                    exit_time = df.iloc[j]['time']
                    exit_slippage = np.random.uniform(self.exit_slippage_range[0], self.exit_slippage_range[1])
                    if result['signal'] == 'BUY':
                        exit_price = exit_price_raw - spread / 2.0 + exit_slippage
                    else:
                        exit_price = exit_price_raw + spread / 2.0 + exit_slippage
                    exit_reason = 'Timeout/Close'

                # Execute trade with determined exit_price and reason
                trade = self.execute_trade(
                    action=result['signal'],
                    entry_price=entry_price,
                    sl_price=sl_price,
                    tp_price=tp_price,
                    lot_size=lot_size,
                    entry_time=current_time,
                    reason=(exit_price, exit_time, exit_reason),
                )
                # record last entry index for cooldown
                self._last_entry_idx[result['signal']] = i

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
