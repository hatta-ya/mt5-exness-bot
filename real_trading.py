#!/usr/bin/env python3
"""
🚀 MT5 Real Trading Bot
สำหรับการเทรดด้วยบัญชีจริง - ใช้ด้วยความระมัดระวัง!
"""

import MetaTrader5 as mt5
import pandas as pd
import time
from datetime import datetime
from config import *
from strategy import ema_strategy
from risk import check_daily_limits, calculate_position_size
from utils.logger import get_logger

log = get_logger("real_trading")

def initialize_mt5():
    """เชื่อมต่อ MT5"""
    if not mt5.initialize():
        log.error("MT5 initialization failed")
        return False
    
    # เข้าสู่ระบบ
    authorized = mt5.login(MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)
    if not authorized:
        log.error(f"Failed to connect to {MT5_SERVER}")
        mt5.shutdown()
        return False
    
    account_info = mt5.account_info()
    if account_info is None:
        log.error("Failed to get account info")
        return False
    
    log.info(f"Connected to {account_info.name}, Balance: {account_info.balance}")
    return True

def place_order(symbol, order_type, lot, sl, tp):
    """วางออเดอร์"""
    # ตรวจสอบ Risk Management ก่อน
    if not check_daily_limits():
        log.warning("Daily limits reached - No new trades")
        return False
    
    # คำนวณขนาด Position
    position_size = calculate_position_size(symbol, sl)
    
    point = mt5.symbol_info(symbol).point
    price = mt5.symbol_info_tick(symbol).ask if order_type == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(symbol).bid
    
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": position_size,
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": MAX_SLIPPAGE,
        "magic": MAGIC,
        "comment": "EMA Strategy Bot",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        log.error(f"Order failed: {result.comment}")
        return False
    
    log.info(f"Order successful: {result.order}")
    return True

def main():
    """Main trading loop"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║                🚀 MT5 REAL TRADING BOT                       ║
║                   ⚠️  LIVE ACCOUNT ⚠️                         ║
║                                                              ║
║        🔴 การเทรดมีความเสี่ยง อาจสูญเสียเงินทุนได้         ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    # ยืนยันก่อนเริ่ม
    confirm = input("\n⚠️  คุณแน่ใจหรือไม่ที่จะเทรดด้วยเงินจริง? (พิมพ์ 'YES' เพื่อยืนยัน): ")
    if confirm != "YES":
        print("❌ ยกเลิกการเทรด")
        return
    
    # เชื่อมต่อ MT5
    if not initialize_mt5():
        print("❌ ไม่สามารถเชื่อมต่อ MT5 ได้")
        return
    
    print("✅ เชื่อมต่อ MT5 สำเร็จ - เริ่มเทรด...")
    
    try:
        while True:
            # ดึงข้อมูล
            rates = mt5.copy_rates_from_pos(SYMBOL, getattr(mt5, f"TIMEFRAME_{TIMEFRAME}"), 0, 200)
            if rates is None:
                log.error("Failed to get market data")
                time.sleep(60)
                continue
            
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            
            # วิเคราะห์ Strategy
            signal = ema_strategy(df, EMA_SHORT, EMA_LONG)
            
            if signal != "HOLD":
                log.info(f"Signal: {signal}")
                
                # ตรวจสอบว่ามี position เปิดอยู่หรือไม่
                positions = mt5.positions_get(symbol=SYMBOL)
                if len(positions) >= MAX_OPEN_TRADES:
                    log.info("Max positions reached")
                else:
                    # วาง Order
                    if signal == "BUY":
                        price = mt5.symbol_info_tick(SYMBOL).ask
                        sl = price - (SL_PIPS * mt5.symbol_info(SYMBOL).point * 10)
                        tp = price + (TP_PIPS * mt5.symbol_info(SYMBOL).point * 10)
                        place_order(SYMBOL, mt5.ORDER_TYPE_BUY, LOT, sl, tp)
                    
                    elif signal == "SELL":
                        price = mt5.symbol_info_tick(SYMBOL).bid
                        sl = price + (SL_PIPS * mt5.symbol_info(SYMBOL).point * 10)
                        tp = price - (TP_PIPS * mt5.symbol_info(SYMBOL).point * 10)
                        place_order(SYMBOL, mt5.ORDER_TYPE_SELL, LOT, sl, tp)
            
            time.sleep(60)  # รอ 1 นาที
            
    except KeyboardInterrupt:
        print("\n🛑 หยุดการเทรด...")
    finally:
        mt5.shutdown()

if __name__ == "__main__":
    main()