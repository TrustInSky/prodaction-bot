from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InputMediaPhoto
from aiogram.exceptions import TelegramBadRequest
import logging

logger = logging.getLogger(__name__)

async def update_message(
    msg: CallbackQuery | Message,
    text: str = None,
    media: InputMediaPhoto = None,
    reply_markup: InlineKeyboardMarkup = None
):
    """
    Универсальная функция для обновления сообщений с поддержкой текста, медиа и клавиатуры
    
    Args:
        msg: Callback или сообщение
        text: Новый текст
        media: Новое медиа (фото)
        reply_markup: Новая клавиатура
    """
    # Получаем правильные объекты в зависимости от типа входного параметра
    if isinstance(msg, CallbackQuery):
        bot = msg.bot
        chat_id = msg.message.chat.id
        message = msg.message
    else:
        bot = msg.bot
        chat_id = msg.chat.id
        message = msg

    try:
        if media:
            # Если сообщение содержит media (например, фото)
            if hasattr(message, 'photo') and message.photo:
                await message.edit_media(media=media, reply_markup=reply_markup)
            else:
                # Нельзя редактировать media в текстовом сообщении — удаляем и отправляем заново
                await message.delete()
                await bot.send_photo(
                    chat_id=chat_id, 
                    photo=media.media, 
                    caption=media.caption, 
                    parse_mode="HTML", 
                    reply_markup=reply_markup
                )
        elif text:
            # Если текущее сообщение содержит фото, а мы хотим показать только текст
            if hasattr(message, 'photo') and message.photo:
                await message.delete()
                await bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )
            elif hasattr(message, 'text') and message.text:
                await message.edit_text(text=text, parse_mode="HTML", reply_markup=reply_markup)
            elif hasattr(message, 'caption') and message.caption:
                await message.edit_caption(caption=text, parse_mode="HTML", reply_markup=reply_markup)
            else:
                await message.delete()
                await bot.send_message(
                    chat_id=chat_id, 
                    text=text, 
                    parse_mode="HTML", 
                    reply_markup=reply_markup
                )
        elif reply_markup:
            await message.edit_reply_markup(reply_markup=reply_markup)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            # Игнорируем ошибку о неизмененном сообщении
            pass
        else:
            # Логируем другие ошибки Bad Request
            logger.error(f"Error updating message: {e}")
            if isinstance(msg, CallbackQuery):
                await msg.answer("❌ Ошибка при обновлении сообщения")
    except Exception as e:
        logger.error(f"Error updating message: {e}")
        if isinstance(msg, CallbackQuery):
            await msg.answer("❌ Произошла ошибка")
        # Fallback: если всё равно что-то не так, просто удалим и отправим новое
        try:
            await message.delete()
            if media:
                await bot.send_photo(
                    chat_id=chat_id, 
                    photo=media.media, 
                    caption=media.caption, 
                    parse_mode="HTML", 
                    reply_markup=reply_markup
                )
            elif text:
                await bot.send_message(
                    chat_id=chat_id, 
                    text=text, 
                    parse_mode="HTML", 
                    reply_markup=reply_markup
                )
        except Exception as ex:
            print(f"Failed to recover: {ex}") 