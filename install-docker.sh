#!/bin/bash

# Скрипт установки Docker и Docker Compose на Ubuntu/Debian

set -e

echo "🐳 Установка Docker и Docker Compose..."

# Проверка прав root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Пожалуйста, запустите скрипт от root"
    exit 1
fi

# Обновляем систему
echo "📦 Обновление системы..."
apt update

# Устанавливаем зависимости
echo "📦 Установка зависимостей..."
apt install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

# Добавляем официальный GPG ключ Docker
echo "🔑 Добавление GPG ключа Docker..."
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

# Определяем версию Ubuntu/Debian
. /etc/os-release
ARCH=$(dpkg --print-architecture)

# Добавляем репозиторий Docker
echo "📦 Добавление репозитория Docker..."
echo \
  "deb [arch=${ARCH} signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

# Устанавливаем Docker
echo "🐳 Установка Docker..."
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Запускаем Docker
echo "🚀 Запуск Docker..."
systemctl start docker
systemctl enable docker

# Проверяем установку
echo "✅ Проверка установки..."
docker --version
docker compose version

echo ""
echo "✅ Docker и Docker Compose установлены!"
echo ""
echo "💡 Теперь используйте команду:"
echo "   docker compose up -d"
echo "   (вместо docker-compose)"
