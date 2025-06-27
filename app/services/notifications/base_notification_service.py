from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from datetime import datetime, time, timedelta
import asyncio
from ...utils.telegram_client import SafeTelegramClient
from ...config import Config

logger = logging.getLogger(__name__)

class BaseNotificationService(ABC):
    """Базовый класс для всех сервисов уведомлений"""
    
    def __init__(self, session: AsyncSession, bot: Bot, config: Config = None):
        self.session = session
        self.bot = bot
        # Создаем безопасный клиент для отправки сообщений
        if config:
            self.safe_client = SafeTelegramClient(bot, config)
        else:
            # Fallback для обратной совместимости
            from ...config import Config
            self.safe_client = SafeTelegramClient(bot, Config())
        
    @abstractmethod
    async def send_notification(self, **kwargs) -> bool:
        """Абстрактный метод для отправки уведомления"""
        pass
    
    async def _send_message_to_users(
        self, 
        user_ids: List[int], 
        text: str, 
        reply_markup: Optional[InlineKeyboardMarkup] = None
    ) -> Dict[int, bool]:
        """
        Отправить сообщение списку пользователей
        Возвращает словарь {user_id: success}
        """
        results = {}
        
        # Создаем задачи для отправки сообщений параллельно
        tasks = []
        for user_id in user_ids:
            task = asyncio.create_task(
                self._send_single_message(user_id, text, reply_markup)
            )
            tasks.append((user_id, task))
        
        # Ждем завершения всех задач
        for user_id, task in tasks:
            try:
                results[user_id] = await task
            except Exception as e:
                logger.error(f"Failed to send notification to user {user_id}: {e}")
                results[user_id] = False
                
        return results
    
    async def _send_single_message(
        self, 
        user_id: int, 
        text: str, 
        reply_markup: Optional[InlineKeyboardMarkup] = None
    ) -> bool:
        """
        Отправить одно сообщение пользователю с безопасной обработкой ошибок
        """
        success, message, error = await self.safe_client.send_message_safe(
            chat_id=user_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        
        if not success:
            logger.error(f"Failed to send notification to user {user_id}: {error}")
        
        return success
    
    def _is_working_day(self, date: datetime = None) -> bool:
        """
        Проверить, является ли день рабочим (пн-пт)
        """
        if date is None:
            date = datetime.now()
            
        # 0 = понедельник, 6 = воскресенье
        return date.weekday() < 5
    
    def _get_next_working_day(self, date: datetime = None) -> datetime:
        """
        Получить следующий рабочий день
        """
        if date is None:
            date = datetime.now()
            
        # Если сегодня рабочий день, возвращаем сегодня
        if self._is_working_day(date):
            return date
            
        # Иначе находим следующий понедельник
        days_until_monday = (7 - date.weekday()) % 7
        if days_until_monday == 0:  # Сегодня воскресенье
            days_until_monday = 1
            
        next_working_day = date + timedelta(days=days_until_monday)
        return next_working_day.replace(hour=9, minute=0, second=0, microsecond=0)
    
    def _should_send_notification_now(self) -> bool:
        """
        Определить, нужно ли отправлять уведомление сейчас
        или отложить до рабочего времени
        """
        # В текущей реализации всегда отправляем уведомления
        # TODO: Добавить настройку для контроля рабочего времени
        return True
        
        # Закомментированная логика рабочего времени:
        # now = datetime.now()
        # 
        # # Проверяем рабочий день
        # if not self._is_working_day(now):
        #     return False
        #     
        # # Проверяем рабочее время (9:00 - 18:00)
        # working_start = time(9, 0)
        # working_end = time(18, 0)
        # current_time = now.time()
        # 
        # return working_start <= current_time <= working_end
    
    async def _get_hr_users(self) -> List[int]:
        """
        Получить список всех HR пользователей и администраторов
        """
        try:
            from ...repositories.user_repository import UserRepository
            user_repo = UserRepository(self.session)
            
            # Получаем HR пользователей и администраторов
            hr_users = await user_repo.get_active_users_by_role('hr')
            admin_users = await user_repo.get_active_users_by_role('admin')
            
            # Объединяем списки и избегаем дубликатов
            all_users = hr_users + admin_users
            unique_telegram_ids = list(set(user.telegram_id for user in all_users))
            
            logger.info(f"Found {len(unique_telegram_ids)} HR/admin users for notifications")
            return unique_telegram_ids
        except Exception as e:
            logger.error(f"Error getting HR users: {e}")
            return []
    
    def _format_user_mention(self, user_id: int, username: str = None, full_name: str = None) -> str:
        """
        Форматировать упоминание пользователя как ссылку
        """
        if username and username.strip():
            return f"@{username.strip()}"
        elif full_name and full_name.strip():
            return f'<a href="tg://user?id={user_id}">{full_name.strip()}</a>'
        else:
            return f'<a href="tg://user?id={user_id}">HR (ID: {user_id})</a>'
    
    def _truncate_text(self, text: str, max_length: int = 4000) -> str:
        """
        Обрезать текст до максимальной длины для Telegram
        """
        if len(text) <= max_length:
            return text
        
        return text[:max_length - 3] + "..." 