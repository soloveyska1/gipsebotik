#!/bin/bash
cd /root/gipsr_bot
pkill -f bot.py || true
sleep 2
python3 bot.py > bot_output.log 2>&1 &
echo "Бот запущен!"
chmod +x /root/gipsr_bot/start.sh