from aiogram import Router, F
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.services.vpn import V2RayService
from app.services.user import SubscriptionService
from app.services.database import db
from config.settings import settings
from datetime import datetime, timedelta
from loguru import logger

router = Router()

v2ray_service = V2RayService(db)
subscription_service = SubscriptionService(db)


@router.message(F.text, F.text.regexp(r"^/freevpn").as_("cmd"))
async def cmd_free_vpn(message: Message):
    """Бесплатный VPN для админа"""
    user_id = message.from_user.id
    
    # Проверяем, что пользователь - админ
    if user_id not in settings.ADMIN_IDS:
        await message.answer("❌ Эта команда доступна только администраторам")
        return
    
    try:
        # Создаем бесплатную подписку на 365 дней
        async with db.session_maker() as session:
            from sqlalchemy import select
            from app.database.models import User, Subscription, Tariff
            
            # Получаем или создаем пользователя
            user_stmt = select(User).where(User.telegram_id == user_id)
            user_result = await session.execute(user_stmt)
            user = user_result.scalar_one_or_none()
            
            if not user:
                user = User(
                    telegram_id=user_id,
                    username=message.from_user.username,
                    first_name=message.from_user.first_name,
                    last_name=message.from_user.last_name
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)
            
            # Создаем или обновляем подписку
            subscription_stmt = select(Subscription).where(Subscription.user_id == user.id)
            subscription_result = await session.execute(subscription_stmt)
            subscription = subscription_result.scalar_one_or_none()
            
            # Получаем тариф (берем первый активный)
            tariff_stmt = select(Tariff).where(Tariff.is_active == True).limit(1)
            tariff_result = await session.execute(tariff_stmt)
            tariff = tariff_result.scalar_one_or_none()
            
            if not tariff:
                await message.answer("❌ Нет доступных тарифов. Создайте тариф в базе данных.")
                return
            
            now = datetime.utcnow()
            end_date = now + timedelta(days=365)  # Бесплатная подписка на год
            
            if subscription:
                subscription.tariff_id = tariff.id
                subscription.start_date = now
                subscription.end_date = end_date
                subscription.is_active = True
            else:
                subscription = Subscription(
                    user_id=user.id,
                    tariff_id=tariff.id,
                    start_date=now,
                    end_date=end_date,
                    is_active=True
                )
                session.add(subscription)
            
            await session.commit()
        
        # Создаем ключ
        if not settings.VPN_SERVERS:
            await message.answer("❌ Серверы VPN не настроены в .env")
            return
        
        server_config = settings.VPN_SERVERS[0]
        key_data = await v2ray_service.create_key(user_id, server_config)
        
        uuid = key_data.get("uuid", "")
        
        # Отправляем информационное сообщение
        info_text = f"""
        ✅ *Бесплатный VPN активирован!*

📅 *Срок действия:* до {key_data['expires_at'].strftime('%d.%m.%Y')}
🌍 *Сервер:* {server_config.get('location', 'Не указан')}

💡 *Всё настроено автоматически!*
Ключ отправлен отдельным сообщением для удобного копирования.
        """
        
        await message.answer(info_text, parse_mode="Markdown")
        
        # Отправляем ключ отдельным сообщением в формате code для легкого копирования
        key_string = key_data['key']
        
        # Логируем ключ для отладки
        logger.debug(f"Отправка ключа админу {user_id}: длина={len(key_string)} символов")
        logger.debug(f"Начало ключа: {key_string[:50]}...")
        logger.debug(f"Конец ключа: ...{key_string[-50:]}")
        
        # Проверяем, что ключ не пустой и содержит все необходимые части
        if not key_string or len(key_string) < 50:
            logger.error(f"⚠️ Ключ слишком короткий: {len(key_string)} символов")
        if not key_string.startswith("vless://") and not key_string.startswith("vmess://"):
            logger.error(f"⚠️ Ключ не начинается с vless:// или vmess://: {key_string[:30]}...")
        
        key_message = f"```\n{key_string}\n```"
        await message.answer(key_message, parse_mode="Markdown")
        
        logger.info(f"Бесплатный VPN активирован для админа {user_id}, UUID: {uuid}")
        
    except Exception as e:
        logger.error(f"Ошибка в /freevpn: {e}")
        await message.answer(f"❌ Ошибка: {e}")
