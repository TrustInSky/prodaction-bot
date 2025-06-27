from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from ..services.user import UserService


class HROrAdminAccess(BaseMiddleware):
    """Middleware для проверки прав HR или администратора"""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Проверка доступа пользователя"""
        # Получаем user_id из события
        user_id = None
        if isinstance(event, (Message, CallbackQuery)):
            user_id = event.from_user.id
        
        if user_id is None:
            # Если не удалось получить user_id, запрещаем доступ
            return
        
        # Получаем UserService из данных (должен быть предоставлен DatabaseMiddleware)
        user_service = data.get('user_service')
        if not user_service:
            # Если сервис недоступен, запрещаем доступ
            return
        
        # Проверяем права пользователя
        user = await user_service.get_user_by_telegram_id(user_id)
        if not user or user.role not in ['hr', 'admin']:
            # Если пользователь не найден или у него нет нужных прав
            if isinstance(event, Message):
                await event.answer("❌ У вас нет прав доступа к этому разделу")
            elif isinstance(event, CallbackQuery):
                await event.answer("❌ У вас нет прав доступа к этому разделу", show_alert=True)
            return
        
        # Если все проверки пройдены, выполняем handler
        return await handler(event, data) 