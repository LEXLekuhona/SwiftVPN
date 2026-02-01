from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.services.vpn import V2RayService
from app.services.user import SubscriptionService
from app.services.database import db
from config.settings import settings
import base64
from io import BytesIO
from datetime import datetime
from loguru import logger

# Инициализация сервисов
v2ray_service = V2RayService(db)
subscription_service = SubscriptionService(db)


router = Router()


@router.message(F.text, F.text.regexp(r"^/(mykey|key|getkey)").as_("cmd"))
async def cmd_mykey(message: Message):
    """Команда получения ключа"""
    user_id = message.from_user.id

    try:
        # Сразу отправляем сообщение о том, что обрабатываем запрос
        processing_msg = await message.answer("⏳ Получаю ключ доступа...")
        
        # Проверяем активную подписку
        has_subscription, end_date = await subscription_service.check_subscription(user_id)

        if not has_subscription:
            await processing_msg.delete()
            kb = InlineKeyboardBuilder()
            kb.button(text="💰 Купить доступ", callback_data="show_tariffs")

            await message.answer(
                "❌ *У вас нет активной подписки*\n\n"
                "Для получения ключа доступа необходимо приобрести подписку.",
                parse_mode="Markdown",
                reply_markup=kb.as_markup()
            )
            return

        # Получаем или создаем ключ
        key_data = await v2ray_service.get_active_key(user_id)

        if not key_data:
            # Создаем новый ключ
            if not settings.VPN_SERVERS:
                await processing_msg.delete()
                await message.answer("❌ Серверы VPN временно недоступны")
                return

            server_config = settings.VPN_SERVERS[0]  # Берем первый сервер
            key_data = await v2ray_service.create_key(user_id, server_config)

        # Удаляем сообщение о обработке
        try:
            await processing_msg.delete()
        except:
            pass

        # Отправляем ключ пользователю
        await send_key_to_user(message.from_user.id, key_data)

    except Exception as e:
        logger.error(f"Ошибка в /mykey: {e}")
        await message.answer("Произошла ошибка при получении ключа. Попробуйте позже.")


async def send_v2ray_key_to_user(user_id: int):
    """Отправка ключа пользователю (используется после оплаты)"""
    try:
        # Проверяем активную подписку
        has_subscription, end_date = await subscription_service.check_subscription(user_id)

        if not has_subscription:
            logger.warning(f"Попытка получить ключ без подписки: user_id={user_id}")
            return

        # Получаем или создаем ключ (это может занять время из-за API запросов)
        key_data = await v2ray_service.get_active_key(user_id)

        if not key_data:
            if not settings.VPN_SERVERS:
                return

            server_config = settings.VPN_SERVERS[0]
            key_data = await v2ray_service.create_key(user_id, server_config)

        # Отправляем ключ
        await send_key_to_user(user_id, key_data)

    except Exception as e:
        logger.error(f"Ошибка отправки ключа: {e}")


