from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery, SuccessfulPayment
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.services.payment import StarsService
from app.services.user import SubscriptionService
from app.services.database import db
from config.settings import settings
import json
from loguru import logger

# Инициализация сервисов
subscription_service = SubscriptionService(db)


router = Router()


@router.message(F.text, F.text.regexp(r"^/buy").as_("cmd"))
async def cmd_buy(message: Message):
    """Команда покупки VPN доступа"""
    await show_tariffs(message)


async def show_tariffs(message_or_callback):
    """Показ списка тарифов (используется и для команды /buy, и для callback)"""
    try:
        async with db.session_maker() as session:
            from sqlalchemy import select
            from app.database.models import Tariff

            stmt = select(Tariff).where(Tariff.is_active == True).order_by(Tariff.price_rub)
            result = await session.execute(stmt)
            tariffs = result.scalars().all()

        if not tariffs:
            text = "❌ На данный момент тарифы недоступны"
            if isinstance(message_or_callback, CallbackQuery):
                await message_or_callback.answer(text, show_alert=True)
            else:
                await message_or_callback.answer(text)
            return

        # Создаем клавиатуру с тарифами
        kb = InlineKeyboardBuilder()

        for tariff in tariffs:
            button_text = f"{tariff.name} - {tariff.price_rub}₽ ({tariff.duration_days} дней)"
            callback_data = f"select_tariff:{tariff.id}"
            kb.button(text=button_text, callback_data=callback_data)

        kb.adjust(1)

        tariffs_text = (
            "📋 *Выберите тарифный план:*\n\n"
            "После оплаты вы сразу получите ключ для V2RayTun!\n\n"
            "💳 *Можно оплатить:*\n"
            "• ⭐ Telegram Stars - *Основной способ оплаты*\n"
            "• СПБ - Скоро появится\n\n"
        )

        if isinstance(message_or_callback, CallbackQuery):
            # Проверяем, есть ли в сообщении фото
            if message_or_callback.message.photo:
                # Если есть фото, редактируем подпись или отправляем новое сообщение
                try:
                    await message_or_callback.message.edit_caption(
                        caption=tariffs_text,
                        parse_mode="Markdown",
                        reply_markup=kb.as_markup()
                    )
                except Exception:
                    # Если не удалось отредактировать подпись, удаляем сообщение и отправляем новое
                    await message_or_callback.message.delete()
                    await message_or_callback.message.answer(
                        tariffs_text,
                        parse_mode="Markdown",
                        reply_markup=kb.as_markup()
                    )
            else:
                # Если нет фото, редактируем текст как обычно
                await message_or_callback.message.edit_text(
                    tariffs_text,
                    parse_mode="Markdown",
                    reply_markup=kb.as_markup()
                )
            await message_or_callback.answer()
        else:
            await message_or_callback.answer(
                tariffs_text,
                parse_mode="Markdown",
                reply_markup=kb.as_markup()
            )

    except Exception as e:
        logger.error(f"Ошибка в show_tariffs: {e}")
        error_text = "Произошла ошибка. Пожалуйста, попробуйте позже."
        if isinstance(message_or_callback, CallbackQuery):
            await message_or_callback.answer(error_text, show_alert=True)
        else:
            await message_or_callback.answer(error_text)


@router.callback_query(F.data == "show_tariffs")
async def callback_show_tariffs(callback: CallbackQuery):
    """Обработчик кнопки 'Купить VPN'"""
    await show_tariffs(callback)


@router.callback_query(F.data.startswith("select_tariff:"))
async def callback_select_tariff(callback: CallbackQuery):
    """Обработка выбора тарифа - показываем выбор способа оплаты"""
    try:
        tariff_id = int(callback.data.split(":")[1])

        async with db.session_maker() as session:
            from sqlalchemy import select
            from app.database.models import Tariff

            stmt = select(Tariff).where(Tariff.id == tariff_id)
            result = await session.execute(stmt)
            tariff = result.scalar_one_or_none()

        if not tariff:
            await callback.answer("Тариф не найден", show_alert=True)
            return

        # Показываем выбор способа оплаты
        payment_methods_text = f"""
💳 *Выберите способ оплаты для тарифа "{tariff.name}"*

💰 *Сумма:* {tariff.price_rub}₽
📅 *Срок:* {tariff.duration_days} дней
📝 *Описание:* {tariff.description}

*Доступные способы оплаты:*
        """

        kb = InlineKeyboardBuilder()
        kb.button(
            text="⭐ Telegram Stars - Основной способ оплаты",
            callback_data=f"create_invoice:{tariff_id}:STARS"
        )
        kb.adjust(1)

        # Проверяем, есть ли в сообщении фото
        if callback.message.photo:
            # Если есть фото, редактируем подпись или отправляем новое сообщение
            try:
                await callback.message.edit_caption(
                    caption=payment_methods_text,
                    parse_mode="Markdown",
                    reply_markup=kb.as_markup()
                )
            except Exception:
                # Если не удалось отредактировать подпись, удаляем сообщение и отправляем новое
                await callback.message.delete()
                await callback.message.answer(
                    payment_methods_text,
                    parse_mode="Markdown",
                    reply_markup=kb.as_markup()
                )
        else:
            # Если нет фото, редактируем текст как обычно
            await callback.message.edit_text(
                payment_methods_text,
                parse_mode="Markdown",
                reply_markup=kb.as_markup(),
            )

        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка в callback_select_tariff: {e}")
        await callback.answer("Произошла ошибка", show_alert=True)


