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
            
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                log.error(f"Order failed: {result.retcode} - {result.comment}")
                return None
            
            log.info(f"✅ Order sent: {action} {lot_size} lots {symbol} @ {price}")
            log.info(f"📋 Order ID: {result.order}")
            log.info(f"💰 SL: {sl_price}, TP: {tp_price}")
            
            return result
            
        except Exception as e:
            log.error(f"Error sending order: {e}")
            return None
    
    def get_positions(self):
        """ดึงรายการ Position ที่เปิดอยู่"""
        try:
            positions = mt5.positions_get(symbol=SYMBOL)
            if positions is None:
                return []
            
            return [
                {
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
                }
                for pos in positions if pos.magic == MAGIC
            ]
            
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
        last_signal_time = None
        
        try:
            print("🔄 เริ่มการซื้อขายจริง... (กด Ctrl+C เพื่อหยุด)")
            
            while True:
                # ดึงข้อมูลปัจจุบัน
                df = self.get_current_data(SYMBOL, TIMEFRAME)
                if df is None:
                    time.sleep(60)
                    continue
                
                current_time = df.iloc[-1]['time']
                current_price = df.iloc[-1]['close']
                
                # ตรวจสอบไม่ให้ signal ซ้ำในเวลาเดียวกัน
                if last_signal_time and current_time <= last_signal_time:
                    time.sleep(30)
                    continue
                
                # ตรวจสอบ consecutive losses
                if consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
                    print(f"⚠️ หยุดเทรดชั่วคราว - ขาดทุนติดกัน {consecutive_losses} ครั้ง")
                    time.sleep(3600)  # รอ 1 ชั่วโมง
                    consecutive_losses = 0
                    continue
                
                # ตรวจสอบจำนวน Position ที่เปิดอยู่
                positions = self.get_positions()
                if len(positions) >= MAX_POSITIONS:
                    print(f"⚠️ มี Position เปิดอยู่ {len(positions)}/{MAX_POSITIONS} แล้ว")
                    time.sleep(60)
                    continue
                
                # วิเคราะห์สัญญาณ
                result = golden_trend_system(
                    df,
                    risk_pct=RISK_PERCENT,
                    account_balance=self.account_info.balance,
                    point_size=POINT_SIZE,
                    value_per_point_per_lot=VALUE_PER_PIP_PER_LOT,
                )
                
                if result['signal'] in ['BUY', 'SELL']:
                    print(f"\n🎯 Signal: {result['signal']} @ {current_price:.2f}")
                    
                    # คำนวณ lot size
                    lot_size = self.calculate_lot_size(SYMBOL, RISK_PERCENT, SL_PIPS)
                    
                    # คำนวณ SL และ TP
                    if result['signal'] == 'BUY':
                        sl_price = current_price - (SL_PIPS * POINT_SIZE)
                        tp_price = current_price + (TP_PIPS * POINT_SIZE)
                    else:
                        sl_price = current_price + (SL_PIPS * POINT_SIZE)
                        tp_price = current_price - (TP_PIPS * POINT_SIZE)
                    
                    # ส่งออเดอร์
                    order_result = self.send_order(
                        action=result['signal'],
                        symbol=SYMBOL,
                        lot_size=lot_size,
                        sl_price=sl_price,
                        tp_price=tp_price
                    )
                    
                    if order_result:
                        last_signal_time = current_time
                        print(f"✅ ส่งออเดอร์สำเร็จ: {result['signal']} {lot_size} lots")
                    else:
                        consecutive_losses += 1
                        print(f"❌ ส่งออเดอร์ไม่สำเร็จ")
                
                # แสดงสถานะปัจจุบัน
                print(f"⏰ {current_time.strftime('%Y-%m-%d %H:%M:%S')} | Price: {current_price:.2f} | Positions: {len(positions)} | Balance: ${self.account_info.balance:.2f}")
                
                # รอ 30 วินาที
                time.sleep(30)
                
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