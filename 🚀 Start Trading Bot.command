#!/bin/bash

# 🚀 MT5 Forex Trading Bot Launcher for macOS
# ดับเบิลคลิกเพื่อรัน

echo "🚀 Starting MT5 Forex Trading Bot..."

# เปลี่ยนไปยังโฟลเดอร์ที่มีไฟล์นี้
cd "$(dirname "$0")"

# ตรวจสอบว่ามี virtual environment หรือไม่
if [ -d ".venv" ]; then
    echo "✅ Using virtual environment..."
    # Run the package entrypoint as a module so package imports work
    .venv/bin/python -m src.run_bot
else
    echo "⚙️ Using system Python..."
    python3 -m src.run_bot
fi

# รอให้ผู้ใช้กด Enter ก่อนปิด Terminal
echo ""
echo "📱 กด Enter เพื่อปิดหน้าต่าง..."
read