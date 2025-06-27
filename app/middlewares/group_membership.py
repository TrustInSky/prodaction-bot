from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, Update, User
from aiogram.exceptions import TelegramBadRequest
from ..models.models import User as DBUser
import logging

logger = logging.getLogger(__name__)

class GroupMembershipMiddleware(BaseMiddleware):
    def __init__(self, target_group_id: int):
        self.target_group_id = target_group_id
        logger.info(f"Initialized GroupMembershipMiddleware with group_id: {target_group_id}")

    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        # Получаем пользователя в зависимости от типа события
        if isinstance(event, Message):
            user = event.from_user
            event_type = "message"
        elif isinstance(event, CallbackQuery):
            user = event.from_user
            event_type = "callback_query"
        else:
            logger.info(f"Skipping middleware for unsupported event type: {type(event)}")
            return await handler(event, data)
            
        logger.info(f"Got {event_type} from user {user.id if user else 'Unknown'}")

        if not user:
            logger.warning("No user data in event")
            return await handler(event, data)

        bot = data.get("bot")
        if not bot:
            logger.error("No bot instance in data")
            return await handler(event, data)

        # Получаем user_service из data (aiogram3-di)
        user_service = data.get("user_service")
        if not user_service:
            logger.error("No user_service in data")
            return await handler(event, data)
            
        logger.info(f"Processing user {user.id} ({user.full_name})")
        
        # Проверяем, является ли пользователь членом группы
        try:
            member = await bot.get_chat_member(
                chat_id=self.target_group_id,
                user_id=user.id
            )
            is_member = member.status not in ["left", "kicked", "banned"]
            logger.info(f"Group membership check: {is_member} (status: {member.status})")
        except TelegramBadRequest as e:
            logger.error(f"Error checking membership: {e}")
            is_member = False
            
        # Только получаем существующего пользователя (НЕ создаем)
        db_user = await user_service.get_user(user.id)
        
        # Добавляем информацию о пользователе в data
        data["is_group_member"] = is_member
        data["user_db"] = db_user  # Может быть None для новых пользователей
        
        # Если не член группы
        if not is_member:
            logger.warning(f"User {user.id} is not a group member")
            
            # Если пользователь есть в БД и активен - деактивируем его
            if db_user and db_user.is_active:
                try:
                    await user_service.deactivate_user(user.id)
                    logger.info(f"Deactivated user {user.id} ({db_user.fullname}) - not a group member")
                except Exception as e:
                    logger.error(f"Failed to deactivate user {user.id}: {e}")
            
            # Отправляем сообщение и прерываем обработку
            if isinstance(event, Message):
                await event.answer(
                    "❌ Вы должны быть участником группы, чтобы использовать этого бота.\n"
                    "Пожалуйста, вступите в группу и попробуйте снова."
                )
            elif isinstance(event, CallbackQuery):
                await event.answer(
                    "❌ Вы должны быть участником группы, чтобы использовать этого бота.\n"
                    "Пожалуйста, вступите в группу и попробуйте снова.",
                    show_alert=True
                )
            return None
        
        # Если пользователь является членом группы и есть в БД, но неактивен - активируем его
        if is_member and db_user and not db_user.is_active:
            try:
                await user_service.activate_user(user.id)
                logger.info(f"Reactivated user {user.id} ({db_user.fullname}) - rejoined the group")
            except Exception as e:
                logger.error(f"Failed to reactivate user {user.id}: {e}")
        
        logger.info("Proceeding to handler")
        return await handler(event, data) 