"""
Скрипт для обновления цен тарифов в базе данных
"""
import asyncio
from app.services.database import db
from app.database.models import Tariff
from sqlalchemy import select, update
from loguru import logger

# НОВЫЕ ЦЕНЫ - измените здесь
NEW_PRICES = {
    "Базовый": 104,      # 30 дней (⭐50)
    "Премиум": 529,      # 180 дней (⭐250)
    "Годовой": 1060      # 365 дней (⭐500)
}

# Обновление длительности для Премиум тарифа
UPDATE_DURATION = {
    "Премиум": 180  # Обновить длительность с 90 на 180 дней
}

async def update_tariff_prices():
    """Обновление цен тарифов"""
    try:
        async with db.session_maker() as session:
            for tariff_name, new_price in NEW_PRICES.items():
                # Находим тариф по имени
                stmt = select(Tariff).where(Tariff.name == tariff_name)
                result = await session.execute(stmt)
                tariff = result.scalar_one_or_none()
                
                if tariff:
                    old_price = tariff.price_rub
                    old_duration = tariff.duration_days
                    tariff.price_rub = new_price
                    
                    # Обновляем длительность, если нужно
                    if tariff_name in UPDATE_DURATION:
                        new_duration = UPDATE_DURATION[tariff_name]
                        tariff.duration_days = new_duration
                        tariff.description = f"VPN доступ на {new_duration} дней"
                        logger.info(f"✅ Тариф '{tariff_name}': {old_price}₽ → {new_price}₽, {old_duration} дней → {new_duration} дней")
                    else:
                        logger.info(f"✅ Тариф '{tariff_name}': {old_price}₽ → {new_price}₽")
                else:
                    logger.warning(f"⚠️ Тариф '{tariff_name}' не найден в базе данных")
            
            await session.commit()
            logger.info("✅ Цены тарифов успешно обновлены!")
            
    except Exception as e:
        logger.error(f"❌ Ошибка обновления цен: {e}")
        raise
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(update_tariff_prices())
