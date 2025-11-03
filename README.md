# 🏆 Golden Trend Trading System (macOS Demo Version)# 🏆 Golden Trend Trading System (macOS Demo Version)

🚀 **Advanced Multi-Indicator Trading Bot สำหรับ XAUUSD (Gold)**🚀 **Advanced Multi-Indicator Trading Bot สำหรับ XAUUSD (Gold)**

## 📊 **Golden Trend System Features:**## 📊 **Golden Trend System Features:**

- ✅ **Multi-Indicator Strategy**: EMA(20,50,200) + MACD + RSI + ADX + ATR- ✅ **Multi-Indicator Strategy**: EMA(20,50,200) + MACD + RSI + ADX + ATR

- ✅ **Live Demo Trading** (Yahoo Finance data)- ✅ **Live Demo Trading** (Yahoo Finance data)

- ✅ **Dynamic Risk Management** (ATR-based SL/TP)- ✅ **Dynamic Risk Management** (ATR-based SL/TP)

- ✅ **Real-time P&L tracking**- ✅ **Real-time P&L tracking**

- ✅ **Comprehensive Backtesting** with detailed statistics- ✅ **Comprehensive Backtesting** with detailed statistics

- ✅ **100% Win Rate** backtesting results (1,538 trades)- ✅ **100% Win Rate** backtesting results

- ✅ **4,002% ROI** in 157 days- ✅ **Daily profit/loss monitoring**

- ✅ **Daily profit/loss monitoring**

## 🎯 **Golden Trend System Settings:**

## 🎯 **Golden Trend System Settings:**

- **Symbol**: XAUUSD (Gold)

- **Symbol**: XAUUSD (Gold)- **Timeframe**: Daily (D1)

- **Timeframe**: Daily (D1) - **Strategy**: Golden Trend Multi-Indicator System

- **Strategy**: Golden Trend Multi-Indicator System- **Technical Indicators**:

- **Technical Indicators**: - EMA Short: 20, Long: 50, Very Long: 200
  - EMA Short: 20, Long: 50, Very Long: 200 - MACD: 12,26,9

  - MACD: 12,26,9 periods - RSI: 14 periods

  - RSI: 14 periods (30-70 range) - ADX: 14 periods

  - ADX: 14 periods (>20 for trend strength) - ATR: 14 periods

  - ATR: 14 periods (for dynamic SL/TP)- **Risk Management**: 1.5% per trade with ATR-based SL/TP

- **Risk Management**: 1.5% per trade with ATR-based SL/TP- **Lot Size**: Dynamic based on account risk

- **Lot Size**: Dynamic based on account risk

## 🚀 **Quick Start:**

## 🚀 **Quick Start:**

### 1. Install Dependencies:

### 1. Install Dependencies:

````bash

```bashpip install -r requirements.txt

pip install -r requirements.txt```

````

### 2. Configure Settings:

### 2. Configure Settings:

Edit `.env` file with your preferences3) คัดลอกไฟล์ `.env.example` เป็น `.env` แล้วแก้ค่าที่ต้องการ

Copy `.env.example` to `.env` and adjust parameters if needed:

4. รันบอต (โหมดสัญญาณทุก ๆ 5 นาที)

````bash

cp .env.example .env### 3. Run Trading Bot:```bash

````

````bashpython main.py

### 3. Launch Golden Trend System:

### 3. Quick Start:
# 🏆 Golden Trend Trading System (macOS Demo)

Golden Trend is a multi-indicator strategy and demo trading/backtesting framework focused on XAUUSD (Gold) in this repository. The code supports indicator calculation, ATR-based dynamic SL/TP, position sizing by risk percent, and a simple backtest engine that uses Yahoo Finance for historical data.

This README has been updated to match the repository's current structure and defaults (XAUUSD).

## Quick overview

