from aiogram import Router, F
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.services.vpn import VPSService
from app.services.database import db
from config.settings import settings
from loguru import logger

router = Router()

vps_service = VPSService()


@router.message(F.text, F.text.regexp(r"^/cleanup").as_("cmd"))
async def cmd_cleanup(message: Message):
    """Очистка ненужных подключений в 3x-ui (только для админов)"""
    user_id = message.from_user.id
    
    # Проверяем, что пользователь - админ
    if user_id not in settings.ADMIN_IDS:
        await message.answer("❌ Эта команда доступна только администраторам")
        return
    
    try:
        await message.answer("🔄 Начинаю очистку ненужных подключений в 3x-ui...")
        
        # Получаем активные UUID из базы данных бота
        from sqlalchemy import select
        from app.database.models import V2RayKey
        
        async with db.session_maker() as session:
            stmt = select(V2RayKey).where(V2RayKey.is_active == True)
            result = await session.execute(stmt)
            keys = result.scalars().all()
            
            active_uuids = {key.uuid for key in keys if key.uuid}
        
        logger.info(f"Найдено {len(active_uuids)} активных UUID в базе данных бота")
        
        # Здесь можно добавить логику получения всех клиентов из 3x-ui
        # и удаления тех, которых нет в active_uuids
        
        await message.answer(
            f"📊 Найдено {len(active_uuids)} активных подключений в базе данных бота.\n\n"
            "💡 Используйте команду `/cleanup_remove <email>` для удаления конкретного клиента.",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Ошибка в /cleanup: {e}")
        await message.answer(f"❌ Ошибка: {e}")


@router.message(F.text, F.text.regexp(r"^/remove_client (.+)").as_("cmd"))
async def cmd_remove_client(message: Message, cmd: str):
    """Удаление конкретного клиента по UUID (только для админов)"""
    user_id = message.from_user.id
    
    # Проверяем, что пользователь - админ
    if user_id not in settings.ADMIN_IDS:
        await message.answer("❌ Эта команда доступна только администраторам")
        return
    
    try:
        # Извлекаем UUID из команды
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.answer(
                "❌ Укажите UUID клиента для удаления\n\n"
                "Использование: `/remove_client <uuid>`",
                parse_mode="Markdown"
            )
            return
        
        uuid = parts[1].strip()
        
        await message.answer(f"🔄 Удаляю клиента {uuid[:8]}...")
        
        # Удаляем клиента
        success = await vps_service.remove_user_from_v2ray(uuid)
        
        if success:
            await message.answer(f"✅ Клиент {uuid[:8]}... успешно удален из 3x-ui")
            logger.info(f"Админ {user_id} удалил клиента {uuid}")
        else:
            await message.answer(f"❌ Не удалось удалить клиента {uuid[:8]}...")
            
    except Exception as e:
        logger.error(f"Ошибка в /remove_client: {e}")
        await message.answer(f"❌ Ошибка: {e}")
