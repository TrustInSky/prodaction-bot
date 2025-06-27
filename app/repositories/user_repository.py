from sqlalchemy import select, update, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.models import User
from ..core.base import BaseRepository
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

class UserRepository(BaseRepository):
    """Репозиторий для работы с пользователями"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session)
        
    async def get_user_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Получить пользователя по Telegram ID"""
        query = select(User).where(User.telegram_id == telegram_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
        
    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Получить пользователя по telegram_id (который является primary key)"""
        return await self.get_user_by_telegram_id(user_id)
        
    async def get_or_create_user(self, telegram_id: int, username: Optional[str], fullname: str, is_active: bool = True) -> User:
        """Получить или создать пользователя"""
        # Пытаемся найти пользователя
        query = select(User).where(User.telegram_id == telegram_id)
        result = await self.session.execute(query)
        user = result.scalar_one_or_none()
        
        if user:
            # Обновляем данные пользователя
            user.username = username
            user.fullname = fullname
            user.is_active = is_active
            # Не нужно коммитить здесь - middleware сделает это
        else:
            # Создаем нового пользователя
            user = User(
                telegram_id=telegram_id,
                username=username,
                fullname=fullname,
                is_active=is_active,
                role="user",
                tpoints=0
            )
            self.session.add(user)
            # Не нужно коммитить здесь - middleware сделает это
            
        return user
        
    async def update_tpoints(self, telegram_id: int, points: int) -> bool:
        """Обновить количество T-Points у пользователя"""
        try:
            query = update(User).where(User.telegram_id == telegram_id).values(tpoints=points)
            await self.session.execute(query)
            return True
        except Exception as e:
            logger.error(f"Error updating T-Points for user {telegram_id}: {e}")
            return False
            
    async def add_tpoints(self, telegram_id: int, points: int) -> bool:
        """Добавить T-Points пользователю"""
        try:
            user = await self.get_user_by_telegram_id(telegram_id)
            if user:
                return await self.update_tpoints(telegram_id, user.tpoints + points)
            return False
        except Exception as e:
            logger.error(f"Error adding T-Points for user {telegram_id}: {e}")
            return False
            
    async def remove_tpoints(self, telegram_id: int, points: int) -> bool:
        """Удалить T-Points у пользователя"""
        try:
            user = await self.get_user_by_telegram_id(telegram_id)
            if user and user.tpoints >= points:
                return await self.update_tpoints(telegram_id, user.tpoints - points)
            return False
        except Exception as e:
            logger.error(f"Error removing T-Points for user {telegram_id}: {e}")
            return False
            
    async def get_all_users(self) -> List[User]:
        """Получить всех пользователей (включая неактивных)"""
        query = select(User)
        result = await self.session.execute(query)
        return list(result.scalars().all())
        
    async def get_all_active_users(self) -> List[User]:
        """Получить всех активных пользователей"""
        query = select(User).where(User.is_active == True)
        result = await self.session.execute(query)
        return list(result.scalars().all())
        
    async def get_all_hr_users(self) -> List[User]:
        """Получить всех HR-пользователей"""
        query = select(User).where(User.role == "hr", User.is_active == True)
        result = await self.session.execute(query)
        return list(result.scalars().all())
        
    async def get_all_hr_and_admin_users(self) -> List[User]:
        """Получить всех HR и админов для работы с заказами"""
        query = select(User).where(User.role.in_(["hr", "admin"]), User.is_active == True)
        result = await self.session.execute(query)
        return list(result.scalars().all())
        
    async def get_all_admins(self) -> List[User]:
        """Получить всех администраторов"""
        query = select(User).where(User.role == "admin")
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def get_users_by_role(self, role: str) -> List[User]:
        """Получить всех пользователей по роли"""
        query = select(User).where(User.role == role)
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def get_active_users_by_role(self, role: str) -> List[User]:
        """Получить всех активных пользователей по роли"""
        query = select(User).where(User.role == role, User.is_active == True)
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def get_blocked_users(self) -> List[User]:
        """Получить всех заблокированных пользователей"""
        query = select(User).where(User.is_active == False)
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def update_user_data(self, telegram_id: int, update_data: dict) -> bool:
        """Обновить данные пользователя"""
        try:
            query = update(User).where(User.telegram_id == telegram_id).values(**update_data)
            result = await self.session.execute(query)
            return result.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating user data for {telegram_id}: {e}")
            return False

    async def get_users_stats(self) -> dict:
        """Получить статистику по пользователям"""
        try:
            # Общее количество пользователей
            total_query = select(func.count(User.telegram_id))
            total_result = await self.session.execute(total_query)
            total_users = total_result.scalar() or 0
            
            # Активные пользователи  
            active_query = select(func.count(User.telegram_id)).where(User.is_active == True)
            active_result = await self.session.execute(active_query)
            active_users = active_result.scalar() or 0
            
            # Количество отделов (уникальные department)
            departments_query = select(func.count(distinct(User.department))).where(User.department.isnot(None))
            departments_result = await self.session.execute(departments_query)
            departments_count = departments_result.scalar() or 0
            
            return {
                'total_users': total_users,
                'active_users': active_users,
                'departments_count': departments_count
            }
        except Exception as e:
            logger.error(f"Error getting users stats: {e}")
            return {
                'total_users': 0,
                'active_users': 0,
                'departments_count': 0
            }

    async def get_users_with_birthdays(self) -> List[User]:
        """Получить всех активных пользователей с заполненными датами рождения"""
        try:
            query = (
                select(User)
                .where(
                    User.is_active == True,
                    User.birth_date.isnot(None)
                )
            )
            result = await self.session.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting users with birthdays: {e}")
            return []