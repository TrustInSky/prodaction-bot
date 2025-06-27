from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List, Optional
from ...models.models import CartItem, Product
from .common_kb import KeyboardBuilder, EMOJI
import logging

logger = logging.getLogger(__name__)

class CartKeyboard(KeyboardBuilder):
    """Клавиатуры для корзины с исправлениями форматов callback_data"""
    
    @classmethod
    def get_cart_keyboard(cls, cart_items: List[CartItem]) -> InlineKeyboardMarkup:
        """Клавиатура корзины"""
        kb = InlineKeyboardBuilder()
        
        # Кнопки товаров
        for item in cart_items:
            if not item.product:
                continue
                
            kb.row(cls.create_button(
                text=cls.format_product_info(
                    product=item.product,
                    size=item.size,
                    quantity=item.quantity,
                    include_stock=False
                ),
                callback_data=f"cart_item_{item.id}"  # УПРОЩЕНО: используем ID самого элемента корзины
            ))
        
        # Кнопки действий с корзиной
        if cart_items:
            kb.row(
                cls.create_button(
                    text=f"{EMOJI['clear']} Очистить",
                    callback_data="cart:clear"
                ),
                cls.create_button(
                    text=f"{EMOJI['confirm']} Оформить",
                    callback_data="cart:start_checkout"
                )
            )
        
        # Навигационные кнопки
        kb.row(*cls.create_nav_row(include_cart=False))
        
        return kb.as_markup()
    
    @classmethod
    def get_empty_cart_keyboard(cls) -> InlineKeyboardMarkup:
        """Клавиатура для пустой корзины"""
        kb = InlineKeyboardBuilder()
        kb.row(*cls.create_nav_row(include_cart=False))
        return kb.as_markup()
    
    @classmethod
    def get_cart_item_keyboard(cls, item: CartItem) -> InlineKeyboardMarkup:
        """Клавиатура для отдельного товара в корзине"""
        kb = InlineKeyboardBuilder()
        
        if not item.product:
            logger.error(f"CartItem {item.id} has no product")
            return cls.get_empty_cart_keyboard()
        
        # Определяем доступное количество
        available_quantity = cls._get_available_quantity(item)
        
        # Если это одежда, показываем кнопку выбора размера
        if item.product.is_clothing():
            kb.row(cls.create_button(
                text=f"{EMOJI['size']} Выбрать размер",
                callback_data=f"cart_size_{item.id}"  # УПРОЩЕНО
            ))
        
        # Кнопки изменения количества - ИСПРАВЛЕНО
        quantity_buttons = cls.create_quantity_row(item)
        if quantity_buttons:
            kb.row(*quantity_buttons)
        
        # Кнопка удаления
        kb.row(cls.create_button(
            text=f"{EMOJI['delete']} Удалить из корзины",
            callback_data=f"cart_remove_{item.id}"  # УПРОЩЕНО
        ))
        
        # Навигационные кнопки
        kb.row(*cls.create_nav_row(
            {"text": f"{EMOJI['back']} К корзине", "callback_data": "menu:cart"},
            include_cart=False
        ))
        
        return kb.as_markup()
    
    @classmethod
    def get_cart_size_keyboard(cls, item: CartItem) -> InlineKeyboardMarkup:
        """Клавиатура выбора размера в корзине"""
        kb = InlineKeyboardBuilder()
        
        if not item.product or not item.product.is_clothing():
            logger.error(f"Invalid product for size selection: {item}")
            return cls.get_cart_item_keyboard(item)
        
        # Получаем размеры безопасно
        sizes_dict = getattr(item.product, 'sizes_dict', {}) or {}
        
        # Добавляем ряды с размерами
        sizes = [(size, qty) for size, qty in sizes_dict.items() if qty > 0 or size == item.size]
        
        if not sizes:
            logger.warning(f"No sizes available for product {item.product_id}")
            return cls.get_cart_item_keyboard(item)
        
        # Сортируем размеры
        sorted_sizes = sorted(sizes, key=lambda x: (
            len(x[0]),  # Сначала по длине (XS, S, M, L, XL)
            x[0]  # Потом по алфавиту
        ))
        
        # Группируем по 3 размера в ряд
        current_row = []
        for size, quantity in sorted_sizes:
            text = size
            if size == item.size:
                text = f"{EMOJI['confirm']}{text}"
            if quantity > 0:
                text += f" ({quantity})"
            
            # ИСПРАВЛЕНО: короткий callback с ID элемента и размером
            button = cls.create_button(
                text=text,
                callback_data=f"cart_setsize_{item.id}_{cls._encode_size(size)}"
            )
            current_row.append(button)
            
            if len(current_row) == 3:
                kb.row(*current_row)
                current_row = []
            
        if current_row:  # Добавляем оставшиеся размеры
            kb.row(*current_row)
        
        # Кнопка возврата
        kb.row(cls.create_button(
            text=f"{EMOJI['back']} Назад",
            callback_data=f"cart_item_{item.id}"
        ))
        
        return kb.as_markup()
    
    @classmethod
    def get_checkout_confirmation_keyboard(cls, total_price: float) -> InlineKeyboardMarkup:
        """Клавиатура подтверждения заказа"""
        kb = InlineKeyboardBuilder()
        
        kb.row(
            cls.create_button(
                text=f"{EMOJI['confirm']} Подтвердить ({total_price} T-points)",
                callback_data="cart:checkout"
            )
        )
        kb.row(
            cls.create_button(
                text=f"{EMOJI['back']} Отмена",
                callback_data="cart:cancel_checkout"
            )
        )
        
        return kb.as_markup()
    
    @classmethod
    def get_order_success_keyboard(cls) -> InlineKeyboardMarkup:
        """Клавиатура после успешного оформления заказа"""
        kb = InlineKeyboardBuilder()
        
        # Кнопка возврата в главное меню
        kb.row(cls.create_button(
            text=f"{EMOJI['home']} Главное меню",
            callback_data="menu:main"
        ))
        
        # Кнопка просмотра заказов
        kb.row(cls.create_button(
            text=f"{EMOJI['orders']} Мои заказы",
            callback_data="menu:my_orders"
        ))
        
        return kb.as_markup()
    
    @classmethod
    def _encode_size(cls, size: Optional[str]) -> str:
        """Безопасно кодируем размер для callback_data"""
        if size is None:
            return "none"
        # Заменяем проблемные символы и ограничиваем длину
        encoded = size.replace(":", "_").replace(" ", "_").replace("/", "_")[:10]
        return encoded
    
    @classmethod
    def _decode_size(cls, encoded_size: str) -> Optional[str]:
        """Декодируем размер из callback_data"""
        if encoded_size == "none" or not encoded_size:
            return None
        # Восстанавливаем символы (простое восстановление)
        return encoded_size.replace("_", " ")
    
    @classmethod
    def _get_available_quantity(cls, item: CartItem) -> int:
        """Безопасно получаем доступное количество товара"""
        if not item.product:
            return 0
            
        try:
            if item.product.is_clothing():
                sizes_dict = getattr(item.product, 'sizes_dict', {}) or {}
                return sizes_dict.get(item.size, 0)
            else:
                return getattr(item.product, 'total_stock', 0) or 0
        except Exception as e:
            logger.error(f"Error getting available quantity for item {item.id}: {e}")
            return 0
    
    @classmethod
    def create_quantity_row(cls, item: CartItem):
        """Создать ряд кнопок для изменения количества (ИСПРАВЛЕННЫЙ)"""
        if not item.product:
            return []
            
        buttons = []
        available_quantity = cls._get_available_quantity(item)
        
        # Кнопка уменьшения
        if item.quantity > 1:
            buttons.append(cls.create_button(
                text=f"{EMOJI['minus']}",
                callback_data=f"cart_minus_{item.id}"  # УПРОЩЕНО: только ID элемента
            ))
        
        # Текущее количество
        buttons.append(cls.create_button(
            text=f"{item.quantity} шт.",
            callback_data="noop"
        ))
        
        # Кнопка увеличения
        if item.quantity < available_quantity:
            buttons.append(cls.create_button(
                text=f"{EMOJI['plus']}",
                callback_data=f"cart_plus_{item.id}"  # УПРОЩЕНО: только ID элемента
            ))
        
        return buttons