@router.callback_query(F.data.startswith("create_invoice:"))
async def callback_create_invoice(callback: CallbackQuery):
    """Создание счета с выбранным способом оплаты"""
    try:
        # Формат: create_invoice:tariff_id:asset
        parts = callback.data.split(":")
        tariff_id = int(parts[1])
        payment_method = parts[2]  # STARS

        async with db.session_maker() as session:
            from sqlalchemy import select
            from app.database.models import Tariff

            stmt = select(Tariff).where(Tariff.id == tariff_id)
            result = await session.execute(stmt)
            tariff = result.scalar_one_or_none()

        if not tariff:
            await callback.answer("Тариф не найден", show_alert=True)
            return

        paid_bot_username = settings.BOT_USERNAME.lstrip("@") if settings.BOT_USERNAME else ""

        if payment_method == "STARS":
            # Оплата через Telegram Stars (СБП/карта)
            from app.bot.loader import bot
            
            stars_amount = StarsService.rub_to_stars(tariff.price_rub)
            payload = StarsService.create_invoice_payload(callback.from_user.id, tariff_id)
            
            # Создаем инвойс через Telegram Stars
            await bot.send_invoice(
                chat_id=callback.from_user.id,
                title=f"VPN доступ: {tariff.name}",
                description=f"{tariff.description}\nСрок: {tariff.duration_days} дней",
                payload=payload,
                provider_token="",  # Пустая строка для Telegram Stars
                currency="XTR",  # XTR = Telegram Stars
                prices=[LabeledPrice(label=f"{tariff.name} ({tariff.duration_days} дней)", amount=stars_amount)],
            )
            
            await callback.answer("✅ Инвойс отправлен! Проверьте личные сообщения.")
            return
        else:
            await callback.answer("Неизвестный способ оплаты", show_alert=True)
            return

    except Exception as e:
        logger.error(f"Ошибка в callback_create_invoice: {e}")
        await callback.answer("Произошла ошибка", show_alert=True)


@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout: PreCheckoutQuery):
    """Обработка предварительной проверки оплаты через Telegram Stars"""
    try:
        payload_data = StarsService.parse_invoice_payload(pre_checkout.invoice_payload)
        
        if not payload_data:
            await pre_checkout.answer(ok=False, error_message="Ошибка обработки платежа")
            return
        
        # Проверяем, что пользователь существует
        async with db.session_maker() as session:
            from sqlalchemy import select
            from app.database.models import User
            
            user_stmt = select(User).where(User.telegram_id == pre_checkout.from_user.id)
            user_result = await session.execute(user_stmt)
            user = user_result.scalar_one_or_none()
            
            if not user:
                await pre_checkout.answer(ok=False, error_message="Пользователь не найден")
                return
        
        # Подтверждаем оплату
        await pre_checkout.answer(ok=True)
        logger.info(f"Предварительная проверка оплаты Stars: user_id={pre_checkout.from_user.id}, payload={payload_data}")
        
    except Exception as e:
        logger.error(f"Ошибка в pre_checkout_handler: {e}")
        await pre_checkout.answer(ok=False, error_message="Ошибка обработки платежа")


@router.message(F.successful_payment)
async def successful_payment_handler(message: Message):
    """Обработка успешной оплаты через Telegram Stars"""
    try:
        payment: SuccessfulPayment = message.successful_payment
        
        # Парсим payload
        payload_data = StarsService.parse_invoice_payload(payment.invoice_payload)
        
        if not payload_data:
            await message.answer("❌ Ошибка обработки платежа. Обратитесь в поддержку.")
            return
        
        user_id = payload_data.get("user_id")
        tariff_id = payload_data.get("tariff_id")
        
        if not user_id or not tariff_id:
            await message.answer("❌ Ошибка обработки платежа. Обратитесь в поддержку.")
            return
        
        # Сохраняем платеж в базе
        async with db.session_maker() as session:
            from sqlalchemy import select
            from app.database.models import Payment, User
            
            user_stmt = select(User.id).where(User.telegram_id == user_id)
            user_result = await session.execute(user_stmt)
            db_user_id = user_result.scalar_one_or_none()
            
            if db_user_id:
                # Сохраняем платеж
                stars_amount = payment.total_amount
                rub_amount = StarsService.stars_to_rub(stars_amount)
                
                payment_record = Payment(
                    user_id=db_user_id,
                    invoice_id=int(payment.telegram_payment_charge_id) if payment.telegram_payment_charge_id else 0,
                    amount=rub_amount,
                    currency="RUB",
                    status="paid",
                    payment_method="stars"
                )
                session.add(payment_record)
                await session.commit()
        
        # Активируем подписку
        success = await subscription_service.create_subscription(user_id, tariff_id)
        
        if success:
            await message.answer(
                "✅ *Оплата успешно получена!*\n\n"
                "🔑 Ваш ключ доступа отправляется...",
                parse_mode="Markdown"
            )
            
            # Отправляем ключ пользователю
            from app.handlers.user.v2ray import send_v2ray_key_to_user
            await send_v2ray_key_to_user(user_id)
            
            logger.info(f"Оплата Stars успешно обработана: user_id={user_id}, tariff_id={tariff_id}")
        else:
            await message.answer(
                "❌ Ошибка активации подписки. Обратитесь в поддержку.\n"
                f"ID платежа: {payment.telegram_payment_charge_id}"
            )
            logger.error(f"Ошибка активации подписки после оплаты Stars: user_id={user_id}, tariff_id={tariff_id}")
            
    except Exception as e:
        logger.error(f"Ошибка в successful_payment_handler: {e}")
        await message.answer("❌ Произошла ошибка при обработке платежа. Обратитесь в поддержку.")
