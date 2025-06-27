from typing import Optional, List
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from .base_notification_service import BaseNotificationService
from ...models.models import Order, User
import logging

logger = logging.getLogger(__name__)

class OrderNotificationService(BaseNotificationService):
    """Сервис уведомлений о заказах"""
    
    async def send_order_created_notification(self, order: Order, user: User, hr_users: List[int] = None) -> bool:
        """
        Отправить уведомление о создании заказа всем HR
        ИСПРАВЛЕНО: удалено дублирование, используется только очередь
        """
        try:
            from ...middlewares.database import add_pending_notification
            
            notification_data = {
                'order_id': order.id,
                'user_id': user.telegram_id,
                'order_total': float(order.total_cost)
            }
            
            add_pending_notification('order_created', notification_data)
            logger.info(f"Order {order.id} notification added to pending queue")
            
            return True
            
        except Exception as e:
            logger.error(f"Error preparing order created notification for order {order.id}: {e}")
            return False
    
    async def send_pending_order_created_notification(self, order_repo, user_repo, order_id: int, user_id: int) -> bool:
        """
        Отправить отложенное уведомление о создании заказа (вызывается из middleware)
        Принимает готовые репозитории для соблюдения архитектуры
        """
        try:
            
            # Получаем данные заказа
            order = await order_repo.get_order_by_id(order_id)
            if not order:
                logger.error(f"Order {order_id} not found for notification")
                return False
            
            # Получаем товары заказа отдельно через репозиторий
            order_items = await order_repo.get_order_items(order_id)
            
            # Получаем данные пользователя
            user = await user_repo.get_user_by_telegram_id(user_id)
            if not user:
                logger.error(f"User {user_id} not found for notification")
                return False
            
            # Получаем список HR пользователей
            hr_users = await user_repo.get_all_hr_and_admin_users()
            hr_user_ids = [hr_user.telegram_id for hr_user in hr_users]
            
            if not hr_user_ids:
                logger.warning("No HR users found for order notification")
                return False
            
            # Формируем и отправляем уведомления
            return await self._send_order_created_notification_actual(order, user, hr_user_ids, order_items)
            
        except Exception as e:
            logger.error(f"Error sending pending order notification for order {order_id}: {e}")
            return False
    
    async def _send_order_created_notification_actual(self, order, user, hr_user_ids: List[int], order_items=None) -> bool:
        """
        Фактическая отправка уведомлений о создании заказа
        """
        try:
            # Формируем упоминание пользователя с полным именем и username
            if user.username:
                user_mention = f'<a href="tg://user?id={user.telegram_id}">{user.fullname}</a> (@{user.username})'
            else:
                user_mention = f'<a href="tg://user?id={user.telegram_id}">{user.fullname}</a>'
            
            text = (
                f"🆕 <b>Новый заказ #{order.id}</b>\n\n"
                f"👤 Заказчик: {user_mention}\n"
                f"🏢 Отдел: {user.department or 'Не указан'}\n"
                f"💰 Сумма: {abs(order.total_cost)} T-Points\n"
                f"📅 Дата: {order.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
                f"📋 Состав заказа:\n"
            )
            
            # Добавляем список товаров
            if order_items:
                for item in order_items:
                    size_text = f" ({item.size})" if item.size else ""
                    text += f"• {item.product.name}{size_text} x{item.quantity}\n"
            else:
                text += "• Состав будет показан при обработке\n"
            
            # Создаем клавиатуру с обработчиками
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Взять в работу",
                        callback_data=f"order_accept_{order.id}"
                    ),
                    InlineKeyboardButton(
                        text="⏰ Проверю позже",
                        callback_data=f"order_later_{order.id}"
                    )
                ]
            ])
            
            # Отправляем уведомления всем HR
            success_count = 0
            for user_id in hr_user_ids:
                try:
                    await self.bot.send_message(
                        chat_id=user_id,
                        text=text,
                        reply_markup=keyboard,
                        parse_mode='HTML'
                    )
                    success_count += 1
                    logger.info(f"Notification sent successfully to HR user {user_id}")
                except Exception as e:
                    logger.error(f"Failed to send notification to HR user {user_id}: {e}")
            
            logger.info(f"Order {order.id} notification sent to {success_count}/{len(hr_user_ids)} HR users")
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Error sending order notification: {e}")
            return False
    
    async def send_order_status_notification(self, order: Order, new_status: str, hr_user: User) -> bool:
        """
        Отправить уведомление пользователю об изменении статуса заказа
        """
        try:
            # Получаем пользователя заказа из order.user (должен быть загружен)
            customer = order.user
            
            if not customer:
                logger.error(f"Customer not found for order {order.id}")
                return False
            
            # Формируем текст в зависимости от статуса
            status_messages = {
                'processing': (
                    f"⏳ <b>Заказ #{order.id} взят в работу</b>\n\n"
                    f"Ваш заказ обрабатывает: {self._format_user_mention(hr_user.telegram_id, hr_user.username, hr_user.fullname)}\n\n"
                    f"💰 Сумма: {abs(order.total_cost)} T-Points\n"
                    f"📅 Дата заказа: {order.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
                    f"Вы получите уведомление, когда заказ будет готов к выдаче."
                ),
                'ready_for_pickup': self._format_order_ready_message(order, order.user, hr_user),
                'delivered': (
                    f"📦 <b>Заказ #{order.id} выдан</b>\n\n"
                    f"💰 Сумма: {abs(order.total_cost)} T-Points\n"
                    f"📅 Дата заказа: {order.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
                    f"✅ Заказ успешно получен.\n"
                    f"👤 Выдал: {self._format_user_mention(hr_user.telegram_id, hr_user.username, hr_user.fullname)}\n\n"
                    f"Спасибо за использование корпоративного магазина!"
                ),
                'cancelled': (
                    f"❌ <b>Заказ #{order.id} отменен</b>\n\n"
                    f"💰 Возвращено: {abs(order.total_cost)} T-Points\n"
                    f"📅 Дата заказа: {order.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
                    f"Причина отмены сообщена отдельно.\n"
                    f"T-Points возвращены на ваш баланс."
                )
            }
            
            text = status_messages.get(new_status, f"📋 Статус заказа #{order.id} изменен на: {new_status}")
            
            # Добавляем кнопку "Мои заказы"
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📋 Мои заказы",
                        callback_data="menu:my_orders"
                    ),
                    InlineKeyboardButton(
                        text="🏠 Главное меню",
                        callback_data="menu:main"
                    )
                ]
            ])
            
            results = await self._send_message_to_users([customer.telegram_id], text, keyboard)
            
            success = results.get(customer.telegram_id, False)
            if success:
                logger.info(f"Status notification sent to user {customer.telegram_id} for order {order.id}")
            else:
                logger.error(f"Failed to send status notification to user {customer.telegram_id} for order {order.id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending order status notification for order {order.id}: {e}")
            return False
    
    async def send_order_cancelled_by_user_notification(self, order: Order, user: User, reason: str = None) -> bool:
        """
        Отправить уведомление HR об отмене заказа пользователем
        """
        try:
            # HR users должны быть переданы извне для избежания проблем с greenlet
            logger.warning("send_order_cancelled_by_user_notification requires hr_users to be passed explicitly")
            return False
            
            user_mention = self._format_user_mention(
                user.telegram_id, 
                user.username, 
                user.fullname
            )
            
            cancel_reason = reason or "Случайный некорректный заказ"
            
            text = (
                f"❌ <b>Заказ #{order.id} отменен пользователем</b>\n\n"
                f"👤 Пользователь: {user_mention}\n"
                f"🏢 Отдел: {user.department or 'Не указан'}\n"
                f"💰 Сумма: {abs(order.total_cost)} T-Points\n"
                f"📅 Дата заказа: {order.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
                f"📝 Причина отмены: <i>{cancel_reason}</i>\n\n"
                f"💳 T-Points возвращены пользователю."
            )
            
            results = await self._send_message_to_users(hr_users, text)
            
            success_count = sum(1 for success in results.values() if success)
            logger.info(f"Order cancellation notification sent to {success_count}/{len(hr_users)} HR users")
            
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Error sending order cancelled notification for order {order.id}: {e}")
            return False

    async def send_hr_order_cancellation_notification(self, order: Order, user: User, hr_user_id: int, reason: str = None) -> bool:
        """
        Отправить уведомление HR об отмене заказа с кнопкой "Просмотрено"
        """
        try:
            # Формируем упоминание пользователя с полным именем и username
            if user.username:
                user_mention = f'<a href="tg://user?id={user.telegram_id}">{user.fullname}</a> (@{user.username})'
            else:
                user_mention = f'<a href="tg://user?id={user.telegram_id}">{user.fullname}</a>'
            
            cancel_reason = reason or "Заказ отменен системой"
            
            text = (
                f"❌ <b>Заказ #{order.id} отменен</b>\n\n"
                f"👤 Заказчик: {user_mention}\n"
                f"🏢 Отдел: {user.department or 'Не указан'}\n"
                f"💰 Сумма: {abs(order.total_cost)} T-Points\n"
                f"📅 Дата заказа: {order.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                f"📅 Дата отмены: {order.updated_at.strftime('%d.%m.%Y %H:%M')}\n\n"
                f"📝 Причина: <i>{cancel_reason}</i>\n\n"
                f"💳 T-Points возвращены заказчику.\n"
                f"📦 Товары возвращены на склад."
            )
            
            # Создаем клавиатуру с кнопкой "Просмотрено"
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Просмотрено",
                        callback_data=f"hr_acknowledge_cancel:{order.id}"
                    )
                ]
            ])
            
            # Отправляем уведомление HR
            try:
                await self.bot.send_message(
                    chat_id=hr_user_id,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
                logger.info(f"HR cancellation notification sent to user {hr_user_id} for order {order.id}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to send HR cancellation notification to user {hr_user_id}: {e}")
                return False
            
        except Exception as e:
            logger.error(f"Error sending HR order cancellation notification for order {order.id}: {e}")
            return False
    
    async def notify_order_status_change(self, order: Order, old_status: str, hr_user: User = None) -> bool:
        """
        НОВЫЙ МЕТОД: Отправить уведомление пользователю об изменении статуса заказа
        Используется в notifications.py при принятии заказа в работу
        """
        try:
            # Проверяем наличие заказа
            if not order:
                logger.error("Order not found for status notification")
                return False
            
            # Определяем новый статус
            new_status = order.status
            
            # Получаем ID пользователя из заказа
            user_id = order.user_id
            if hasattr(order, 'user') and order.user:
                user_id = order.user.telegram_id
            
            # Отправляем уведомление через существующий метод
            success = await self.send_status_change_notification(
                order_id=order.id,
                user_id=user_id,
                old_status=old_status,
                new_status=new_status,
                hr_user_id=hr_user.telegram_id if hr_user else None
            )
            
            if success:
                logger.info(f"Order status change notification sent for order {order.id}: {old_status} → {new_status}")
            else:
                logger.error(f"Failed to send order status change notification for order {order.id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error in notify_order_status_change for order {order.id}: {e}")
            return False
    
    async def send_notification(self, notification_type: str, **kwargs) -> bool:
        """
        Реализация абстрактного метода для отправки уведомлений о заказах
        """
        if notification_type == "order_created":
            return await self.send_order_created_notification(
                kwargs.get('order'), 
                kwargs.get('user')
            )
        elif notification_type == "order_status_changed":
            return await self.send_order_status_notification(
                kwargs.get('order'),
                kwargs.get('new_status'),
                kwargs.get('hr_user')
            )
        elif notification_type == "order_cancelled_by_user":
            return await self.send_order_cancelled_by_user_notification(
                kwargs.get('order'),
                kwargs.get('user'),
                kwargs.get('reason')
            )
        else:
            logger.warning(f"Unknown order notification type: {notification_type}")
            return False
    
    async def send_status_change_notification(self, order_id: int, user_id: int, old_status: str, new_status: str, hr_user_id: int = None) -> bool:
        """Отправить уведомление пользователю об изменении статуса заказа"""
        try:
            from ...repositories.order_repository import OrderRepository
            from ...repositories.user_repository import UserRepository
            
            order_repo = OrderRepository(self.session)
            user_repo = UserRepository(self.session)
            
            # Получаем данные заказа и пользователя
            order = await order_repo.get_order_by_id(order_id)
            if not order:
                logger.error(f"Order {order_id} not found for status change notification")
                return False
            
            user = await user_repo.get_user_by_telegram_id(user_id)
            if not user:
                logger.error(f"User {user_id} not found for status change notification")
                return False
            
            # Получаем информацию о HR, если указан
            hr_user = None
            if hr_user_id:
                hr_user = await user_repo.get_user_by_telegram_id(hr_user_id)
            
            # Формируем текст уведомления в зависимости от изменения статуса
            status_messages = {
                'order_taken': self._format_order_taken_message,
                'order_ready': self._format_order_ready_message,
                'order_completed': self._format_order_completed_message,
                'order_cancelled': self._format_order_cancelled_message,
            }
            
            notification_type = self._determine_notification_type(old_status, new_status)
            message_formatter = status_messages.get(notification_type)
            
            if not message_formatter:
                logger.warning(f"No message formatter for status change {old_status} -> {new_status}")
                return False
            
            message_text = message_formatter(order, user, hr_user)
            
            # Создаем клавиатуру с кнопками
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📋 Мои заказы",
                        callback_data="menu:my_orders"
                    ),
                    InlineKeyboardButton(
                        text="🏠 Главное меню",
                        callback_data="menu:main"
                    )
                ]
            ])
            
            # Отправляем уведомление пользователю
            try:
                await self.bot.send_message(
                    chat_id=user_id,
                    text=message_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
                logger.info(f"Status change notification sent to user {user_id} for order {order_id}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to send status change notification to user {user_id}: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending status change notification: {e}")
            return False
    
    def _determine_notification_type(self, old_status: str, new_status: str) -> str:
        """Определить тип уведомления по изменению статуса"""
        # Определяем тип уведомления по изменению статуса
        if new_status == 'processing':
            return 'order_taken'
        elif new_status == 'ready_for_pickup':
            return 'order_ready'
        elif new_status == 'delivered':
            return 'order_completed'
        elif new_status == 'cancelled':
            return 'order_cancelled'
        else:
            return 'unknown'
    
    def _format_order_taken_message(self, order, user, hr_user) -> str:
        """Форматировать сообщение о взятии заказа в работу"""
        
        # Формируем имя HR с username
        if hr_user:
            if hr_user.username:
                hr_mention = f"{hr_user.fullname} (@{hr_user.username})"
            else:
                hr_mention = hr_user.fullname
        else:
            hr_mention = "HR-менеджер"
        
        # Формируем состав заказа
        order_items_text = ""
        if hasattr(order, 'items') and order.items:
            order_items_text += "📋 Состав заказа:\n"
            for item in order.items:
                size_text = f" ({item.size})" if item.size else ""
                order_items_text += f"• {item.product.name}{size_text} x{item.quantity}\n"
            order_items_text += "\n"
        
        return (
            f"⚡ <b>Ваш заказ #{order.id} взят в работу!</b>\n\n"
            f"👤 Ответственный: {hr_mention}\n"
            f"💰 Сумма: {abs(order.total_cost)} T-Points\n\n"
            f"{order_items_text}"
            f"📋 Мы начали обработку вашего заказа. "
            f"Вы получите уведомление, когда заказ будет готов к выдаче."
        )
    
    def _format_order_ready_message(self, order, user, hr_user) -> str:
        """Форматировать сообщение о готовности заказа к выдаче"""
        
        # Формируем имя и юзернейм HR для обращения
        if hr_user:
            if hr_user.username:
                hr_contact = f"{hr_user.fullname} (@{hr_user.username})"
            else:
                hr_contact = hr_user.fullname
        else:
            hr_contact = "HR-менеджеру"
        
        # Формируем состав заказа
        order_items_text = ""
        if hasattr(order, 'items') and order.items:
            order_items_text += "📋 Состав заказа:\n"
            for item in order.items:
                size_text = f" ({item.size})" if item.size else ""
                order_items_text += f"• {item.product.name}{size_text} x{item.quantity}\n"
            order_items_text += "\n"
        
        return (
            f"📦 <b>Ваш заказ #{order.id} готов к выдаче!</b>\n\n"
            f"💰 Сумма: {abs(order.total_cost)} T-Points\n"
            f"📅 Дата создания: {order.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            f"{order_items_text}"
            f"🏢 Вы можете забрать заказ в офисе.\n"
            f"По вопросу получения обращайтесь к {hr_contact}."
        )
    
    def _format_order_completed_message(self, order, user, hr_user) -> str:
        """Форматировать сообщение о выполнении заказа"""
        
        # Формируем состав заказа
        order_items_text = ""
        if hasattr(order, 'items') and order.items:
            order_items_text += "📋 Состав заказа:\n"
            for item in order.items:
                size_text = f" ({item.size})" if item.size else ""
                order_items_text += f"• {item.product.name}{size_text} x{item.quantity}\n"
            order_items_text += "\n"
        
        return (
            f"✅ <b>Ваш заказ #{order.id} выполнен!</b>\n\n"
            f"💰 Сумма заказа: {abs(order.total_cost)} T-Points\n"
            f"📅 Дата получения: {order.updated_at.strftime('%d.%m.%Y %H:%M') if order.updated_at else 'сегодня'}\n\n"
            f"{order_items_text}"
            f"🎉 Спасибо за использование системы заказов!"
        )
    
    def _format_order_cancelled_message(self, order, user, hr_user) -> str:
        """Форматировать сообщение об отмене заказа"""
        
        # Формируем состав заказа
        order_items_text = ""
        if hasattr(order, 'items') and order.items:
            order_items_text += "📋 Состав заказа:\n"
            for item in order.items:
                size_text = f" ({item.size})" if item.size else ""
                order_items_text += f"• {item.product.name}{size_text} x{item.quantity}\n"
            order_items_text += "\n"
        
        # Формируем информацию о том, кто отменил
        cancellation_info = ""
        if hr_user:
            if hr_user.username:
                hr_mention = f"{hr_user.fullname} (@{hr_user.username})"
            else:
                hr_mention = hr_user.fullname
            cancellation_info = f"👤 Отменил: {hr_mention}\n"
        
        return (
            f"❌ <b>Ваш заказ #{order.id} отменён</b>\n\n"
            f"💰 Возвращено: {abs(order.total_cost)} T-Points\n"
            f"📅 Дата отмены: {order.updated_at.strftime('%d.%m.%Y %H:%M') if order.updated_at else 'сегодня'}\n"
            f"{cancellation_info}\n"
            f"{order_items_text}"
            f"🔄 T-Points возвращены на ваш баланс\n\n"
            f"❓ Если у вас есть вопросы, обращайтесь к HR-менеджеру."
        ) 