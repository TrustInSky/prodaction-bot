"""
Обработчики для автоуведомлений (кнопки в сообщениях)
"""
from aiogram import Router, F, types
import logging

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data.startswith("birthday_thanks_"))
async def handle_birthday_thanks(callback: types.CallbackQuery):
    """Обработка кнопки 'Спасибо' от пользователя"""
    try:
        await callback.answer("Уведомление получено", show_alert=True)
        
        # Скрываем сообщение полностью
        await callback.message.delete()
        
    except Exception as e:
        logger.error(f"Error handling birthday thanks: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("birthday_hr_thanks_"))
async def handle_birthday_hr_thanks(callback: types.CallbackQuery):
    """Обработка кнопки 'Спасибо' от HR"""
    try:
        await callback.answer("Уведомление получено", show_alert=True)
        
        # Скрываем сообщение полностью
        await callback.message.delete()
        
    except Exception as e:
        logger.error(f"Error handling birthday HR thanks: {e}")
        await callback.answer("❌ Ошибка", show_alert=True) 