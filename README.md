# VPN Telegram Bot

Telegram бот для продажи VPN-ключей с автоматическим управлением через 3x-ui API.

## 🚀 Быстрый старт

### Локальная разработка

#### 1. Установка зависимостей

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows

pip install -r requirements.txt
```

#### 2. Настройка

Скопируйте `.env.example` в `.env` и заполните настройки:

```bash
cp .env.example .env
```

Обязательные настройки:
- `BOT_TOKEN` - токен Telegram бота
- `ADMIN_IDS` - ID администраторов (через запятую)
- `X3UI_API_URL` - URL 3x-ui панели
- `X3UI_USERNAME` - логин 3x-ui
- `X3UI_PASSWORD` - пароль 3x-ui
- `X3UI_INBOUND_ID` - ID inbound в 3x-ui
- `VPN_SERVERS` - JSON массив с настройками серверов

#### 3. Запуск

```bash
python3 main.py
```

Или через скрипт:

```bash
./start_bot.sh
```

### Развертывание на сервере (Docker) ⭐ Рекомендуется

#### Быстрая установка через Docker

```bash
# 1. Загрузите файлы на сервер
scp -r vpn-tg-bot root@your_server:/opt/

# 2. Подключитесь к серверу
ssh root@your_server

# 3. Установите Docker (если не установлен)
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# 4. Установите Docker Compose (если не установлен)
apt install docker-compose -y

# 5. Настройте .env
cd /opt/vpn-tg-bot
cp .env.example .env
nano .env
# Заполните BOT_TOKEN, X3UI_API_URL и т.д.

# 6. Создайте необходимые папки
mkdir -p data logs static/images

# 7. Запустите через Docker Compose
docker-compose up -d

# 8. Проверьте статус
docker-compose ps
docker-compose logs -f
```

**Важно для Docker:**
- Если бот и 3x-ui на одном сервере: `X3UI_API_URL=http://host.docker.internal:2053`
- Если 3x-ui в Docker: `X3UI_API_URL=http://x-ui-container:2053`
- Если 3x-ui на другом сервере: `X3UI_API_URL=http://external-ip:2053`

Подробная инструкция: [DOCKER_DEPLOY.md](DOCKER_DEPLOY.md)

### Развертывание на сервере (systemd)

Альтернативный способ через systemd сервис:

```bash
# Используйте install.sh для установки
bash install.sh
```

Подробная инструкция: [DEPLOY.md](DEPLOY.md)

## 📁 Структура проекта

```
vpn-tg-bot/
├── app/
│   ├── bot/              # Инициализация бота
│   ├── database/         # Модели БД
│   ├── handlers/         # Обработчики сообщений
│   │   ├── admin/        # Админские команды
│   │   └── user/         # Пользовательские команды
│   ├── keyboards/        # Клавиатуры
│   ├── middlewares/      # Middleware
│   ├── services/         # Бизнес-логика
│   └── utils/           # Утилиты
├── config/              # Конфигурация
├── data/                # База данных
├── static/              # Статические файлы
│   └── images/          # Изображения
├── scripts/             # Скрипты
└── logs/                # Логи
```

## ⚙️ Основные функции

- ✅ Автоматическое создание VPN-ключей
- ✅ Интеграция с 3x-ui API
- ✅ Поддержка Reality протокола
- ✅ Оплата через Telegram Stars
- ✅ Оплата через СБП (ЮKassa)
- ✅ Управление подписками
- ✅ Админ-панель

## 💳 Оплата через СБП (ЮKassa)

1. Зарегистрируйтесь в [ЮKassa](https://yookassa.ru) и подключите приём платежей через СБП.
2. В `.env` укажите:
   - `YOOKASSA_SHOP_ID` — идентификатор магазина
   - `YOOKASSA_SECRET_KEY` — секретный ключ
   - `YOOKASSA_RETURN_URL` — куда вернуть пользователя после оплаты (например `https://t.me/your_bot`)
3. В личном кабинете ЮKassa → **Интеграция → HTTP-уведомления** укажите URL:
   `https://ваш-домен:443/yookassa/webhook` (события `payment.succeeded`, `payment.canceled`).
4. Пробросьте порт webhook на сервер (по умолчанию `8080`, см. `YOOKASSA_WEBHOOK_PORT` в Docker).

Без webhook пользователь может подтвердить оплату кнопкой **«Проверить оплату»** в боте.

## 🔧 Настройка VPN серверов

В `.env` укажите минимальную конфигурацию:

```json
VPN_SERVERS=[{
  "address": "your.server.ip",
  "port": 443,
  "location": "🌍 Location",
  "reality_pbk": "your_public_key"
}]
```

Параметры Reality (type, security, server_name, fingerprint, reality_sid, spiderx) автоматически извлекаются из 3x-ui inbound.

## 📝 Команды бота

- `/start` - Запустить бота
- `/buy` - Купить VPN доступ
- `/mykey` - Получить ключ доступа
- `/profile` - Мой профиль
- `/help` - Помощь

## 🛠️ Разработка

### Обновление тарифов

```bash
python3 scripts/update_tariffs.py
```

### Логи

Логи сохраняются в `logs/bot.log`

## 📄 Лицензия

Проект для личного использования.
