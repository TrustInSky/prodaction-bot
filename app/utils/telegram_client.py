import asyncio
import logging
from typing import Optional, Union, Dict, Any
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, Message
from aiogram.exceptions import (
    TelegramNetworkError, 
    TelegramServerError, 
    TelegramRetryAfter,
    TelegramBadRequest,
    TelegramUnauthorizedError,
    TelegramForbiddenError
)
from aiogram.client.session.aiohttp import AiohttpSession
import aiohttp
from app.config import Config

logger = logging.getLogger(__name__)

class SafeTelegramClient:
    """Безопасный клиент для работы с Telegram API с обработкой сетевых ошибок"""
    
    def __init__(self, bot: Bot, config: Config):
        self.bot = bot
        self.config = config
        self.retry_count = config.TELEGRAM_RETRY_COUNT
        self.retry_delay = config.TELEGRAM_RETRY_DELAY
        self.timeout = config.TELEGRAM_TIMEOUT
    
    async def send_message_safe(
        self,
        chat_id: Union[int, str],
        text: str,
        reply_markup: Optional[InlineKeyboardMarkup] = None,
        parse_mode: str = 'HTML',
        disable_notification: bool = False,
        **kwargs
    ) -> tuple[bool, Optional[Message], Optional[str]]:
        """
        Безопасная отправка сообщения с retry логикой
        
        Returns:
            tuple[bool, Optional[Message], Optional[str]]: (success, message, error_description)
        """
        
        for attempt in range(self.retry_count + 1):
            try:
                message = await self.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                    disable_notification=disable_notification,
                    **kwargs
                )
                
                logger.info(f"Message sent successfully to {chat_id} on attempt {attempt + 1}")
                return True, message, None
                
            except TelegramRetryAfter as e:
                # Telegram просит подождать
                retry_after = e.retry_after
                logger.warning(f"Rate limited for {chat_id}, waiting {retry_after} seconds")
                
                if attempt < self.retry_count:
                    await asyncio.sleep(retry_after)
                    continue
                else:
                    return False, None, f"Rate limited: {retry_after}s"
                    
            except TelegramNetworkError as e:
                # Сетевая ошибка - повторяем попытку
                logger.warning(f"Network error for {chat_id} on attempt {attempt + 1}: {e}")
                
                if attempt < self.retry_count:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))  # Экспоненциальная задержка
                    continue
                else:
                    return False, None, f"Network error: {str(e)}"
                    
            except TelegramServerError as e:
                # Ошибка сервера Telegram - повторяем попытку
                logger.warning(f"Server error for {chat_id} on attempt {attempt + 1}: {e}")
                
                if attempt < self.retry_count:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    continue
                else:
                    return False, None, f"Server error: {str(e)}"
                    
            except TelegramUnauthorizedError as e:
                # Бот заблокирован - не повторяем
                logger.error(f"Bot unauthorized for {chat_id}: {e}")
                return False, None, f"Unauthorized: {str(e)}"
                
            except TelegramForbiddenError as e:
                # Бот заблокирован пользователем - не повторяем
                logger.warning(f"Bot blocked by user {chat_id}: {e}")
                return False, None, f"Blocked by user: {str(e)}"
                
            except TelegramBadRequest as e:
                # Неправильный запрос - не повторяем
                logger.error(f"Bad request for {chat_id}: {e}")
                return False, None, f"Bad request: {str(e)}"
                
            except Exception as e:
                # Прочие ошибки
                logger.error(f"Unexpected error for {chat_id} on attempt {attempt + 1}: {e}")
                
                if attempt < self.retry_count:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    continue
                else:
                    return False, None, f"Unexpected error: {str(e)}"
        
        return False, None, "Max retry count exceeded"
    
    async def send_messages_batch(
        self,
        messages: list[Dict[str, Any]],
        max_concurrent: int = 5
    ) -> Dict[Union[int, str], tuple[bool, Optional[str]]]:
        """
        Отправка сообщений пачками с ограничением на количество одновременных запросов
        
        Args:
            messages: Список словарей с параметрами для send_message_safe
            max_concurrent: Максимальное количество одновременных запросов
            
        Returns:
            Dict[chat_id, (success, error_description)]
        """
        
        semaphore = asyncio.Semaphore(max_concurrent)
        results = {}
        
        async def send_single(message_data: Dict[str, Any]):
            async with semaphore:
                chat_id = message_data.get('chat_id')
                
                success, msg, error = await self.send_message_safe(**message_data)
                results[chat_id] = (success, error)
                
                # Небольшая задержка между запросами для предотвращения rate limiting
                await asyncio.sleep(0.1)
        
        # Создаем задачи для всех сообщений
        tasks = [send_single(msg_data) for msg_data in messages]
        
        # Выполняем все задачи
        await asyncio.gather(*tasks, return_exceptions=True)
        
        return results
    
    async def edit_message_safe(
        self,
        chat_id: Union[int, str],
        message_id: int,
        text: str,
        reply_markup: Optional[InlineKeyboardMarkup] = None,
        parse_mode: str = 'HTML'
    ) -> tuple[bool, Optional[str]]:
        """
        Безопасное редактирование сообщения
        
        Returns:
            tuple[bool, Optional[str]]: (success, error_description)
        """
        
        for attempt in range(self.retry_count + 1):
            try:
                await self.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode
                )
                
                logger.info(f"Message edited successfully in {chat_id}")
                return True, None
                
            except TelegramBadRequest as e:
                if "message is not modified" in str(e).lower():
                    # Сообщение не изменилось - это не ошибка
                    return True, None
                elif "message to edit not found" in str(e).lower():
                    # Сообщение не найдено - не повторяем
                    return False, f"Message not found: {str(e)}"
                else:
                    logger.error(f"Bad request editing message in {chat_id}: {e}")
                    return False, f"Bad request: {str(e)}"
                    
            except (TelegramNetworkError, TelegramServerError) as e:
                logger.warning(f"Network/Server error editing message in {chat_id} on attempt {attempt + 1}: {e}")
                
                if attempt < self.retry_count:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    continue
                else:
                    return False, f"Network/Server error: {str(e)}"
                    
            except Exception as e:
                logger.error(f"Unexpected error editing message in {chat_id}: {e}")
                return False, f"Unexpected error: {str(e)}"
        
        return False, "Max retry count exceeded"


def create_safe_telegram_client(bot: Bot, config: Config) -> SafeTelegramClient:
    """Фабричная функция для создания безопасного Telegram клиента"""
    return SafeTelegramClient(bot, config)


# Функция create_aiohttp_session удалена, так как AiohttpSession 
# от aiogram имеет ограниченные возможности настройки 