from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from config.settings import settings

# Проверка токена
if not settings.BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в .env файле")

# Инициализация бота и диспетчера (aiogram v3)
bot = Bot(
    token=settings.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode="HTML"),
)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
