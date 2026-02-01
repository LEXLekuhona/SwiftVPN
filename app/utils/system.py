import sys
from pathlib import Path
from loguru import logger

def setup_logging():
    """Настройка логирования"""
    logger.remove()
    
    # Консоль
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO"
    )
    
    # Файл
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    logger.add(
        log_dir / "bot.log",
        rotation="10 MB",
        retention="30 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG"
    )

def create_dirs():
    """Создание необходимых директорий"""
    # Создаем папку data для базы данных
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    
    # Создаем папку static/images для изображений
    static_dir = Path("static/images")
    static_dir.mkdir(parents=True, exist_ok=True)
    
    # Создаем папку scripts для скриптов
    scripts_dir = Path("scripts")
    scripts_dir.mkdir(exist_ok=True)
    
    logger.debug("Директории созданы/проверены")