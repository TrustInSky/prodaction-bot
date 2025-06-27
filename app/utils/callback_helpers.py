from aiogram.types import CallbackQuery
from aiogram.exceptions import TelegramBadRequest
import logging

logger = logging.getLogger(__name__)

async def safe_callback_answer(
    callback: CallbackQuery, 
    text: str = "", 
    show_alert: bool = False, 
    cache_time: int = 0
) -> bool:
    """
    Безопасно отвечает на callback query с обработкой ошибки "query is too old"
    
    Args:
        callback: CallbackQuery объект
        text: Текст ответа (опционально)
        show_alert: Показывать ли всплывающее окно
        cache_time: Время кэширования в секундах
        
    Returns:
        bool: True если ответ был отправлен успешно, False если произошла ошибка
    """
    try:
        await callback.answer(text=text, show_alert=show_alert, cache_time=cache_time)
        return True
    except TelegramBadRequest as e:
        if "query is too old" in str(e).lower():
            logger.warning(f"Callback query is too old for user {callback.from_user.id}, proceeding without answering")
            return False
        elif "query id is invalid" in str(e).lower():
            logger.warning(f"Callback query ID is invalid for user {callback.from_user.id}")
            return False
        elif "response timeout expired" in str(e).lower():
            logger.warning(f"Callback query response timeout expired for user {callback.from_user.id}")
            return False
        else:
            logger.error(f"Error answering callback query for user {callback.from_user.id}: {e}")
            raise  # Пробрасываем другие ошибки
    except Exception as e:
        logger.error(f"Unexpected error answering callback query for user {callback.from_user.id}: {e}")
        raise

async def safe_callback_answer_with_fallback(
    callback: CallbackQuery,
    text: str = "",
    show_alert: bool = False,
    fallback_message: str = None
) -> bool:
    """
    Безопасно отвечает на callback query с резервным сообщением
    
    Args:
        callback: CallbackQuery объект
        text: Текст ответа
        show_alert: Показывать ли всплывающее окно
        fallback_message: Резервное сообщение, если основной ответ не прошёл
        
    Returns:
        bool: True если ответ был отправлен (основной или резервный)
    """
    success = await safe_callback_answer(callback, text, show_alert)
    
    if not success and fallback_message:
        try:
            # Пытаемся отправить обычное сообщение в чат
            await callback.message.answer(fallback_message)
            logger.info(f"Sent fallback message to user {callback.from_user.id}")
            return True
        except Exception as e:
            logger.error(f"Failed to send fallback message to user {callback.from_user.id}: {e}")
            return False
    
    return success 