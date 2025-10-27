import pandas as pd
import numpy as np
from datetime import datetime, time as dt_time

def calculate_indicators(df: pd.DataFrame):
    """คำนวณ indicators ทั้งหมดสำหรับ Golden Trend System"""
    df = df.copy()
    
    # EMA 20, 50, 200
    df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    # MACD (12, 26, 9)
    exp12 = df['close'].ewm(span=12, adjust=False).mean()
    exp26 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = exp12 - exp26
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_histogram'] = df['macd'] - df['macd_signal']
    
    # RSI (14)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # ADX (14) - Wilder's method (more standard)
    n = 14
    high = df['high']
    low = df['low']
    close = df['close']

    prev_high = high.shift(1)
    prev_low = low.shift(1)
    prev_close = close.shift(1)

    # True Range
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # +DM and -DM per Wilder rules
    up_move = high - prev_high
    down_move = prev_low - low
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

    # Wilder smoothing (RMA) approximation using ewm(alpha=1/n)
    tr_rma = true_range.ewm(alpha=1.0 / n, adjust=False).mean()
    plus_dm_rma = plus_dm.ewm(alpha=1.0 / n, adjust=False).mean()
    minus_dm_rma = minus_dm.ewm(alpha=1.0 / n, adjust=False).mean()

    # Directional Indicators
    plus_di = 100.0 * (plus_dm_rma / tr_rma)
    minus_di = 100.0 * (minus_dm_rma / tr_rma)

    # DX and ADX
    denom = (plus_di + minus_di).replace(0, np.nan)
    dx = (plus_di - minus_di).abs() / denom * 100.0
    adx = dx.ewm(alpha=1.0 / n, adjust=False).mean().fillna(0.0)

    df['plus_di'] = plus_di.fillna(0.0)
    df['minus_di'] = minus_di.fillna(0.0)
    df['adx'] = adx

    # ATR (14) using Wilder-style smoothing to be consistent
    df['atr'] = tr_rma
    
    return df

def is_trading_session():
    """ตรวจสอบว่าอยู่ในช่วงเวลา Asia, London หรือ NY session หรือไม่"""
    now = datetime.now().time()

    # Asia Session: 07:00 - 15:00
    asia_start = dt_time(7, 0)
    asia_end = dt_time(15, 0)

    # London Session: 15:00 - 23:59
    london_start = dt_time(15, 0)
    london_end = dt_time(23, 59)

    # NY Session: 20:00 - 05:00
    ny_start = dt_time(20, 0)
    ny_end = dt_time(5, 0)

    return (
        (asia_start <= now < asia_end) or
        (london_start <= now <= london_end) or
        (now >= ny_start or now < ny_end)
    )


def calculate_lot_size(
    account_balance: float,
    risk_pct: float,
    entry_price: float,
    sl_price: float,
    point_size: float = 0.01,
    value_per_point_per_lot: float = 1.0,
    min_lot: float = 0.01,
    max_lot: float = 0.1,
    lot_precision: int = 2,
):
    """Calculate lot size using dollar risk per pip/point.

    Args:
        account_balance: account balance in USD
        risk_pct: percent of balance to risk (e.g., 1.5)
        entry_price: trade entry price
        sl_price: stop loss price
        point_size: price move equivalent to 1 point/pip (e.g., 0.0001 for GBPUSD, 0.01 for XAUUSD)
        value_per_point_per_lot: USD value per 1 point for 1 standard lot (e.g., ~10 for GBPUSD)
        min_lot, max_lot: lot bounds
        lot_precision: decimals to round lot to (e.g., 2 -> 0.01)

    Returns:
        float: lot size rounded to lot_precision and clamped between min_lot and max_lot
    """
    sl_distance_points = abs(entry_price - sl_price) / point_size
    if sl_distance_points <= 0:
        return round(min_lot, lot_precision)

    dollar_risk_per_lot = sl_distance_points * value_per_point_per_lot
    if dollar_risk_per_lot <= 0:
        return round(min_lot, lot_precision)

    risk_amount = account_balance * (risk_pct / 100.0)
    raw_lots = risk_amount / dollar_risk_per_lot
    lots = max(min_lot, min(max_lot, raw_lots))
    return round(lots, lot_precision)

