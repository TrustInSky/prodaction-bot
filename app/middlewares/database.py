from typing import Any, Awaitable, Callable, Dict, List
from aiogram import BaseMiddleware, Bot
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy import event
import threading
import logging
import asyncio
from datetime import datetime

from app.services.cart import CartService
from app.services.catalog import CatalogService
from app.services.order import OrderService
from app.services.user import UserService
from app.services.status_service import StatusService
from app.services.onboarding_service import OnboardingService
from app.services.notifications.order_notifications import OrderNotificationService
from app.services.excel_service import ExcelService
from app.services.transaction_service import TransactionService
from app.services.question import QuestionService
from app.services.user_manager_service import UserManagerService
from app.services.tpoints_activity_service import TPointsActivityService
from app.services.auto_events_service import AutoEventsService
from app.services.notifications.question_notifications import QuestionNotificationService
from app.services.group_management_service import GroupManagementService
from app.repositories.user_repository import UserRepository
from app.config import Config

logger = logging.getLogger(__name__)

# ИСПРАВЛЕНО: Заменено на thread-local storage для безопасности
_local = threading.local()

def get_pending_notifications() -> List[Dict[str, Any]]:
    """Получить очередь уведомлений для текущего потока"""
    if not hasattr(_local, 'pending_notifications'):
        _local.pending_notifications = []
    return _local.pending_notifications

def add_pending_notification(notification_type: str, data: dict):
    """Добавить уведомление в очередь для текущего потока"""
    notifications = get_pending_notifications()
    notifications.append({
        'type': notification_type,
        'data': data,
        'timestamp': datetime.now()
    })


