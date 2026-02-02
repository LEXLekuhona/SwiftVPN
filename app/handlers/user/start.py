from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.services.database import db
from config.settings import settings
from loguru import logger


router = Router()


@router.message(F.text, F.text.regexp(r"^/start").as_("cmd"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    user = message.from_user

    try:
        async with db.session_maker() as session:
            from sqlalchemy import select
            from app.database.models import User

            # Проверяем, есть ли пользователь
            stmt = select(User).where(User.telegram_id == user.id)
            result = await session.execute(stmt)
            existing_user = result.scalar_one_or_none()

            if not existing_user:
                # Регистрируем нового пользователя
                new_user = User(
                    telegram_id=user.id,
                    username=user.username,
                    first_name=user.first_name,
                    last_name=user.last_name
                )
                session.add(new_user)
                await session.commit()
                logger.info(f"Новый пользователь: {user.id} - {user.username}")

        # Приветственное сообщение
        welcome_text = f"""
👋 Здравствуйте, {user.first_name}!

Добро пожаловать в SwiftVPN! 
Ваш ключ к быстрому и безопасному интернету.
        """

        # Клавиатура
        kb = InlineKeyboardBuilder()
        kb.button(text="💰 Купить VPN", callback_data="show_tariffs")
        kb.button(text="❓ Как подключиться?", callback_data="how_to_connect")
        kb.adjust(2)

        # Отправляем фото с текстом в подписи (caption)
        from pathlib import Path
        from aiogram.types import FSInputFile
        
        image_path = Path("static/images/gemini.jpg")
        if image_path.exists():
            photo = FSInputFile(image_path)
            await message.answer_photo(
                photo=photo,
                caption=welcome_text,
                parse_mode="Markdown",
                reply_markup=kb.as_markup()
            )
        else:
            # Если изображение не найдено, отправляем только текст
            await message.answer(welcome_text, parse_mode="Markdown", reply_markup=kb.as_markup())

    except Exception as e:
        logger.error(f"Ошибка в /start: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")


@router.callback_query(F.data == "how_to_connect")
async def callback_how_to_connect(callback: CallbackQuery):
    """Обработчик кнопки 'Как подключиться?'"""
    try:
        instruction_text = """
📱 *Как подключиться в V2RayTun:*

1️⃣ *Установите приложение:*
• Android: V2RayTun из Play Market
• iOS: V2RayTun из App Store

2️⃣ *Подключитесь:*
• Откройте V2RayTun
• Нажмите ➕ (добавить)
• Выберите *"Импорт из буфера обмена"*
• Приложение автоматически определит конфигурацию
• Нажмите *"Подключиться"*

✅ *Готово!* Вы защищены.

🛠 *Если возникли проблемы:*
• Перезапустите приложение
• Проверьте интернет соединение
• Напишите в поддержку
        """

        kb = InlineKeyboardBuilder()
        kb.button(
            text="📥 Скачать V2RayTun",
            url="https://play.google.com/store/apps/details?id=com.v2raytun.app",
        )
        
        # Кнопка поддержки ведет на профиль администратора
        if settings.ADMIN_IDS:
            admin_id = settings.ADMIN_IDS[0]  # Берем первого администратора
            kb.button(
                text="🛠 Поддержка",
                url=f"tg://user?id={admin_id}",
            )
        elif settings.SUPPORT_USERNAME:
            # Fallback на username, если ADMIN_IDS не указан
            kb.button(
                text="🛠 Поддержка",
                url=f"https://t.me/{settings.SUPPORT_USERNAME}",
            )
        kb.adjust(2)

        # Проверяем, есть ли фото в сообщении
        if callback.message.photo:
            # Если сообщение содержит фото, используем edit_caption или отправляем новое
            try:
                await callback.message.edit_caption(
                    caption=instruction_text,
                    parse_mode="Markdown",
                    reply_markup=kb.as_markup()
                )
            except Exception:
                # Если edit_caption не работает, отправляем новое сообщение
                await callback.message.delete()
                await callback.message.answer(
                    instruction_text,
                    parse_mode="Markdown",
                    reply_markup=kb.as_markup()
                )
        else:
            # Если фото нет, используем обычный edit_text
            await callback.message.edit_text(
                instruction_text,
                parse_mode="Markdown",
                reply_markup=kb.as_markup()
            )
        
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка в callback_how_to_connect: {e}")
        import traceback
        logger.error(traceback.format_exc())
        await callback.answer("Произошла ошибка", show_alert=True)


@router.message(F.text, F.text.regexp(r"^/help").as_("cmd"))
async def cmd_help(message: Message):
    """Обработчик команды /help"""
    try:
        help_text = """
📖 *Помощь по использованию бота*

🔹 *Основные команды:*
/start - Запустить бота
/buy - Купить VPN доступ
/mykey - Получить ключ доступа
/profile - Мой профиль
/help - Показать эту справку

🔹 *Как это работает:*
1️⃣ Выберите тариф и оплатите через Telegram Stars
2️⃣ Получите ключ доступа автоматически
3️⃣ Скопируйте ключ и импортируйте в V2RayTun
4️⃣ Наслаждайтесь быстрым и безопасным интернетом!

🔹 *Приложения для подключения:*
• Android: V2RayTun из Play Market
• iOS: V2RayTun из App Store

🔹 *Нужна помощь?*
Нажмите кнопку "❓ Как подключиться?" для подробной инструкции.
        """

        kb = InlineKeyboardBuilder()
        kb.button(text="💰 Купить VPN", callback_data="show_tariffs")
        kb.button(text="❓ Как подключиться?", callback_data="how_to_connect")
        
        # Кнопка поддержки ведет на профиль администратора
        if settings.ADMIN_IDS:
            admin_id = settings.ADMIN_IDS[0]
            kb.button(
                text="🛠 Поддержка",
                url=f"tg://user?id={admin_id}",
            )
        elif settings.SUPPORT_USERNAME:
            kb.button(
                text="🛠 Поддержка",
                url=f"https://t.me/{settings.SUPPORT_USERNAME}",
            )
        kb.adjust(2, 1)

        await message.answer(
            help_text,
            parse_mode="Markdown",
            reply_markup=kb.as_markup()
        )

    except Exception as e:
        logger.error(f"Ошибка в /help: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

