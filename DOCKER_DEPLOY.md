# 🐳 Развертывание VPN Telegram Bot через Docker

## 📋 Требования

- Docker и Docker Compose установлены на сервере
- Telegram Bot Token
- Доступ к серверу по SSH

### Установка Docker (если не установлен)

```bash
# Быстрая установка через скрипт
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Или используйте скрипт из проекта
bash install-docker.sh

# Проверьте установку
docker --version
docker compose version
```

**Важно:** В новых версиях Docker используется `docker compose` (без дефиса), а не `docker-compose`.

## 🚀 Быстрая установка

### 1. Подключитесь к серверу

```bash
ssh root@your_server_ip
```

### 2. Клонируйте репозиторий (или загрузите файлы)

```bash
cd /opt
git clone <your_repo_url> vpn-tg-bot
# или загрузите файлы через scp/sftp
cd vpn-tg-bot
```

### 3. Настройте переменные окружения

```bash
# Копируем пример конфигурации
cp .env.example .env

# Редактируем конфигурацию
nano .env
```

**Важно для Docker:**
- Если бот и 3x-ui на одном сервере (3x-ui НЕ в Docker) - используйте:
  ```
  X3UI_API_URL=http://host.docker.internal:2053
  ```
  или если `host.docker.internal` не работает:
  ```
  X3UI_API_URL=http://localhost:2053
  ```
  и используйте `docker-compose -f docker-compose.host-network.yml up -d`
  
- Если 3x-ui в Docker:
  ```
  X3UI_API_URL=http://x-ui-container-name:2053
  ```
  
- Если 3x-ui на другом сервере:
  ```
  X3UI_API_URL=http://external-ip:2053
  ```

### 4. Запустите через Docker Compose

```bash
# Для Docker Compose v2 (рекомендуется)
docker compose up -d

# Для старой версии docker-compose
docker-compose up -d

# Проверяем статус
docker compose ps
# или
docker-compose ps

# Смотрим логи
docker compose logs -f
# или
docker-compose logs -f
```

**Примечание:** В новых версиях Docker используется `docker compose` (без дефиса).

### 5. Проверьте работу

```bash
# Логи в реальном времени
docker-compose logs -f vpn-bot

# Статус контейнера
docker-compose ps
```

## 🔧 Управление

### Запуск

```bash
docker-compose up -d
```

### Остановка

```bash
docker-compose stop
```

### Перезапуск

```bash
docker-compose restart
```

### Остановка и удаление

```bash
docker-compose down
```

### Просмотр логов

```bash
# Все логи
docker-compose logs

# Логи в реальном времени
docker-compose logs -f

# Последние 100 строк
docker-compose logs --tail=100
```

### Обновление

```bash
# Останавливаем
docker-compose down

# Обновляем код (если используете git)
git pull

# Пересобираем образ
docker-compose build --no-cache

# Запускаем
docker-compose up -d
```

## 🔗 Подключение к 3x-ui

### Вариант 1: 3x-ui на том же хосте (не в Docker) ⭐ Ваш случай

**Способ 1 (рекомендуется):** Используйте `host.docker.internal`:
```env
X3UI_API_URL=http://host.docker.internal:2053
```

Если в 3x-ui есть WebBasePath:
```env
X3UI_API_URL=http://host.docker.internal:2053/WebBasePath
```

**Способ 2:** Если `host.docker.internal` не работает, используйте host network:
```bash
# Запустите с host network
docker-compose -f docker-compose.host-network.yml up -d
```

И в `.env`:
```env
X3UI_API_URL=http://localhost:2053
```

**Способ 3:** Узнайте IP хоста из контейнера:
```bash
docker-compose exec vpn-bot ip route | awk '/default/ {print $3}'
```

Обычно это `172.17.0.1`, тогда в `.env`:
```env
X3UI_API_URL=http://172.17.0.1:2053
```

### Вариант 2: 3x-ui в Docker

Если 3x-ui тоже в Docker, добавьте в `docker-compose.yml`:

