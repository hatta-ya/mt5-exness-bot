#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🚀 MT5 Live Trading Module — improved
- Safer lot sizing based on tick value/size
- SL/TP normalization to tick size & stops level
- Requote-aware order sending with small retries
- Better timeframe handling & data fetch fallbacks
- Lightweight reconnect/heartbeat checks
- Richer typing + defensive logging

Notes:
- Keep your existing `config.py`, `strategy.py`, and `utils.logger`.
- This file preserves your public API (MT5Trader class + main()).
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import MetaTrader5 as mt5
import pandas as pd

from .config import *  # noqa: F401,F403  (keep your current constants)
from .strategy import golden_trend_system, calculate_indicators
from .utils.logger import get_logger

log = get_logger("mt5_trader")

# ---------- Helpers ----------

_TIMEFRAME_MAP: Dict[str, int] = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
}


def _tf(name: str) -> int:
    tf = _TIMEFRAME_MAP.get(name.upper())
    if tf is None:
        raise ValueError(f"Unsupported timeframe: {name}")
    return tf


def _now() -> datetime:
    return datetime.now()


@dataclass
class TrailState:
    last_base_price: float


class MT5Trader:
    def __init__(self) -> None:
        self.is_connected: bool = False
        self.account_info: Optional[Any] = None
        self.positions: List[Dict[str, Any]] = []
        self.orders: List[Dict[str, Any]] = []
        self.trade_history: List[Dict[str, Any]] = []
        self.order_count: int = 0

        self.auto_trading_disabled: bool = False
        self._auto_trading_warned: bool = False
        self.failed_send_count: int = 0
        self.consecutive_trade_losses: int = 0
        self._last_auto_check: Optional[datetime] = None

        try:
            self.no_signal_log_throttle: int = int(os.getenv("NO_SIGNAL_LOG_THROTTLE_SECONDS", "30"))
        except Exception:
            self.no_signal_log_throttle = 30
        self._last_no_signal_log_time: Optional[datetime] = None

        self.debug_m5: bool = os.getenv("DEBUG_M5_LOG", "false").lower() in ("1", "true", "yes")
        self._last_sculpt_time: Optional[datetime] = None
        self._trailing_state: Dict[int, TrailState] = {}
        self._symbol_cache: Dict[str, Any] = {}
        self._last_heartbeat: Optional[datetime] = None

    # ---------- Connection ----------

    def _heartbeat(self) -> None:
        """Light heartbeat to detect terminal disconnects and refresh account info."""
        try:
            if not mt5.initialize():
                return  # a later call to connect() will re-init
        except Exception:
            return
        try:
            self.account_info = mt5.account_info()
            self._last_heartbeat = _now()
        except Exception:
            pass

    def connect(self) -> bool:
        """เชื่อมต่อกับ MT5"""
        try:
            if not mt5.initialize():
                log.error(f"Failed to initialize MT5: {mt5.last_error()}")
                return False

            if not mt5.login(int(MT5_LOGIN), password=MT5_PASSWORD, server=MT5_SERVER):
                log.error(f"Failed to login: {mt5.last_error()}")
                mt5.shutdown()
                return False

            self.account_info = mt5.account_info()
            if self.account_info is None:
                log.error("Failed to get account info")
                return False

            self.is_connected = True
            log.info("✅ Connected to MT5")
            log.info(f"📊 Account: {self.account_info.login}")
            log.info(f"💰 Balance: ${self.account_info.balance:.2f}")
            log.info(f"📈 Equity: ${self.account_info.equity:.2f}")
            log.info(f"🌐 Server: {self.account_info.server}")
            return True
        except Exception as e:
            log.error(f"Connection error: {e}")
            return False

    def disconnect(self) -> None:
        """ตัดการเชื่อมต่อ MT5"""
        if self.is_connected:
            try:
                mt5.shutdown()
            finally:
                self.is_connected = False
                log.info("🔌 Disconnected from MT5")

    # ---------- Symbol utils ----------

    def get_symbol_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """ดึงข้อมูล Symbol (cached)"""
        try:
            if symbol in self._symbol_cache:
                return self._symbol_cache[symbol]
            si = mt5.symbol_info(symbol)
            if si is None:
                log.error(f"Symbol {symbol} not found")
                return None
            info = {
                "symbol": si.name,
                "bid": si.bid,
                "ask": si.ask,
                "spread": si.spread,
                "point": si.point,
                "digits": si.digits,
                "trade_mode": si.trade_mode,
                "min_lot": si.volume_min,
                "max_lot": si.volume_max,
                "lot_step": si.volume_step,
                "tick_size": getattr(si, "trade_tick_size", si.point),
                "tick_value": getattr(si, "trade_tick_value", 0.0),
                "stops_level": getattr(si, "trade_stops_level", 0),
                "freeze_level": getattr(si, "trade_freeze_level", 0),
            }
            self._symbol_cache[symbol] = info
            return info
        except Exception as e:
            log.error(f"Error getting symbol info: {e}")
            return None

    def _round_volume(self, symbol: str, vol: float) -> float:
        info = self.get_symbol_info(symbol)
        if not info:
            return round(vol, 2)
        step = info["lot_step"] or 0.01
        min_lot = info["min_lot"] or step
        max_lot = info["max_lot"] or 100.0
        v = max(min_lot, min(max_lot, round(vol / step) * step))
        return v

    def _normalize_price(self, symbol: str, price: Optional[float]) -> Optional[float]:
        if price is None or price == 0:
            return price
        info = self.get_symbol_info(symbol)
        if not info:
            return price
        digits = info["digits"]
        return float(round(price, digits))

    def _respect_stops_level(self, symbol: str, order_type: int, price: float, sl: Optional[float], tp: Optional[float]) -> tuple[Optional[float], Optional[float]]:
        info = self.get_symbol_info(symbol) or {}
        point = info.get("point", 0.0) or 0.0
        stops = info.get("stops_level", 0) or 0
        if point <= 0 or stops <= 0:
            return sl, tp
        min_dist = stops * point
        if order_type == mt5.ORDER_TYPE_BUY:
            if sl is not None and sl > 0 and (price - sl) < min_dist:
                sl = price - min_dist
            if tp is not None and tp > 0 and (tp - price) < min_dist:
                tp = price + min_dist
        else:
            if sl is not None and sl > 0 and (sl - price) < min_dist:
                sl = price + min_dist
            if tp is not None and tp > 0 and (price - tp) < min_dist:
                tp = price - min_dist
        return sl, tp

    # ---------- Market data ----------

    def get_current_data(self, symbol: str, timeframe: str, count: int = 300) -> Optional[pd.DataFrame]:
        """ดึงข้อมูลราคาปัจจุบัน with simple fallback."""
        try:
            mtf = _tf(timeframe)
            rates = mt5.copy_rates_from_pos(symbol, mtf, 0, count)
            if rates is None or len(rates) == 0:
                # fallback  — try with range for the last N bars (~ count * bar_len)
                end = _now()
                # heuristics: 1m -> count*90s, 5m -> count*7min, etc.
                minutes = {mt5.TIMEFRAME_M1: 2, mt5.TIMEFRAME_M5: 7, mt5.TIMEFRAME_M15: 20, mt5.TIMEFRAME_M30: 40, mt5.TIMEFRAME_H1: 80, mt5.TIMEFRAME_H4: 300, mt5.TIMEFRAME_D1: 1500}.get(mtf, 10)
                start = end - timedelta(minutes=count * minutes)
                rates = mt5.copy_rates_range(symbol, mtf, start, end)
            if rates is None or len(rates) == 0:
                log.error(f"Failed to get rates for {symbol}")
                return None
            df = pd.DataFrame(rates)
            df["time"] = pd.to_datetime(df["time"], unit="s")
            cols = ["time", "open", "high", "low", "close", "tick_volume"]
            df = df[cols].copy()
            df.rename(columns={"tick_volume": "volume"}, inplace=True)
            return df
        except Exception as e:
            log.error(f"Error getting data: {e}")
            return None

    # ---------- Risk / lot sizing ----------

    def calculate_lot_size(self, symbol: str, risk_percent: float, stop_loss_pips: float) -> float:
        """คำนวณขนาด lot ตาม Risk Management (tick-based, broker-agnostic).
        - risk $ = balance * risk%
        - risk per 1 lot for given SL distance = distance_in_price_units * (tick_value/tick_size)
        distance_in_price_units = stop_loss_pips * POINT_SIZE
        """
        try:
            if not self.account_info:
                return 0.01
            balance = float(self.account_info.balance)
            risk_amount = balance * (risk_percent / 100.0)
            info = self.get_symbol_info(symbol)
            if not info:
                return 0.01
            tick_value = float(info.get("tick_value", 0.0) or 0.0)
            tick_size = float(info.get("tick_size", info.get("point", 0.0)) or 0.0)
            if tick_value <= 0 or tick_size <= 0 or POINT_SIZE <= 0:
                log.warning("Fallback lot calc due to missing tick params")
                # Fallback: your original simple cap
                base = max(info["min_lot"], min(0.1, info["min_lot"]))
                return self._round_volume(symbol, base)
            distance = abs(stop_loss_pips) * float(POINT_SIZE)
            risk_per_lot = distance * (tick_value / tick_size)
            if risk_per_lot <= 0:
                return info["min_lot"]
            lots = risk_amount / risk_per_lot
            lots = self._round_volume(symbol, lots)
            lots = min(lots, 0.1)  # global safety cap
            log.info(f"💡 Calculated lot size: {lots} for risk {risk_percent}% (SL {stop_loss_pips} pips)")
            return lots
        except Exception as e:
            log.error(f"Error calculating lot size: {e}")
            return 0.01

    # ---------- Orders ----------

    def _autotrade_allowed(self) -> bool:
        try:
            ti = mt5.terminal_info()
            allowed = bool(getattr(ti, "trade_allowed", True))
            if not allowed and not self._auto_trading_warned:
                log.error("Order blocked: AutoTrading disabled on the MT5 client. Enable AutoTrading.")
                self._auto_trading_warned = True
            return allowed
        except Exception:
            return True  # if unknown, allow and let order_send decide

    def send_order(self, action: str, symbol: str, lot_size: float, sl_price: Optional[float] = None, tp_price: Optional[float] = None, comment: str = "Golden Trend Bot") -> Optional[Any]:
        """ส่งออเดอร์ — requote aware, normalizes SL/TP, respects stops level."""
        try:
            if not self._autotrade_allowed():
                self.auto_trading_disabled = True
                return None

            info = self.get_symbol_info(symbol)
            if not info:
                return None

            order_type = mt5.ORDER_TYPE_BUY if action.upper() == "BUY" else mt5.ORDER_TYPE_SELL
            price = info["ask"] if order_type == mt5.ORDER_TYPE_BUY else info["bid"]

            # Normalize SL/TP
            sl_price = self._normalize_price(symbol, sl_price)
            tp_price = self._normalize_price(symbol, tp_price)
            sl_price, tp_price = self._respect_stops_level(symbol, order_type, price, sl_price, tp_price)

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": float(self._round_volume(symbol, lot_size)),
                "type": order_type,
                "price": float(self._normalize_price(symbol, price) or price),
                "sl": float(sl_price) if sl_price else 0.0,
                "tp": float(tp_price) if tp_price else 0.0,
                "deviation": int(MAX_SLIPPAGE),
                "magic": int(MAGIC),
                "comment": comment,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            # Small retry loop for requotes/price change
            for attempt in range(1, 4):
                result = mt5.order_send(request)
                ret = getattr(result, "retcode", None)
                if ret == mt5.TRADE_RETCODE_DONE:
                    log.info(f"✅ Order sent: {action} {request['volume']} lots {symbol} @ {request['price']}")
                    log.info(f"📋 Order ID: {getattr(result, 'order', None)} | 💰 SL: {request['sl']}, TP: {request['tp']}")
                    self._record_trade(action, request['price'], request['volume'], request['sl'], request['tp'], getattr(result, 'order', None))
                    self.failed_send_count = 0
                    return result
                # Requote/price changed — refresh price and retry quickly
                if ret in (mt5.TRADE_RETCODE_REQUOTE, mt5.TRADE_RETCODE_PRICE_CHANGED):
                    tick = mt5.symbol_info_tick(symbol)
                    if tick:
                        request["price"] = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid
                        request["price"] = float(self._normalize_price(symbol, request["price"]))
                    time.sleep(0.3)
                    continue
                # AutoTrading off code
                if ret == 10027:
                    self.auto_trading_disabled = True
                    if not self._auto_trading_warned:
                        log.error("Order blocked: AutoTrading disabled on the client terminal. Enable AutoTrading.")
                        self._auto_trading_warned = True
                    return None
                # Other failure — one shot
                log.error(f"Order failed: {ret} - {getattr(result, 'comment', '')}")
                self.failed_send_count += 1
                return None

            # If loop exits without success
            log.error("Order failed after retry attempts (requotes)")
            self.failed_send_count += 1
            return None
        except Exception as e:
            log.error(f"Error sending order: {e}")
            self.failed_send_count += 1
            return None

    def _record_trade(self, action: str, price: float, lot: float, sl: Optional[float], tp: Optional[float], order_id: Optional[int]) -> None:
        try:
            self.order_count += 1
            trade_no = self.order_count
            trade_entry = {
                "no": trade_no,
                "action": action,
                "entry_price": price,
                "lot_size": lot,
                "sl_price": sl,
                "tp_price": tp,
                "order_id": order_id,
                "time": _now(),
            }
            self.trade_history.append(trade_entry)
            log.info(f"#{trade_no:04d} 🎯 {action} @ ${price:.2f} | Lots: {lot} | OrderID: {order_id} | SL: {sl} | TP: {tp}")
        except Exception:
            pass

    # ---------- Notifications ----------

    def send_notification(self, message: str) -> None:
        try:
            log.warning(f"NOTIFY: {message}")
            if NOTIFICATIONS_ENABLE:
                os.makedirs(os.path.dirname(NOTIFICATIONS_LOG_PATH), exist_ok=True)
                with open(NOTIFICATIONS_LOG_PATH, "a", encoding="utf-8") as f:
                    f.write(f"{_now().isoformat()} | {message}\n")
        except Exception as e:
            log.error(f"Failed to send notification: {e}")

    # ---------- Positions ----------

    def get_positions(self) -> List[Dict[str, Any]]:
        try:
            positions = mt5.positions_get(symbol=SYMBOL)
            if positions is None:
                log.debug("mt5.positions_get returned None")
                return []
            filtered: List[Dict[str, Any]] = []
            for p in positions:
                try:
                    if getattr(p, "magic", None) == MAGIC:
                        filtered.append({
                            "ticket": p.ticket,
                            "symbol": p.symbol,
                            "type": "BUY" if p.type == mt5.POSITION_TYPE_BUY else "SELL",
                            "volume": p.volume,
                            "price_open": p.price_open,
                            "sl": p.sl,
                            "tp": p.tp,
                            "profit": p.profit,
                            "time": datetime.fromtimestamp(p.time),
                            "comment": p.comment,
                        })
                except Exception:
                    continue
            return filtered
        except Exception as e:
            log.error(f"Error getting positions: {e}")
            return []

    def close_position(self, ticket: int) -> bool:
        try:
            positions = mt5.positions_get(ticket=ticket)
            if not positions:
                log.error(f"Position {ticket} not found")
                return False
            p = positions[0]
            order_type = mt5.ORDER_TYPE_SELL if p.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
            tick = mt5.symbol_info_tick(p.symbol)
            if not tick:
                log.error("No tick for symbol while closing")
                return False
            price = tick.bid if order_type == mt5.ORDER_TYPE_SELL else tick.ask
            req = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": p.symbol,
                "volume": p.volume,
                "type": order_type,
                "position": ticket,
                "price": float(self._normalize_price(p.symbol, price) or price),
                "deviation": int(MAX_SLIPPAGE),
                "magic": int(MAGIC),
                "comment": "Close by Golden Trend Bot",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            result = mt5.order_send(req)
            if getattr(result, "retcode", None) != mt5.TRADE_RETCODE_DONE:
                log.error(f"Close failed: {getattr(result,'retcode', None)} - {getattr(result,'comment','')}")
                return False
            try:
                self.account_info = mt5.account_info()
            except Exception:
                pass
            profit = getattr(p, "profit", None)
            try:
                self.order_count += 1
                close_no = self.order_count
                balance_str = f"${self.account_info.balance:.2f}" if self.account_info else "N/A"
                log.info(f"#{close_no:04d} 🔒 Close ticket {ticket} | P&L: ${profit:.2f if profit is not None else 0.0} | Balance: {balance_str} | Reason: Close by Golden Trend Bot")
            except Exception:
                log.info(f"✅ Position {ticket} closed")
            return True
        except Exception as e:
            log.error(f"Error closing position: {e}")
            return False

    def close_position_with_retry(self, ticket: int, attempts: int = AGGREGATE_CLOSE_RETRY_ATTEMPTS, backoff: float = AGGREGATE_CLOSE_RETRY_BACKOFF_SECONDS) -> bool:
        if not ticket:
            log.error(f"close_position_with_retry called with empty ticket: {ticket}")
            return False
        for attempt in range(1, attempts + 1):
            try:
                log.info(f"Attempt {attempt}/{attempts} to close position {ticket}")
                if self.close_position(ticket):
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

    # ---------- Main loop ----------

    def run_live_trading(self) -> None:
        print(f"""
╔══════════════════════════════════════════════════════════════╗
║                        MT5 Live Trading                      ║
║                                                              ║
║                    {SYMBOL} Golden Trend System                ║
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

        last_signal_time: Optional[datetime] = None
        try:
            print("🔄 เริ่มการซื้อขายจริง... (กด Ctrl+C เพื่อหยุด)")
            while True:
                # Heartbeat every 30s
                if not self._last_heartbeat or (_now() - self._last_heartbeat).total_seconds() >= 30:
                    self._heartbeat()

                df = self.get_current_data(SYMBOL, TIMEFRAME)
                if df is None or df.empty:
                    time.sleep(3)
                    continue

                current_time = df.iloc[-1]["time"]
                current_price = float(df.iloc[-1]["close"])  # display only

                if last_signal_time and _now() <= last_signal_time + timedelta(seconds=3):
                    time.sleep(1)
                    continue

                # AutoTrading guard & auto-resume
                if self.auto_trading_disabled:
                    now = _now()
                    if not self._last_auto_check or (now - self._last_auto_check).total_seconds() >= 10:
                        self._last_auto_check = now
                        try:
                            if self._autotrade_allowed():
                                self.auto_trading_disabled = False
                                self._auto_trading_warned = False
                                self.failed_send_count = 0
                                log.info("AutoTrading re-enabled — resuming order attempts.")
                                self.send_notification("AutoTrading re-enabled — bot resumed sending orders.")
                            else:
                                if not self._auto_trading_warned:
                                    log.error("AutoTrading disabled — pausing order attempts until enabled in MT5.")
                                    self._auto_trading_warned = True
                        except Exception:
                            pass
                    time.sleep(10)
                    continue

                if self.failed_send_count >= MAX_CONSECUTIVE_LOSSES:
                    msg = f"Bot paused: {self.failed_send_count} consecutive send failures."
                    print(f"⚠️ {msg}")
                    self.send_notification(msg)
                    time.sleep(3600)
                    self.failed_send_count = 0
                    continue

                positions = self.get_positions()

                # Aggregate close
                try:
                    if AGGREGATE_CLOSE_ENABLED and positions:
                        total_profit = sum([p.get("profit", 0.0) for p in positions])
                        log.debug(f"Aggregate profit for open positions: {total_profit}")
                        if total_profit >= AGGREGATE_CLOSE_PROFIT_USD:
                            log.info(f"Aggregate profit ${total_profit:.2f} >= ${AGGREGATE_CLOSE_PROFIT_USD:.2f}. Closing all positions.")
                            for pos in positions:
                                try:
                                    ticket = pos.get("ticket")
                                    if ticket:
                                        closed = self.close_position(ticket)
                                        if closed:
                                            log.info(f"Closed position {ticket} successfully")
                                        else:
                                            log.error(f"Failed to close position {ticket}")
                                except Exception as e:
                                    log.error(f"Error closing position {pos}: {e}")
                            self.failed_send_count = 0
                            time.sleep(3)
                            continue
                except Exception as e:
                    log.error(f"Error computing aggregate profit: {e}")

                # Manage open positions — breakeven + ATR trailing
                try:
                    for pos in positions:
                        try:
                            ticket = int(pos.get("ticket"))
                            symbol = str(pos.get("symbol"))
                            vol = float(pos.get("volume"))
                            entry_price = float(pos.get("price_open"))
                            cur_sl = pos.get("sl") or 0.0
                            cur_tp = pos.get("tp") or 0.0
                            pos_type = str(pos.get("type"))
                            profit_usd = float(pos.get("profit", 0.0))

                            tick = mt5.symbol_info_tick(symbol)
                            if not tick:
                                continue
                            mkt_price = tick.bid if pos_type == "BUY" else tick.ask

                            df_m1_pos = self.get_current_data(symbol, "M1", count=100)
                            if df_m1_pos is None:
                                continue
                            inds_pos = calculate_indicators(df_m1_pos.copy()).iloc[-1]
                            atr = float(inds_pos.get("atr", 0.0) or 0.0)
                            if atr < SCULPT_MIN_ATR:
                                continue

                            # risk in USD using SL distance
                            if cur_sl == 0:
                                continue
                            sl_points = abs(entry_price - cur_sl) / float(POINT_SIZE or 1.0)
                            risk_usd = sl_points * float(VALUE_PER_PIP_PER_LOT) * vol

                            # breakeven
                            if risk_usd > 0 and profit_usd >= (SCULPT_BREAKEVEN_R_MULT * risk_usd):
                                if abs(cur_sl - entry_price) > 1e-9:
                                    try:
                                        res = mt5.order_send({
                                            "action": mt5.TRADE_ACTION_SLTP,
                                            "position": ticket,
                                            "sl": float(self._normalize_price(symbol, entry_price)),
                                            "tp": float(cur_tp),
                                        })
                                        if getattr(res, "retcode", None) == mt5.TRADE_RETCODE_DONE:
                                            log.info(f"Breakeven set for ticket {ticket} at {entry_price}")
                                            self._trailing_state[ticket] = TrailState(last_base_price=entry_price)
                                    except Exception as e:
                                        log.error(f"Error setting breakeven for {ticket}: {e}")

                            # ATR trailing
                            step = float(SCULPT_TRAILING_ATR_STEP_MULT) * atr
                            base = self._trailing_state.get(ticket, TrailState(last_base_price=entry_price)).last_base_price
                            if pos_type == "BUY":
                                if (mkt_price - base) >= step and step > 0:
                                    new_sl = max(cur_sl, mkt_price - step)
                                    if new_sl > cur_sl:
                                        res = mt5.order_send({
                                            "action": mt5.TRADE_ACTION_SLTP,
                                            "position": ticket,
                                            "sl": float(self._normalize_price(symbol, new_sl)),
                                            "tp": float(cur_tp),
                                        })
                                        if getattr(res, "retcode", None) == mt5.TRADE_RETCODE_DONE:
                                            log.info(f"Trailing SL updated for ticket {ticket} -> {new_sl}")
                                            self._trailing_state[ticket] = TrailState(last_base_price=mkt_price)
                            else:
                                if (base - mkt_price) >= step and step > 0:
                                    new_sl = min(cur_sl, mkt_price + step) if cur_sl else (mkt_price + step)
                                    if cur_sl == 0 or new_sl < cur_sl:
                                        res = mt5.order_send({
                                            "action": mt5.TRADE_ACTION_SLTP,
                                            "position": ticket,
                                            "sl": float(self._normalize_price(symbol, new_sl)),
                                            "tp": float(cur_tp),
                                        })
                                        if getattr(res, "retcode", None) == mt5.TRADE_RETCODE_DONE:
                                            log.info(f"Trailing SL updated for ticket {ticket} -> {new_sl}")
                                            self._trailing_state[ticket] = TrailState(last_base_price=mkt_price)
                        except Exception:
                            continue
                except Exception as e:
                    log.error(f"Error managing breakeven/trailing: {e}")

                try:
                    total_open = mt5.positions_total()
                except Exception:
                    total_open = None
                if total_open == 0 and len(positions) > 0:
                    log.warning("mt5.positions_total()==0 but get_positions returned entries; treating as 0 and continuing")
                    positions = []
                if len(positions) >= MAX_POSITIONS:
                    print(f"⚠️ มี Position เปิดอยู่ {len(positions)}/{MAX_POSITIONS} แล้ว")
                    time.sleep(60)
                    continue

                # --- Entry logic ---
                if SCULPT_MODE:
                    try:
                        symbol_info = self.get_symbol_info(SYMBOL) or {}
                        account_balance = (self.account_info.balance if self.account_info else 0.0)
                        now = _now()
                        if self._last_sculpt_time and (now - self._last_sculpt_time).total_seconds() < SCULPT_COOLDOWN_SECONDS:
                            time.sleep(1)
                            continue
                        df_m1 = self.get_current_data(SYMBOL, "M1", count=200)
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
                            min_lot=symbol_info.get("min_lot", 0.01),
                            max_lot=symbol_info.get("max_lot", 0.1),
                        )
                    except Exception as e:
                        log.error(f"Strategy execution error on M1 sculpting: {e}")
                        time.sleep(1)
                        continue

                    sig1 = res_m1.get("signal", "NONE")
                    log.debug(f"Sculpt M1 signal={sig1}")
                    if sig1 == "NONE":
                        msg = f"No valid sculpt signal at {current_time.strftime('%Y-%m-%d %H:%M:%S')} (M1=NONE)"
                        print(f"\n🔎 {msg}")
                        now = _now()
                        if not self._last_no_signal_log_time or (now - self._last_no_signal_log_time).total_seconds() >= self.no_signal_log_throttle:
                            log.info(msg)
                            self._last_no_signal_log_time = now
                        time.sleep(1)
                        continue

                    action = sig1
                    per_trade_lot = SCULPT_PER_TRADE_LOT
                    desired_trades = SCULPT_MAX_TRADES
                    positions = self.get_positions()
                    current_count = len(positions)
                    max_allowed = min(MAX_POSITIONS, desired_trades)
                    to_open = max(0, max_allowed - current_count)
                    sl_price = res_m1.get("sl_price")
                    tp_price = res_m1.get("tp_price")

                    if to_open <= 0:
                        log.info(f"Already have {current_count} position(s); not opening sculpt trades (target {desired_trades})")
                        time.sleep(1)
                        continue

                    if self.debug_m5:
                        try:
                            inds = calculate_indicators(df_m1.copy()).iloc[-1]
                            log.info(
                                f"M1 debug | close={inds.get('close', 'N/A'):.5f} ema20={inds.get('ema20', 0):.5f} "
                                f"ema50={inds.get('ema50', 0):.5f} ema200={inds.get('ema200', 0):.5f} "
                                f"macd_hist={inds.get('macd_hist', 0):.5f} atr={inds.get('atr', 0):.5f}"
                            )
                            log.info(f"M1 strategy result: {res_m1}")
                        except Exception:
                            pass

                    print(f"\n🎯 Sculpt Confirmed (M1): {action} — opening {to_open} trade(s) x {per_trade_lot} lots")
                    opened_any = False
                    for n in range(to_open):
                        if len(self.get_positions()) >= MAX_POSITIONS:
                            log.info(f"Reached MAX_POSITIONS ({MAX_POSITIONS}); stopping.")
                            break
                        order_result = self.send_order(action=action, symbol=SYMBOL, lot_size=per_trade_lot, sl_price=sl_price, tp_price=tp_price)
                        if order_result:
                            opened_any = True
                            last_signal_time = _now()
                            print(f"✅ Sent sculpt order {n+1}/{to_open}: {action} {per_trade_lot} lots")
                            time.sleep(0.5)
                        else:
                            print("❌ ส่งออเดอร์ไม่สำเร็จ" + (" (AutoTrading ปิดอยู่) — จะไม่ถูกนับเป็นการขาดทุน" if self.auto_trading_disabled else ""))
                    if opened_any:
                        self._last_sculpt_time = _now()
                    continue

                # ---- Non-sculpt (M5) ----
                try:
                    symbol_info = self.get_symbol_info(SYMBOL) or {}
                    account_balance = (self.account_info.balance if self.account_info else 0.0)
                    df_m5 = self.get_current_data(SYMBOL, "M5", count=200)
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
                        min_lot=symbol_info.get("min_lot", 0.01),
                        max_lot=symbol_info.get("max_lot", 0.1),
                    )
                except Exception as e:
                    log.error(f"Strategy execution error on M5: {e}")
                    time.sleep(1)
                    continue

                sig5 = res_m5.get("signal", "NONE")
                log.debug(f"Strategy M5 signal={sig5}")
                if sig5 == "NONE":
                    msg = f"No valid strategy signal at {current_time.strftime('%Y-%m-%d %H:%M:%S')} (M5=NONE)"
                    print(f"\n🔎 {msg}")
                    now = _now()
                    if not self._last_no_signal_log_time or (now - self._last_no_signal_log_time).total_seconds() >= self.no_signal_log_throttle:
                        log.info(msg)
                        self._last_no_signal_log_time = now
                    time.sleep(1)
                    continue

                action = "BUY" if SCALP_FORCE_BUY_ONLY else sig5
                per_trade_lot = 0.01
                desired_trades = SCALP_GRID_LEGS if SCALP_GRID_ENABLED else 1

                positions = self.get_positions()
                current_count = len(positions)
                max_allowed = min(MAX_POSITIONS, desired_trades)
                to_open = max(0, max_allowed - current_count)

                sl_price = res_m5.get("sl_price")
                tp_price = res_m5.get("tp_price")

                if to_open <= 0:
                    log.info(f"Already have {current_count} position(s); not opening more (target {desired_trades})")
                    time.sleep(1)
                    continue

                if self.debug_m5:
                    try:
                        inds = calculate_indicators(df_m5.copy()).iloc[-1]
                        log.info(
                            f"M5 debug | close={inds.get('close', 'N/A'):.5f} ema20={inds.get('ema20', 0):.5f} "
                            f"ema50={inds.get('ema50', 0):.5f} ema200={inds.get('ema200', 0):.5f} "
                            f"macd_hist={inds.get('macd_hist', 0):.5f} atr={inds.get('atr', 0):.5f}"
                        )
                        log.info(f"M5 strategy result: {res_m5}")
                    except Exception:
                        pass

                print(f"\n🎯 Confirmed Signal (M5): {action} — opening {to_open} trade(s) (grid enabled={SCALP_GRID_ENABLED})")

                opened = 0
                shared_tp_price = None
                try:
                    shared_tp_price = current_price + (SCALP_GRID_SHARED_TP_PIPS * POINT_SIZE)
                except Exception:
                    shared_tp_price = tp_price

                for leg in range(min(to_open, desired_trades)):
                    if len(self.get_positions()) >= MAX_POSITIONS:
                        log.info(f"Reached MAX_POSITIONS ({MAX_POSITIONS}) before opening remaining grid trades; stopping.")
                        break
                    lot = per_trade_lot * (SCALP_GRID_LOT_MULTIPLIER ** leg)
                    try:
                        sl_distance = SL_PIPS + (leg * SCALP_GRID_DISTANCE_PIPS)
                    except Exception:
                        sl_distance = SL_PIPS
                    # respect signal direction
                    tick = mt5.symbol_info_tick(SYMBOL)
                    if not tick:
                        break
                    ref_price = tick.ask if action == "BUY" else tick.bid
                    if action == "BUY":
                        sl_for_leg = ref_price - (sl_distance * POINT_SIZE)
                        tp_for_leg = (shared_tp_price if SCALP_GRID_ENABLED and shared_tp_price is not None else tp_price)
                    else:
                        sl_for_leg = ref_price + (sl_distance * POINT_SIZE)
                        tpsh = (shared_tp_price if SCALP_GRID_ENABLED and shared_tp_price is not None else tp_price)
                        tp_for_leg = tpsh if tpsh is not None else (ref_price - (SL_PIPS * POINT_SIZE))

                    order_result = self.send_order(action=action, symbol=SYMBOL, lot_size=lot, sl_price=sl_for_leg, tp_price=tp_for_leg)
                    if order_result:
                        opened += 1
                        last_signal_time = _now()
                        print(f"✅ Sent grid leg {leg+1}/{min(to_open, desired_trades)}: {action} {lot} lots | SL: {sl_for_leg} | TP: {tp_for_leg}")
                        time.sleep(0.5)
                    else:
                        print("❌ ส่งออเดอร์ไม่สำเร็จ" + (" (AutoTrading ปิดอยู่) — จะไม่ถูกนับเป็นการขาดทุน" if self.auto_trading_disabled else ""))

                print(f"⏰ {current_time.strftime('%Y-%m-%d %H:%M:%S')} | Price: {current_price:.2f} | Positions: {len(positions)} | Balance: ${self.account_info.balance:.2f}")
                time.sleep(3)
        except KeyboardInterrupt:
            print("\n🛑 หยุดการซื้อขายโดยผู้ใช้")
        except Exception as e:
            log.error(f"Live trading error: {e}")
            print(f"❌ เกิดข้อผิดพลาด: {e}")
        finally:
            self.disconnect()


# ---------- Entrypoint ----------

def main() -> None:
    """เริ่มการซื้อขายจริง"""
    trader = MT5Trader()
    if not MT5_LOGIN or not MT5_PASSWORD or not MT5_SERVER:
        print("❌ กรุณาตั้งค่า MT5_LOGIN, MT5_PASSWORD, MT5_SERVER ใน .env file")
        return
    trader.run_live_trading()


if __name__ == "__main__":
    main()
