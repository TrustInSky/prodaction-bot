"""
Клавиатуры для управления событиями
"""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


class EventsKeyboard:
    """Клавиатуры для работы с событиями"""
    
    @staticmethod
    def get_events_menu() -> InlineKeyboardMarkup:
        """Главное меню проверки событий"""
        kb = InlineKeyboardBuilder()
        
        kb.row(InlineKeyboardButton(text="🎂 Дни рождения", callback_data="check_birthdays"))
        kb.row(InlineKeyboardButton(text="🏆 Годовщины работы", callback_data="check_anniversaries"))
        kb.row(InlineKeyboardButton(text="📦 Остатки товаров", callback_data="check_stock"))
        kb.row(InlineKeyboardButton(text="🔄 Все события", callback_data="check_all_events"))
        kb.row(InlineKeyboardButton(text="« В главное меню", callback_data="menu:main"))
        
        return kb.as_markup()
    
    @staticmethod
    def get_back_to_events() -> InlineKeyboardMarkup:
        """Кнопка возврата к событиям"""
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="« Назад к событиям", callback_data="check_events"))
        return kb.as_markup()
    
    @staticmethod
    def get_back_to_main() -> InlineKeyboardMarkup:
        """Кнопка возврата в главное меню"""
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="↩️ В главное меню", callback_data="menu:main"))
        return kb.as_markup() 