- Default instrument: XAUUSD (Gold)
- Strategy: EMA(20,50,200) trend + MACD + RSI + ADX confirmation + ATR-based SL/TP
- Position sizing: percent risk per trade (default 1.5%) with a helper to convert SL distance into lots
- Backtesting: `src/golden_backtest.py` (uses Yahoo Finance via `yfinance`)
- Launcher / menu: `src/run_bot.py`

## Files you care about

- `src/strategy.py` — core strategy and indicator calculations
- `src/golden_backtest.py` — backtest runner and P&L simulation
- `src/run_bot.py` — simple CLI launcher (menu)
- `src/config.py` — loads `.env` configuration into Python variables
- `src/utils/logger.py` — logging helper
- `.env` — runtime settings (symbol, timeframe, sizing, risk, etc.)
- `requirements.txt` — Python dependencies

## Important `.env` keys (defaults used by the project)

Edit `.env` to change behavior. Key values used by the code:

- `SYMBOL` — instrument symbol (MT5 style). Default in repo: `XAUUSD`
- `TIMEFRAME` — timeframe short code, e.g. `H4`
- `LOT` — fallback lot
- `SL_PIPS`, `TP_PIPS` — fallback SL/TP in pips (used if strategy doesn't return explicit prices)
- `RISK_PERCENT` — percent of account to risk per trade (default 1.5)
- `BACKTEST_DAYS` — how many days of history to request from Yahoo Finance

Instrument sizing (used for lot sizing and P&L):
- `POINT_SIZE` — price move equivalent to one point/pip. For XAUUSD the repo defaults to `0.01`.
- `VALUE_PER_PIP_PER_LOT` — USD value per 1 point for 1 standard lot. For XAUUSD default is `1.0` in this repo.

Example: `.env` excerpt (already in repo):

```
SYMBOL=XAUUSD
TIMEFRAME=H4
POINT_SIZE=0.01
VALUE_PER_PIP_PER_LOT=1.0
RISK_PERCENT=1.5
BACKTEST_DAYS=365
```

## How to run

Install dependencies (prefer a venv):

```bash
python3 -m pip install -r requirements.txt
```

Run the interactive launcher (recommended):

```bash
python3 src/run_bot.py
```

From the launcher choose "Golden Trend Backtest" to run the backtest with your `.env` settings.

You can also run the backtest directly:

```bash
python3 -m src.golden_backtest
```

The backtest downloads historical data from Yahoo Finance (hourly bars by default), calculates indicators, generates signals, simulates entries/exits, and prints a performance summary.

## Notes on instrument support

- The code contains helpers to support different instruments by configuring `POINT_SIZE` and `VALUE_PER_PIP_PER_LOT` in `.env`.
- The repository is configured by default for XAUUSD (point size 0.01, value per point ≈ $1). If you change to forex pairs (e.g., `GBPUSD`), update `POINT_SIZE=0.0001` and `VALUE_PER_PIP_PER_LOT=10.0` accordingly.

## What I changed recently (summary)

- Added a safe `calculate_lot_size()` helper in `src/strategy.py` that converts SL distance to pips and computes lot size using dollar risk per lot.
- Wired `POINT_SIZE` and `VALUE_PER_PIP_PER_LOT` from `.env` into `src/config.py` and used them in backtest P&L calculations.
- Reverted repository defaults to XAUUSD per your request.

## Tips & next steps

- To test a different starting balance, run `src/golden_backtest.py` directly and input the starting balance prompt.
- If you plan to live trade with MetaTrader5, move to Windows and use the MT5-specific modules; this demo uses Yahoo Finance and is not a live execution engine.
- Consider increasing `BACKTEST_DAYS` or adding more data history to improve the statistical significance of results.

## Disclaimer

Trading is risky. This project is for educational and strategy development only. You are responsible for testing, verifying, and using the code.

------

If you'd like, I can:

- Run a quick backtest with the current `.env` and paste the results here.
- Update the README further with examples of typical `.env` configurations for other instruments (FX, XAUUSD).
- Add small unit tests for the lot-sizing helper.

Tell me which you want next.

````
