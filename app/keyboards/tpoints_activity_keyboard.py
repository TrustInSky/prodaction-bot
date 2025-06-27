from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import Optional


def create_tpoints_keyboard(user_id: int, user_role: Optional[str] = None) -> InlineKeyboardMarkup:
    """
    Создаёт клавиатуру для просмотра T-Points активностей
    
    Args:
        user_id: ID пользователя
        user_role: Роль пользователя (hr, admin, user)
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопками в зависимости от роли
    """
    buttons = []
    
    # Для HR и Admin - кнопка редактирования
    if user_role in ["hr", "admin"]:
        buttons.append([
            InlineKeyboardButton(
                text="✏️ Редактировать список", 
                callback_data="edit_tpoints"
            )
        ])
    
    # Кнопка "Назад в главное меню" для всех пользователей
    buttons.append([
        InlineKeyboardButton(
            text="🏠 Главное меню", 
            callback_data="back_to_main"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def create_edit_keyboard() -> InlineKeyboardMarkup:
    """
    Создаёт клавиатуру для режима редактирования T-Points
    Показывается только для HR и Admin после начала редактирования
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопками сохранения/отмены
    """
    buttons = [
        [
            InlineKeyboardButton(
                text="💾 Сохранить изменения", 
                callback_data="save_tpoints"
            )
        ],
        [
            InlineKeyboardButton(
                text="❌ Отменить", 
                callback_data="cancel_edit"
            )
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def create_confirmation_keyboard() -> InlineKeyboardMarkup:
    """
    Создаёт клавиатуру подтверждения для важных операций
    (например, при очистке всего списка активностей)
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопками подтверждения
    """
    buttons = [
        [
            InlineKeyboardButton(
                text="✅ Да, подтвердить", 
                callback_data="confirm_action"
            ),
            InlineKeyboardButton(
                text="❌ Отменить", 
                callback_data="cancel_action"
            )
        ],
        [
            InlineKeyboardButton(
                text="🏠 Главное меню", 
                callback_data="back_to_main"
            )
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def create_admin_management_keyboard() -> InlineKeyboardMarkup:
    """
    Создаёт расширенную клавиатуру управления T-Points для админов
    (дополнительные функции управления)
    
    Returns:
        InlineKeyboardMarkup: Расширенная админская клавиатура
    """
    buttons = [
        [
            InlineKeyboardButton(
                text="✏️ Редактировать список", 
                callback_data="edit_tpoints"
            )
        ],
        [
            InlineKeyboardButton(
                text="📊 Статистика активностей", 
                callback_data="tpoints_stats"
            ),
            InlineKeyboardButton(
                text="🔄 Обновить из файла", 
                callback_data="upload_tpoints"
            )
        ],
        [
            InlineKeyboardButton(
                text="🗑️ Очистить все", 
                callback_data="clear_all_tpoints"
            )
        ],
        [
            InlineKeyboardButton(
                text="🏠 Главное меню", 
                callback_data="back_to_main"
            )
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def create_role_based_keyboard(user_id: int, user_role: Optional[str] = None, 
                              extended_admin: bool = False) -> InlineKeyboardMarkup:
    """
    Универсальная функция создания клавиатуры на основе роли пользователя
    
    Args:
        user_id: ID пользователя
        user_role: Роль пользователя
        extended_admin: Использовать расширенную админскую клавиатуру
    
    Returns:
        InlineKeyboardMarkup: Клавиатура в зависимости от роли и настроек
    """
    # Для админов с расширенными правами
    if user_role == "admin" and extended_admin:
        return create_admin_management_keyboard()
    
    # Стандартная клавиатура для HR/Admin или обычных пользователей
    return create_tpoints_keyboard(user_id, user_role) 