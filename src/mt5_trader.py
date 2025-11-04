#!/usr/bin/env python3
"""
🚀 MT5 Live Trading Module
เชื่อมต่อกับ MetaTrader 5 เพื่อทำการซื้อขายจริง
"""

import MetaTrader5 as mt5
import pandas as pd
import time
import os
from datetime import datetime, timedelta
from .config import *
from .strategy import golden_trend_system, calculate_indicators
from .utils.logger import get_logger

log = get_logger("mt5_trader")

class MT5Trader:
    def __init__(self):
        self.is_connected = False
        self.account_info = None
        self.positions = []
        self.orders = []
        # history of executed orders/trades for logging similar to backtest
        self.trade_history = []
        self.order_count = 0
        # Flag to stop attempting orders when AutoTrading is disabled on MT5 terminal
        self.auto_trading_disabled = False
        # Internal flag to avoid repeating the same warning message
        self._auto_trading_warned = False
        # Separate counters
        self.failed_send_count = 0          # counts consecutive failed send attempts
        self.consecutive_trade_losses = 0   # reserved for real P/L-based loss counting
        # Auto-resume check
        self._last_auto_check = None
        # throttle for logging repeated "no signal" messages (seconds)
        try:
            self.no_signal_log_throttle = int(os.getenv('NO_SIGNAL_LOG_THROTTLE_SECONDS', '30'))
        except Exception:
            self.no_signal_log_throttle = 30
        self._last_no_signal_log_time = None
        # debug flag to enable detailed M5 indicators logging
        self.debug_m5 = os.getenv('DEBUG_M5_LOG', 'false').lower() in ('1', 'true', 'yes')
        # sculpt mode cooldown
        self._last_sculpt_time = None
        # trailing state per ticket: store last trail price used
        self._trailing_state = {}

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
            # Record trade in history and emit a single-line backtest-style log
            try:
                self.order_count += 1
                trade_no = self.order_count
                trade_entry = {
                    'no': trade_no,
                    'action': action,
                    'entry_price': price,
                    'lot_size': lot_size,
                    'sl_price': sl_price,
                    'tp_price': tp_price,
                    'order_id': getattr(result, 'order', None),
                    'time': datetime.now(),
                }
                self.trade_history.append(trade_entry)
                # single-line summary similar to golden_backtest
                log.info(f"#{trade_no:04d} 🎯 {action} @ ${price:.2f} | Lots: {lot_size} | OrderID: {trade_entry['order_id']} | SL: {sl_price} | TP: {tp_price}")
            except Exception:
                pass
            
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
            # Update account info
            try:
                self.account_info = mt5.account_info()
            except Exception:
                pass

            # Try to report profit if available
            try:
                profit = getattr(position, 'profit', None)
            except Exception:
                profit = None

            # single-line summary similar to backtest
            try:
                self.order_count += 1
                close_no = self.order_count
                balance_str = f"${self.account_info.balance:.2f}" if self.account_info else "N/A"
                log.info(f"#{close_no:04d} 🔒 Close ticket {ticket} | P&L: ${profit:.2f} | Balance: {balance_str} | Reason: Close by Golden Trend Bot")
            except Exception:
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
                # --- Manage open positions: breakeven and ATR-based trailing (applies to sculpt or normal modes) ---
                try:
                    for pos in positions:
                        try:
                            ticket = pos.get('ticket')
                            symbol = pos.get('symbol')
                            vol = pos.get('volume')
                            entry_price = pos.get('price_open')
                            cur_sl = pos.get('sl')
                            cur_tp = pos.get('tp')
                            pos_type = pos.get('type')
                            profit_usd = pos.get('profit', 0.0)

                            # get current price
                            tick = mt5.symbol_info_tick(symbol)
                            if tick is None:
                                continue
                            current_price = tick.bid if pos_type == 'BUY' else tick.ask

                            # get ATR from M1
                            df_m1_pos = self.get_current_data(symbol, 'M1', count=100)
                            if df_m1_pos is None:
                                continue
                            inds_pos = calculate_indicators(df_m1_pos.copy()).iloc[-1]
                            atr = inds_pos.get('atr', 0.0) or 0.0
                            if atr < SCULPT_MIN_ATR:
                                continue

                            # compute risk in USD using sl distance
                            if cur_sl is None or cur_sl == 0:
                                continue
                            sl_points = abs(entry_price - cur_sl) / POINT_SIZE if POINT_SIZE > 0 else 0
                            risk_usd = sl_points * VALUE_PER_PIP_PER_LOT * vol

                            # breakeven
                            if risk_usd > 0 and profit_usd >= (SCULPT_BREAKEVEN_R_MULT * risk_usd):
                                # move SL to entry_price if not already
                                if abs(cur_sl - entry_price) > 1e-9:
                                    try:
                                        req = {
                                            'action': mt5.TRADE_ACTION_SLTP,
                                            'position': int(ticket),
                                            'sl': float(entry_price),
                                            'tp': float(cur_tp) if cur_tp else 0.0,
                                        }
                                        res = mt5.order_send(req)
                                        if getattr(res, 'retcode', None) == mt5.TRADE_RETCODE_DONE:
                                            log.info(f"Breakeven set for ticket {ticket} at {entry_price}")
                                            # update trailing baseline
                                            self._trailing_state[ticket] = entry_price
                                        else:
                                            log.debug(f"Breakeven modify failed for {ticket}: {getattr(res,'retcode', None)}")
                                    except Exception as e:
                                        log.error(f"Error setting breakeven for {ticket}: {e}")

                            # ATR-based trailing: move SL in ATR steps
                            try:
                                step = SCULPT_TRAILING_ATR_STEP_MULT * atr
                                last_base = self._trailing_state.get(ticket, entry_price)
                                if pos_type == 'BUY':
                                    if (current_price - last_base) >= step:
                                        new_sl = max(cur_sl, current_price - step)
                                        if new_sl > cur_sl:
                                            req = {
                                                'action': mt5.TRADE_ACTION_SLTP,
                                                'position': int(ticket),
                                                'sl': float(new_sl),
                                                'tp': float(cur_tp) if cur_tp else 0.0,
                                            }
                                            res = mt5.order_send(req)
                                            if getattr(res, 'retcode', None) == mt5.TRADE_RETCODE_DONE:
                                                log.info(f"Trailing SL updated for ticket {ticket} -> {new_sl}")
                                                self._trailing_state[ticket] = current_price
                                else:
                                    # SELL
                                    if (last_base - current_price) >= step:
                                        new_sl = min(cur_sl, current_price + step) if cur_sl else (current_price + step)
                                        if cur_sl is None or new_sl < cur_sl:
                                            req = {
                                                'action': mt5.TRADE_ACTION_SLTP,
                                                'position': int(ticket),
                                                'sl': float(new_sl),
                                                'tp': float(cur_tp) if cur_tp else 0.0,
                                            }
                                            res = mt5.order_send(req)
                                            if getattr(res, 'retcode', None) == mt5.TRADE_RETCODE_DONE:
                                                log.info(f"Trailing SL updated for ticket {ticket} -> {new_sl}")
                                                self._trailing_state[ticket] = current_price
                            except Exception:
                                pass

                        except Exception:
                            continue
                except Exception as e:
                    log.error(f"Error managing breakeven/trailing: {e}")
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
                
                # If SCULPT_MODE enabled, use M1 sculpting logic; otherwise use M5 as before
                if SCULPT_MODE:
                    try:
                        symbol_info = self.get_symbol_info(SYMBOL) or {}
                        account_balance = (self.account_info.balance if self.account_info else 0.0)

                        # respect sculpt cooldown
                        now = datetime.now()
                        if self._last_sculpt_time and (now - self._last_sculpt_time).total_seconds() < SCULPT_COOLDOWN_SECONDS:
                            # still in cooldown
                            time.sleep(1)
                            continue

                        df_m1 = self.get_current_data(SYMBOL, 'M1', count=200)
                        if df_m1 is None:
                            log.debug("Insufficient data for M1 sculpting check")
                            time.sleep(1)
                            continue

                        res_m1 = golden_trend_system(
                            df_m1,
                            risk_pct=RISK_PERCENT,
                            account_balance=account_balance,
                            macd_hist_threshold=SCULPT_MACD_THRESHOLD,
                            sl_multiplier=SCULPT_SL_MULT,
                            tp_multiplier=SCULPT_TP_MULT,
                            point_size=POINT_SIZE,
                            value_per_point_per_lot=VALUE_PER_PIP_PER_LOT,
                            min_lot=symbol_info.get('min_lot', 0.01),
                            max_lot=symbol_info.get('max_lot', 0.1),
                        )
                    except Exception as e:
                        log.error(f"Strategy execution error on M1 sculpting: {e}")
                        time.sleep(1)
                        continue

                    sig1 = res_m1.get('signal', 'NONE')
                    log.debug(f"Sculpt M1 signal={sig1}")

                    if sig1 == 'NONE':
                        msg = f"No valid sculpt signal at {current_time.strftime('%Y-%m-%d %H:%M:%S')} (M1=NONE)"
                        print(f"\n🔎 {msg}")
                        try:
                            now = datetime.now()
                            if not self._last_no_signal_log_time or (now - self._last_no_signal_log_time).total_seconds() >= self.no_signal_log_throttle:
                                log.info(msg)
                                self._last_no_signal_log_time = now
                        except Exception:
                            pass
                        time.sleep(1)
                        continue

                    action = sig1
                    per_trade_lot = SCULPT_PER_TRADE_LOT
                    desired_trades = SCULPT_MAX_TRADES

                    positions = self.get_positions()
                    current_count = len(positions)
                    max_allowed = min(MAX_POSITIONS, desired_trades)
                    to_open = max(0, max_allowed - current_count)

                    sl_price = res_m1.get('sl_price')
                    tp_price = res_m1.get('tp_price')

                    if to_open <= 0:
                        log.info(f"Already have {current_count} position(s); not opening sculpt trades (target {desired_trades})")
                        time.sleep(1)
                        continue

                    # Optionally log detailed M1 indicators for debugging
                    try:
                        if self.debug_m5:
                            inds = calculate_indicators(df_m1.copy()).iloc[-1]
                            dbg_msg = (
                                f"M1 debug | time={inds.name if hasattr(inds,'name') else df_m1.iloc[-1]['time']} "
                                f"close={inds.get('close', 'N/A'):.5f} ema20={inds.get('ema20', 0):.5f} ema50={inds.get('ema50', 0):.5f} ema200={inds.get('ema200', 0):.5f} "
                                f"macd_hist={inds.get('macd_hist', 0):.5f} atr={inds.get('atr', 0):.5f}"
                            )
                            log.info(dbg_msg)
                            log.info(f"M1 strategy result: {res_m1}")
                    except Exception:
                        pass

                    print(f"\n🎯 Sculpt Confirmed (M1): {action} — opening {to_open} trade(s) x {per_trade_lot} lots")

                    opened_any = False
                    for n in range(to_open):
                        positions_now = self.get_positions()
                        if len(positions_now) >= MAX_POSITIONS:
                            log.info(f"Reached MAX_POSITIONS ({MAX_POSITIONS}) before opening remaining sculpt trades; stopping.")
                            break

                        order_result = self.send_order(
                            action=action,
                            symbol=SYMBOL,
                            lot_size=per_trade_lot,
                            sl_price=sl_price,
                            tp_price=tp_price
                        )

                        if order_result:
                            opened_any = True
                            last_signal_time = datetime.now()
                            print(f"✅ Sent sculpt order {n+1}/{to_open}: {action} {per_trade_lot} lots")
                            self.failed_send_count = 0
                            time.sleep(0.5)
                        else:
                            if self.auto_trading_disabled:
                                print("❌ ส่งออเดอร์ไม่สำเร็จ (AutoTrading ปิดอยู่) — จะไม่ถูกนับเป็นการขาดทุน")
                            else:
                                self.failed_send_count += 1
                                print("❌ ส่งออเดอร์ไม่สำเร็จ")

                    if opened_any:
                        self._last_sculpt_time = datetime.now()

                    continue
                else:
                    # existing M5 logic (unchanged)
                    try:
                        symbol_info = self.get_symbol_info(SYMBOL) or {}
                        account_balance = (self.account_info.balance if self.account_info else 0.0)

                        df_m5 = self.get_current_data(SYMBOL, 'M5', count=200)
                        if df_m5 is None:
                            log.debug("Insufficient data for M5 strategy check")
                            time.sleep(1)
                            continue

                        res_m5 = golden_trend_system(
                            df_m5,
                            risk_pct=RISK_PERCENT,
                            account_balance=account_balance,
                            macd_hist_threshold=M5_MACD_THRESHOLD,
                            point_size=POINT_SIZE,
                            value_per_point_per_lot=VALUE_PER_PIP_PER_LOT,
                            min_lot=symbol_info.get('min_lot', 0.01),
                            max_lot=symbol_info.get('max_lot', 0.1),
                        )
                    except Exception as e:
                        log.error(f"Strategy execution error on M5: {e}")
                        time.sleep(1)
                        continue

                    sig5 = res_m5.get('signal', 'NONE')

                    # Log debug summary of M5
                    log.debug(f"Strategy M5 signal={sig5}")

                    if sig5 == 'NONE':
                        msg = f"No valid strategy signal at {current_time.strftime('%Y-%m-%d %H:%M:%S')} (M5=NONE)"
                        print(f"\n🔎 {msg}")
                        # Throttle file logging to reduce noise
                        try:
                            now = datetime.now()
                            if not self._last_no_signal_log_time or (now - self._last_no_signal_log_time).total_seconds() >= self.no_signal_log_throttle:
                                log.info(msg)
                                self._last_no_signal_log_time = now
                        except Exception:
                            pass
                        time.sleep(1)
                        continue

                    action = sig5

                    # We will open up to 5 trades of 0.01 lots (or less if broker/MAX_POSITIONS limits apply)
                    per_trade_lot = 0.01
                    desired_trades = 5

                    # Check current bot-managed positions
                    positions = self.get_positions()
                    current_count = len(positions)
                    max_allowed = min(MAX_POSITIONS, desired_trades)
                    to_open = max(0, max_allowed - current_count)

                    sl_price = res_m5.get('sl_price')
                    tp_price = res_m5.get('tp_price')

                    if to_open <= 0:
                        log.info(f"Already have {current_count} position(s); not opening more (target {desired_trades})")
                        time.sleep(1)
                        continue

                    # Optionally log detailed M5 indicators for debugging
                    try:
                        if self.debug_m5:
                            inds = calculate_indicators(df_m5.copy()).iloc[-1]
                            dbg_msg = (
                                f"M5 debug | time={inds.name if hasattr(inds,'name') else df_m5.iloc[-1]['time']} "
                                f"close={inds.get('close', 'N/A'):.5f} ema20={inds.get('ema20', 0):.5f} ema50={inds.get('ema50', 0):.5f} ema200={inds.get('ema200', 0):.5f} "
                                f"macd_hist={inds.get('macd_hist', 0):.5f} atr={inds.get('atr', 0):.5f}"
                            )
                            log.info(dbg_msg)
                            log.info(f"M5 strategy result: {res_m5}")
                    except Exception:
                        pass

                    print(f"\n🎯 Confirmed Signal (M5): {action} — opening {to_open} trade(s) x {per_trade_lot} lots")

                    # Open trades but ensure we never exceed MAX_POSITIONS (bot-managed positions)
                    for n in range(to_open):
                        # double-check current bot positions before each order
                        positions_now = self.get_positions()
                        if len(positions_now) >= MAX_POSITIONS:
                            log.info(f"Reached MAX_POSITIONS ({MAX_POSITIONS}) before opening remaining trades; stopping.")
                            break

                        order_result = self.send_order(
                            action=action,
                            symbol=SYMBOL,
                            lot_size=per_trade_lot,
                            sl_price=sl_price,
                            tp_price=tp_price
                        )

                        if order_result:
                            last_signal_time = datetime.now()
                            print(f"✅ Sent order {n+1}/{to_open}: {action} {per_trade_lot} lots")
                            self.failed_send_count = 0
                            # small delay between sends to avoid spamming
                            time.sleep(0.5)
                        else:
                            if self.auto_trading_disabled:
                                print("❌ ส่งออเดอร์ไม่สำเร็จ (AutoTrading ปิดอยู่) — จะไม่ถูกนับเป็นการขาดทุน")
                            else:
                                self.failed_send_count += 1
                                print("❌ ส่งออเดอร์ไม่สำเร็จ")


                # cleanup: we handled per-order success/failure inside the loops above
                
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