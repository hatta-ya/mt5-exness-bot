#!/usr/bin/env python3
"""
🚀 MT5 Forex Trading Bot - Main Launcher (inside src package)
"""

import sys
import os
import time
import importlib
from datetime import datetime

def clear_screen():
    import platform
    if platform.system() == "Windows":
        os.system('cls')
    else:
        os.system('clear')

def print_banner():
    from dotenv import load_dotenv
    load_dotenv()
    symbol = os.getenv("SYMBOL", "XAUUSD")
    symbol_display = {
        "XAUUSD": "XAUUSD (Gold)",
        "BTCUSD": "BTCUSD (Bitcoin)",
        "EURUSD": "EURUSD (Euro)",
        "GBPUSD": "GBPUSD (Pound)",
        "USDJPY": "USDJPY (Yen)"
    }.get(symbol, symbol)
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                    MT5 Forex Trading Bot                     ║
║                         Demo Version                         ║
║                                                              ║
║                         {symbol_display}                        ║
╚══════════════════════════════════════════════════════════════╝
    """)
    print(f"📅 วันที่: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"💻 ระบบ: Windows")
    print("=" * 60)

def check_dependencies():
    try:
        import pandas
        import numpy
        import yfinance
        from dotenv import load_dotenv
        print("✅ Dependencies: OK")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("🔧 Please install: pip install -r requirements.txt")
        return False

def show_menu(available_scripts):
    print("\n🎯 เลือกโหมดการใช้งาน:")
    print("=" * 40)
    for i, (label, _) in enumerate(available_scripts, start=1):
        print(f"{i}. {label}")
    base = len(available_scripts)
    print(f"{base+1}. ⚙️ Settings (.env)")
    print(f"{base+2}. 📊 View Current Config")
    print("0. ❌ Exit")
    print("=" * 40)

def run_script(script_name, description, script_dir):
    """Run a moved script by importing its module and calling main() if available"""
    print(f"\n🔄 กำลังรัน {description}...")
    print("=" * 50)

    try:
        # Add parent directory to sys.path to allow src package imports
        parent_dir = os.path.dirname(script_dir)
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
            
        module_name = os.path.splitext(script_name)[0]
        full_module = f"src.{module_name}"
        mod = importlib.import_module(full_module)
        if hasattr(mod, 'main'):
            mod.main()
        else:
            print(f"❌ Module {full_module} ไม่มีฟังก์ชัน main()")
    except Exception as e:
        print(f"\n❌ Error while running {description}: {e}")

    input("\n📱 กด Enter เพื่อกลับเมนูหลัก...")

def show_settings():
    print("\n⚙️ การตั้งค่าปัจจุบัน:")
    print("=" * 40)
    try:
        # Look for .env file in parent directory (project root)
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#"):
                print(f"📝 {line}")
    except FileNotFoundError:
        print("❌ ไม่พบไฟล์ .env")
        print(f"💡 คาดหวังไฟล์ที่: {env_path}")
    except Exception as e:
        print(f"❌ Error: {e}")
    input("\n📱 กด Enter เพื่อกลับเมนูหลัก...")

def edit_settings():
    print("\n⚙️ แก้ไขการตั้งค่า:")
    print("=" * 30)
    print("💡 เปิดไฟล์ .env ด้วย Notepad...")
    try:
        import subprocess
        import platform
        
        # Check if .env file exists, create if not
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
        if not os.path.exists(env_path):
            # Create default .env file
            default_env = """# --- Trading Params ---
SYMBOL=XAUUSD
TIMEFRAME=H4
LOT=0.05
SL_PIPS=70
TP_PIPS=210
MAGIC=234000
MAX_SLIPPAGE=10

# --- Risk Management ---
RISK_PERCENT=1.5
MAX_POSITIONS=3
MAX_CONSECUTIVE_LOSSES=3

# --- Backtest ---
BACKTEST_DAYS=365

# --- MT5 Connection ---
MT5_LOGIN=your_login
MT5_PASSWORD=your_password
MT5_SERVER=your_server
"""
            with open(env_path, "w", encoding="utf-8") as f:
                f.write(default_env)
            print(f"✅ สร้างไฟล์ .env ใหม่ที่ {env_path}")
        
        # Open with appropriate editor based on OS
        if platform.system() == "Windows":
            subprocess.run(["notepad.exe", env_path])
        elif platform.system() == "Darwin":  # macOS
            subprocess.run(["open", "-a", "TextEdit", env_path])
        else:  # Linux
            subprocess.run(["nano", env_path])
            
        print("✅ เปิดไฟล์ .env แล้ว")
    except Exception as e:
        print(f"❌ Error: {e}")
        print("💡 กรุณาแก้ไขไฟล์ .env ด้วยตัวเองใน text editor")
    input("\n📱 กด Enter เพื่อกลับเมนูหลัก...")

def main():
    # ensure cwd is package src directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    while True:
        clear_screen()
        print_banner()
        if not check_dependencies():
            input("\n📱 กด Enter เพื่อออก...")
            sys.exit(1)

        candidate_scripts = [
            ("📈 Golden Trend Backtest", "golden_backtest.py"),
            ("🚀 Live Trading (MT5)", "mt5_trader.py"),
        ]

        available_scripts = [(label, fname) for (label, fname) in candidate_scripts if os.path.exists(os.path.join(script_dir, fname))]

        show_menu(available_scripts)

        try:
            choice = input(f"\n🎯 เลือก [0-{len(available_scripts)+2}]: ").strip()
            if choice.isdigit():
                num = int(choice)
                if num == 0:
                    clear_screen()
                    print("👋 ขอบคุณที่ใช้งาน MT5 Forex Trading Bot!")
                    print("🎯 Happy Trading!")
                    sys.exit(0)

                scripts_count = len(available_scripts)
                if 1 <= num <= scripts_count:
                    label, fname = available_scripts[num-1]
                    run_script(fname, label, script_dir)
                    continue

                if num == scripts_count + 1:
                    edit_settings()
                    continue
                if num == scripts_count + 2:
                    show_settings()
                    continue

            print("❌ การเลือกไม่ถูกต้อง — กรุณาเลือกหมายเลขที่แสดงในเมนู")
            time.sleep(2)

        except KeyboardInterrupt:
            clear_screen()
            print("\n👋 ขอบคุณที่ใช้งาน!")
            sys.exit(0)
        except Exception as e:
            print(f"❌ Error: {e}")
            time.sleep(2)

if __name__ == "__main__":
    main()
