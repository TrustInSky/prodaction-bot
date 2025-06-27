from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


class AdminKeyboard:
    """Клавиатуры для админ-панели"""
    
    @staticmethod
    def get_admin_settings_menu() -> InlineKeyboardMarkup:
        """Главное меню настроек админа"""
        kb = InlineKeyboardBuilder()
        
        kb.row(InlineKeyboardButton(text="🔔 Персональные уведомления", callback_data="admin:personal"))
        kb.row(InlineKeyboardButton(text="🎂 Настройки дней рождения", callback_data="admin:birthday"))
        kb.row(InlineKeyboardButton(text="🏆 Настройки годовщин", callback_data="admin:anniversary"))
        kb.row(InlineKeyboardButton(text="📦 Настройки остатков", callback_data="admin:stock_low"))
        kb.row(InlineKeyboardButton(text="↩️ В главное меню", callback_data="menu:main"))
        
        return kb.as_markup()
    
    @staticmethod
    def get_event_settings_menu(event_type: str, is_enabled: bool = True) -> InlineKeyboardMarkup:
        """Меню настроек конкретного события"""
        kb = InlineKeyboardBuilder()
        
        # Кнопка включения/выключения
        toggle_text = "❌ Выключить" if is_enabled else "✅ Включить"
        kb.row(InlineKeyboardButton(
            text=toggle_text, 
            callback_data=f"admin:toggle:{event_type}"
        ))
        
        # Кнопки редактирования настроек
        kb.row(InlineKeyboardButton(
            text="📅 Дни уведомлений", 
            callback_data=f"admin:edit:{event_type}:days"
        ))
        kb.row(InlineKeyboardButton(
            text="⏰ Время отправки", 
            callback_data=f"admin:edit:{event_type}:time"
        ))
        
        # Специфичные настройки для каждого типа
        if event_type in ["birthday", "anniversary"]:
            kb.row(InlineKeyboardButton(
                text="💎 T-Points", 
                callback_data=f"admin:edit:{event_type}:points"
            ))
        elif event_type == "stock_low":
            kb.row(InlineKeyboardButton(
                text="📊 Порог остатков", 
                callback_data=f"admin:edit:{event_type}:threshold"
            ))
        
        # Тестовое уведомление
        kb.row(InlineKeyboardButton(
            text="🔔 Тестовое уведомление", 
            callback_data=f"admin:test:{event_type}"
        ))
        
        # Назад
        kb.row(InlineKeyboardButton(
            text="↩️ Назад к настройкам", 
            callback_data="admin:menu"
        ))
        
        return kb.as_markup()
    
    @staticmethod
    def get_personal_settings_menu(preferences) -> InlineKeyboardMarkup:
        """Меню персональных настроек админа"""
        kb = InlineKeyboardBuilder()
        
        # Статусы для кнопок
        birthday_text = "✅ Дни рождения" if preferences.birthday_enabled else "❌ Дни рождения"
        anniversary_text = "✅ Юбилеи" if preferences.anniversary_enabled else "❌ Юбилеи"
        stock_text = "✅ Остатки" if preferences.stock_low_enabled else "❌ Остатки"
        
        kb.row(InlineKeyboardButton(
            text=birthday_text, 
            callback_data="personal:toggle:birthday"
        ))
        kb.row(InlineKeyboardButton(
            text=anniversary_text, 
            callback_data="personal:toggle:anniversary"
        ))
        kb.row(InlineKeyboardButton(
            text=stock_text, 
            callback_data="personal:toggle:stock_low"
        ))
        
        kb.row(InlineKeyboardButton(
            text="↩️ Назад к настройкам", 
            callback_data="admin:menu"
        ))
        
        return kb.as_markup()
    
    @staticmethod
    def get_edit_cancel_keyboard() -> InlineKeyboardMarkup:
        """Кнопка отмены редактирования настроек"""
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="❌ Отмена", callback_data="admin:cancel"))
        return kb.as_markup()
    
    @staticmethod
    def get_notification_settings_menu(
        birthday_enabled: bool = True,
        anniversary_enabled: bool = True,
        stock_enabled: bool = True
    ) -> InlineKeyboardMarkup:
        """Меню настроек уведомлений"""
        kb = InlineKeyboardBuilder()
        
        # Статусы для эмодзи
        birthday_status = "✅" if birthday_enabled else "❌"
        anniversary_status = "✅" if anniversary_enabled else "❌"
        stock_status = "✅" if stock_enabled else "❌"
        
        kb.row(InlineKeyboardButton(
            text=f"{birthday_status} Дни рождения", 
            callback_data="notifications:toggle:birthday"
        ))
        kb.row(InlineKeyboardButton(
            text=f"{anniversary_status} Юбилеи работы", 
            callback_data="notifications:toggle:anniversary"
        ))
        kb.row(InlineKeyboardButton(
            text=f"{stock_status} Остатки товаров", 
            callback_data="notifications:toggle:stock"
        ))
        kb.row(InlineKeyboardButton(
            text="↩️ Назад к настройкам", 
            callback_data="admin:menu"
        ))
        
        return kb.as_markup()
    
    @staticmethod
    def get_confirm_settings(event_type: str) -> InlineKeyboardMarkup:
        """Подтверждение изменения настроек"""
        kb = InlineKeyboardBuilder()
        
        kb.row(InlineKeyboardButton(
            text="✅ Сохранить", 
            callback_data=f"settings:save:{event_type}"
        ))
        kb.row(InlineKeyboardButton(
            text="❌ Отмена", 
            callback_data=f"settings:cancel:{event_type}"
        ))
        
        return kb.as_markup() 