from aiogram import Router
from aiogram.types import Update, ErrorEvent
from loguru import logger
from config.settings import settings

router = Router()


@router.errors()
async def error_handler(event: ErrorEvent):
    """Глобальный обработчик ошибок"""
    exception = event.exception
    update = event.update
    
    # Логируем ошибку
    logger.error(f"❌ Ошибка в обработчике: {exception}")
    logger.error(f"Update: {update}")
    
    # Если есть traceback, логируем его
    import traceback
    logger.error(f"Traceback:\n{traceback.format_exc()}")
    
    # Отправляем сообщение пользователю, если это возможно
    try:
        if update.message:
            await update.message.answer(
                "❌ Произошла ошибка при обработке вашего запроса.\n"
                "Пожалуйста, попробуйте позже или обратитесь в поддержку."
            )
        elif update.callback_query:
            await update.callback_query.answer(
                "❌ Произошла ошибка",
                show_alert=True
            )
    except Exception as e:
        logger.error(f"Не удалось отправить сообщение об ошибке: {e}")
    
    # Уведомляем админов о критических ошибках
    try:
        if settings.ADMIN_IDS:
            from app.bot.loader import bot
            error_message = (
                f"⚠️ *Критическая ошибка в боте*\n\n"
                f"Ошибка: `{type(exception).__name__}: {str(exception)}`\n"
                f"Update ID: {update.update_id}"
            )
            for admin_id in settings.ADMIN_IDS:
                try:
                    await bot.send_message(
                        admin_id,
                        error_message,
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Не удалось отправить уведомление админу {admin_id}: {e}")
    except Exception as e:
        logger.error(f"Ошибка при уведомлении админов: {e}")
