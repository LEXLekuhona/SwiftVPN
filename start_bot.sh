#!/bin/bash
# Скрипт запуска бота с проверкой настроек

echo "🚀 Запуск VPN Telegram Bot..."
echo ""

# Проверка .env файла
if [ ! -f .env ]; then
    echo "❌ Ошибка: .env файл не найден"
    exit 1
fi

# Проверка наличия настроек 3x-ui
if grep -q "USE_X3UI_API=true" .env; then
    echo "✅ 3x-ui API включен"
    X3UI_URL=$(grep "X3UI_API_URL=" .env | cut -d'=' -f2)
    echo "   URL: $X3UI_URL"
else
    echo "⚠️  3x-ui API не включен (USE_X3UI_API не установлен в true)"
fi

echo ""
echo "📋 Запуск бота..."
echo "💡 Логи: tail -f logs/bot.log"
echo "💡 Для остановки: Ctrl+C"
echo ""

python main.py
