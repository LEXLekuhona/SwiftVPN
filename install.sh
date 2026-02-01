#!/bin/bash

# Скрипт установки VPN Telegram Bot на сервере
# Использование: ./install.sh

set -e

echo "🚀 Установка VPN Telegram Bot..."

# Проверка прав root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Пожалуйста, запустите скрипт от root"
    exit 1
fi

# Определяем путь установки
INSTALL_DIR="/opt/vpn-tg-bot"
CURRENT_DIR=$(pwd)

echo "📁 Путь установки: $INSTALL_DIR"

# Обновляем систему
echo "📦 Обновление системы..."
apt update && apt upgrade -y

# Устанавливаем зависимости
echo "📦 Установка зависимостей..."
apt install -y python3 python3-pip python3-venv git curl

# Создаем директорию для бота
if [ ! -d "$INSTALL_DIR" ]; then
    echo "📁 Создание директории $INSTALL_DIR..."
    mkdir -p "$INSTALL_DIR"
fi

# Копируем файлы проекта
echo "📋 Копирование файлов..."
if [ "$CURRENT_DIR" != "$INSTALL_DIR" ]; then
    cp -r . "$INSTALL_DIR/"
fi

cd "$INSTALL_DIR"

# Создаем виртуальное окружение
echo "🐍 Создание виртуального окружения..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# Активируем виртуальное окружение
source venv/bin/activate

# Устанавливаем зависимости
echo "📦 Установка Python зависимостей..."
pip install --upgrade pip
pip install -r requirements.txt

# Создаем необходимые директории
echo "📁 Создание директорий..."
mkdir -p data static/images scripts logs

# Создаем .env если его нет
if [ ! -f ".env" ]; then
    echo "⚙️ Создание .env файла..."
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "✅ Создан .env из .env.example"
        echo "⚠️  ВАЖНО: Отредактируйте .env и заполните все необходимые параметры!"
    else
        echo "❌ .env.example не найден!"
    fi
fi

# Создаем systemd сервис
echo "🔧 Настройка systemd сервиса..."
cat > /etc/systemd/system/vpn-bot.service << EOF
[Unit]
Description=VPN Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin"
ExecStart=$INSTALL_DIR/venv/bin/python3 $INSTALL_DIR/main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Перезагружаем systemd
systemctl daemon-reload

echo ""
echo "✅ Установка завершена!"
echo ""
echo "📝 Следующие шаги:"
echo "1. Отредактируйте .env файл: nano $INSTALL_DIR/.env"
echo "2. Заполните все необходимые параметры (BOT_TOKEN, X3UI_API_URL и т.д.)"
echo "3. Запустите бота: systemctl start vpn-bot"
echo "4. Включите автозапуск: systemctl enable vpn-bot"
echo "5. Проверьте статус: systemctl status vpn-bot"
echo ""
echo "📋 Полезные команды:"
echo "   - Просмотр логов: journalctl -u vpn-bot -f"
echo "   - Остановка: systemctl stop vpn-bot"
echo "   - Запуск: systemctl start vpn-bot"
echo "   - Перезапуск: systemctl restart vpn-bot"
echo ""
