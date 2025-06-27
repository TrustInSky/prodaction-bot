from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List, Optional, Dict
from ...models.models import Product
from .common_kb import KeyboardBuilder, EMOJI
import logging

logger = logging.getLogger(__name__)

class CatalogKeyboard(KeyboardBuilder):
    """Клавиатуры для каталога"""
    
    @classmethod
    def get_catalog_keyboard(cls, products: List[Product], page: int = 1) -> InlineKeyboardMarkup:
        """Клавиатура каталога с товарами"""
        kb = InlineKeyboardBuilder()
        
        # Количество товаров на странице
        per_page = 5
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        
        # Добавляем кнопки товаров
        for product in products[start_idx:end_idx]:
            kb.row(cls.create_button(
                text=cls.format_product_info(product),
                callback_data=f"product:{product.id}"
            ))
        
        # Кнопки пагинации и корзина в одном ряду
        nav_row = []
        if page > 1:
            nav_row.append(cls.create_button(
                text=EMOJI["back"],
                callback_data=f"catalog:page:{page-1}"
            ))
        nav_row.append(cls.create_button(
            text=f"{EMOJI['cart']} Корзина",
            callback_data="menu:cart"
        ))
        if end_idx < len(products):
            nav_row.append(cls.create_button(
                text=EMOJI["next"],
                callback_data=f"catalog:page:{page+1}"
            ))
        kb.row(*nav_row)
        
        # Кнопка главного меню
        kb.row(cls.create_button(
            text=f"{EMOJI['home']} Главное меню",
            callback_data="menu:main"
        ))
        
        return kb.as_markup()
    
    @classmethod
    def get_product_keyboard(
        cls,
        product: Product,
        prev_product: Optional[Product] = None,
        next_product: Optional[Product] = None
    ) -> InlineKeyboardMarkup:
        """Клавиатура для карточки товара"""
        kb = InlineKeyboardBuilder()
        
        # Кнопки навигации между товарами
        nav_row = []
        if prev_product:
            nav_row.append(cls.create_button(
                text=EMOJI["back"],
                callback_data=f"product:{prev_product.id}"
            ))
        if next_product:
            nav_row.append(cls.create_button(
                text=EMOJI["next"],
                callback_data=f"product:{next_product.id}"
            ))
        if nav_row:
            kb.row(*nav_row)
        
        # Кнопка добавления в корзину
        kb.row(cls.create_button(
            text=f"{EMOJI['cart']} Добавить в корзину",
            callback_data=f"product:{'size' if product.is_clothing() else 'quantity'}:{product.id}"
        ))
        
        # Кнопки навигации по меню
        kb.row(
            cls.create_button(
                text=f"{EMOJI['cart']} Корзина",
                callback_data="menu:cart"
            ),
            cls.create_button(
                text=f"{EMOJI['catalog']} Каталог",
                callback_data="menu:catalog"
            )
        )
        
        return kb.as_markup()
    
    @classmethod
    def get_size_selection_keyboard(
        cls,
        product: Product,
        prev_product: Optional[Product] = None,
        next_product: Optional[Product] = None
    ) -> InlineKeyboardMarkup:
        """Клавиатура выбора размера"""
        kb = InlineKeyboardBuilder()
        
        # Добавляем кнопки размеров
        sizes = product.sizes_dict
        if sizes:
            # Сортируем размеры
            sorted_sizes = sorted(sizes.items(), key=lambda x: (
                len(x[0]),  # Сначала по длине (XS, S, M, L, XL)
                x[0]  # Потом по алфавиту
            ))
            
            # Группируем по 3 размера в ряд
            current_row = []
            for size, quantity in sorted_sizes:
                if quantity > 0:  # Показываем только доступные размеры
                    button = cls.create_button(
                        text=f"{size} ({quantity} шт.)",
                        callback_data=f"product:quantity:{product.id}:{size}"
                    )
                    current_row.append(button)
                    
                    if len(current_row) == 3:
                        kb.row(*current_row)
                        current_row = []
                        
            if current_row:  # Добавляем оставшиеся размеры
                kb.row(*current_row)
        
        # Кнопка возврата
        kb.row(cls.create_button(
            text=f"{EMOJI['back']} Назад к товару",
            callback_data=f"product:{product.id}"
        ))
        
        return kb.as_markup()
    
    @classmethod
    def get_quantity_selection_keyboard(
        cls,
        product_id: int,
        current_quantity: int,
        available_quantity: int,
        size: Optional[str] = None
    ) -> InlineKeyboardMarkup:
        """Клавиатура выбора количества"""
        kb = InlineKeyboardBuilder()
        
        # Кнопки изменения количества
        quantity_row = []
        if current_quantity > 1:
            quantity_row.append(cls.create_button(
                text=EMOJI["minus"],
                callback_data=f"product:adjust_quantity:{product_id}:{size or 'none'}:{current_quantity - 1}"
            ))
        quantity_row.append(cls.create_button(
            text=f"{current_quantity} шт.",
            callback_data="ignore"
        ))
        if current_quantity < available_quantity:
            quantity_row.append(cls.create_button(
                text=EMOJI["plus"],
                callback_data=f"product:adjust_quantity:{product_id}:{size or 'none'}:{current_quantity + 1}"
            ))
        kb.row(*quantity_row)
        
        # Кнопка подтверждения
        kb.row(cls.create_button(
            text=f"{EMOJI['confirm']} Добавить в корзину",
            callback_data=f"cart:add:{product_id}:{current_quantity}:{size or 'none'}"
        ))
        
        # Кнопка возврата
        kb.row(cls.create_button(
            text=f"{EMOJI['back']} Назад",
            callback_data=f"product:{product_id}"
        ))
        
        return kb.as_markup()
    
    @classmethod
    def get_success_add_to_cart_keyboard(cls, product_id: int) -> InlineKeyboardMarkup:
        """Клавиатура после успешного добавления в корзину"""
        kb = InlineKeyboardBuilder()
        
        # Кнопки действий
        kb.row(
            cls.create_button(
                text=f"{EMOJI['cart']} Перейти в корзину",
                callback_data="menu:cart"
            ),
            cls.create_button(
                text=f"{EMOJI['catalog']} Продолжить покупки",
                callback_data="menu:catalog"
            )
        )
        
        return kb.as_markup()
        
    @classmethod
    def create_size_rows(cls, product: Product, current_size: Optional[str] = None, prefix: str = "product") -> List[List[InlineKeyboardButton]]:
        """Создать ряды кнопок с размерами"""
        sizes = product.sizes_dict
        if not sizes:
            return []
            
        # Сортируем размеры
        sorted_sizes = sorted(sizes.items(), key=lambda x: (
            len(x[0]),  # Сначала по длине (XS, S, M, L, XL)
            x[0]  # Потом по алфавиту
        ))
        
        # Группируем по 3 размера в ряд
        rows = []
        current_row = []
        
        for size, quantity in sorted_sizes:
            if quantity > 0:  # Показываем только доступные размеры
                button = cls.create_button(
                    text=f"{size} ({quantity})" if size == current_size else size,
                    callback_data=f"{prefix}:set_size:{product.id}:{current_size or 'none'}:{size}"
                )
                current_row.append(button)
                
                if len(current_row) == 3:
                    rows.append(current_row)
                    current_row = []
                    
        if current_row:  # Добавляем оставшиеся размеры
            rows.append(current_row)
            
        return rows 