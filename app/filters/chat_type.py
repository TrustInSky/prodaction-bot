"""
Фильтры для типов чатов
"""
from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery
from typing import Union


class PrivateChatOnly(BaseFilter):
    """Фильтр для обработки только в личных чатах (не в группах)"""
    
    async def __call__(self, event: Union[Message, CallbackQuery]) -> bool:
        """
        Проверяем, что сообщение/callback пришло из личного чата
        """
        # Получаем chat из Message или из callback
        if isinstance(event, Message):
            chat = event.chat
        elif isinstance(event, CallbackQuery):
            chat = event.message.chat if event.message else None
        else:
            return False
        
        if not chat:
            return False
        
        # Разрешаем только личные чаты (private)
        # Блокируем группы (group, supergroup) и каналы (channel)
        return chat.type == "private"


class GroupChatOnly(BaseFilter):
    """Фильтр для обработки только в группах"""
    
    async def __call__(self, event: Union[Message, CallbackQuery]) -> bool:
        """
        Проверяем, что сообщение/callback пришло из группы
        """
        if isinstance(event, Message):
            chat = event.chat
        elif isinstance(event, CallbackQuery):
            chat = event.message.chat if event.message else None
        else:
            return False
        
        if not chat:
            return False
        
        # Разрешаем только группы и супергруппы
        return chat.type in ["group", "supergroup"] 