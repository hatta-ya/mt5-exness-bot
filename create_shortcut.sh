#!/bin/bash

# สร้าง Desktop Shortcut สำหรับ MT5 Trading Bot

echo "🔗 Creating Desktop Shortcut..."

# สร้าง AppleScript app
cat > ~/Desktop/MT5_Trading_Bot.app << 'EOF'
#!/usr/bin/osascript

tell application "Terminal"
    do script "cd '/Users/fdev/Documents/Docs/mt5-exness-forex-bot' && ./\"🚀 Start Trading Bot.command\""
    activate
end tell
EOF

# ให้สิทธิ์รัน
chmod +x ~/Desktop/MT5_Trading_Bot.app

echo "✅ Desktop shortcut created: ~/Desktop/MT5_Trading_Bot.app"
echo "🖱️ Double-click to run the trading bot!"