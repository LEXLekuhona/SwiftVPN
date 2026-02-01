import asyncio
import sys
from loguru import logger

# Проверка версии Python
if sys.version_info < (3, 7):
    print("❌ Требуется Python 3.7 или выше")
    print(f"⚠️  У вас Python {sys.version}")
    sys.exit(1)


async def main():
    """Основная функция запуска бота"""

    # Импорты внутри функции для правильной загрузки
    try:
        from app.bot.loader import dp, bot
        from app.handlers import register_all_handlers
        from app.utils.system import setup_logging, create_dirs
        from app.services.database import db
        from aiogram.types import BotCommand
    except ImportError as e:
        print(f"❌ Ошибка импорта: {e}")
        print("⚠️  Установите зависимости: pip install -r requirements.txt")
        sys.exit(1)

    # Настройка логирования
    setup_logging()

    logger.info("🚀 Запуск VPN Telegram Bot...")
    logger.info(f"📊 Python версия: {sys.version}")

    try:
        # Создаем необходимые директории
        create_dirs()

        # Инициализируем базу данных
        logger.info("🔧 Инициализация базы данных...")
        await db.init_db()

        # Регистрируем обработчики
        logger.info("📝 Регистрация обработчиков...")
        register_all_handlers(dp)

        # Устанавливаем команды бота
        logger.info("⚙️ Установка команд бота...")
        try:
            await asyncio.wait_for(
                bot.set_my_commands(
                    [
                        BotCommand(command="start", description="Запустить бота"),
                        BotCommand(command="buy", description="Купить VPN доступ"),
                        BotCommand(command="mykey", description="Мой ключ доступа"),
                        BotCommand(command="profile", description="Мой профиль"),
                        BotCommand(command="help", description="Помощь"),
                    ]
                ),
                timeout=10.0
            )
        except asyncio.TimeoutError:
            logger.warning("Таймаут при установке команд бота. Продолжаем запуск...")
        except Exception as e:
            logger.warning(f"Ошибка при установке команд бота: {e}. Продолжаем запуск...")

        logger.info("✅ Бот успешно запущен!")
        logger.info("📱 Перейдите в Telegram и откройте своего бота")

        # Удаляем webhook, если он установлен (чтобы избежать конфликтов)
        try:
            webhook_info = await asyncio.wait_for(
                bot.get_webhook_info(),
                timeout=10.0  # Таймаут для проверки webhook
            )
            if webhook_info.url:
                logger.info(f"⚠️  Найден webhook: {webhook_info.url}. Удаляем...")
                await asyncio.wait_for(
                    bot.delete_webhook(drop_pending_updates=True),
                    timeout=10.0
                )
                logger.info("✅ Webhook удален")
                # Небольшая задержка для применения изменений на стороне Telegram
                await asyncio.sleep(2)
            else:
                logger.info("✅ Webhook не установлен")
        except asyncio.TimeoutError:
            logger.warning("Таймаут при проверке webhook. Продолжаем запуск...")
            
            # Принудительно получаем и подтверждаем все обновления для сброса состояния
            logger.info("🔄 Сброс состояния getUpdates...")
            try:
                # Пробуем несколько раз с разными offset для полного сброса
                for attempt in range(3):
                    try:
                        # Используем asyncio.wait_for для контроля таймаута
                        updates = await asyncio.wait_for(
                            bot.get_updates(offset=-1, limit=100, timeout=2),
                            timeout=5.0  # Максимальное время ожидания
                        )
                        if updates:
                            # Подтверждаем последнее обновление
                            last_update_id = updates[-1].update_id
                            await asyncio.wait_for(
                                bot.get_updates(offset=last_update_id + 1, limit=1, timeout=1),
                                timeout=3.0
                            )
                            logger.info(f"✅ Состояние getUpdates сброшено (последний update_id: {last_update_id}, попытка {attempt + 1})")
                            break
                        else:
                            logger.info(f"✅ Нет pending обновлений (попытка {attempt + 1})")
                            break
                    except asyncio.TimeoutError:
                        if attempt < 2:
                            logger.warning(f"Таймаут при попытке {attempt + 1}, пробуем еще раз...")
                            await asyncio.sleep(2)
                        else:
                            logger.warning("Таймаут при сбросе состояния getUpdates. Продолжаем запуск...")
                            break
                    except Exception as e:
                        if attempt < 2:
                            logger.warning(f"Попытка {attempt + 1} не удалась: {e}, пробуем еще раз...")
                            await asyncio.sleep(2)
                        else:
                            logger.warning(f"Не удалось сбросить состояние getUpdates после 3 попыток: {e}. Продолжаем запуск...")
            except Exception as e:
                logger.warning(f"Ошибка при сбросе состояния getUpdates: {e}. Продолжаем запуск...")
            
            # Дополнительная задержка перед запуском polling (увеличена для надежности)
            logger.info("⏳ Ожидание 3 секунды перед запуском polling...")
            await asyncio.sleep(3)
            
        except Exception as e:
            logger.warning(f"Не удалось проверить/удалить webhook: {e}")

        # Запускаем polling с параметрами для избежания конфликтов
        logger.info("🔄 Запуск polling...")
        try:
            await dp.start_polling(
                bot, 
                drop_pending_updates=True,
                allowed_updates=["message", "callback_query", "pre_checkout_query"],
                timeout=20,  # Таймаут для long polling
                request_timeout=30  # Таймаут для HTTP запросов
            )
        except asyncio.TimeoutError:
            logger.error("Таймаут при запуске polling. Проверьте подключение к интернету и Telegram API.")
            raise
        except Exception as e:
            logger.error(f"Ошибка при запуске polling: {e}")
            raise

    except Exception as e:
        logger.error(f"❌ Критическая ошибка при запуске: {e}")
        raise
    finally:
        logger.info("Завершение работы...")
        await db.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except asyncio.TimeoutError as e:
        logger.error(f"❌ Таймаут подключения: {e}")
        logger.error("💡 Возможные причины:")
        logger.error("  1. Проблемы с интернет-соединением")
        logger.error("  2. Telegram API недоступен")
        logger.error("  3. Неверный BOT_TOKEN в .env файле")
        logger.error("  4. Блокировка Telegram в вашей стране/сети")
        logger.error("\n🔧 Попробуйте:")
        logger.error("  • Проверить интернет-соединение")
        logger.error("  • Проверить BOT_TOKEN в .env файле")
        logger.error("  • Использовать VPN, если Telegram заблокирован")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Непредвиденная ошибка: {e}")
        import traceback
        logger.error(f"Детали ошибки:\n{traceback.format_exc()}")
        sys.exit(1)

