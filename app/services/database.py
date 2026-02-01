from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import text
from app.database.models import Base
from config.settings import settings
from loguru import logger

class Database:
    def __init__(self):
        self.engine = create_async_engine(
            settings.DATABASE_URL,
            echo=False,
            future=True
        )
        self.session_maker = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
    
    async def init_db(self):
        """Инициализация базы данных"""
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            
            # Добавляем тестовые тарифы
            async with self.session_maker() as session:
                from app.database.models import Tariff

                # Проверяем, есть ли уже тарифы
                result = await session.execute(text("SELECT COUNT(*) FROM tariffs"))
                count = result.scalar()
                
                if count == 0:
                    tariffs = [
                        Tariff(
                            name="Базовый",
                            price_rub=104,
                            duration_days=30,
                            description="VPN доступ на 30 дней"
                        ),
                        Tariff(
                            name="Премиум",
                            price_rub=529,
                            duration_days=180,
                            description="VPN доступ на 180 дней"
                        ),
                        Tariff(
                            name="Годовой",
                            price_rub=1060,
                            duration_days=365,
                            description="VPN доступ на 365 дней"
                        )
                    ]
                    
                    session.add_all(tariffs)
                    await session.commit()
                    logger.info("Добавлены тестовые тарифы")
            
            logger.info("База данных инициализирована")
            
        except Exception as e:
            logger.error(f"Ошибка инициализации БД: {e}")
            raise
    
    async def close(self):
        """Закрытие соединения с базой данных"""
        await self.engine.dispose()
        logger.info("Соединение с БД закрыто")
    
    async def get_session(self):
        """Получение сессии базы данных"""
        async with self.session_maker() as session:
            try:
                yield session
            finally:
                await session.close()

# Создаем глобальный экземпляр
db = Database()