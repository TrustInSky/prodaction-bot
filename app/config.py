from dataclasses import dataclass
from os import getenv
from typing import Optional
from dotenv import load_dotenv
import os

# Загружаем переменные окружения из файла .env
load_dotenv()

@dataclass
class Config:
    """Конфигурация приложения"""
    
    def __init__(self):
        """Инициализация конфигурации"""
        self.BOT_TOKEN = getenv("BOT_TOKEN")
        self.GROUP_ID = getenv("GROUP_ID")
        self.DATABASE_URL = getenv("DATABASE_URL", "sqlite+aiosqlite:///data/shop.db")
        self.DEBUG = getenv("DEBUG", "false")
        
        # Настройки сети и Telegram API
        self.TELEGRAM_TIMEOUT = int(getenv("TELEGRAM_TIMEOUT", "30"))  # Таймаут запросов к Telegram API
        self.TELEGRAM_RETRY_COUNT = int(getenv("TELEGRAM_RETRY_COUNT", "3"))  # Количество повторных попыток
        self.TELEGRAM_RETRY_DELAY = float(getenv("TELEGRAM_RETRY_DELAY", "1.0"))  # Задержка между попытками
        self.AIOHTTP_POOL_SIZE = int(getenv("AIOHTTP_POOL_SIZE", "100"))  # Размер пула соединений
        self.AIOHTTP_TIMEOUT = int(getenv("AIOHTTP_TIMEOUT", "60"))  # Таймаут aiohttp клиента
        
        # Преобразуем GROUP_ID в int
        try:
            self.GROUP_ID = int(self.GROUP_ID) if self.GROUP_ID else None
        except (ValueError, TypeError):
            self.GROUP_ID = None
            
        # Преобразуем DEBUG в bool
        self.DEBUG = str(self.DEBUG).lower() in ('true', '1', 'yes')