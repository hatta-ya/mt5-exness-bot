#!/bin/bash

# 🚀 MT5 Forex Trading Bot Launcher for macOS
# ดับเบิลคลิกเพื่อรัน

echo "🚀 Starting MT5 Forex Trading Bot..."

# เปลี่ยนไปยังโฟลเดอร์ที่มีไฟล์นี้
cd "$(dirname "$0")"

# ตรวจสอบว่ามี virtual environment หรือไม่
if [ -d ".venv" ]; then
    echo "✅ Using virtual environment..."
    .venv/bin/python run_bot.py
else
    echo "⚙️ Using system Python..."
    python3 run_bot.py
fi

# รอให้ผู้ใช้กด Enter ก่อนปิด Terminal
echo ""
echo "📱 กด Enter เพื่อปิดหน้าต่าง..."
read