```yaml
services:
  vpn-bot:
    # ... существующая конфигурация ...
    networks:
      - vpn-network
    depends_on:
      - x-ui  # если 3x-ui называется x-ui

  x-ui:
    # конфигурация 3x-ui
    networks:
      - vpn-network
```

И в `.env`:
```env
X3UI_API_URL=http://x-ui:2053
```

### Вариант 3: 3x-ui на другом сервере

Просто используйте внешний IP:
```env
X3UI_API_URL=http://external-ip:2053
```

## 📁 Структура данных

Все данные сохраняются в volumes:
- `./data` - база данных
- `./logs` - логи приложения
- `./static` - статические файлы

**Важно:** Эти папки должны существовать и иметь правильные права:
```bash
mkdir -p data logs static/images
chmod -R 755 data logs static
```

## 🔒 Безопасность

### 1. Защитите .env файл

```bash
chmod 600 .env
```

### 2. Используйте Docker secrets (для production)

Вместо `.env` файла можно использовать Docker secrets:
```yaml
secrets:
  bot_token:
    file: ./secrets/bot_token.txt
```

### 3. Ограничьте ресурсы

В `docker-compose.yml`:
```yaml
services:
  vpn-bot:
    # ... существующая конфигурация ...
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 512M
        reservations:
          cpus: '0.5'
          memory: 256M
```

## 🛠️ Полезные команды

```bash
# Войти в контейнер
docker-compose exec vpn-bot bash

# Выполнить команду в контейнере
docker-compose exec vpn-bot python3 scripts/update_tariffs.py

# Пересобрать образ
docker-compose build

# Пересобрать без кэша
docker-compose build --no-cache

# Просмотр использования ресурсов
docker stats vpn-tg-bot
```

## ❌ Устранение проблем

### Контейнер не запускается

1. Проверьте логи:
   ```bash
   docker-compose logs vpn-bot
   ```

2. Проверьте конфигурацию:
   ```bash
   docker-compose config
   ```

3. Проверьте .env файл:
   ```bash
   cat .env
   ```

### Ошибка подключения к 3x-ui

1. Проверьте, что 3x-ui доступен:
   ```bash
   # Из контейнера
   docker-compose exec vpn-bot curl http://host.docker.internal:2053
   ```

2. Проверьте сеть:
   ```bash
   docker network inspect vpn-tg-bot_vpn-network
   ```

3. Попробуйте использовать IP хоста:
   ```bash
   # Узнайте IP хоста
   docker-compose exec vpn-bot ip route | awk '/default/ {print $3}'
   ```

### Ошибка базы данных

1. Проверьте права на папку data:
   ```bash
   ls -la data/
   chmod 755 data/
   ```

2. Проверьте, что папка монтируется:
   ```bash
   docker-compose exec vpn-bot ls -la /app/data
   ```

## 📊 Мониторинг

### Просмотр использования ресурсов

```bash
docker stats vpn-tg-bot
```

### Просмотр логов

```bash
# Все логи
docker-compose logs

# Только ошибки
docker-compose logs | grep ERROR

# Последние 50 строк
docker-compose logs --tail=50
```

## 🔄 Автоматический перезапуск

Docker Compose автоматически перезапускает контейнер при сбое благодаря `restart: unless-stopped` в `docker-compose.yml`.

## 📝 Пример полной установки

```bash
# 1. Клонируем репозиторий
cd /opt
git clone <repo> vpn-tg-bot
cd vpn-tg-bot

# 2. Настраиваем .env
cp .env.example .env
nano .env

# 3. Создаем папки
mkdir -p data logs static/images

# 4. Запускаем
docker-compose up -d

# 5. Проверяем
docker-compose logs -f
```

## 🎯 Преимущества Docker

✅ Изолированное окружение  
✅ Легкое обновление  
✅ Простое развертывание  
✅ Автоматический перезапуск  
✅ Легкое масштабирование  
✅ Консистентность между окружениями  
