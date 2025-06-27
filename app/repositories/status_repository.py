"""
Репозиторий для работы со статусами заказов и типами уведомлений
"""

from typing import List, Optional, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, insert
from sqlalchemy.orm import selectinload
import logging

from ..models.models import OrderStatus, NotificationType, StatusTransition
from ..core.base import BaseRepository

logger = logging.getLogger(__name__)


class StatusRepository(BaseRepository):
    """Репозиторий для работы со статусами заказов"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session)
    
    async def get_status_by_code(self, code: str) -> Optional[OrderStatus]:
        """Получить статус по коду"""
        try:
            query = select(OrderStatus).where(
                and_(OrderStatus.code == code, OrderStatus.is_active == True)
            )
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting status by code {code}: {e}")
            return None
    
    async def get_statuses_by_codes(self, codes: List[str]) -> List[OrderStatus]:
        """Получить несколько статусов по списку кодов"""
        try:
            query = select(OrderStatus).where(
                and_(
                    OrderStatus.code.in_(codes), 
                    OrderStatus.is_active == True
                )
            ).order_by(OrderStatus.order_index)
            result = await self.session.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting statuses by codes {codes}: {e}")
            return []
    
    async def get_status_by_id(self, status_id: int) -> Optional[OrderStatus]:
        """Получить статус по ID"""
        try:
            query = select(OrderStatus).where(OrderStatus.id == status_id)
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting status by id {status_id}: {e}")
            return None
    
    async def get_all_active_statuses(self) -> List[OrderStatus]:
        """Получить все активные статусы"""
        try:
            query = select(OrderStatus).where(OrderStatus.is_active == True).order_by(OrderStatus.order_index)
            result = await self.session.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting all statuses: {e}")
            return []
    
    async def create_status(self, status_data: dict) -> Optional[OrderStatus]:
        """Создать новый статус"""
        try:
            status = OrderStatus(**status_data)
            self.session.add(status)
            await self.session.flush()
            return status
        except Exception as e:
            logger.error(f"Error creating status: {e}")
            return None
    
    async def update_status(self, status: OrderStatus) -> bool:
        """Обновить статус"""
        try:
            await self.session.flush()
            return True
        except Exception as e:
            logger.error(f"Error updating status {status.id}: {e}")
            return False
    
    async def get_notification_type_by_code(self, code: str) -> Optional[NotificationType]:
        """Получить тип уведомления по коду"""
        try:
            query = select(NotificationType).where(
                and_(NotificationType.code == code, NotificationType.is_active == True)
            )
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting notification type by code {code}: {e}")
            return None
    
    async def get_all_notification_types(self) -> List[NotificationType]:
        """Получить все типы уведомлений"""
        try:
            query = select(NotificationType).where(NotificationType.is_active == True)
            result = await self.session.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting all notification types: {e}")
            return []
    
    async def create_notification_type(self, notification_data: dict) -> Optional[NotificationType]:
        """Создать новый тип уведомления"""
        try:
            notification_type = NotificationType(**notification_data)
            self.session.add(notification_type)
            await self.session.flush()
            return notification_type
        except Exception as e:
            logger.error(f"Error creating notification type: {e}")
            return None
    
    async def get_status_transition(self, from_status_id: Optional[int], to_status_id: int) -> Optional[StatusTransition]:
        """Получить переход между статусами"""
        try:
            query = select(StatusTransition).options(
                selectinload(StatusTransition.notification_type)
            ).where(
                and_(
                    StatusTransition.from_status_id == from_status_id,
                    StatusTransition.to_status_id == to_status_id,
                    StatusTransition.is_active == True
                )
            )
            result = await self.session.execute(query)
            transition = result.scalar_one_or_none()
            
            # Если не найден специфичный переход, ищем общий (from_status_id = NULL)
            if not transition and from_status_id is not None:
                query = select(StatusTransition).options(
                    selectinload(StatusTransition.notification_type)
                ).where(
                    and_(
                        StatusTransition.from_status_id.is_(None),
                        StatusTransition.to_status_id == to_status_id,
                        StatusTransition.is_active == True
                    )
                )
                result = await self.session.execute(query)
                transition = result.scalar_one_or_none()
            
            return transition
        except Exception as e:
            logger.error(f"Error getting status transition: {e}")
            return None
    
    async def create_status_transition(self, transition_data: dict) -> Optional[StatusTransition]:
        """Создать переход между статусами"""
        try:
            transition = StatusTransition(**transition_data)
            self.session.add(transition)
            await self.session.flush()
            return transition
        except Exception as e:
            logger.error(f"Error creating status transition: {e}")
            return None
    
    async def get_all_transitions(self) -> List[StatusTransition]:
        """Получить все переходы статусов"""
        try:
            query = select(StatusTransition).options(
                selectinload(StatusTransition.from_status),
                selectinload(StatusTransition.to_status),
                selectinload(StatusTransition.notification_type)
            ).where(StatusTransition.is_active == True)
            result = await self.session.execute(query)
            return list(result.unique().scalars().all())
        except Exception as e:
            logger.error(f"Error getting all transitions: {e}")
            return []
    
    async def bulk_create_statuses(self, statuses_data: List[dict]) -> bool:
        """Массовое создание статусов"""
        try:
            stmt = insert(OrderStatus).values(statuses_data)
            await self.session.execute(stmt)
            return True
        except Exception as e:
            logger.error(f"Error bulk creating statuses: {e}")
            return False
    
    async def bulk_create_notification_types(self, notifications_data: List[dict]) -> bool:
        """Массовое создание типов уведомлений"""
        try:
            stmt = insert(NotificationType).values(notifications_data)
            await self.session.execute(stmt)
            return True
        except Exception as e:
            logger.error(f"Error bulk creating notification types: {e}")
            return False
    
    async def bulk_create_transitions(self, transitions_data: List[dict]) -> bool:
        """Массовое создание переходов статусов"""
        try:
            stmt = insert(StatusTransition).values(transitions_data)
            await self.session.execute(stmt)
            return True
        except Exception as e:
            logger.error(f"Error bulk creating transitions: {e}")
            return False 