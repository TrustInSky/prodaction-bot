from sqlalchemy.ext.asyncio import AsyncSession
from ..repositories.user_repository import UserRepository
from ..models.models import User
from ..core.base import BaseService
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

class UserService(BaseService):
    """Сервис для работы с пользователями"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.repository = UserRepository(session)
        
    async def get_user(self, telegram_id: int) -> Optional[User]:
        """Получить пользователя по Telegram ID"""
        try:
            return await self.repository.get_user_by_telegram_id(telegram_id)
        except Exception as e:
            logger.error(f"Error getting user {telegram_id}: {e}")
            return None
            
    async def get_user_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Получить пользователя по Telegram ID (алиас для совместимости)"""
        return await self.get_user(telegram_id)
            
    async def get_or_create_user(self, telegram_id: int, username: Optional[str], fullname: str, is_active: bool = True) -> Optional[User]:
        """Получить или создать пользователя"""
        try:
            return await self.repository.get_or_create_user(telegram_id, username, fullname, is_active)
        except Exception as e:
            logger.error(f"Error getting or creating user {telegram_id}: {e}")
            return None
            
    async def get_user_role(self, telegram_id: int) -> str:
        """Получить роль пользователя"""
        try:
            user = await self.repository.get_user_by_telegram_id(telegram_id)
            if user:
                return user.role
            return "user"  # Роль по умолчанию
        except Exception as e:
            logger.error(f"Error getting user role for {telegram_id}: {e}")
            return "user"
            
    async def update_tpoints(self, telegram_id: int, points: int) -> bool:
        """Обновить количество T-Points у пользователя"""
        try:
            return await self.repository.update_tpoints(telegram_id, points)
        except Exception as e:
            logger.error(f"Error updating T-Points for user {telegram_id}: {e}")
            return False
            
    async def add_tpoints(self, telegram_id: int, points: int) -> bool:
        """Добавить T-Points пользователю"""
        try:
            return await self.repository.add_tpoints(telegram_id, points)
        except Exception as e:
            logger.error(f"Error adding T-Points for user {telegram_id}: {e}")
            return False
            
    async def remove_tpoints(self, telegram_id: int, points: int) -> bool:
        """Удалить T-Points у пользователя"""
        try:
            return await self.repository.remove_tpoints(telegram_id, points)
        except Exception as e:
            logger.error(f"Error removing T-Points for user {telegram_id}: {e}")
            return False
            
    async def get_all_users(self) -> List[User]:
        """Получить всех пользователей"""
        try:
            return await self.repository.get_all_users()
        except Exception as e:
            logger.error(f"Error getting all users: {e}")
            return []
            
    async def get_all_active_users(self) -> List[User]:
        """Получить всех активных пользователей"""
        try:
            return await self.repository.get_all_active_users()
        except Exception as e:
            logger.error(f"Error getting active users: {e}")
            return []
            
    async def get_all_hr_users(self) -> List[User]:
        """Получить всех HR-пользователей"""
        try:
            return await self.repository.get_all_hr_users()
        except Exception as e:
            logger.error(f"Error getting HR users: {e}")
            return []
    
    async def get_all_hr_and_admin_users(self) -> List[User]:
        """Получить всех HR и админов для работы с заказами"""
        try:
            return await self.repository.get_all_hr_and_admin_users()
        except Exception as e:
            logger.error(f"Error getting HR and admin users: {e}")
            return []
            
    async def get_all_admins(self) -> List[User]:
        """Получить всех администраторов"""
        try:
            return await self.repository.get_all_admins()
        except Exception as e:
            logger.error(f"Error getting admin users: {e}")
            return []
    
    async def get_users_by_role(self, role: str) -> List[User]:
        """Получить пользователей по роли"""
        try:
            if role == "admin":
                return await self.repository.get_all_admins()
            elif role == "hr":
                return await self.repository.get_all_hr_users()
            elif role == "user":
                # Получаем всех пользователей с ролью "user"
                return await self.repository.get_users_by_role("user")
            else:
                return await self.repository.get_users_by_role(role)
        except Exception as e:
            logger.error(f"Error getting users by role {role}: {e}")
            return []
    
    async def get_blocked_users(self) -> List[User]:
        """Получить заблокированных пользователей"""
        try:
            return await self.repository.get_blocked_users()
        except Exception as e:
            logger.error(f"Error getting blocked users: {e}")
            return []

    async def needs_onboarding(self, telegram_id: int) -> bool:
        """Проверить, нужен ли онбординг пользователю"""
        try:
            user = await self.repository.get_user_by_telegram_id(telegram_id)
            if not user:
                return False
            
            # Проверяем, заполнены ли обязательные поля
            return not user.birth_date or not user.hire_date
            
        except Exception as e:
            logger.error(f"Error checking onboarding for user {telegram_id}: {e}")
            return False

    async def notify_hr_about_new_employee(self, bot, new_user) -> bool:
        """Уведомление HR о новом сотруднике"""
        try:
            hr_users = await self.repository.get_all_hr_and_admin_users()
            
            if not hr_users:
                logger.warning("No HR users found to notify about new employee")
                return False
            
            # Формируем данные пользователя
            birth_date_str = new_user.birth_date.strftime("%d.%m.%Y") if new_user.birth_date else "❌ не указана"
            hire_date_str = new_user.hire_date.strftime("%d.%m.%Y") if new_user.hire_date else "❌ не указана"
            department_str = new_user.department if new_user.department else "❌ не указан"
            
            notification_text = (
                f"👤 <b>Новый сотрудник в системе!</b>\n\n"
                f"🆔 ID: <code>{new_user.telegram_id}</code>\n"
                f"👤 Имя: {new_user.fullname}\n"
                f"💬 Username: @{new_user.username or 'не указан'}\n"
                f"📅 Присоединился: сейчас\n\n"
                f"📋 <b>Данные сотрудника:</b>\n"
                f"🎂 Дата рождения: {birth_date_str}\n"
                f"💼 Дата трудоустройства: {hire_date_str}\n"
                f"🏢 Отдел: {department_str}\n\n"
                f"❗️ <b>Требуется проверить:</b>\n"
                f"• Корректность введенных данных\n"
                f"• Заполнение пропущенных полей\n"
                f"• Присвоение правильной роли\n\n"
                f"Используйте кнопки ниже для управления сотрудником."
            )
            
            # Импортируем клавиатуру для уведомлений HR
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="👥 Управление сотрудниками",
                        callback_data="menu:users"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="⏰ Позже",
                        callback_data="hr_notification_later"
                    )
                ]
            ])
            
            # Отправляем уведомление всем HR
            success_count = 0
            for hr_user in hr_users:
                try:
                    await bot.send_message(
                        chat_id=hr_user.telegram_id,
                        text=notification_text,
                        reply_markup=keyboard
                    )
                    success_count += 1
                    logger.info(f"Sent new employee notification to HR {hr_user.telegram_id}")
                except Exception as e:
                    logger.error(f"Failed to send notification to HR {hr_user.telegram_id}: {e}")
            
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Error notifying HR about new employee: {e}")
            return False

    async def get_onboarding_message(self, user) -> str:
        """Генерация приветственного сообщения для нового сотрудника"""
        return (
            f"🎉 <b>Добро пожаловать, {user.fullname}!</b>\n\n"
            f"Поздравляем с присоединением к нашей команде! 🚀\n\n"
            f"📱 <b>О боте HR Support:</b>\n"
            f"• 🛍 Корпоративный магазин с товарами\n"
            f"• 💎 Система T-Points для покупок\n"
            f"• ❓ Анонимные вопросы и предложения\n"
            f"• 📋 Управление заказами\n\n"
            f"💰 <b>Ваш стартовый баланс:</b> {user.tpoints:,} T-Points\n\n"
            f"ℹ️ <b>Как зарабатывать T-Points:</b>\n"
            f"• Активное участие в жизни компании\n"
            f"• Выполнение специальных активностей\n"
            f"• Достижения и успехи в работе\n\n"
            f"📝 Дополнительные данные (дата рождения, отдел) можно будет заполнить через HR.\n\n"
            f"🏠 Нажмите кнопку ниже, чтобы перейти в главное меню:"
        )

    async def get_welcome_message(self, user) -> str:
        """Генерация приветственного сообщения для существующего пользователя"""
        # Извлекаем имя из ФИО
        parts = user.fullname.strip().split()
        first_name = parts[1] if len(parts) >= 2 else parts[0] if parts else user.fullname
        
        return (
            f"👋 Привет, {first_name}!\n\n"
            f"💎 Ваш баланс: {user.tpoints:,} T-Points\n\n"
            f"Выберите действие:"
        )

    async def get_users_stats(self) -> dict:
        """Получить статистику по пользователям"""
        try:
            stats = await self.repository.get_users_stats()
            return {
                'total_users': stats.get('total_users', 0),
                'active_users': stats.get('active_users', 0),
                'departments_count': stats.get('departments_count', 0)
            }
        except Exception as e:
            logger.error(f"Error getting users stats: {e}")
            return {
                'total_users': 0,
                'active_users': 0,
                'departments_count': 0
            }
    
    async def set_role(self, telegram_id: int, role: str) -> Optional[User]:
        """Установить роль пользователя"""
        try:
            success = await self.repository.update_user_data(telegram_id, {'role': role})
            if success:
                return await self.repository.get_user_by_telegram_id(telegram_id)
            return None
        except Exception as e:
            logger.error(f"Error setting role for user {telegram_id}: {e}")
            return None
    
    async def activate_user(self, telegram_id: int) -> Optional[User]:
        """Активировать пользователя"""
        try:
            success = await self.repository.update_user_data(telegram_id, {'is_active': True})
            if success:
                return await self.repository.get_user_by_telegram_id(telegram_id)
            return None
        except Exception as e:
            logger.error(f"Error activating user {telegram_id}: {e}")
            return None
    
    async def deactivate_user(self, telegram_id: int, remove_from_group: bool = False, 
                             bot=None, group_management_service=None) -> Optional[User]:
        """Деактивировать пользователя и опционально удалить из группы"""
        try:
            success = await self.repository.update_user_data(telegram_id, {'is_active': False})
            if success:
                user = await self.repository.get_user_by_telegram_id(telegram_id)
                
                # Автоматическое удаление из группы если переданы нужные сервисы
                if remove_from_group and bot and group_management_service:
                    try:
                        removal_success = await group_management_service.remove_user_from_group(
                            bot=bot,
                            user_id=telegram_id,
                            reason=f"Деактивация пользователя {user.fullname}"
                        )
                        
                        if removal_success:
                            logger.warning(f"🚨 USER REMOVED FROM GROUP: {user.fullname} (ID: {telegram_id})")
                            
                            # Уведомляем пользователя
                            await group_management_service.notify_user_about_removal(
                                bot=bot,
                                user_id=telegram_id,
                                reason="деактивации аккаунта"
                            )
                        else:
                            logger.error(f"Failed to remove deactivated user {telegram_id} from group")
                            
                    except Exception as group_error:
                        logger.error(f"Error removing user {telegram_id} from group: {group_error}")
                
                return user
            return None
        except Exception as e:
            logger.error(f"Error deactivating user {telegram_id}: {e}")
            return None