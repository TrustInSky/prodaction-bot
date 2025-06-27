from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List, Dict, Optional, Union, Any
from ...models.models import Product, CartItem

# Эмодзи для кнопок
EMOJI = {
    "cart": "🛒",
    "back": "↩️",
    "next": "▶️",
    "confirm": "✅",
    "catalog": "🛍",
    "home": "🏠",
    "delete": "🗑",
    "minus": "➖",
    "plus": "➕",
    "package": "📦",
    "size": "📏",
    "money": "💰",
    "order": "��",
    "clear": "🧹",
    "settings": "⚙️",
    "success": "✅",
    "cancel": "❌",
    "upload": "📤",
    "download": "📥",
    "link": "🔗",
    "orders": "📦",
    "questions": "❓",
    "users": "👥",
    "tpoints": "💎"
}

class KeyboardBuilder:
    """Базовый класс для создания клавиатур"""
    
    @staticmethod
    def create_button(text: str, callback_data: str) -> InlineKeyboardButton:
        """Создает кнопку с текстом и callback_data"""
        return InlineKeyboardButton(text=text, callback_data=callback_data)
    
    @staticmethod
    def create_nav_row(
        *buttons: Union[str, Dict[str, str]],
        include_cart: bool = True,
        include_catalog: bool = True,
        include_main: bool = True
    ) -> List[InlineKeyboardButton]:
        """Создает ряд навигационных кнопок"""
        nav_row = []
        
        # Добавляем переданные кнопки
        for button in buttons:
            if isinstance(button, str):
                nav_row.append(InlineKeyboardButton(
                    text=button,
                    callback_data="ignore"
                ))
            else:
                nav_row.append(InlineKeyboardButton(
                    text=button["text"],
                    callback_data=button["callback_data"]
                ))
        
        # Добавляем стандартные кнопки навигации
        if include_cart:
            nav_row.append(InlineKeyboardButton(
                text=f"{EMOJI['cart']} Корзина",
                callback_data="menu:cart"
            ))
        
        if include_catalog:
            nav_row.append(InlineKeyboardButton(
                text=f"{EMOJI['catalog']} Каталог",
                callback_data="menu:catalog"
            ))
        
        if include_main:
            nav_row.append(InlineKeyboardButton(
                text=f"{EMOJI['home']} Меню",
                callback_data="menu:main"
            ))
        
        return nav_row
    
    @staticmethod
    def create_quantity_row(
        entity_id: int,
        current_quantity: int,
        available_quantity: int,
        size: Optional[str] = None,
        prefix: str = "cart"
    ) -> List[InlineKeyboardButton]:
        """Создает ряд кнопок для управления количеством"""
        quantity_row = []
        
        # Кнопка уменьшения количества
        if current_quantity > 1:
            quantity_row.append(InlineKeyboardButton(
                text=EMOJI["minus"],
                callback_data=f"{prefix}:quantity:{entity_id}:minus:{size or 'none'}"
            ))
        
        # Текущее количество
        quantity_row.append(InlineKeyboardButton(
            text=f"{current_quantity} шт.",
            callback_data="ignore"
        ))
        
        # Кнопка увеличения количества
        if current_quantity < available_quantity:
            quantity_row.append(InlineKeyboardButton(
                text=EMOJI["plus"],
                callback_data=f"{prefix}:quantity:{entity_id}:plus:{size or 'none'}"
            ))
        
        return quantity_row
    
    @staticmethod
    def create_size_rows(
        product: Product,
        current_size: Optional[str] = None,
        prefix: str = "product"
    ) -> List[List[InlineKeyboardButton]]:
        """Создает ряды кнопок для выбора размера"""
        size_rows = []
        current_row = []
        
        # Получаем доступные размеры
        sizes = [(size, quantity) for size, quantity in product.sizes_dict.items() if quantity > 0 or size == current_size]
        
        # Группируем размеры по 3 в ряд
        for size, quantity in sizes:
            text = size
            if size == current_size:
                text = f"{EMOJI['confirm']}{text}"
            if quantity > 0:
                text += f" ({quantity})"
                
            current_row.append(InlineKeyboardButton(
                text=text,
                callback_data=f"{prefix}:size:{product.id}:{size}"
            ))
            
            if len(current_row) == 3:
                size_rows.append(current_row)
                current_row = []
        
        # Добавляем оставшиеся размеры
        if current_row:
            size_rows.append(current_row)
        
        return size_rows
    
    @staticmethod
    def create_action_row(*actions: Dict[str, str]) -> List[InlineKeyboardButton]:
        """Создает ряд кнопок действий"""
        return [InlineKeyboardButton(
            text=action["text"],
            callback_data=action["callback_data"]
        ) for action in actions]
    
    @staticmethod
    def format_product_info(
        product: Product,
        size: Optional[str] = None,
        quantity: Optional[int] = None,
        include_stock: bool = True
    ) -> str:
        """Форматирует информацию о товаре"""
        text = product.name
        
        if product.color:
            text += f" ({product.color})"
        
        if size:
            text += f" • {EMOJI['size']}{size}"
            
        text += f" • {EMOJI['money']}{product.price}"
        
        if quantity:
            text += f" × {quantity} = {product.price * quantity}"
            
        if include_stock:
            # Используем универсальное свойство total_stock
            text += f" {EMOJI['package']}{product.total_stock}"
        
        return text 