import logging
from typing import Optional
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from ..core.base import BaseService

logger = logging.getLogger(__name__)

class GroupManagementService(BaseService):
    """Сервис для управления членством пользователей в группе"""
    
    def __init__(self, session, group_id: int):
        super().__init__(session)
        self.group_id = group_id
        logger.info(f"Initialized GroupManagementService with group_id: {group_id}")
    
    async def remove_user_from_group(self, bot: Bot, user_id: int, reason: str = "Деактивация аккаунта") -> bool:
        """
        Удаляет пользователя из группы
        
        Args:
            bot: Экземпляр бота
            user_id: ID пользователя для удаления
            reason: Причина удаления (для логов)
            
        Returns:
            bool: True если пользователь успешно удален
        """
        try:
            # Сначала проверяем, что пользователь действительно в группе
            try:
                member = await bot.get_chat_member(
                    chat_id=self.group_id,
                    user_id=user_id
                )
                
                if member.status in ["left", "kicked", "banned"]:
                    logger.info(f"User {user_id} is already not a member (status: {member.status})")
                    return True
                    
            except TelegramBadRequest as e:
                if "user not found" in str(e).lower():
                    logger.warning(f"User {user_id} not found in group")
                    return True
                raise
            
            # Удаляем пользователя из группы
            success = await bot.ban_chat_member(
                chat_id=self.group_id,
                user_id=user_id,
                revoke_messages=False  # Не удаляем сообщения пользователя
            )
            
            if success:
                # Сразу разбаниваем, чтобы пользователь мог вернуться через приглашение
                await bot.unban_chat_member(
                    chat_id=self.group_id,
                    user_id=user_id,
                    only_if_banned=True
                )
                
                logger.warning(f"🚨 USER REMOVED FROM GROUP: {user_id} - Reason: {reason}")
                return True
            else:
                logger.error(f"Failed to remove user {user_id} from group")
                return False
                
        except TelegramForbiddenError as e:
            logger.error(f"Bot lacks permissions to remove user {user_id}: {e}")
            return False
        except TelegramBadRequest as e:
            logger.error(f"Bad request when removing user {user_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error removing user {user_id} from group: {e}")
            return False
    
    async def check_bot_permissions(self, bot: Bot) -> dict:
        """
        Проверяет права бота в группе
        
        Returns:
            dict: Словарь с информацией о правах бота
        """
        try:
            # Получаем информацию о боте в группе
            bot_member = await bot.get_chat_member(
                chat_id=self.group_id,
                user_id=(await bot.get_me()).id
            )
            
            permissions = {
                "is_admin": bot_member.status in ["creator", "administrator"],
                "can_restrict_members": False,
                "status": bot_member.status
            }
            
            if hasattr(bot_member, 'can_restrict_members'):
                permissions["can_restrict_members"] = bot_member.can_restrict_members
            
            logger.info(f"Bot permissions in group {self.group_id}: {permissions}")
            return permissions
            
        except Exception as e:
            logger.error(f"Error checking bot permissions: {e}")
            return {
                "is_admin": False,
                "can_restrict_members": False,
                "status": "unknown",
                "error": str(e)
            }
    
    async def get_user_status_in_group(self, bot: Bot, user_id: int) -> Optional[str]:
        """
        Получает статус пользователя в группе
        
        Returns:
            Optional[str]: Статус пользователя или None при ошибке
        """
        try:
            member = await bot.get_chat_member(
                chat_id=self.group_id,
                user_id=user_id
            )
            return member.status
        except Exception as e:
            logger.error(f"Error getting user {user_id} status in group: {e}")
            return None
    
    async def notify_user_about_removal(self, bot: Bot, user_id: int, reason: str = "деактивации аккаунта"):
        """
        Уведомляет пользователя об удалении из группы
        
        Args:
            bot: Экземпляр бота
            user_id: ID пользователя
            reason: Причина удаления
        """
        try:
            message = (
                "🚨 <b>Уведомление об удалении из группы</b>\n\n"
                f"❌ Вы были удалены из группы по причине: {reason}\n\n"
                "📝 Для восстановления доступа обратитесь к администратору или HR.\n"
                "💡 После восстановления активности вам нужно будет заново вступить в группу."
            )
            
            await bot.send_message(
                chat_id=user_id,
                text=message
            )
            
            logger.info(f"Sent removal notification to user {user_id}")
            
        except Exception as e:
            logger.error(f"Failed to send removal notification to user {user_id}: {e}") 