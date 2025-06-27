from aiogram.filters import Filter
from aiogram import types
from ..middlewares.database import get_user_service


class IsAdmin(Filter):
    """Фильтр для проверки прав администратора"""
    
    async def __call__(self, message_or_callback: types.Message | types.CallbackQuery) -> bool:
        user_service = get_user_service()
        user_id = message_or_callback.from_user.id
        
        user = await user_service.get_user_by_telegram_id(user_id)
        return user and user.role == 'admin' 