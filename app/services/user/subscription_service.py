from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
from loguru import logger

class SubscriptionService:
    def __init__(self, db):
        self.db = db
    
    async def check_subscription(self, user_id: int) -> Tuple[bool, Optional[datetime]]:
        """Проверка подписки пользователя"""
        async with self.db.session_maker() as session:
            from sqlalchemy import select, and_
            from app.database.models import Subscription, User
            
            stmt = select(Subscription).join(User).where(
                and_(
                    User.telegram_id == user_id,
                    Subscription.is_active == True
                )
            )
            
            result = await session.execute(stmt)
            subscription = result.scalar_one_or_none()
            
            if not subscription:
                return False, None
            
            now = datetime.utcnow()
            
            # Проверяем не истекла ли подписка
            if subscription.end_date and subscription.end_date < now:
                subscription.is_active = False
                await session.commit()
                logger.info(f"Подписка истекла для user_id={user_id}")
                return False, None
            
            return True, subscription.end_date
    
    async def create_subscription(self, user_id: int, tariff_id: int) -> bool:
        """Создание или продление подписки"""
        async with self.db.session_maker() as session:
            from sqlalchemy import select, and_
            from app.database.models import Subscription, User, Tariff
            
            # Получаем пользователя
            user_stmt = select(User).where(User.telegram_id == user_id)
            user_result = await session.execute(user_stmt)
            user = user_result.scalar_one_or_none()
            
            if not user:
                logger.error(f"Пользователь {user_id} не найден")
                return False
            
            # Получаем тариф
            tariff_stmt = select(Tariff).where(Tariff.id == tariff_id)
            tariff_result = await session.execute(tariff_stmt)
            tariff = tariff_result.scalar_one_or_none()
            
            if not tariff:
                logger.error(f"Тариф {tariff_id} не найден")
                return False
            
            # Проверяем существующую подписку
            subscription_stmt = select(Subscription).where(
                Subscription.user_id == user.id
            )
            subscription_result = await session.execute(subscription_stmt)
            existing_subscription = subscription_result.scalar_one_or_none()
            
            now = datetime.utcnow()
            end_date = now + timedelta(days=tariff.duration_days)
            
            if existing_subscription:
                # Продлеваем существующую
                if existing_subscription.end_date and existing_subscription.end_date > now:
                    end_date = existing_subscription.end_date + timedelta(days=tariff.duration_days)
                
                existing_subscription.tariff_id = tariff_id
                existing_subscription.end_date = end_date
                existing_subscription.is_active = True
            else:
                # Создаем новую
                new_subscription = Subscription(
                    user_id=user.id,
                    tariff_id=tariff_id,
                    start_date=now,
                    end_date=end_date,
                    is_active=True
                )
                session.add(new_subscription)
            
            await session.commit()
            logger.info(f"Подписка создана/продлена для user_id={user_id}")
            return True
    
    async def get_subscription_info(self, user_id: int) -> Optional[Dict]:
        """Получение информации о подписке"""
        async with self.db.session_maker() as session:
            from sqlalchemy import select, and_
            from app.database.models import Subscription, User, Tariff
            
            stmt = select(
                Subscription.start_date,
                Subscription.end_date,
                Subscription.is_active,
                Tariff.name,
                Tariff.price_rub,
                Tariff.duration_days
            ).join(User).join(Tariff).where(
                and_(
                    User.telegram_id == user_id,
                    Subscription.is_active == True
                )
            )
            
            result = await session.execute(stmt)
            row = result.fetchone()
            
            if row:
                days_left = 0
                if row.end_date:
                    days_left = max(0, (row.end_date - datetime.utcnow()).days)
                
                return {
                    "start_date": row.start_date,
                    "end_date": row.end_date,
                    "is_active": row.is_active,
                    "tariff_name": row.name,
                    "price": row.price_rub,
                    "duration": row.duration_days,
                    "days_left": days_left
                }
            
            return None