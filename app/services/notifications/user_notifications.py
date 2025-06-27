from typing import Optional, List
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from .base_notification_service import BaseNotificationService
from ...models.models import User
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class UserNotificationService(BaseNotificationService):
    """Сервис пользовательских уведомлений (баланс, статусы и т.д.)"""
    
    async def send_balance_update_notification(self, user: User, old_balance: int, new_balance: int, reason: str) -> bool:
        """
        Отправить уведомление об изменении баланса T-Points
        """
        try:
            difference = new_balance - old_balance
            emoji = "💚" if difference > 0 else "💔"
            action = "начислено" if difference > 0 else "списано"
            
            text = (
                f"{emoji} <b>Изменение баланса T-Points</b>\n\n"
                f"💰 Было: {old_balance} T-Points\n"
                f"💰 Стало: {new_balance} T-Points\n"
                f"📊 Изменение: {difference:+d} T-Points\n\n"
                f"📝 Причина: {reason}\n\n"
                f"💳 {action.capitalize()}: {abs(difference)} T-Points"
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="💰 Мой баланс",
                        callback_data="menu:balance"
                    ),
                    InlineKeyboardButton(
                        text="🏠 Главное меню",
                        callback_data="menu:main"
                    )
                ]
            ])
            
            results = await self._send_message_to_users([user.telegram_id], text, keyboard)
            
            success = results.get(user.telegram_id, False)
            if success:
                logger.info(f"Balance notification sent to user {user.telegram_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending balance notification to user {user.telegram_id}: {e}")
            return False
    
    async def send_welcome_notification(self, user: User) -> bool:
        """
        Отправить приветственное уведомление новому пользователю
        """
        try:
            text = (
                f"👋 <b>Добро пожаловать, {user.full_name or user.username or 'Пользователь'}!</b>\n\n"
                f"🎉 Вы успешно зарегистрированы в системе HR Support Bot.\n\n"
                f"💰 Ваш стартовый баланс: {user.tpoints} T-Points\n\n"
                f"📋 Что вы можете делать:\n"
                f"• 🛍️ Заказывать товары из каталога\n"
                f"• 📊 Отслеживать свои заказы\n"
                f"• 💳 Проверять баланс T-Points\n"
                f"• ❓ Задавать вопросы HR\n\n"
                f"Для начала нажмите /start или выберите действие в главном меню!"
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🏠 Главное меню",
                        callback_data="menu:main"
                    ),
                    InlineKeyboardButton(
                        text="🛍️ Каталог",
                        callback_data="menu:catalog"
                    )
                ]
            ])
            
            results = await self._send_message_to_users([user.telegram_id], text, keyboard)
            
            success = results.get(user.telegram_id, False)
            if success:
                logger.info(f"Welcome notification sent to user {user.telegram_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending welcome notification to user {user.telegram_id}: {e}")
            return False
    
    async def send_profile_update_notification(self, user: User, updated_fields: List[str]) -> bool:
        """
        Отправить уведомление об обновлении профиля
        """
        try:
            field_names = {
                'full_name': 'имя',
                'department': 'отдел',
                'role': 'роль',
                'username': 'username'
            }
            
            updated_fields_text = ", ".join(field_names.get(field, field) for field in updated_fields)
            
            text = (
                f"✅ <b>Профиль обновлен</b>\n\n"
                f"📝 Обновлены поля: {updated_fields_text}\n\n"
                f"👤 Имя: {user.full_name or 'Не указано'}\n"
                f"🏢 Отдел: {user.department or 'Не указан'}\n"
                f"🎭 Роль: {user.role or 'Пользователь'}\n"
                f"💰 Баланс: {user.tpoints} T-Points"
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="👤 Мой профиль",
                        callback_data="menu:profile"
                    ),
                    InlineKeyboardButton(
                        text="🏠 Главное меню",
                        callback_data="menu:main"
                    )
                ]
            ])
            
            results = await self._send_message_to_users([user.telegram_id], text, keyboard)
            
            success = results.get(user.telegram_id, False)
            if success:
                logger.info(f"Profile update notification sent to user {user.telegram_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending profile update notification to user {user.telegram_id}: {e}")
            return False
    
    async def send_reminder_notification(self, user: User, reminder_type: str, details: str) -> bool:
        """
        Отправить напоминание пользователю
        """
        try:
            reminder_titles = {
                'order_pickup': '📦 Напоминание о получении заказа',
                'profile_incomplete': '📝 Напоминание о заполнении профиля',
                'survey': '📊 Напоминание об опросе'
            }
            
            title = reminder_titles.get(reminder_type, '🔔 Напоминание')
            
            text = (
                f"🔔 <b>{title}</b>\n\n"
                f"{details}\n\n"
                f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            )
            
            # Кнопки зависят от типа напоминания
            if reminder_type == 'order_pickup':
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="📋 Мои заказы",
                            callback_data="menu:my_orders"
                        )
                    ]
                ])
            elif reminder_type == 'profile_incomplete':
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="👤 Заполнить профиль",
                            callback_data="menu:profile"
                        )
                    ]
                ])
            else:
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🏠 Главное меню",
                            callback_data="menu:main"
                        )
                    ]
                ])
            
            results = await self._send_message_to_users([user.telegram_id], text, keyboard)
            
            success = results.get(user.telegram_id, False)
            if success:
                logger.info(f"Reminder notification sent to user {user.telegram_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending reminder notification to user {user.telegram_id}: {e}")
            return False
    
    async def send_notification(self, notification_type: str, **kwargs) -> bool:
        """
        Реализация абстрактного метода для отправки пользовательских уведомлений
        """
        if notification_type == "balance_update":
            return await self.send_balance_update_notification(
                kwargs.get('user'),
                kwargs.get('old_balance'),
                kwargs.get('new_balance'),
                kwargs.get('reason')
            )
        elif notification_type == "welcome":
            return await self.send_welcome_notification(kwargs.get('user'))
        elif notification_type == "profile_update":
            return await self.send_profile_update_notification(
                kwargs.get('user'),
                kwargs.get('updated_fields', [])
            )
        elif notification_type == "reminder":
            return await self.send_reminder_notification(
                kwargs.get('user'),
                kwargs.get('reminder_type'),
                kwargs.get('details')
            )
        else:
            logger.warning(f"Unknown user notification type: {notification_type}")
            return False 