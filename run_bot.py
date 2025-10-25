#!/usr/bin/env python3
"""
🚀 MT5 Forex Trading Bot - Main Launcher
ดับเบิลคลิกเพื่อเริ่มใช้งาน
"""

import sys
import os
import subprocess
import time
from datetime import datetime

def clear_screen():
    """ล้างหน้าจอ"""
    os.system('clear')

def print_banner():
    """แสดงแบนเนอร์"""
    # โหลด SYMBOL จาก .env
    from dotenv import load_dotenv
    load_dotenv()
    symbol = os.getenv("SYMBOL", "XAUUSD")
    
    # กำหนดชื่อ symbol ที่แสดง
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
    """ตรวจสอบ dependencies"""
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

def show_menu():
    """แสดงเมนูหลัก"""
    print("\n🎯 เลือกโหมดการใช้งาน:")
    print("=" * 40)
    print("1. 🏆 Golden Trend Live Demo")
    print("2. 🔍 Test Golden Trend System")  
    print("3. 🟢 REAL TRADING (เงินจริง)")
    print("4. 📈 Golden Trend Backtest")
    print("5. ⚙️ Settings (.env)")
    print("6. 📊 View Current Config")
    print("0. ❌ Exit")
    print("=" * 40)

def run_script(script_name, description):
    """รันสคริปต์"""
    print(f"\n🔄 กำลังรัน {description}...")
    print("=" * 50)
    
    try:
        # รันสคริปต์ใน virtual environment - ใช้ path ปัจจุบัน
        current_dir = os.path.dirname(os.path.abspath(__file__))
        venv_python = os.path.join(current_dir, ".venv", "bin", "python")
        
        if os.path.exists(venv_python):
            cmd = [venv_python, script_name]
        else:
            cmd = ["python3", script_name]
        
        process = subprocess.run(cmd, check=True)
        
        if process.returncode == 0:
            print(f"\n✅ {description} เสร็จสิ้น")
        else:
            print(f"\n❌ {description} เกิดข้อผิดพลาด")
            
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error: {e}")
    except KeyboardInterrupt:
        print(f"\n🛑 {description} ถูกหยุดโดยผู้ใช้")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
    
    input("\n📱 กด Enter เพื่อกลับเมนูหลัก...")

def show_settings():
    """แสดงการตั้งค่า"""
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
    """แก้ไขการตั้งค่า"""
    print("\n⚙️ แก้ไขการตั้งค่า:")
    print("=" * 30)
    print("💡 เปิดไฟล์ .env ด้วย TextEdit...")
    
    try:
        subprocess.run(["open", "-a", "TextEdit", ".env"])
        print("✅ เปิดไฟล์ .env แล้ว")
        print("📝 แก้ไขแล้วบันทึก จากนั้นรันโปรแกรมใหม่")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    input("\n📱 กด Enter เพื่อกลับเมนูหลัก...")

def main():
    """ฟังก์ชันหลัก"""
    # เปลี่ยน directory ไปที่โฟลเดอร์โปรแกรม
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    while True:
        clear_screen()
        print_banner()
        
        # ตรวจสอบ dependencies
        if not check_dependencies():
            input("\n📱 กด Enter เพื่อออก...")
            sys.exit(1)
        
        show_menu()
        
        try:
            choice = input("\n🎯 เลือก (0-6): ").strip()
            
            if choice == "1":
                run_script("golden_live_demo.py", "🏆 Golden Trend Live Demo")
            elif choice == "2":
                run_script("test_golden_trend.py", "🔍 Golden Trend System Test")
            elif choice == "3":
                run_script("real_trading.py", "🔴 REAL TRADING")
            elif choice == "4":
                run_script("golden_backtest.py", "🏆 Golden Trend Backtest")
            elif choice == "5":
                edit_settings()
            elif choice == "6":
                show_settings()
            elif choice == "0":
                clear_screen()
                print("👋 ขอบคุณที่ใช้งาน MT5 Forex Trading Bot!")
                print("🎯 Happy Trading!")
                sys.exit(0)
            else:
                print("❌ กรุณาเลือก 0-6 เท่านั้น")
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