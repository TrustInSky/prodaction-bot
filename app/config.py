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
        
        # Преобразуем GROUP_ID в int
        try:
            self.GROUP_ID = int(self.GROUP_ID) if self.GROUP_ID else None
        except (ValueError, TypeError):
            self.GROUP_ID = None
            
        # Преобразуем DEBUG в bool
        self.DEBUG = str(self.DEBUG).lower() in ('true', '1', 'yes')