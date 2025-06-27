"""
Базовые классы для архитектуры
"""
from abc import ABC
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from typing import Generic, TypeVar
import logging

logger = logging.getLogger(__name__)

# Generic типы для моделей
ModelType = TypeVar('ModelType')

class BaseRepository(ABC):
    """Базовый класс для всех репозиториев"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        
    async def commit(self):
        """Коммитить транзакцию (обычно делается в middleware)"""
        await self.session.commit()
        
    async def rollback(self):
        """Откатить транзакцию"""
        await self.session.rollback()


class BaseService(ABC):
    """Базовый класс для всех сервисов"""
    
    def __init__(self, session: AsyncSession):
        self.session = session


class BaseSessionFactoryService(ABC):
    """Базовый класс для сервисов, которые создают собственные сессии"""
    
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self.session_factory = session_factory
        
    async def session(self):
        """Создать новую сессию"""
        return self.session_factory() 