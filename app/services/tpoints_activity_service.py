from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from typing import List, Optional, Dict, Tuple
import logging
from datetime import datetime

from app.core.base import BaseService
from ..repositories.tpoints_activity_repository import TPointsActivityRepository
from ..models.models import TPointsActivity

logger = logging.getLogger(__name__)


class TPointsActivityService(BaseService):
    """Сервис для работы с T-Points активностями"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.activity_repo = TPointsActivityRepository(session)
    
    async def get_activities_dict(self) -> Dict[str, int]:
        """
        Получить список активностей в виде словаря {название: поинты}
        Бизнес-логика: только активные активности, отсортированные по поинтам
        """
        try:
            activities = await self.activity_repo.get_all_activities()
            return {activity.name: activity.points for activity in activities}
        except Exception as e:
            logger.error(f"Error getting activities dict: {e}")
            return {}
    
    async def get_all_activities_full(self) -> List[TPointsActivity]:
        """
        Получить полный список активностей (для админки)
        """
        try:
            return await self.activity_repo.get_all_activities()
        except Exception as e:
            logger.error(f"Error getting full activities: {e}")
            return []
    
    async def create_activity(self, name: str, points: int, description: str = None) -> Tuple[bool, str]:
        """
        Создать новую активность
        Бизнес-логика: проверка уникальности названия, валидация поинтов
        """
        try:
            # Бизнес-логика: валидация данных
            if not name or not name.strip():
                return False, "Название активности не может быть пустым"
            
            if points < 0:
                return False, "Количество поинтов не может быть отрицательным"
            
            name = name.strip()
            
            # Бизнес-логика: проверка уникальности
            existing = await self.activity_repo.get_activity_by_name(name)
            if existing:
                return False, f"Активность '{name}' уже существует"
            
            # Создаём через репозиторий
            activity = await self.activity_repo.create_activity(name, points, description)
            
            if activity:
                logger.info(f"Created new activity: {name} ({points} points)")
                return True, f"Активность '{name}' создана успешно"
            else:
                return False, "Ошибка при создании активности"
                
        except Exception as e:
            logger.error(f"Error creating activity {name}: {e}")
            return False, f"Ошибка: {str(e)}"
    
    async def update_activity(self, activity_id: int, name: str = None, points: int = None, 
                            description: str = None) -> Tuple[bool, str]:
        """
        Обновить активность
        Бизнес-логика: валидация и проверка уникальности имени
        """
        try:
            activity = await self.activity_repo.get_activity_by_id(activity_id)
            if not activity:
                return False, "Активность не найдена"
            
            # Бизнес-логика: обновляем только переданные поля
            if name is not None:
                name = name.strip()
                if not name:
                    return False, "Название не может быть пустым"
                
                # Проверяем уникальность нового имени
                if name != activity.name:
                    existing = await self.activity_repo.get_activity_by_name(name)
                    if existing:
                        return False, f"Активность '{name}' уже существует"
                
                activity.name = name
            
            if points is not None:
                if points < 0:
                    return False, "Количество поинтов не может быть отрицательным"
                activity.points = points
            
            if description is not None:
                activity.description = description
            
            # Обновляем время изменения
            activity.updated_at = datetime.utcnow()
            
            # Сохраняем через репозиторий
            success = await self.activity_repo.update_activity(activity)
            
            if success:
                logger.info(f"Updated activity {activity_id}: {activity.name}")
                return True, "Активность обновлена успешно"
            else:
                return False, "Ошибка при обновлении активности"
                
        except Exception as e:
            logger.error(f"Error updating activity {activity_id}: {e}")
            return False, f"Ошибка: {str(e)}"
    
    async def delete_activity(self, activity_id: int) -> Tuple[bool, str]:
        """
        Удалить активность (мягкое удаление)
        """
        try:
            activity = await self.activity_repo.get_activity_by_id(activity_id)
            if not activity:
                return False, "Активность не найдена"
            
            success = await self.activity_repo.delete_activity(activity_id)
            
            if success:
                logger.info(f"Deleted activity {activity_id}: {activity.name}")
                return True, f"Активность '{activity.name}' удалена"
            else:
                return False, "Ошибка при удалении активности"
                
        except Exception as e:
            logger.error(f"Error deleting activity {activity_id}: {e}")
            return False, f"Ошибка: {str(e)}"
    
    async def update_activities_from_text(self, text_data: str) -> Tuple[bool, str]:
        """
        Обновить весь список активностей из текстового формата
        Бизнес-логика: парсинг, валидация, замена существующих данных
        """
        try:
            # Бизнес-логика: парсим текстовые данные
            new_activities = []
            lines = text_data.strip().split('\n')
            
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                if not line:
                    continue
                
                if ':' not in line:
                    return False, f"Строка {line_num}: неверный формат. Ожидается 'название:поинты'"
                
                parts = line.split(':', 1)
                if len(parts) != 2:
                    return False, f"Строка {line_num}: неверный формат"
                
                name = parts[0].strip()
                try:
                    points = int(parts[1].strip())
                except ValueError:
                    return False, f"Строка {line_num}: '{parts[1].strip()}' не является числом"
                
                if not name:
                    return False, f"Строка {line_num}: название не может быть пустым"
                
                if points < 0:
                    return False, f"Строка {line_num}: поинты не могут быть отрицательными"
                
                # Проверяем дубликаты в самом списке
                if any(act['name'] == name for act in new_activities):
                    return False, f"Дубликат активности: '{name}'"
                
                new_activities.append({
                    'name': name,
                    'points': points,
                    'description': f"Обновлено из списка {datetime.now().strftime('%d.%m.%Y %H:%M')}"
                })
            
            if not new_activities:
                return False, "Не найдено ни одной валидной активности"
            
            # Бизнес-логика: заменяем весь список
            # 1. Очищаем старые данные
            success = await self.activity_repo.clear_all_activities()
            if not success:
                return False, "Ошибка при очистке старых данных"
            
            # 2. Добавляем новые данные
            success = await self.activity_repo.bulk_create_activities(new_activities)
            if not success:
                return False, "Ошибка при добавлении новых данных"
            
            logger.info(f"Updated activities list: {len(new_activities)} activities")
            return True, f"Список обновлён: {len(new_activities)} активностей"
            
        except SQLAlchemyError as db_e:
            logger.error(f"Database error updating activities: {db_e}")
            raise  # Пробрасываем для rollback
        except Exception as e:
            logger.error(f"Error updating activities from text: {e}")
            return False, f"Ошибка: {str(e)}"
    
    async def get_activity_by_name(self, name: str) -> Optional[TPointsActivity]:
        """
        Получить активность по названию
        """
        try:
            return await self.activity_repo.get_activity_by_name(name.strip())
        except Exception as e:
            logger.error(f"Error getting activity by name {name}: {e}")
            return None
    
    async def get_activity_points(self, name: str) -> int:
        """
        Получить количество поинтов за активность
        Бизнес-логика: возвращает 0 если активность не найдена
        """
        try:
            activity = await self.get_activity_by_name(name)
            return activity.points if activity else 0
        except Exception as e:
            logger.error(f"Error getting points for activity {name}: {e}")
            return 0


# Алиас для обратной совместимости (возможно используется в старом коде)
TPointService = TPointsActivityService 