from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Optional
import math
from ...models.models import Order
from ..constants import (
    ORDERS_PER_PAGE
)

def get_user_orders_keyboard(orders: List[Order], page: int = 1, total_pages: Optional[int] = None) -> InlineKeyboardMarkup:
    """Клавиатура со списком заказов пользователя с пагинацией"""
    keyboard = []
    
    if not orders:
        # Если заказов нет
        keyboard.append([
            InlineKeyboardButton(text='🛍 Сделать заказ', callback_data='menu:catalog')
        ])
    else:
        # Вычисляем параметры пагинации
        if total_pages is None:
            total_pages = math.ceil(len(orders) / ORDERS_PER_PAGE)
        
        # Вычисляем индексы для текущей страницы
        start_idx = (page - 1) * ORDERS_PER_PAGE
        end_idx = min(start_idx + ORDERS_PER_PAGE, len(orders))
        page_orders = orders[start_idx:end_idx]
        
        # Показываем заказы инлайн кнопками (только заказы текущей страницы)
        for order in page_orders:
            # Получаем эмодзи статуса из модели заказа (будет добавлен в роутере)
            status_emoji = getattr(order, 'status_emoji', '📋')
            
            button_text = f'{status_emoji} #{order.id} - {order.total_cost:,} T-Points'
            keyboard.append([
                InlineKeyboardButton(
                    text=button_text, 
                    callback_data=f'user_order_view:{order.id}'
                )
            ])
        
        # Добавляем кнопки пагинации если больше одной страницы
        if total_pages > 1:
            pagination_row = []
            
            # Кнопка "Назад"
            if page > 1:
                pagination_row.append(
                    InlineKeyboardButton(
                        text='⬅️ Назад', 
                        callback_data=f'user_orders_page:{page - 1}'
                    )
                )
            
            # Информация о странице
            pagination_row.append(
                InlineKeyboardButton(
                    text=f'{page}/{total_pages}', 
                    callback_data='noop'
                )
            )
            
            # Кнопка "Вперёд"
            if page < total_pages:
                pagination_row.append(
                    InlineKeyboardButton(
                        text='Вперёд ➡️', 
                        callback_data=f'user_orders_page:{page + 1}'
                    )
                )
            
            keyboard.append(pagination_row)
        
        # Добавляем кнопку для нового заказа
        keyboard.append([
            InlineKeyboardButton(text='🛍 Сделать новый заказ', callback_data='menu:catalog')
        ])
    
    # Кнопка возврата в главное меню
    keyboard.append([
        InlineKeyboardButton(text='🏠 Главное меню', callback_data='menu:main')
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_order_detail_keyboard(order: Order) -> InlineKeyboardMarkup:
    """Клавиатура для детального просмотра заказа"""
    keyboard = []
    
    # Если заказ можно отменить (не выдан и не отменён)
    if order.status not in ['delivered', 'cancelled']:
        keyboard.append([
            InlineKeyboardButton(
                text='❌ Отменить заказ', 
                callback_data=f'user_order_cancel:{order.id}'
            )
        ])
    
    # Кнопки навигации
    keyboard.append([
        InlineKeyboardButton(text='🔙 К моим заказам', callback_data='menu:my_orders'),
        InlineKeyboardButton(text='🏠 Главное меню', callback_data='menu:main')
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_order_cancel_confirmation_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения отмены заказа"""
    keyboard = [
        [
            InlineKeyboardButton(
                text='✅ Да, отменить', 
                callback_data=f'user_order_cancel_confirm:{order_id}'
            ),
            InlineKeyboardButton(
                text='❌ Нет, оставить', 
                callback_data=f'user_order_view:{order_id}'
            )
        ],
        [
            InlineKeyboardButton(text='🔙 К моим заказам', callback_data='menu:my_orders')
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard) 