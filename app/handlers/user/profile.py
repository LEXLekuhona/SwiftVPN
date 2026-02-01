from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.services.user import SubscriptionService
from app.services.database import db
from datetime import datetime
from loguru import logger

subscription_service = SubscriptionService(db)

router = Router()


@router.message(F.text, F.text.regexp(r"^/(profile|me)").as_("cmd"))
async def cmd_profile(message: Message):
    """Команда просмотра профиля"""
    user_id = message.from_user.id

    try:
        # Получаем информацию о подписке
        subscription_info = await subscription_service.get_subscription_info(user_id)

        if not subscription_info:
            kb = InlineKeyboardBuilder()
            kb.button(text="💰 Купить доступ", callback_data="show_tariffs")

            await message.answer(
                "👤 *Ваш профиль*\n\n"
                "❌ *Статус подписки:* Нет активной подписки\n\n"
                "Для получения доступа к VPN нажмите кнопку ниже:",
                parse_mode="Markdown",
                reply_markup=kb.as_markup()
            )
            return

        # Форматируем даты
        start_date = subscription_info['start_date'].strftime('%d.%m.%Y')
        end_date = subscription_info['end_date'].strftime('%d.%m.%Y') if subscription_info['end_date'] else "∞"

        profile_text = f"""
👤 *Ваш профиль*

📅 *Тариф:* {subscription_info['tariff_name']}
💰 *Стоимость:* {subscription_info['price']}₽
⏳ *Срок:* {subscription_info['duration']} дней

🟢 *Статус:* {'Активна' if subscription_info['is_active'] else 'Неактивна'}
📅 *Начало:* {start_date}
📅 *Окончание:* {end_date}
⏰ *Осталось дней:* {subscription_info['days_left']}

💎 *Что включено:*
• 🚀 Неограниченный трафик
• 🔒 Полная анонимность
• 🌍 Доступ ко всем сайтам
• 📱 Поддержка V2RayTun
        """

        kb = InlineKeyboardBuilder()

        if subscription_info['days_left'] < 7:
            kb.button(text="🔄 Продлить подписку", callback_data="show_tariffs")

        kb.button(text="🔑 Получить ключ", callback_data="get_key")
        kb.button(text="📊 Статистика", callback_data="show_stats")
        kb.adjust(2)

        await message.answer(
            profile_text,
            parse_mode="Markdown",
            reply_markup=kb.as_markup()
        )

    except Exception as e:
        logger.error(f"Ошибка в /profile: {e}")
        await message.answer("Произошла ошибка при загрузке профиля.")


@router.callback_query(F.data == "get_key")
async def callback_get_key(callback: CallbackQuery):
    """Получение ключа из профиля"""
    from app.handlers.user.v2ray import send_v2ray_key_to_user

    user_id = callback.from_user.id

    try:
        # Сразу отвечаем пользователю, что обрабатываем запрос
        await callback.answer("⏳ Получаю ключ...", show_alert=False)
        
        # Проверяем подписку
        has_subscription, _ = await subscription_service.check_subscription(user_id)

        if not has_subscription:
            await callback.message.answer("❌ У вас нет активной подписки")
            return

        # Отправляем ключ (это может занять время, но пользователь уже получил ответ)
        await send_v2ray_key_to_user(user_id)

    except Exception as e:
        logger.error(f"Ошибка получения ключа: {e}")
        await callback.message.answer("❌ Ошибка получения ключа. Попробуйте позже.")


