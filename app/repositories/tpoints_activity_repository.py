from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.exc import SQLAlchemyError
from typing import List, Optional, Dict
import logging

from ..models.models import TPointsActivity

logger = logging.getLogger(__name__)


class TPointsActivityRepository:
    """Репозиторий для работы с T-Points активностями"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_all_activities(self) -> List[TPointsActivity]:
        """Получить все активности"""
        try:
            query = select(TPointsActivity).where(TPointsActivity.is_active == True).order_by(TPointsActivity.points)
            result = await self.session.execute(query)
            return result.scalars().all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting all activities: {e}")
            return []
    
    async def get_activity_by_id(self, activity_id: int) -> Optional[TPointsActivity]:
        """Получить активность по ID"""
        try:
            query = select(TPointsActivity).where(TPointsActivity.id == activity_id)
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"Error getting activity {activity_id}: {e}")
            return None
    
    async def get_activity_by_name(self, name: str) -> Optional[TPointsActivity]:
        """Получить активность по имени"""
        try:
            query = select(TPointsActivity).where(TPointsActivity.name == name)
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"Error getting activity by name {name}: {e}")
            return None
    
    async def create_activity(self, name: str, points: int, description: str = None) -> Optional[TPointsActivity]:
        """Создать новую активность"""
        try:
            activity = TPointsActivity(
                name=name,
                points=points,
                description=description,
                is_active=True
            )
            self.session.add(activity)
            await self.session.flush()  # Получаем ID без коммита
            return activity
        except SQLAlchemyError as e:
            logger.error(f"Error creating activity {name}: {e}")
            return None
    
    async def update_activity(self, activity: TPointsActivity) -> bool:
        """Обновить активность"""
        try:
            await self.session.merge(activity)
            return True
        except SQLAlchemyError as e:
            logger.error(f"Error updating activity {activity.id}: {e}")
            return False
    
    async def delete_activity(self, activity_id: int) -> bool:
        """Удалить активность (мягкое удаление - is_active = False)"""
        try:
            activity = await self.get_activity_by_id(activity_id)
            if activity:
                activity.is_active = False
                await self.session.merge(activity)
                return True
            return False
        except SQLAlchemyError as e:
            logger.error(f"Error deleting activity {activity_id}: {e}")
            return False
    
    async def hard_delete_activity(self, activity_id: int) -> bool:
        """Жёсткое удаление активности из БД"""
        try:
            query = delete(TPointsActivity).where(TPointsActivity.id == activity_id)
            await self.session.execute(query)
            return True
        except SQLAlchemyError as e:
            logger.error(f"Error hard deleting activity {activity_id}: {e}")
            return False
    
    async def clear_all_activities(self) -> bool:
        """Очистить все активности (жёсткое удаление)"""
        try:
            query = delete(TPointsActivity)
            await self.session.execute(query)
            return True
        except SQLAlchemyError as e:
            logger.error(f"Error clearing all activities: {e}")
            return False
    
    async def bulk_create_activities(self, activities_data: List[Dict]) -> bool:
        """Массовое создание активностей"""
        try:
            activities = []
            for data in activities_data:
                activity = TPointsActivity(
                    name=data['name'],
                    points=data['points'],
                    description=data.get('description'),
                    is_active=True
                )
                activities.append(activity)
            
            self.session.add_all(activities)
            return True
        except SQLAlchemyError as e:
            logger.error(f"Error bulk creating activities: {e}")
            return False 