def golden_trend_system(
    df: pd.DataFrame,
    risk_pct=1.5,
    account_balance=10000,
    macd_hist_threshold: float = 0.5,
    adx_threshold: float = 25.0,
    rsi_buy_max: float = 65.0,
    rsi_sell_min: float = 35.0,
    sl_multiplier: float = 1.5,
    tp_multiplier: float = 2.5,
    require_pullback_to_ema20: bool = False,
    # instrument sizing (for forex vs XAU)
    point_size: float = 0.01,
    value_per_point_per_lot: float = 1.0,
    min_lot: float = 0.01,
    max_lot: float = 0.1,
    lot_precision: int = 2,
):
    """
    Golden Trend System สำหรับ XAUUSD พร้อมจำลอง Spread และ Commission
    
    Args:
        df: DataFrame with OHLC data
        risk_pct: Risk percentage per trade (1-2%)
        account_balance: Account balance for position sizing
    
    Returns:
        dict: {
            'signal': 'BUY'/'SELL'/'HOLD',
            'entry_price': float,
            'sl_price': float, 
            'tp_price': float,
            'lot_size': float,
            'reason': str
        }
    """
    
    # ตรวจสอบข้อมูลเพียงพอ
    if len(df) < 200:
        return {'signal': 'HOLD', 'reason': 'ข้อมูลไม่เพียงพอ (ต้อง >= 200 candles)'}
    
    # คำนวณ indicators
    df = calculate_indicators(df)
    
    # ใช้ข้อมูล candle ล่าสุด (closed candle)
    current = df.iloc[-1]
    
    # ตรวจสอบเวลา trading
    if not is_trading_session():
        return {'signal': 'HOLD', 'reason': 'นอกเวลา Asia/London/NY session'}
    
    # ค่า Spread และ Commission (Exness Zero)
    spread = 0.0  # Zero spread account
    commission_per_lot = 7.0  # $7 per lot per side

    # เงื่อนไข BUY Setup
    buy_conditions = [
        current['ema20'] > current['ema50'],           # EMA20 > EMA50
        current['ema50'] > current['ema200'],          # EMA50 > EMA200
        current['macd'] > -0.5,                        # MACD > -0.5 (loose)
        current['macd_histogram'] >= macd_hist_threshold,  # MACD histogram momentum confirmation
        40 <= current['rsi'] <= rsi_buy_max,           # RSI between 40-rsi_buy_max
        current['adx'] >= adx_threshold,               # ADX stronger trend threshold
        current.get('plus_di', 0) > current.get('minus_di', 0)  # DI polarity: +DI > -DI for BUY
    ]
    
    # เงื่อนไข SELL Setup
    sell_conditions = [
        current['ema20'] < current['ema50'],           # EMA20 < EMA50
        current['ema50'] < current['ema200'],          # EMA50 < EMA200
        current['macd'] < 0.5,                         # MACD < 0.5 (loose)
        current['macd_histogram'] <= -macd_hist_threshold, # MACD histogram momentum confirmation
        rsi_sell_min <= current['rsi'] <= 60,          # RSI between rsi_sell_min-60
        current['adx'] >= adx_threshold,               # ADX stronger trend threshold
        current.get('plus_di', 0) < current.get('minus_di', 0)  # DI polarity: +DI < -DI for SELL
    ]
    
    entry_price = current['close']
    atr = current['atr']

    # BUY Signal
    if require_pullback_to_ema20:
        # require price to be near ema20 (within 0.5% by default)
        if not (abs((current['close'] - current['ema20']) / current['ema20']) <= 0.005):
            return {'signal': 'HOLD', 'reason': 'รอ pullback to EMA20'}

    if all(buy_conditions):
        sl_price = entry_price - (sl_multiplier * atr)
        tp_price = entry_price + (tp_multiplier * atr)

        # คำนวณ lot size using helper (supports forex pip sizing)
        lot_size = calculate_lot_size(
            account_balance=account_balance,
            risk_pct=risk_pct,
            entry_price=entry_price,
            sl_price=sl_price,
            point_size=point_size,
            value_per_point_per_lot=value_per_point_per_lot,
            min_lot=min_lot,
            max_lot=max_lot,
            lot_precision=lot_precision,
        )

        return {
            'signal': 'BUY',
            'entry_price': entry_price,
            'sl_price': sl_price,
            'tp_price': tp_price,
            'lot_size': lot_size,
            'atr': atr,
            'reason': f'Golden Trend BUY: EMA Stack✅ MACD+✅ RSI:{current["rsi"]:.1f}✅ ADX:{current["adx"]:.1f}✅',
            'spread': spread,
            'commission': commission_per_lot * lot_size * 2
        }

    # SELL Signal
    elif all(sell_conditions):
        sl_price = entry_price + (sl_multiplier * atr)
        tp_price = entry_price - (tp_multiplier * atr)

        # คำนวณ lot size using helper (supports forex pip sizing)
        lot_size = calculate_lot_size(
            account_balance=account_balance,
            risk_pct=risk_pct,
            entry_price=entry_price,
            sl_price=sl_price,
            point_size=point_size,
            value_per_point_per_lot=value_per_point_per_lot,
            min_lot=min_lot,
            max_lot=max_lot,
            lot_precision=lot_precision,
        )

        return {
            'signal': 'SELL',
            'entry_price': entry_price,
            'sl_price': sl_price,
            'tp_price': tp_price,
            'lot_size': lot_size,
            'atr': atr,
            'reason': f'Golden Trend SELL: EMA Stack✅ MACD-✅ RSI:{current["rsi"]:.1f}✅ ADX:{current["adx"]:.1f}✅',
            'spread': spread,
            'commission': commission_per_lot * lot_size * 2
        }

    # วิเคราะห์เงื่อนไขที่ไม่ผ่าน
    failed_conditions = []
    if not (current['ema20'] > current['ema50'] > current['ema200']) and not (current['ema20'] < current['ema50'] < current['ema200']):
        failed_conditions.append("EMA Stack")
    if abs(current['macd']) > 2:
        failed_conditions.append("MACD ผันผวนมาก")
    if current['rsi'] < 30 or current['rsi'] > 70:
        failed_conditions.append(f"RSI:{current['rsi']:.1f} extreme")
    if current['adx'] <= 15:
        failed_conditions.append(f"ADX:{current['adx']:.1f} ไม่มี trend")

    return {
        'signal': 'HOLD',
        'reason': f'รอสัญญาณ: {", ".join(failed_conditions) if failed_conditions else "ตรวจสอบเงื่อนไข"}'
    }

