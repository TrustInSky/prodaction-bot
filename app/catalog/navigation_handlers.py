from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import CallbackQuery
from ..middlewares.database import DatabaseMiddleware
from .keyboards import catalog_kb
from ..utils.message_editor import update_message
from ..services.catalog import CatalogService
from ..utils.callback_helpers import safe_callback_answer
import logging

logger = logging.getLogger(__name__)

router = Router(name="navigation_handlers")

@router.callback_query(F.data == "menu:catalog")
async def show_catalog_menu(callback: CallbackQuery, catalog_service: CatalogService):
    """Переход в каталог из главного меню"""
    try:
        logger.info(f"User {callback.from_user.id} opening catalog")
        
        # Получаем доступные товары
        products = await catalog_service.get_available_products()
        
        text = "🛍 Каталог товаров:\n\n"
        if not products:
            text += "К сожалению, сейчас нет доступных товаров."
            keyboard = catalog_kb.CatalogKeyboard.get_catalog_keyboard([], 1)
            await update_message(callback, text=text, reply_markup=keyboard)
            return
        
        # Показываем каталог
        keyboard = catalog_kb.CatalogKeyboard.get_catalog_keyboard(products, 1)
        await update_message(callback, text=text, reply_markup=keyboard)
        await safe_callback_answer(callback)
        
    except Exception as e:
        logger.error(f"Error showing catalog: {e}", exc_info=True)
        await safe_callback_answer(callback, "❌ Ошибка при переходе в каталог")


@router.callback_query(F.data == "back_to_catalog")
async def back_to_catalog(callback: CallbackQuery, middleware: DatabaseMiddleware):
    """Вернуться к каталогу"""
    try:
        products = await middleware.catalog_service.get_all_products()
        
        text = "🛍️ <b>Каталог товаров</b>\n\n"
        text += "Выберите товар для просмотра подробной информации:"
        
        await update_message(
            callback,
            text=text,
            reply_markup=catalog_kb.get_catalog_keyboard(products)
        )
        await safe_callback_answer(callback)
        
    except Exception as e:
        logger.error(f"Error in back_to_catalog: {e}")
        await safe_callback_answer(callback, "❌ Произошла ошибка") 