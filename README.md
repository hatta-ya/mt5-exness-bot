# MT5 Exness Forex Bot (macOS Demo Version)# MT5 Exness Forex Bot (Python)

🚀 **Live Demo Trading Bot สำหรับ XAUUSD (Gold)**บอตเทรด Forex สำหรับ Exness ผ่าน MetaTrader 5 (MT5) — โครงสร้างพร้อมรันบนบัญชีเดโมได้ทันที

## 📊 **Features:**## โครงสร้างโปรเจกต์

- ✅ Live Demo Trading (Yahoo Finance data)```

- ✅ EMA Crossover Strategy (9/21)mt5-exness-forex-bot/

- ✅ Auto Risk Management (SL/TP)├─ README.md

- ✅ Real-time P&L tracking├─ requirements.txt

- ✅ Daily profit/loss limits├─ .env.example

- ✅ Backtesting engine├─ config.py

- ✅ Strategy analysis tools├─ main.py

├─ strategy.py

## 🎯 **Current Settings:**├─ trader.py

- **Symbol**: XAUUSD (Gold)├─ risk.py

- **Timeframe**: Daily (D1)├─ utils/

- **Strategy**: EMA 9/21 Crossover│ └─ logger.py

- **Risk**: SL 50 pips, TP 100 pips├─ backtest.py

- **Lot Size**: 0.01├─ data/

└─ logs/

## 🚀 **Quick Start:**```

### 1. Install Dependencies:## ขั้นตอนเริ่มต้น

````bash1) ติดตั้ง Python 3.9–3.12 และติดตั้งไลบรารี

pip install -r requirements.txt```bash

```pip install -r requirements.txt

````

### 2. Configure Settings:2) เปิด MetaTrader 5 และล็อกอินบัญชี **Exness** (แนะนำเริ่มจากบัญชีเดโม)

Edit `.env` file with your preferences3) คัดลอกไฟล์ `.env.example` เป็น `.env` แล้วแก้ค่าที่ต้องการ

4. รันบอต (โหมดสัญญาณทุก ๆ 5 นาที)

### 3. Run Trading Bot:```bash

````bashpython main.py

# Live demo trading```

python live_demo.py

> **สำคัญ:** ทดสอบบนเดโมก่อนเสมอ ตรวจสอบ size order, SL/TP, และเงื่อนไข risk ว่าถูกต้องกับพอร์ตของคุณ

# One-time demo

python demo_mode.py## ตั้งรันอัตโนมัติทุก 5 นาที (บน Linux/macOS)

```bash

# Backtest performance*/5 * * * * /usr/bin/python3 /path/to/mt5-exness-forex-bot/main.py >> /path/to/mt5-exness-forex-bot/logs/cron.log 2>&1

python backtest_mac.py```



# Analyze strategy## Troubleshooting

python analyze_strategy.py- ถ้า `MetaTrader5.initialize()` ล้มเหลว: ให้เปิด MT5 ไว้ และตรวจสอบว่าใช้ MT5 64-bit ตรงกับไลบรารี

```- ถ้า `symbol_info` เป็น `None` หรือ `visible=False`: ตั้งค่า Market Watch ให้โชว์สัญลักษณ์ หรือให้ `trader.ensure_symbol(symbol)` ทำงานก่อน

- ถ้า order ไม่ถูกส่ง: ตรวจสอบ `result.comment` และ `result.retcode` ใน log

## 📁 **File Structure:**

```## คำเตือนด้านความเสี่ยง

📁 Core Files (Required):การเทรดมีความเสี่ยงสูง โปรเจกต์นี้เพื่อการศึกษา ผู้ใช้รับผิดชอบผลลัพธ์เองทั้งหมด

├── live_demo.py       # Main live trading bot
├── config.py          # Configuration loader
├── strategy.py        # EMA crossover strategy
├── risk.py           # Risk management
├── .env              # Settings file
└── utils/logger.py   # Logging system

📁 Testing/Analysis:
├── backtest_mac.py    # Historical backtesting
├── demo_mode.py       # Quick demo run
└── analyze_strategy.py # Strategy analysis

📁 Configuration:
├── requirements.txt   # Python dependencies
└── .env.example      # Settings template
````

## ⚙️ **Configuration (.env):**

```bash
# Trading Parameters
SYMBOL=XAUUSD
TIMEFRAME=D1
LOT=0.01
SL_PIPS=50
TP_PIPS=100

# Risk Management
DAILY_PROFIT_TARGET=2.0
DAILY_DRAWDOWN_LIMIT=2.0
MAX_OPEN_TRADES=1

# Strategy
EMA_SHORT=9
EMA_LONG=21

# Backtest
BACKTEST_DAYS=90
```

## 📊 **Backtest Results:**

- **ROI**: +1.25% (90 days)
- **Win Rate**: 75% (3/4 trades)
- **Risk/Reward**: 2:1
- **Max Drawdown**: -$25

## 🎮 **Controls:**

- **Start**: `python live_demo.py`
- **Stop**: `Ctrl+C`
- **View Status**: Real-time updates every 10 seconds

## ⚠️ **Important Notes:**

- This is a **DEMO VERSION** for macOS
- Uses **Yahoo Finance** data (not real-time tick data)
- For **live trading**, migrate to Windows + MT5
- **No real money** involved in demo mode

## 🔄 **Migration to Live Trading:**

1. Move to Windows environment
2. Install MetaTrader 5
3. Add MT5 connection credentials to `.env`
4. Use original MT5-based files (not included in this demo)

## 📞 **Support:**

This demo version is for **testing and strategy development** purposes only.

---

🎯 **Happy Trading!** 🚀
