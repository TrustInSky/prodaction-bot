from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from ..services.user import UserService


class MainKeyboard:
    """Клавиатуры главного меню"""
    
    @staticmethod
    async def get_main_keyboard(user_service: UserService = None, user_id: int = None, role: str = "user") -> InlineKeyboardMarkup:
        """Главное меню пользователя с балансом T-Points"""
        kb = InlineKeyboardBuilder()
        
        if user_service and user_id:
            # Получаем пользователя из сервиса
            user = await user_service.get_user(user_id)
            balance = user.tpoints if user else 0
            
            # Форматируем баланс с разделителями тысяч
            formatted_balance = f"{balance:,}".replace(",", " ")
            
            # Добавляем кнопку баланса в начало
            kb.row(InlineKeyboardButton(
                text=f"💎 Баланс: {formatted_balance} T-Points",
                callback_data="menu:balance"
            ))
        
        # Общие кнопки для всех пользователей
        kb.row(InlineKeyboardButton(text="🛍 Каталог", callback_data="menu:catalog"))
        kb.row(InlineKeyboardButton(text="🛒 Корзина", callback_data="menu:cart"))
        kb.row(InlineKeyboardButton(text="📦 Мои заказы", callback_data="menu:my_orders"))
        kb.row(InlineKeyboardButton(text="✉️ Задать анонимный вопрос", callback_data="menu:ask_question"))
        kb.row(InlineKeyboardButton(text="💵 Как получить T-Points?", callback_data="menu:how_to_get_tpoints"))
             
        # Кнопки для админов и HR
        if role in ("admin", "hr"):
            kb.row(InlineKeyboardButton(text="📊 Управление магазином", callback_data="menu:catalog_management"))
            kb.row(InlineKeyboardButton(text="📋 Управление заказами", callback_data="menu:orders"))
            kb.row(InlineKeyboardButton(text="❓ Анонимные вопросы", callback_data="menu:questions"))
            kb.row(InlineKeyboardButton(text="👥 Управление сотрудниками", callback_data="menu:users"))
            kb.row(InlineKeyboardButton(text="📅 Проверка событий", callback_data="check_events"))
            
                                      
        # Дополнительные кнопки только для админов
        if role == "admin":
            kb.row(InlineKeyboardButton(text="⚙️ Настройки", callback_data="menu:settings"))
        
        return kb.as_markup()

    @staticmethod
    def get_back_to_main_menu() -> InlineKeyboardMarkup:
        """Кнопка возврата в главное меню"""
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="↩️ В главное меню", callback_data="menu:main"))
        return kb.as_markup()

    @staticmethod
    def get_onboarding_keyboard() -> InlineKeyboardMarkup:
        """Клавиатура для онбординга нового сотрудника"""
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="🏠 Перейти в главное меню", callback_data="menu:main"))
        kb.row(InlineKeyboardButton(text="🛍 Посмотреть каталог", callback_data="menu:catalog"))
        kb.row(InlineKeyboardButton(text="💵 Как зарабатывать T-Points?", callback_data="menu:how_to_get_tpoints"))
        return kb.as_markup() 