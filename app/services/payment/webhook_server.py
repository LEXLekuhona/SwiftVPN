"""HTTP-сервер для webhook-уведомлений ЮKassa."""
import ipaddress
from typing import Optional

from aiohttp import web
from loguru import logger

from app.services.payment.payment_fulfillment import fulfill_tariff_payment, mark_payment_canceled
from app.services.payment.yookassa_service import YooKassaService
from config.settings import settings

# IP-адреса ЮKassa: https://yookassa.ru/developers/using-api/webhooks
YOOKASSA_IP_NETWORKS = [
    ipaddress.ip_network("185.71.76.0/27"),
    ipaddress.ip_network("185.71.77.0/27"),
    ipaddress.ip_network("77.75.153.0/25"),
    ipaddress.ip_network("77.75.154.128/25"),
    ipaddress.ip_network("2a02:5180::/32"),
]
YOOKASSA_IP_HOSTS = [
    ipaddress.ip_address("77.75.156.11"),
    ipaddress.ip_address("77.75.156.35"),
]


def _is_yookassa_ip(peer_ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(peer_ip)
    except ValueError:
        return False
    if addr in YOOKASSA_IP_HOSTS:
        return True
    return any(addr in network for network in YOOKASSA_IP_NETWORKS)


async def _process_payment_object(payment: dict) -> None:
    if payment.get("status") != "succeeded":
        return

    metadata = payment.get("metadata") or {}
    telegram_user_id = metadata.get("telegram_user_id")
    tariff_id = metadata.get("tariff_id")
    if not telegram_user_id or not tariff_id:
        logger.warning(f"В платеже {payment.get('id')} нет metadata")
        return

    amount = payment.get("amount") or {}
    amount_rub = float(amount.get("value", 0))

    from app.bot.loader import bot
    from app.handlers.user.v2ray import send_v2ray_key_to_user

    user_id = int(telegram_user_id)
    tariff = int(tariff_id)
    payment_id = payment["id"]

    success = await fulfill_tariff_payment(
        telegram_user_id=user_id,
        tariff_id=tariff,
        amount_rub=amount_rub,
        payment_method="sbp",
        external_id=payment_id,
    )
    if not success:
        return

    try:
        await bot.send_message(
            user_id,
            "✅ <b>Оплата через СБП получена!</b>\n\n"
            "🔑 Ваш ключ доступа отправляется...",
        )
        await send_v2ray_key_to_user(user_id)
    except Exception as e:
        logger.error(f"Не удалось уведомить пользователя {user_id}: {e}")


async def yookassa_webhook_handler(request: web.Request) -> web.Response:
    peer = request.remote or ""
    if settings.YOOKASSA_WEBHOOK_VERIFY_IP and not _is_yookassa_ip(peer):
        logger.warning(f"Webhook с неизвестного IP: {peer}")
        return web.Response(status=403)

    try:
        body = await request.json()
    except Exception:
        return web.Response(status=400)

    event = body.get("event")
    payment = body.get("object") or {}
    payment_id = payment.get("id")

    if not payment_id:
        return web.Response(status=200)

    if event == "payment.canceled":
        await mark_payment_canceled(payment_id)
        return web.Response(status=200)

    if event != "payment.succeeded":
        return web.Response(status=200)

    try:
        verified = await YooKassaService.get_payment(payment_id)
    except Exception as e:
        logger.error(f"Не удалось проверить платёж {payment_id}: {e}")
        return web.Response(status=500)

    await _process_payment_object(verified)
    return web.Response(status=200)


def create_webhook_app() -> web.Application:
    app = web.Application()
    app.router.add_post(settings.YOOKASSA_WEBHOOK_PATH, yookassa_webhook_handler)
    return app


async def start_webhook_server() -> Optional[web.AppRunner]:
    if not YooKassaService.is_configured():
        return None
    if not settings.YOOKASSA_WEBHOOK_ENABLED:
        logger.info("Webhook ЮKassa отключён (YOOKASSA_WEBHOOK_ENABLED=false)")
        return None

    app = create_webhook_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.YOOKASSA_WEBHOOK_HOST, settings.YOOKASSA_WEBHOOK_PORT)
    await site.start()
    logger.info(
        f"Webhook ЮKassa: http://{settings.YOOKASSA_WEBHOOK_HOST}:"
        f"{settings.YOOKASSA_WEBHOOK_PORT}{settings.YOOKASSA_WEBHOOK_PATH}"
    )
    return runner


async def stop_webhook_server(runner: Optional[web.AppRunner]) -> None:
    if runner:
        await runner.cleanup()
