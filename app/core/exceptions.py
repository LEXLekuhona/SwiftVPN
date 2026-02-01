"""
Кастомные исключения проекта
"""


class VPNBotException(Exception):
    """Базовое исключение для VPN бота"""
    pass


class DatabaseError(VPNBotException):
    """Ошибка базы данных"""
    pass


class APIError(VPNBotException):
    """Ошибка API"""
    pass


class ConfigurationError(VPNBotException):
    """Ошибка конфигурации"""
    pass


class ValidationError(VPNBotException):
    """Ошибка валидации данных"""
    pass


class ServiceError(VPNBotException):
    """Ошибка сервиса"""
    pass
