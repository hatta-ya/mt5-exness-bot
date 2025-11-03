#!/usr/bin/env python3
"""
🚀 MT5 Live Trading Module
เชื่อมต่อกับ MetaTrader 5 เพื่อทำการซื้อขายจริง
"""

import MetaTrader5 as mt5
import pandas as pd
import time
from datetime import datetime, timedelta
from .config import *
from .strategy import golden_trend_system
from .utils.logger import get_logger

log = get_logger("mt5_trader")

class MT5Trader:
    def __init__(self):
        self.is_connected = False
        self.account_info = None
        self.positions = []
        self.orders = []
        # Flag to stop attempting orders when AutoTrading is disabled on MT5 terminal
        self.auto_trading_disabled = False
        # Internal flag to avoid repeating the same warning message
        self._auto_trading_warned = False
        # Separate counters
        self.failed_send_count = 0          # counts consecutive failed send attempts
        self.consecutive_trade_losses = 0   # reserved for real P/L-based loss counting
        # Auto-resume check
        self._last_auto_check = None
        
    def connect(self):
        """เชื่อมต่อกับ MT5"""
        try:
            # Initialize MT5
            if not mt5.initialize():
                log.error(f"Failed to initialize MT5: {mt5.last_error()}")
                return False
            
            # Login to account
            if not mt5.login(int(MT5_LOGIN), password=MT5_PASSWORD, server=MT5_SERVER):
                log.error(f"Failed to login: {mt5.last_error()}")
                mt5.shutdown()
                return False
            
            # Get account info
            self.account_info = mt5.account_info()
            if self.account_info is None:
                log.error("Failed to get account info")
                return False
            
            self.is_connected = True
            log.info(f"✅ Connected to MT5")
            log.info(f"📊 Account: {self.account_info.login}")
            log.info(f"💰 Balance: ${self.account_info.balance:.2f}")
            log.info(f"📈 Equity: ${self.account_info.equity:.2f}")
            log.info(f"🌐 Server: {self.account_info.server}")
            
            return True
            
        except Exception as e:
            log.error(f"Connection error: {e}")
            return False
    
    def disconnect(self):
        """ตัดการเชื่อมต่อ MT5"""
        if self.is_connected:
            mt5.shutdown()
            self.is_connected = False
            log.info("🔌 Disconnected from MT5")
    
    def get_current_data(self, symbol, timeframe, count=300):
        """ดึงข้อมูลราคาปัจจุบัน"""
        try:
            # Convert timeframe
            mt5_timeframe = getattr(mt5, f"TIMEFRAME_{timeframe}")
            rates = mt5.copy_rates_from_pos(symbol, mt5_timeframe, 0, count)
            
            if rates is None or len(rates) == 0:
                log.error(f"Failed to get rates for {symbol}")
                return None
            
            # Convert to DataFrame
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df = df[['time', 'open', 'high', 'low', 'close', 'tick_volume']].copy()
            df.rename(columns={'tick_volume': 'volume'}, inplace=True)
            
            return df
            
        except Exception as e:
            log.error(f"Error getting data: {e}")
            return None
    
    def get_symbol_info(self, symbol):
        """ดึงข้อมูล Symbol"""
        try:
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                log.error(f"Symbol {symbol} not found")
                return None
            
            return {
                'symbol': symbol_info.name,
                'bid': symbol_info.bid,
                'ask': symbol_info.ask,
                'spread': symbol_info.spread,
                'point': symbol_info.point,
                'digits': symbol_info.digits,
                'trade_mode': symbol_info.trade_mode,
                'min_lot': symbol_info.volume_min,
                'max_lot': symbol_info.volume_max,
                'lot_step': symbol_info.volume_step,
            }
            
        except Exception as e:
            log.error(f"Error getting symbol info: {e}")
            return None
    
    def calculate_lot_size(self, symbol, risk_percent, stop_loss_pips):
        """คำนวณขนาด lot ตาม Risk Management"""
        try:
            if not self.account_info:
                return 0.01
            
            account_balance = self.account_info.balance
            risk_amount = account_balance * (risk_percent / 100)
            
            symbol_info = self.get_symbol_info(symbol)
            if not symbol_info:
                return 0.01
            
            # Calculate value per pip
            if symbol == "XAUUSD":
                value_per_pip = 0.01  # $0.01 per pip per 0.01 lot
                lot_size = risk_amount / (stop_loss_pips * value_per_pip * 100)
            else:
                # For forex pairs
                pip_value = 10 * symbol_info['point']  # Standard lot pip value
                lot_size = risk_amount / (stop_loss_pips * pip_value)
            
            # Round to lot step
            lot_step = symbol_info['lot_step']
            lot_size = round(lot_size / lot_step) * lot_step
            
            # Apply limits
            lot_size = max(symbol_info['min_lot'], min(lot_size, symbol_info['max_lot']))
            lot_size = min(lot_size, 0.1)  # Safety limit
            
            log.info(f"💡 Calculated lot size: {lot_size} for risk {risk_percent}%")
            return lot_size
            
        except Exception as e:
            log.error(f"Error calculating lot size: {e}")
            return 0.01
    
    def send_order(self, action, symbol, lot_size, sl_price=None, tp_price=None, comment="Golden Trend Bot"):
        """ส่งออเดอร์"""
        try:
            # Check whether AutoTrading is allowed on the terminal
            try:
                terminal_info = mt5.terminal_info()
                # terminal_info.trade_allowed is False when AutoTrading is disabled by client
                if terminal_info is not None and hasattr(terminal_info, 'trade_allowed') and not terminal_info.trade_allowed:
                    # set flag so main loop can pause and avoid spamming attempts
                    self.auto_trading_disabled = True
                    if not self._auto_trading_warned:
                        log.error("Order blocked: AutoTrading disabled on the client terminal. Please enable AutoTrading in MT5.")
                        self._auto_trading_warned = True
                    return None
            except Exception:
                # If terminal_info not available, continue and let order_send report errors
                pass

            symbol_info = self.get_symbol_info(symbol)
            if not symbol_info:
                return None
            
            # Prepare request
            if action == "BUY":
                order_type = mt5.ORDER_TYPE_BUY
                price = symbol_info['ask']
            else:  # SELL
                order_type = mt5.ORDER_TYPE_SELL
                price = symbol_info['bid']
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": lot_size,
                "type": order_type,
                "price": price,
                "sl": sl_price,
                "tp": tp_price,
                "deviation": MAX_SLIPPAGE,
                "magic": MAGIC,
                "comment": comment,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            # Send order
            result = mt5.order_send(request)

            # If terminal blocks algo trading after we checked, handle retcode too
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                # Specific handling for AutoTrading disabled
                try:
                    if int(result.retcode) == 10027:
                        self.auto_trading_disabled = True
                        if not self._auto_trading_warned:
                            log.error("Order blocked: AutoTrading disabled on the client terminal. Please enable AutoTrading in MT5.")
                            self._auto_trading_warned = True
                except Exception:
                    pass

                log.error(f"Order failed: {result.retcode} - {getattr(result, 'comment', '')}")
                return None
            
            log.info(f"✅ Order sent: {action} {lot_size} lots {symbol} @ {price}")
            log.info(f"📋 Order ID: {result.order}")
            log.info(f"💰 SL: {sl_price}, TP: {tp_price}")
            
            return result
            
        except Exception as e:
            log.error(f"Error sending order: {e}")
            return None

    def send_notification(self, message: str):
        """Simple notification: log + optional file write (controlled by config)."""
        try:
            log.warning(f"NOTIFY: {message}")
            if NOTIFICATIONS_ENABLE:
                # ensure logs directory exists
                import os
                os.makedirs(os.path.dirname(NOTIFICATIONS_LOG_PATH), exist_ok=True)
                with open(NOTIFICATIONS_LOG_PATH, 'a', encoding='utf-8') as f:
                    f.write(f"{datetime.now().isoformat()} | {message}\n")
        except Exception as e:
            log.error(f"Failed to send notification: {e}")
    
    def get_positions(self):
        """ดึงรายการ Position ที่เปิดอยู่"""
        try:
            positions = mt5.positions_get(symbol=SYMBOL)
            if positions is None:
                log.debug("mt5.positions_get returned None")
                return []

            # Log raw positions for debug to detect stale/inconsistent state
            raw = []
            for pos in positions:
                try:
                    raw.append({
                        'ticket': pos.ticket,
                        'symbol': pos.symbol,
                        'magic': getattr(pos, 'magic', None),
                        'type': 'BUY' if pos.type == mt5.POSITION_TYPE_BUY else 'SELL',
                        'volume': pos.volume,
                        'price_open': pos.price_open,
                        'sl': pos.sl,
                        'tp': pos.tp,
                        'profit': pos.profit,
                        'time': datetime.fromtimestamp(pos.time),
                        'comment': pos.comment,
                    })
                except Exception:
                    # fallback minimal info
                    raw.append({'ticket': getattr(pos, 'ticket', None), 'symbol': getattr(pos, 'symbol', None)})

            log.debug(f"Raw mt5.positions_get for {SYMBOL}: {raw}")

            # Filter to positions created by this bot (by MAGIC)
            filtered = []
            for pos in positions:
                try:
                    if getattr(pos, 'magic', None) == MAGIC:
                        filtered.append({
                            'ticket': pos.ticket,
                            'symbol': pos.symbol,
                            'type': 'BUY' if pos.type == mt5.POSITION_TYPE_BUY else 'SELL',
                            'volume': pos.volume,
                            'price_open': pos.price_open,
                            'sl': pos.sl,
                            'tp': pos.tp,
                            'profit': pos.profit,
                            'time': datetime.fromtimestamp(pos.time),
                            'comment': pos.comment,
                        })
                except Exception:
                    continue

            log.debug(f"Filtered positions for MAGIC={MAGIC}: {filtered}")
            return filtered
            
        except Exception as e:
            log.error(f"Error getting positions: {e}")
            return []
    
    def close_position(self, ticket):
        """ปิด Position"""
        try:
            positions = mt5.positions_get(ticket=ticket)
            if not positions:
                log.error(f"Position {ticket} not found")
                return False
            
            position = positions[0]
            
            if position.type == mt5.POSITION_TYPE_BUY:
                order_type = mt5.ORDER_TYPE_SELL
                price = mt5.symbol_info_tick(position.symbol).bid
            else:
                order_type = mt5.ORDER_TYPE_BUY
                price = mt5.symbol_info_tick(position.symbol).ask
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": position.symbol,
                "volume": position.volume,
                "type": order_type,
                "position": ticket,
                "price": price,
                "deviation": MAX_SLIPPAGE,
                "magic": MAGIC,
                "comment": "Close by Golden Trend Bot",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            result = mt5.order_send(request)
            
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                log.error(f"Close failed: {result.retcode} - {result.comment}")
                return False
            
            log.info(f"✅ Position {ticket} closed")
            return True
            
        except Exception as e:
            log.error(f"Error closing position: {e}")
            return False

    def close_position_with_retry(self, ticket, attempts: int = AGGREGATE_CLOSE_RETRY_ATTEMPTS, backoff: float = AGGREGATE_CLOSE_RETRY_BACKOFF_SECONDS):
        """Try to close a position with retries and exponential backoff.

        Returns True if closed, False otherwise.
        """
        if not ticket:
            log.error(f"close_position_with_retry called with empty ticket: {ticket}")
            return False

        for attempt in range(1, attempts + 1):
            try:
                log.info(f"Attempt {attempt}/{attempts} to close position {ticket}")
                ok = self.close_position(ticket)
                if ok:
                    log.info(f"Position {ticket} closed on attempt {attempt}")
                    return True
                else:
                    log.warning(f"Close attempt {attempt} for position {ticket} failed")
            except Exception as e:
                log.error(f"Exception on close attempt {attempt} for {ticket}: {e}")

            if attempt < attempts:
                sleep_seconds = backoff * (2 ** (attempt - 1))
                log.info(f"Waiting {sleep_seconds}s before next close attempt for {ticket}")
                time.sleep(sleep_seconds)

        log.error(f"Failed to close position {ticket} after {attempts} attempts")
        return False
    
    def run_live_trading(self):
        """รันการซื้อขายจริง"""
        print(f"""
╔══════════════════════════════════════════════════════════════╗
║                        MT5 Live Trading                      ║
║                                                              ║
║                    {SYMBOL} Golden Trend System              ║
╚══════════════════════════════════════════════════════════════╝
📊 Symbol: {SYMBOL}
📅 Timeframe: {TIMEFRAME}
💰 Lot Size: {LOT}
🛡️ Risk per Trade: {RISK_PERCENT}%
🎯 Max Positions: {MAX_POSITIONS}
        """)
        
        if not self.connect():
            print("❌ ไม่สามารถเชื่อมต่อ MT5 ได้")
            return

        consecutive_losses = 0
        last_signal_time = None  # store datetime of last sent order to throttle repeats

        try:
            print("🔄 เริ่มการซื้อขายจริง... (กด Ctrl+C เพื่อหยุด)")
            
            while True:
                # ดึงข้อมูลปัจจุบัน
                df = self.get_current_data(SYMBOL, TIMEFRAME)
                if df is None:
                    # if we couldn't fetch data, try again quickly
                    time.sleep(3)
                    continue
                
                current_time = df.iloc[-1]['time']
                current_price = df.iloc[-1]['close']
                
                # ตรวจสอบไม่ให้ส่งสัญญาณซ้ำบ่อยเกินไป (throttle ด้วยเวลา)
                # last_signal_time ถูกเก็บเป็น datetime ของเวลาที่ส่งออเดอร์ล่าสุด
                if last_signal_time and datetime.now() <= last_signal_time + timedelta(seconds=3):
                    # ถ้าเพิ่งส่งออเดอร์ไปภายใน 3 วินาที ให้รอและข้ามการประมวลผลรอบนี้
                    time.sleep(3)
                    continue
                
                # Auto-resume: if AutoTrading is disabled, re-check terminal_info every 10s
                if self.auto_trading_disabled:
                    now = datetime.now()
                    if not self._last_auto_check or (now - self._last_auto_check).total_seconds() >= 10:
                        self._last_auto_check = now
                        try:
                            ti = mt5.terminal_info()
                            if ti is not None and hasattr(ti, 'trade_allowed') and ti.trade_allowed:
                                # re-enabled
                                self.auto_trading_disabled = False
                                self._auto_trading_warned = False
                                self.failed_send_count = 0
                                log.info("AutoTrading was re-enabled on terminal — resuming order attempts.")
                                # notify
                                self.send_notification("AutoTrading re-enabled — bot resumed sending orders.")
                                # continue to main loop (do not sleep further)
                            else:
                                if not self._auto_trading_warned:
                                    log.error("AutoTrading disabled - pausing order attempts until enabled in MT5.")
                                    self._auto_trading_warned = True
                        except Exception:
                            # couldn't fetch terminal info — just wait
                            pass
                    # wait a bit before next main loop iteration to avoid busy loop
                    time.sleep(10)
                    continue

                # ตรวจสอบ failed send attempts (separate counter) และหยุดชั่วคราวถ้าครบ limit
                if self.failed_send_count >= MAX_CONSECUTIVE_LOSSES:
                    print(f"⚠️ หยุดการพยายามส่งคำสั่งชั่วคราว - ล้มเหลวติดต่อกัน {self.failed_send_count} ครั้ง")
                    # แจ้งเตือนและรอเป็นเวลานานขึ้น
                    self.send_notification(f"Bot paused: {self.failed_send_count} consecutive send failures.")
                    time.sleep(3600)
                    self.failed_send_count = 0
                    continue
                
                # ตรวจสอบจำนวน Position ที่เปิดอยู่
                positions = self.get_positions()
                # If aggregate close feature enabled, compute combined profit and close all if threshold reached
                try:
                    if AGGREGATE_CLOSE_ENABLED and positions:
                        total_profit = sum([p.get('profit', 0.0) for p in positions])
                        log.debug(f"Aggregate profit for open positions: {total_profit}")
                        if total_profit >= AGGREGATE_CLOSE_PROFIT_USD:
                            log.info(f"Aggregate profit ${total_profit:.2f} >= ${AGGREGATE_CLOSE_PROFIT_USD:.2f}. Closing all positions.")
                            # attempt to close all filtered positions
                            for pos in positions:
                                try:
                                    ticket = pos.get('ticket')
                                    if ticket:
                                        closed = self.close_position(ticket)
                                        if closed:
                                            log.info(f"Closed position {ticket} successfully")
                                        else:
                                            log.error(f"Failed to close position {ticket}")
                                except Exception as e:
                                    log.error(f"Error closing position {pos}: {e}")
                            # after attempting to close, reset counters and skip placing new orders this loop
                            self.failed_send_count = 0
                            time.sleep(3)
                            continue
                except Exception as e:
                    log.error(f"Error computing aggregate profit: {e}")
                # Sanity check vs terminal total positions to handle inconsistent state
                try:
                    total_open = mt5.positions_total()
                except Exception:
                    total_open = None

                if total_open == 0 and len(positions) > 0:
                    # Terminal reports zero open positions; treat as cleared (avoid blocking)
                    log.warning(f"mt5.positions_total()==0 but get_positions returned {len(positions)}; treating as 0 and continuing")
                    positions = []

                if len(positions) >= MAX_POSITIONS:
                    print(f"⚠️ มี Position เปิดอยู่ {len(positions)}/{MAX_POSITIONS} แล้ว")
                    time.sleep(60)
                    continue
                
                # Force a BUY 0.01 every run (ignore strategy result)
                action = 'BUY'
                lot_size = 0.01

                # คำนวณ SL และ TP ตามค่า SL_PIPS/TP_PIPS เดิม (สามารถปรับเป็น None ถ้าไม่ต้องการ)
                sl_price = current_price - (SL_PIPS * POINT_SIZE)
                tp_price = current_price + (TP_PIPS * POINT_SIZE)

                print(f"\n🎯 Forced Signal: {action} @ {current_price:.2f} | Lot: {lot_size}")

                order_result = self.send_order(
                    action=action,
                    symbol=SYMBOL,
                    lot_size=lot_size,
                    sl_price=sl_price,
                    tp_price=tp_price
                )

                if order_result:
                    last_signal_time = datetime.now()
                    print(f"✅ ส่งออเดอร์สำเร็จ: {action} {lot_size} lots")
                    # reset failed send counter on success
                    self.failed_send_count = 0
                else:
                    # Don't count failed send attempts due to AutoTrading being disabled as failures
                    if self.auto_trading_disabled:
                        print("❌ ส่งออเดอร์ไม่สำเร็จ (AutoTrading ปิดอยู่) — จะไม่ถูกนับเป็นการขาดทุน")
                    else:
                        self.failed_send_count += 1
                        print(f"❌ ส่งออเดอร์ไม่สำเร็จ")
                
                # แสดงสถานะปัจจุบัน
                print(f"⏰ {current_time.strftime('%Y-%m-%d %H:%M:%S')} | Price: {current_price:.2f} | Positions: {len(positions)} | Balance: ${self.account_info.balance:.2f}")
                
                # รอ 3 วินาที ก่อนรอบถัดไป (ตามคำขอให้รันทุก 3 วินาที)
                time.sleep(3)
                
        except KeyboardInterrupt:
            print("\n🛑 หยุดการซื้อขายโดยผู้ใช้")
        except Exception as e:
            log.error(f"Live trading error: {e}")
            print(f"❌ เกิดข้อผิดพลาด: {e}")
        finally:
            self.disconnect()

def main():
    """เริ่มการซื้อขายจริง"""
    trader = MT5Trader()
    
    # ตรวจสอบการตั้งค่า
    if not MT5_LOGIN or not MT5_PASSWORD or not MT5_SERVER:
        print("❌ กรุณาตั้งค่า MT5_LOGIN, MT5_PASSWORD, MT5_SERVER ใน .env file")
        return
    
    # เริ่มซื้อขายจริง
    trader.run_live_trading()

if __name__ == "__main__":
    main()