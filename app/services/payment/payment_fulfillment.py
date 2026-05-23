"""Общая логика завершения оплаты и активации подписки."""
from datetime import datetime
from typing import Optional

from loguru import logger
from sqlalchemy import select

from app.database.models import Payment, User
from app.services.database import db
from app.services.user import SubscriptionService

subscription_service = SubscriptionService(db)


async def fulfill_tariff_payment(
    telegram_user_id: int,
    tariff_id: int,
    amount_rub: float,
    payment_method: str,
    external_id: str,
) -> bool:
    """
    Активирует подписку после успешной оплаты.
    Идемпотентна: повторный вызов для уже оплаченного платежа не дублирует подписку.
    """
    async with db.session_maker() as session:
        existing_stmt = select(Payment).where(Payment.yookassa_payment_id == external_id)
        existing_result = await session.execute(existing_stmt)
        payment_record = existing_result.scalar_one_or_none()

        if payment_record and payment_record.status == "paid":
            logger.info(f"Платёж {external_id} уже обработан")
            return True

        user_stmt = select(User).where(User.telegram_id == telegram_user_id)
        user_result = await session.execute(user_stmt)
        user = user_result.scalar_one_or_none()
        if not user:
            logger.error(f"Пользователь telegram_id={telegram_user_id} не найден")
            return False

        if payment_record:
            payment_record.status = "paid"
            payment_record.paid_at = datetime.utcnow()
            payment_record.amount = amount_rub
        else:
            payment_record = Payment(
                user_id=user.id,
                amount=amount_rub,
                currency="RUB",
                status="paid",
                payment_method=payment_method,
                yookassa_payment_id=external_id,
                paid_at=datetime.utcnow(),
            )
            session.add(payment_record)

        await session.commit()

    success = await subscription_service.create_subscription(telegram_user_id, tariff_id)
    if not success:
        logger.error(
            f"Ошибка активации подписки: user_id={telegram_user_id}, tariff_id={tariff_id}"
        )
    return success


async def mark_payment_canceled(external_id: str) -> None:
    async with db.session_maker() as session:
        stmt = select(Payment).where(Payment.yookassa_payment_id == external_id)
        result = await session.execute(stmt)
        payment_record = result.scalar_one_or_none()
        if payment_record and payment_record.status == "pending":
            payment_record.status = "canceled"
            await session.commit()


async def create_pending_payment(
    telegram_user_id: int,
    tariff_id: int,
    amount_rub: float,
    yookassa_payment_id: str,
) -> None:
    async with db.session_maker() as session:
        user_stmt = select(User.id).where(User.telegram_id == telegram_user_id)
        user_result = await session.execute(user_stmt)
        db_user_id = user_result.scalar_one_or_none()
        if not db_user_id:
            raise ValueError(f"Пользователь {telegram_user_id} не найден")

        payment_record = Payment(
            user_id=db_user_id,
            amount=amount_rub,
            currency="RUB",
            status="pending",
            payment_method="sbp",
            yookassa_payment_id=yookassa_payment_id,
        )
        session.add(payment_record)
        await session.commit()
