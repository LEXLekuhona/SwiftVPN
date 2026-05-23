"""Асинхронный клиент API ЮKassa для оплаты через СБП."""
import base64
import uuid
from typing import Any, Dict, Optional

import aiohttp
from loguru import logger

from config.settings import settings

API_BASE = "https://api.yookassa.ru/v3"


class YooKassaError(Exception):
    """Ошибка при обращении к API ЮKassa."""


class YooKassaService:
    @staticmethod
    def is_configured() -> bool:
        return bool(settings.YOOKASSA_SHOP_ID and settings.YOOKASSA_SECRET_KEY)

    @staticmethod
    def _auth_header() -> str:
        credentials = f"{settings.YOOKASSA_SHOP_ID}:{settings.YOOKASSA_SECRET_KEY}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    @staticmethod
    def _return_url() -> str:
        if settings.YOOKASSA_RETURN_URL:
            return settings.YOOKASSA_RETURN_URL
        username = settings.BOT_USERNAME.lstrip("@")
        if username:
            return f"https://t.me/{username}"
        return "https://t.me"

    @classmethod
    async def _request(
        cls,
        method: str,
        path: str,
        *,
        json_data: Optional[Dict[str, Any]] = None,
        idempotence_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        headers = {
            "Authorization": cls._auth_header(),
            "Content-Type": "application/json",
        }
        if idempotence_key:
            headers["Idempotence-Key"] = idempotence_key

        url = f"{API_BASE}{path}"
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json_data, headers=headers) as resp:
                body = await resp.json(content_type=None)
                if resp.status >= 400:
                    logger.error(f"ЮKassa API {resp.status}: {body}")
                    description = ""
                    if isinstance(body, dict):
                        description = body.get("description", "") or str(body)
                    raise YooKassaError(description or f"HTTP {resp.status}")
                if not isinstance(body, dict):
                    raise YooKassaError("Некорректный ответ API ЮKassa")
                return body

    @classmethod
    async def create_sbp_payment(
        cls,
        amount_rub: float,
        description: str,
        metadata: Dict[str, str],
    ) -> Dict[str, Any]:
        """Создаёт платёж СБП и возвращает объект payment от API."""
        payload = {
            "amount": {
                "value": f"{amount_rub:.2f}",
                "currency": "RUB",
            },
            "payment_method_data": {"type": "sbp"},
            "confirmation": {
                "type": "redirect",
                "return_url": cls._return_url(),
            },
            "capture": True,
            "description": description[:128],
            "metadata": metadata,
        }
        return await cls._request(
            "POST",
            "/payments",
            json_data=payload,
            idempotence_key=str(uuid.uuid4()),
        )

    @classmethod
    async def get_payment(cls, payment_id: str) -> Dict[str, Any]:
        return await cls._request("GET", f"/payments/{payment_id}")

    @classmethod
    def get_confirmation_url(cls, payment: Dict[str, Any]) -> Optional[str]:
        confirmation = payment.get("confirmation") or {}
        return confirmation.get("confirmation_url")