class DatabaseMiddleware(BaseMiddleware):
    """Middleware для работы с базой данных и предоставления сервисов"""
    
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], bot: Bot):
        """Инициализация middleware"""
        self.session_factory = session_factory
        self.bot = bot
        self.config = Config()
        self.group_id = self.config.GROUP_ID
        
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Обработка запроса"""
        # ИСПРАВЛЕНО: Используем thread-local storage вместо глобальной переменной
        notifications = get_pending_notifications()
        notifications.clear()  # Очищаем очередь для этого запроса
        
        async with self.session_factory() as session:
            try:
                # Создаем экземпляры сервисов для этого запроса
                order_notification_service = OrderNotificationService(session, self.bot)
                question_service = QuestionService(session)
                user_service = UserService(session)
                catalog_service = CatalogService(session)
                cart_service = CartService(session)
                status_service = StatusService(session)
                onboarding_service = OnboardingService(session)
                order_service = OrderService(session)
                excel_service = ExcelService(session)
                transaction_service = TransactionService(session)
                
                # Создаем GroupManagementService если есть GROUP_ID
                group_management_service = None
                if self.group_id:
                    group_management_service = GroupManagementService(session, self.group_id)
                
                # Передаем группу-сервис в UserManagerService
                user_manager_service = UserManagerService(
                    session, 
                    group_management_service=group_management_service, 
                    bot=self.bot
                )
                
                tpoints_activity_service = TPointsActivityService(session)
                auto_events_service = AutoEventsService(session, self.bot)
                question_notification_service = QuestionNotificationService(session, self.bot)
                user_repository = UserRepository(session)
                
                # Добавляем все сервисы в data для aiogram3-di
                data.update({
                    "session": session,
                    "question_service": question_service,
                    "user_service": user_service,
                    "catalog_service": catalog_service,
                    "cart_service": cart_service,
                    "status_service": status_service,
                    "onboarding_service": onboarding_service,
                    "order_service": order_service,
                    "excel_service": excel_service,
                    "order_notification_service": order_notification_service,
                    "notification_service": order_notification_service,
                    "transaction_service": transaction_service,
                    "user_manager_service": user_manager_service,
                    "group_management_service": group_management_service,
                    "tpoints_activity_service": tpoints_activity_service,
                    "auto_events_service": auto_events_service,
                    "question_notification_service": question_notification_service,
                    "user_repository": user_repository,
                    "database_middleware": self,
                })
                
                # Логируем для отладки
                logger.debug(f"Services created for request: {[k for k in data.keys() if k.endswith('_service')]}")
                
                # Выполняем handler
                result = await handler(event, data)
                
                # Если всё прошло успешно, коммитим транзакцию
                await session.commit()
                
                # После коммита отправляем отложенные уведомления
                await self._send_pending_notifications()
                
                return result
                
            except Exception as e:
                # В случае ошибки откатываем транзакцию
                await session.rollback()
                # ИСПРАВЛЕНО: Очищаем очередь уведомлений при ошибке
                notifications = get_pending_notifications()
                notifications.clear()
                logger.error(f"Database error in middleware: {e}", exc_info=True)
                raise
    
    async def _send_pending_notifications(self):
        """Отправить все отложенные уведомления"""
        # ИСПРАВЛЕНО: Используем thread-local storage
        notifications = get_pending_notifications()
        
        if not notifications:
            return
            
        logger.info(f"Sending {len(notifications)} pending notifications")
        
        for notification_data in notifications:
            try:
                await self._send_notification(notification_data)
            except Exception as e:
                logger.error(f"Failed to send pending notification: {e}")
        
        # Очищаем очередь после отправки
        notifications.clear()
    
    async def _send_notification(self, notification_data: dict):
        """Отправить одно уведомление через соответствующий сервис"""
        notification_type = notification_data.get('type')
        
        if notification_type == 'order_created':
            # Создаем новую сессию и сервис уведомлений для фонового выполнения
            async with self.session_factory() as session:
                try:
                    from ..repositories.order_repository import OrderRepository
                    from ..repositories.user_repository import UserRepository
                    from ..services.notifications.order_notifications import OrderNotificationService
                    
                    # Создаём репозитории для передачи в сервис
                    order_repo = OrderRepository(session)
                    user_repo = UserRepository(session)
                    notification_service = OrderNotificationService(session, self.bot)
                    
                    # Делегируем отправку уведомления сервису с репозиториями
                    await notification_service.send_pending_order_created_notification(
                        order_repo,
                        user_repo,
                        notification_data['data']['order_id'],
                        notification_data['data']['user_id']
                    )
                    
                except Exception as e:
                    logger.error(f"Error processing order_created notification: {e}")
        
        elif notification_type in ['order_taken', 'order_ready', 'order_completed', 'order_cancelled']:
            # Уведомления об изменении статуса заказа
            async with self.session_factory() as session:
                try:
                    from ..services.notifications.order_notifications import OrderNotificationService
                    notification_service = OrderNotificationService(session, self.bot)
                    
                    # Вызываем соответствующий метод сервиса для уведомления о статусе
                    await notification_service.send_status_change_notification(
                        notification_data['data']['order_id'],
                        notification_data['data']['user_id'],
                        notification_data['data']['old_status'],
                        notification_data['data']['new_status'],
                        notification_data['data'].get('hr_user_id')
                    )
                    
                except Exception as e:
                    logger.error(f"Error processing {notification_type} notification: {e}")
        
        elif notification_type == 'order_cancelled_by_user':
            # Уведомление HR об отмене заказа пользователем
            async with self.session_factory() as session:
                try:
                    from ..repositories.order_repository import OrderRepository
                    from ..repositories.user_repository import UserRepository
                    from ..services.notifications.order_notifications import OrderNotificationService
                    
                    order_repo = OrderRepository(session)
                    user_repo = UserRepository(session)
                    notification_service = OrderNotificationService(session, self.bot)
                    
                    # Получаем заказ и пользователя
                    order = await order_repo.get_order_with_details(notification_data['data']['order_id'])
                    user = await user_repo.get_user_by_telegram_id(notification_data['data']['user_id'])
                    
                    if order and user:
                        # Получаем всех HR пользователей
                        hr_users = await user_repo.get_all_hr_and_admin_users()
                        
                        # Отправляем уведомления каждому HR
                        for hr_user in hr_users:
                            await notification_service.send_hr_order_cancellation_notification(
                                order, user, hr_user.telegram_id, notification_data['data'].get('reason', 'Отменено пользователем')
                            )
                            
                        logger.info(f"Sent user cancellation notifications to {len(hr_users)} HR users for order {order.id}")
                    else:
                        logger.error(f"Order or user not found for cancellation notification: order_id={notification_data['data']['order_id']}, user_id={notification_data['data']['user_id']}")
                        
                except Exception as e:
                    logger.error(f"Error processing order_cancelled_by_user notification: {e}")
        
        else:
            logger.warning(f"Unknown notification type: {notification_type}")
    

            
    def create_session(self):
        """Создать новую сессию базы данных для фоновых задач"""
        return self.session_factory()
        
    async def get_service_with_new_session(self, service_class, *args):
        """Создать сервис с новой сессией для фоновых операций"""
        async with self.session_factory() as session:
            if service_class == OrderNotificationService:
                return service_class(session, self.bot, *args)
            else:
                return service_class(session, *args)


# ИСПРАВЛЕНО: Функция перенесена выше и исправлена


# Глобальные переменные для хранения ссылки на middleware
_database_middleware = None

def set_database_middleware(middleware: DatabaseMiddleware):
    """Установить ссылку на middleware для использования в фильтрах"""
    global _database_middleware
    _database_middleware = middleware

def get_user_service():
    """Получить UserService для использования в фильтрах"""
    global _database_middleware
    if _database_middleware is None:
        raise RuntimeError("Database middleware not initialized")
    
    # Создаем временную сессию и UserService
    class TempUserService:
        async def get_user_by_telegram_id(self, telegram_id: int):
            async with _database_middleware.session_factory() as session:
                user_service = UserService(session)
                return await user_service.get_user_by_telegram_id(telegram_id)
    
    return TempUserService()

