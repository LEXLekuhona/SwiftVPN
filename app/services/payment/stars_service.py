"""
Сервис для работы с Telegram Stars
Telegram Stars - встроенная система оплаты Telegram, не требует ИП/самозанятости
Пользователи могут оплачивать через СБП/карты, покупая Stars
"""
from typing import Optional, Dict
from loguru import logger


class StarsService:
    """Сервис для работы с Telegram Stars"""
    
    # Курс Stars к рублям (примерный, можно обновлять через API Telegram)
    # 1 Star ≈ 0.01 USD, при курсе 100 RUB/USD = 1 Star ≈ 1 RUB
    # Но лучше использовать реальный курс из API или обновлять вручную
    STARS_TO_RUB_RATE = 1.0  # 1 Star = 1 RUB (примерно)
    
    @staticmethod
    def rub_to_stars(rub_amount: float) -> int:
        """Конвертация рублей в Stars"""
        return int(rub_amount / StarsService.STARS_TO_RUB_RATE)
    
    @staticmethod
    def stars_to_rub(stars_amount: int) -> float:
        """Конвертация Stars в рубли"""
        return stars_amount * StarsService.STARS_TO_RUB_RATE
    
    @staticmethod
    def create_invoice_payload(user_id: int, tariff_id: int) -> str:
        """Создание payload для инвойса"""
        import json
        return json.dumps({
            "user_id": user_id,
            "tariff_id": tariff_id,
            "payment_method": "stars"
        })
    
    @staticmethod
    def parse_invoice_payload(payload: str) -> Optional[Dict]:
        """Парсинг payload из инвойса"""
        try:
            import json
            return json.loads(payload)
        except Exception as e:
            logger.error(f"Ошибка парсинга payload: {e}")
            return None
