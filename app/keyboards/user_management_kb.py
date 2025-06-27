from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


class UserManagementKeyboard:
    """Клавиатуры для управления пользователями"""
    
    @staticmethod
    def get_users_management_menu() -> InlineKeyboardMarkup:
        """Главное меню управления сотрудниками"""
        kb = InlineKeyboardBuilder()
        
        kb.row(InlineKeyboardButton(text="📤 Экспорт сотрудников", callback_data="users:export"))
        kb.row(InlineKeyboardButton(text="📥 Импорт сотрудников", callback_data="users:import"))
        kb.row(InlineKeyboardButton(text="💎 Управление T-Points", callback_data="menu:tpoints"))
        kb.row(InlineKeyboardButton(text="↩️ В главное меню", callback_data="menu:main"))
        
        return kb.as_markup()
    
    @staticmethod
    def get_tpoints_management_menu() -> InlineKeyboardMarkup:
        """Главное меню управления T-Points"""
        kb = InlineKeyboardBuilder()
        
        kb.row(InlineKeyboardButton(text="📋 Шаблон T-Points", callback_data="tpoints:template"))
        kb.row(InlineKeyboardButton(text="📥 Импорт T-Points", callback_data="tpoints:import"))
        kb.row(InlineKeyboardButton(text="📊 Журнал операций", callback_data="tpoints:journal"))
        kb.row(InlineKeyboardButton(text="👥 Управление сотрудниками", callback_data="menu:users"))
        kb.row(InlineKeyboardButton(text="↩️ В главное меню", callback_data="menu:main"))
        
        return kb.as_markup()
    
    @staticmethod
    def get_users_export_menu() -> InlineKeyboardMarkup:
        """Меню после экспорта сотрудников"""
        kb = InlineKeyboardBuilder()
        
        kb.row(InlineKeyboardButton(text="📥 Импорт сотрудников", callback_data="users:import"))
        kb.row(InlineKeyboardButton(text="💎 Управление T-Points", callback_data="menu:tpoints"))
        kb.row(InlineKeyboardButton(text="↩️ В главное меню", callback_data="menu:main"))
        
        return kb.as_markup()
    
    @staticmethod
    def get_tpoints_export_menu() -> InlineKeyboardMarkup:
        """Меню после экспорта шаблона T-Points"""
        kb = InlineKeyboardBuilder()
        
        kb.row(InlineKeyboardButton(text="📥 Импорт T-Points", callback_data="tpoints:import"))
        kb.row(InlineKeyboardButton(text="📊 Журнал операций", callback_data="tpoints:journal"))
        kb.row(InlineKeyboardButton(text="👥 Управление сотрудниками", callback_data="menu:users"))
        kb.row(InlineKeyboardButton(text="↩️ В главное меню", callback_data="menu:main"))
        
        return kb.as_markup()
    
    @staticmethod
    def get_users_import_cancel() -> InlineKeyboardMarkup:
        """Кнопка отмены импорта сотрудников"""
        kb = InlineKeyboardBuilder()
        
        kb.row(InlineKeyboardButton(text="❌ Отмена", callback_data="menu:users"))
        
        return kb.as_markup()
    
    @staticmethod
    def get_tpoints_import_cancel() -> InlineKeyboardMarkup:
        """Кнопка отмены импорта T-Points"""
        kb = InlineKeyboardBuilder()
        
        kb.row(InlineKeyboardButton(text="❌ Отмена", callback_data="menu:tpoints"))
        
        return kb.as_markup()
    
    @staticmethod
    def get_tpoints_confirm_operations(file_id: str) -> InlineKeyboardMarkup:
        """Подтверждение T-Points операций"""
        kb = InlineKeyboardBuilder()
        
        kb.row(InlineKeyboardButton(text="✅ Применить операции", callback_data=f"tpoints:confirm:{file_id}"))
        kb.row(InlineKeyboardButton(text="❌ Отмена", callback_data=f"tpoints:cancel:{file_id}"))
        
        return kb.as_markup()
    
    @staticmethod
    def get_users_confirm_import(file_id: str) -> InlineKeyboardMarkup:
        """Подтверждение импорта пользователей"""
        kb = InlineKeyboardBuilder()
        
        kb.row(InlineKeyboardButton(text="✅ Применить изменения", callback_data=f"users:confirm:{file_id}"))
        kb.row(InlineKeyboardButton(text="❌ Отмена", callback_data=f"users:cancel:{file_id}"))
        
        return kb.as_markup()
    
    @staticmethod
    def get_tpoints_journal_menu() -> InlineKeyboardMarkup:
        """Меню журнала T-Points операций"""
        kb = InlineKeyboardBuilder()
        
        kb.row(InlineKeyboardButton(text="📊 Журнал за 30 дней", callback_data="tpoints:journal"))
        kb.row(InlineKeyboardButton(text="📋 Шаблон T-Points", callback_data="tpoints:template"))
        kb.row(InlineKeyboardButton(text="📥 Импорт T-Points", callback_data="tpoints:import"))
        kb.row(InlineKeyboardButton(text="↩️ Управление T-Points", callback_data="menu:tpoints"))
        
        return kb.as_markup()
    
    @staticmethod
    def get_back_to_main() -> InlineKeyboardMarkup:
        """Кнопка возврата в главное меню"""
        kb = InlineKeyboardBuilder()
        
        kb.row(InlineKeyboardButton(text="↩️ В главное меню", callback_data="menu:main"))
        
        return kb.as_markup() 