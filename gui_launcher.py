#!/usr/bin/env python3
"""
🎮 MT5 Trading Bot - GUI Launcher
ใช้ tkinter สำหรับ GUI แบบง่าย
"""

import tkinter as tk
from tkinter import messagebox, scrolledtext
import subprocess
import threading
import os
import sys

class TradingBotGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🚀 MT5 Forex Trading Bot")
        self.root.geometry("600x500")
        self.root.configure(bg="#1e1e1e")
        
        # เปลี่ยน directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(script_dir)
        
        self.setup_ui()
        
    def setup_ui(self):
        """สร้าง UI"""
        # Header
        header_frame = tk.Frame(self.root, bg="#1e1e1e")
        header_frame.pack(pady=20)
        
        title_label = tk.Label(
            header_frame, 
            text="🏆 Golden Trend Trading System", 
            font=("Arial", 20, "bold"),
            fg="#00ff88",
            bg="#1e1e1e"
        )
        title_label.pack()
        
        subtitle_label = tk.Label(
            header_frame,
            text="💰 Advanced Multi-Indicator XAUUSD Trading - macOS Demo",
            font=("Arial", 12),
            fg="#ffaa00", 
            bg="#1e1e1e"
        )
        subtitle_label.pack()
        
        # Buttons Frame
        button_frame = tk.Frame(self.root, bg="#1e1e1e")
        button_frame.pack(pady=20)
        
        # Main Buttons
        self.create_button(button_frame, "🏆 Golden Trend Live Demo", self.run_golden_live, "#00aa00")
        self.create_button(button_frame, "🔍 Test Golden Trend", self.run_golden_test, "#0088aa")
        self.create_button(button_frame, "📈 Golden Trend Backtest", self.run_golden_backtest, "#aa8800")
        self.create_button(button_frame, "� Real Trading", self.run_real_trading, "#aa0000")
        
        # Settings Frame
        settings_frame = tk.Frame(self.root, bg="#1e1e1e")
        settings_frame.pack(pady=10)
        
        self.create_button(settings_frame, "⚙️ View Settings", self.view_settings, "#666666")
        self.create_button(settings_frame, "📝 Edit Settings", self.edit_settings, "#666666")
        
        # Output Area
        output_frame = tk.Frame(self.root, bg="#1e1e1e")
        output_frame.pack(pady=20, padx=20, fill=tk.BOTH, expand=True)
        
        tk.Label(output_frame, text="📋 Output:", font=("Arial", 12, "bold"), 
                fg="#ffffff", bg="#1e1e1e").pack(anchor="w")
        
        self.output_text = scrolledtext.ScrolledText(
            output_frame,
            height=8,
            bg="#2d2d2d",
            fg="#00ff00",
            font=("Monaco", 10),
            insertbackground="#00ff00"
        )
        self.output_text.pack(fill=tk.BOTH, expand=True)
        
        # Status
        self.status_label = tk.Label(
            self.root,
            text="✅ Ready to Trade",
            font=("Arial", 10),
            fg="#00ff88",
            bg="#1e1e1e"
        )
        self.status_label.pack(pady=5)
        
    def create_button(self, parent, text, command, color):
        """สร้างปุ่ม"""
        btn = tk.Button(
            parent,
            text=text,
            command=command,
            font=("Arial", 11, "bold"),
            bg=color,
            fg="white",
            width=25,
            height=2,
            relief=tk.RAISED,
            cursor="hand2"
        )
        btn.pack(pady=5)
        return btn
        
    def log_output(self, text):
        """แสดงข้อความใน output area"""
        self.output_text.insert(tk.END, f"{text}\n")
        self.output_text.see(tk.END)
        
    def run_command(self, script_name, description):
        """รันคำสั่งใน background"""
        def worker():
            self.status_label.config(text=f"🔄 Running {description}...")
            self.log_output(f"🚀 Starting {description}...")
            
            try:
                venv_python = ".venv/bin/python"
                if os.path.exists(venv_python):
                    cmd = [venv_python, script_name]
                else:
                    cmd = ["python3", script_name]
                
                process = subprocess.Popen(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                
                # อ่าน output แบบ real-time
                while True:
                    output = process.stdout.readline()
                    if output == '' and process.poll() is not None:
                        break
                    if output:
                        self.root.after(0, self.log_output, output.strip())
                
                return_code = process.poll()
                if return_code == 0:
                    self.root.after(0, self.log_output, f"✅ {description} completed successfully!")
                else:
                    self.root.after(0, self.log_output, f"❌ {description} failed with code {return_code}")
                    
            except Exception as e:
                self.root.after(0, self.log_output, f"❌ Error: {str(e)}")
                
            finally:
                self.root.after(0, lambda: self.status_label.config(text="✅ Ready to Trade"))
        
        thread = threading.Thread(target=worker)
        thread.daemon = True
        thread.start()
        
    def run_golden_live(self):
        """รัน Golden Trend Live Demo"""
        self.run_command("golden_live_demo.py", "Golden Trend Live Demo")
        
    def run_golden_test(self):
        """รัน Golden Trend Test"""
        self.run_command("test_golden_trend.py", "Golden Trend System Test")
        
    def run_golden_backtest(self):
        """รัน Golden Trend Backtest"""
        self.run_command("golden_backtest.py", "Golden Trend Backtest")
        
    def run_real_trading(self):
        """รัน Real Trading"""
        result = messagebox.askyesno(
            "⚠️ Warning", 
            "This will start REAL TRADING with real money!\nAre you sure you want to continue?"
        )
        if result:
            self.run_command("real_trading.py", "Real Trading")
        
    def view_settings(self):
        """แสดงการตั้งค่า"""
        try:
            with open(".env", "r") as f:
                content = f.read()
            self.log_output("⚙️ Current Settings:")
            self.log_output("-" * 30)
            for line in content.split('\n'):
                if line.strip() and not line.startswith('#'):
                    self.log_output(line)
            self.log_output("-" * 30)
        except Exception as e:
            self.log_output(f"❌ Error reading settings: {e}")
            
    def edit_settings(self):
        """แก้ไขการตั้งค่า"""
        try:
            subprocess.run(["open", "-a", "TextEdit", ".env"])
            self.log_output("📝 Opening .env file in TextEdit...")
        except Exception as e:
            self.log_output(f"❌ Error opening settings: {e}")
            
    def run(self):
        """เริ่มรัน GUI"""
        self.root.mainloop()

def main():
    """ฟังก์ชันหลัก"""
    app = TradingBotGUI()
    app.run()

if __name__ == "__main__":
    main()