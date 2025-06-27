"""
Репозиторий для работы с автоматическими событиями
"""
from typing import List, Optional
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.models import (
    AutoEventSettings, AdminNotificationPreferences, 
    User, Product, TPointsTransaction
)


class AutoEventsRepository:
    """Репозиторий для работы с автоматическими событиями"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    # =============================================================================
    # НАСТРОЙКИ СОБЫТИЙ
    # =============================================================================
    
    async def get_event_settings(self, event_type: str) -> Optional[AutoEventSettings]:
        """Получить настройки события по типу"""
        stmt = select(AutoEventSettings).where(AutoEventSettings.event_type == event_type)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_all_event_settings(self) -> List[AutoEventSettings]:
        """Получить все настройки событий"""
        stmt = select(AutoEventSettings).order_by(AutoEventSettings.event_type)
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    async def create_event_settings(self, event_type: str, **kwargs) -> AutoEventSettings:
        """Создать новые настройки события"""
        settings = AutoEventSettings(event_type=event_type, **kwargs)
        self.session.add(settings)
        return settings
    
    async def update_event_settings(self, settings: AutoEventSettings, **kwargs) -> AutoEventSettings:
        """Обновить настройки события"""
        for key, value in kwargs.items():
            if hasattr(settings, key):
                setattr(settings, key, value)
        return settings
    
    # =============================================================================
    # ПЕРСОНАЛЬНЫЕ НАСТРОЙКИ АДМИНОВ
    # =============================================================================
    
    async def get_admin_preferences(self, user_id: int) -> Optional[AdminNotificationPreferences]:
        """Получить персональные настройки админа"""
        stmt = select(AdminNotificationPreferences).where(
            AdminNotificationPreferences.user_id == user_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def create_admin_preferences(self, user_id: int, **kwargs) -> AdminNotificationPreferences:
        """Создать персональные настройки админа"""
        preferences = AdminNotificationPreferences(user_id=user_id, **kwargs)
        self.session.add(preferences)
        return preferences
    
    async def update_admin_preferences(self, preferences: AdminNotificationPreferences, **kwargs) -> AdminNotificationPreferences:
        """Обновить персональные настройки админа"""
        for key, value in kwargs.items():
            if hasattr(preferences, key):
                setattr(preferences, key, value)
        return preferences
    
    # =============================================================================
    # ПОЛЬЗОВАТЕЛИ
    # =============================================================================
    
    async def get_all_hr_users(self) -> List[User]:
        """Получить всех активных HR пользователей"""
        stmt = select(User).where(
            and_(
                User.role == "hr",
                User.is_active == True
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Получить пользователя по ID"""
        return await self.session.get(User, user_id)
    
    async def get_users_with_birthdays(self) -> List[User]:
        """Получить всех активных пользователей с днями рождения"""
        stmt = select(User).where(
            and_(
                User.is_active == True,
                User.birth_date.isnot(None)
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    async def get_users_with_hire_dates(self) -> List[User]:
        """Получить всех активных пользователей с датами найма"""
        stmt = select(User).where(
            and_(
                User.is_active == True,
                User.hire_date.isnot(None)
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    # =============================================================================
    # ТОВАРЫ
    # =============================================================================
    
    async def get_all_active_products(self) -> List[Product]:
        """Получить все активные товары"""
        stmt = select(Product).where(Product.is_available == True)
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    # =============================================================================
    # ТРАНЗАКЦИИ T-POINTS
    # =============================================================================
    
    async def check_birthday_transaction_exists(self, user_id: int, year: int) -> bool:
        """Проверить, есть ли уже транзакция за день рождения в этом году"""
        from datetime import date
        year_start = date(year, 1, 1)
        
        stmt = select(TPointsTransaction).where(
            and_(
                TPointsTransaction.user_id == user_id,
                TPointsTransaction.description.like('%день рождения%'),
                TPointsTransaction.created_at >= year_start
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None
    
    async def check_anniversary_transaction_exists(self, user_id: int, years: int) -> bool:
        """Проверить, есть ли уже транзакция за юбилей работы"""
        description_pattern = f"{years} лет работы"
        
        stmt = select(TPointsTransaction).where(
            and_(
                TPointsTransaction.user_id == user_id,
                TPointsTransaction.description.like(f'%{description_pattern}%')
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None 