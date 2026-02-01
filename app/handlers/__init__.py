from aiogram import Dispatcher

from app.handlers.user import start, payment, profile, v2ray
from app.handlers.admin import free_vpn, cleanup
from app.handlers import errors


def register_all_handlers(dp: Dispatcher) -> None:
    """Регистрация всех обработчиков (aiogram v3 routers)"""
    # Сначала регистрируем обработчик ошибок (должен быть последним)
    # Но в aiogram v3 ошибки обрабатываются автоматически через router.errors()
    
    # Регистрируем пользовательские обработчики
    dp.include_router(start.router)
    dp.include_router(payment.router)
    dp.include_router(profile.router)
    dp.include_router(v2ray.router)
    
    # Регистрируем админские обработчики
    dp.include_router(free_vpn.router)
    dp.include_router(cleanup.router)
    
    # Регистрируем обработчик ошибок последним
    dp.include_router(errors.router)

