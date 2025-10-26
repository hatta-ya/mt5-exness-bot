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
║                  🚀 MT5 Forex Trading Bot                    ║
║                     macOS Demo Version                       ║
║                                                              ║
║               💰 {symbol_display:^30}                ║
╚══════════════════════════════════════════════════════════════╝
    """)
    print(f"📅 วันที่: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"💻 ระบบ: macOS Compatible")
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
        with open(".env", "r", encoding="utf-8") as f:
            lines = f.readlines()
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#"):
                print(f"📝 {line}")
    except FileNotFoundError:
        print("❌ ไม่พบไฟล์ .env")
    except Exception as e:
        print(f"❌ Error: {e}")
    input("\n📱 กด Enter เพื่อกลับเมนูหลัก...")

def edit_settings():
    print("\n⚙️ แก้ไขการตั้งค่า:")
    print("=" * 30)
    print("💡 เปิดไฟล์ .env ด้วย TextEdit...")
    try:
        import subprocess
        subprocess.run(["open", "-a", "TextEdit", ".env"])
        print("✅ เปิดไฟล์ .env แล้ว")
    except Exception as e:
        print(f"❌ Error: {e}")
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
        ]

        available_scripts = [(label, fname) for (label, fname) in candidate_scripts if os.path.exists(os.path.join(script_dir, fname))]

        show_menu(available_scripts)

        try:
            choice = input("\n🎯 เลือก: ").strip()
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
