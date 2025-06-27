"""
Сервис для работы со статусами заказов и типами уведомлений
Централизованное управление статусами через БД
"""

from typing import List, Optional, Dict, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from ..models.models import OrderStatus, NotificationType, StatusTransition
from ..repositories.status_repository import StatusRepository
from ..core.base import BaseService

logger = logging.getLogger(__name__)


class StatusService(BaseService):
    """Сервис для работы со статусами заказов"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.status_repo = StatusRepository(session)
    
    async def get_status_by_code(self, code: str) -> Optional[OrderStatus]:
        """Получить статус по коду"""
        return await self.status_repo.get_status_by_code(code)
    
    async def get_statuses_by_codes(self, codes: List[str]) -> List[OrderStatus]:
        """Получить несколько статусов по списку кодов"""
        return await self.status_repo.get_statuses_by_codes(codes)
    
    async def get_all_active_statuses(self) -> List[OrderStatus]:
        """Получить все активные статусы"""
        return await self.status_repo.get_all_active_statuses()
    
    async def get_notification_type_by_code(self, code: str) -> Optional[NotificationType]:
        """Получить тип уведомления по коду"""
        return await self.status_repo.get_notification_type_by_code(code)
    
    async def get_notification_for_transition(self, from_status_code: str, to_status_code: str) -> Optional[NotificationType]:
        """Получить тип уведомления для перехода между статусами"""
        try:
            from_status = await self.status_repo.get_status_by_code(from_status_code)
            to_status = await self.status_repo.get_status_by_code(to_status_code)
            
            if not to_status:
                return None
            
            from_status_id = from_status.id if from_status else None
            transition = await self.status_repo.get_status_transition(from_status_id, to_status.id)
            
            return transition.notification_type if transition else None
            
        except Exception as e:
            logger.error(f"Error getting notification for transition {from_status_code} -> {to_status_code}: {e}")
            return None
    
    async def create_status(self, code: str, name: str, emoji: str = None, 
                           description: str = None, comment_user: str = None, 
                           comment_hr: str = None, order_index: int = 0) -> Optional[OrderStatus]:
        """Создать новый статус"""
        status_data = {
            'code': code,
            'name': name,
            'emoji': emoji,
            'description': description,
            'comment_user': comment_user,
            'comment_hr': comment_hr,
            'order_index': order_index
        }
        return await self.status_repo.create_status(status_data)
    
    async def create_notification_type(self, code: str, name: str, description: str = None) -> Optional[NotificationType]:
        """Создать новый тип уведомления"""
        notification_data = {
            'code': code,
            'name': name,
            'description': description
        }
        return await self.status_repo.create_notification_type(notification_data)
    
    async def create_status_transition(self, from_status_code: str, to_status_code: str, 
                                     notification_type_code: str) -> Optional[StatusTransition]:
        """Создать переход между статусами"""
        try:
            from_status = await self.status_repo.get_status_by_code(from_status_code) if from_status_code else None
            to_status = await self.status_repo.get_status_by_code(to_status_code)
            notification_type = await self.status_repo.get_notification_type_by_code(notification_type_code)
            
            if not to_status or not notification_type:
                logger.error(f"Status or notification type not found")
                return None
            
            transition_data = {
                'from_status_id': from_status.id if from_status else None,
                'to_status_id': to_status.id,
                'notification_type_id': notification_type.id
            }
            return await self.status_repo.create_status_transition(transition_data)
        except Exception as e:
            logger.error(f"Error creating status transition: {e}")
            return None
    
    async def get_status_display_mapping(self) -> Dict[str, str]:
        """Получить маппинг кодов статусов на отображаемые названия"""
        try:
            statuses = await self.status_repo.get_all_active_statuses()
            return {status.code: status.display_name for status in statuses}
        except Exception as e:
            logger.error(f"Error getting status display mapping: {e}")
            return {}
    
    async def get_status_comments_mapping(self) -> Dict[str, Tuple[str, str]]:
        """Получить маппинг кодов статусов на комментарии (user, hr)"""
        try:
            statuses = await self.status_repo.get_all_active_statuses()
            return {
                status.code: (status.comment_user or "", status.comment_hr or "") 
                for status in statuses
            }
        except Exception as e:
            logger.error(f"Error getting status comments mapping: {e}")
            return {}
    
    async def initialize_default_statuses(self) -> bool:
        """Инициализация базовых статусов и типов уведомлений"""
        try:
            # Создаем статусы
            statuses_data = [
                {
                    'code': 'new',
                    'name': 'Новый',
                    'emoji': '🆕',
                    'description': 'Заказ создан и ожидает обработки',
                    'comment_user': 'Ваш заказ создан и ожидает обработки HR-менеджером.',
                    'comment_hr': 'Новый заказ от пользователя',
                    'order_index': 1
                },
                {
                    'code': 'processing',
                    'name': 'В работе',
                    'emoji': '⚡',
                    'description': 'Заказ взят в работу HR-менеджером',
                    'comment_user': 'Ваш заказ взят в работу. Вы получите уведомление, когда заказ будет готов к выдаче.',
                    'comment_hr': 'Заказ взят в работу',
                    'order_index': 2
                },
                {
                    'code': 'ready_for_pickup',
                    'name': 'Готов к выдаче',
                    'emoji': '📦',
                    'description': 'Заказ готов к выдаче',
                    'comment_user': 'Ваш заказ готов к выдаче! Пожалуйста, обратитесь к HR-менеджеру для получения заказа.',
                    'comment_hr': 'Заказ готов к выдаче пользователю',
                    'order_index': 3
                },
                {
                    'code': 'delivered',
                    'name': 'Выполнен',
                    'emoji': '✅',
                    'description': 'Заказ выдан пользователю',
                    'comment_user': 'Заказ успешно выдан. Спасибо за заказ!',
                    'comment_hr': 'Заказ выдан пользователю',
                    'order_index': 4
                },
                {
                    'code': 'cancelled',
                    'name': 'Отменен',
                    'emoji': '❌',
                    'description': 'Заказ отменен',
                    'comment_user': 'Ваш заказ был отменен. T-points возвращены на ваш баланс.',
                    'comment_hr': 'Заказ отменен. T-points возвращены, товары возвращены на склад',
                    'order_index': 5
                }
            ]
            
            # Создаем типы уведомлений
            notifications_data = [
                {
                    'code': 'order_created',
                    'name': 'Заказ создан',
                    'description': 'Уведомление о создании нового заказа'
                },
                {
                    'code': 'order_taken',
                    'name': 'Заказ взят в работу',
                    'description': 'Уведомление о взятии заказа в работу'
                },
                {
                    'code': 'order_ready',
                    'name': 'Заказ готов к выдаче',
                    'description': 'Уведомление о готовности заказа к выдаче'
                },
                {
                    'code': 'order_completed',
                    'name': 'Заказ выполнен',
                    'description': 'Уведомление о выполнении заказа'
                },
                {
                    'code': 'order_cancelled',
                    'name': 'Заказ отменен',
                    'description': 'Уведомление об отмене заказа'
                },
                {
                    'code': 'order_cancelled_by_user',
                    'name': 'Заказ отменен пользователем',
                    'description': 'Уведомление об отмене заказа пользователем'
                }
            ]
            
            await self.status_repo.bulk_create_statuses(statuses_data)
            await self.status_repo.bulk_create_notification_types(notifications_data)
            
            # Создаем переходы между статусами
            await self._create_status_transitions()
            
            return True
        except Exception as e:
            logger.error(f"Error initializing default statuses: {e}")
            return False
    
    async def _create_status_transitions(self) -> bool:
        """Создать переходы между статусами с соответствующими уведомлениями"""
        try:
            # Получаем все статусы и типы уведомлений
            new_status = await self.status_repo.get_status_by_code('new')
            processing_status = await self.status_repo.get_status_by_code('processing')
            ready_status = await self.status_repo.get_status_by_code('ready_for_pickup')
            delivered_status = await self.status_repo.get_status_by_code('delivered')
            cancelled_status = await self.status_repo.get_status_by_code('cancelled')
            
            order_created_nt = await self.status_repo.get_notification_type_by_code('order_created')
            order_taken_nt = await self.status_repo.get_notification_type_by_code('order_taken')
            order_ready_nt = await self.status_repo.get_notification_type_by_code('order_ready')
            order_completed_nt = await self.status_repo.get_notification_type_by_code('order_completed')
            order_cancelled_nt = await self.status_repo.get_notification_type_by_code('order_cancelled')
            order_cancelled_by_user_nt = await self.status_repo.get_notification_type_by_code('order_cancelled_by_user')
            
            # Создаем переходы
            transitions_data = []
            
            # Создание заказа (любой статус -> new)
            if new_status and order_created_nt:
                transitions_data.append({
                    'from_status_id': None,  # Любой статус (создание с нуля)
                    'to_status_id': new_status.id,
                    'notification_type_id': order_created_nt.id
                })
            
            # Взятие в работу (new -> processing)
            if new_status and processing_status and order_taken_nt:
                transitions_data.append({
                    'from_status_id': new_status.id,
                    'to_status_id': processing_status.id,
                    'notification_type_id': order_taken_nt.id
                })
            
            # Готов к выдаче (processing -> ready_for_pickup)
            if processing_status and ready_status and order_ready_nt:
                transitions_data.append({
                    'from_status_id': processing_status.id,
                    'to_status_id': ready_status.id,
                    'notification_type_id': order_ready_nt.id
                })
            
            # Выполнен (ready_for_pickup -> delivered)
            if ready_status and delivered_status and order_completed_nt:
                transitions_data.append({
                    'from_status_id': ready_status.id,
                    'to_status_id': delivered_status.id,
                    'notification_type_id': order_completed_nt.id
                })
            
            # Отмена заказа (любой статус -> cancelled)
            if cancelled_status and order_cancelled_nt:
                transitions_data.append({
                    'from_status_id': None,  # Из любого статуса
                    'to_status_id': cancelled_status.id,
                    'notification_type_id': order_cancelled_nt.id
                })
            
            # Отмена пользователем (отдельный тип уведомления)
            if cancelled_status and order_cancelled_by_user_nt:
                transitions_data.append({
                    'from_status_id': new_status.id,  # Только из статуса "новый"
                    'to_status_id': cancelled_status.id,
                    'notification_type_id': order_cancelled_by_user_nt.id
                })
            
            if transitions_data:
                await self.status_repo.bulk_create_transitions(transitions_data)
            
            return True
        except Exception as e:
            logger.error(f"Error creating status transitions: {e}")
            return False 