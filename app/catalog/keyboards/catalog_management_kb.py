from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from .common_kb import KeyboardBuilder, EMOJI

class CatalogManagementKeyboard(KeyboardBuilder):
    """Клавиатуры для управления каталогом"""
    
    @classmethod
    def get_management_keyboard(cls) -> InlineKeyboardMarkup:
        """Основная клавиатура управления каталогом"""
        kb = InlineKeyboardBuilder()
        
        # Кнопки управления
        kb.row(cls.create_button(
            text=f"{EMOJI['upload']} Загрузить Excel",
            callback_data="catalog:upload_excel"
        ))
        
        kb.row(cls.create_button(
            text=f"{EMOJI['download']} Выгрузить каталог",
            callback_data="catalog:export"
        ))
        
        # Навигационные кнопки
        kb.row(*cls.create_nav_row())
        
        return kb.as_markup()
    
    @classmethod
    def get_cancel_keyboard(cls) -> InlineKeyboardMarkup:
        """Клавиатура отмены"""
        kb = InlineKeyboardBuilder()
        
        kb.row(cls.create_button(
            text=f"{EMOJI['cancel']} Отмена",
            callback_data="menu:catalog_management"
        ))
        
        return kb.as_markup() 