async def send_key_to_user(user_id: int, key_data: dict):
    """Отправка ключа и инструкции пользователю"""
    from app.bot.loader import bot

    try:
        # Сообщение с ключом
        expires_info = ""
        if isinstance(key_data.get('expires_at'), datetime):
            expires_info = f"📅 *Срок действия:* до {key_data['expires_at'].strftime('%d.%m.%Y')}"
        elif key_data.get('expires_at'):
            expires_info = f"📅 *Срок действия:* до {key_data['expires_at']}"
        
        server_info = ""
        # Получаем location из server_config или из settings
        location = None
        if key_data.get('server'):
            location = key_data['server'].get('location')
        
        # Если location не найден, пытаемся получить из settings.VPN_SERVERS
        if not location and settings.VPN_SERVERS:
            # Ищем сервер по адресу и порту из key_data
            server_address = key_data.get('server', {}).get('address') or key_data.get('server_address')
            server_port = key_data.get('server', {}).get('port') or key_data.get('server_port')
            
            for server in settings.VPN_SERVERS:
                if server.get('address') == server_address and server.get('port') == server_port:
                    location = server.get('location')
                    break
        
        # Если location найден и это не значение по умолчанию, используем его как есть
        if location and location != "Сервер" and location != "Не указан":
            server_info = f"🌍 *Сервер:* {location}"
        else:
            server_info = "🌍 *Сервер:* Настроен автоматически"
        
        # Отправляем информационное сообщение
        info_text = f"""
✅ *Ваш VPN готов к использованию!*

{expires_info}
{server_info}

💡 *Всё настроено!*
Ключ отправлен отдельным сообщением для удобного копирования.
        """

        await bot.send_message(
            user_id,
            info_text,
            parse_mode="Markdown"
        )

        # Отправляем ключ отдельным сообщением в формате code для легкого копирования
        # Формат code делает текст кликабельным - пользователь может нажать на него и скопировать
        key_string = key_data['key']
        
        # Логируем ключ для отладки (первые и последние 50 символов)
        logger.debug(f"Отправка ключа пользователю {user_id}: длина={len(key_string)} символов")
        logger.debug(f"Начало ключа: {key_string[:50]}...")
        logger.debug(f"Конец ключа: ...{key_string[-50:]}")
        
        # Проверяем, что ключ не пустой и содержит все необходимые части
        if not key_string or len(key_string) < 50:
            logger.error(f"⚠️ Ключ слишком короткий: {len(key_string)} символов")
        if not key_string.startswith("vless://") and not key_string.startswith("vmess://"):
            logger.error(f"⚠️ Ключ не начинается с vless:// или vmess://: {key_string[:30]}...")
        
        key_message = f"```\n{key_string}\n```"
        await bot.send_message(
            user_id,
            key_message,
            parse_mode="Markdown"  # Используем Markdown для форматирования code блока
        )

        logger.info(f"Ключ отправлен пользователю {user_id}")

    except Exception as e:
        logger.error(f"Ошибка отправки ключа пользователю {user_id}: {e}")


@router.callback_query(F.data.startswith("copy_key:"))
async def callback_copy_key(callback: CallbackQuery):
    """Обработчик кнопки копирования ключа по UUID"""
    try:
        uuid = callback.data.split(":")[1]
        
        async with db.session_maker() as session:
            from sqlalchemy import select
            from app.database.models import V2RayKey
            
            stmt = select(V2RayKey).where(
                V2RayKey.uuid == uuid,
                V2RayKey.is_active == True
            ).limit(1)
            
            result = await session.execute(stmt)
            key = result.scalar_one_or_none()
            
            if not key:
                await callback.answer("❌ Ключ не найден", show_alert=True)
                return
            
            # Отправляем ключ отдельным сообщением в формате code для легкого копирования
            key_message = f"```\n{key.key_string}\n```"
            await callback.message.answer(
                key_message,
                parse_mode="Markdown"  # Используем Markdown для форматирования code блока
            )
            
            await callback.answer("✅ Ключ отправлен! Нажмите на него для копирования.")
            
    except Exception as e:
        logger.error(f"Ошибка в callback_copy_key: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("copy_key_user:"))
async def callback_copy_key_by_user(callback: CallbackQuery):
    """Обработчик кнопки копирования ключа по user_id"""
    try:
        target_user_id = int(callback.data.split(":")[1])
        user_id = callback.from_user.id
        
        # Проверяем, что пользователь запрашивает свой ключ
        if target_user_id != user_id:
            await callback.answer("❌ Доступ запрещен", show_alert=True)
            return
        
        async with db.session_maker() as session:
            from sqlalchemy import select
            from app.database.models import V2RayKey
            
            stmt = select(V2RayKey).where(
                V2RayKey.user_id == user_id,
                V2RayKey.is_active == True
            ).limit(1)
            
            result = await session.execute(stmt)
            key = result.scalar_one_or_none()
            
            if not key:
                await callback.answer("❌ Ключ не найден", show_alert=True)
                return
            
            # Отправляем ключ отдельным сообщением в формате code для легкого копирования
            key_message = f"```\n{key.key_string}\n```"
            await callback.message.answer(
                key_message,
                parse_mode="Markdown"  # Используем Markdown для форматирования code блока
            )
            
            await callback.answer("✅ Ключ отправлен! Нажмите на него для копирования.")
            
    except Exception as e:
        logger.error(f"Ошибка в callback_copy_key_by_user: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

