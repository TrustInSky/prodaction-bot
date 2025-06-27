from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Tuple, Optional
from ...models.models import Order
from ..constants import (
    normalize_admin_status
)
import logging

def get_orders_menu_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура главного меню заказов"""
    keyboard = [
        [
            InlineKeyboardButton(text="📋 Новые заказы", callback_data="orders_status_new"),
            InlineKeyboardButton(text="⚡ В работе", callback_data="orders_status_processing")
        ],
        [
            InlineKeyboardButton(text="📦 Готовы к выдаче", callback_data="orders_status_ready"),
            InlineKeyboardButton(text="✅ Выполненные", callback_data="orders_status_completed")
        ],
        [
            InlineKeyboardButton(text="❌ Отмененные", callback_data="orders_status_cancelled"),
            InlineKeyboardButton(text="📊 Все заказы", callback_data="orders_status_all")
        ],
        [
            InlineKeyboardButton(text="📈 Аналитика", callback_data="orders_analytics"),
            InlineKeyboardButton(text="🔙 В меню", callback_data="menu:main")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_orders_list_keyboard(orders: List[Order], status: str) -> InlineKeyboardMarkup:
    """Клавиатура со списком заказов"""
    keyboard = []
    
    # Группируем по 2 кнопки в ряд
    for i in range(0, len(orders), 2):
        row = []
        for order in orders[i:i+2]:
            row.append(InlineKeyboardButton(
                text=f"#{order.id} ({order.total_cost} T-Points)",
                callback_data=f"view_order_{order.id}_{status}"
            ))
        keyboard.append(row)
    
    # Добавляем кнопку возврата
    keyboard.append([InlineKeyboardButton(
        text="🔙 Назад",
        callback_data="back_to_orders_menu"
    )])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_order_details_keyboard(order_id: int, status: str, status_list: str) -> InlineKeyboardMarkup:
    """Клавиатура для управления заказом"""
    keyboard = []
    
    # Нормализуем статус для правильного сравнения
    normalized_status = normalize_admin_status(status)
    
    # Логирование для отладки
    logger = logging.getLogger(__name__)
    logger.info(f"Order {order_id}: original_status='{status}', normalized_status='{normalized_status}'")
    
    # Кнопки действий в зависимости от статуса
    if normalized_status == 'new':
        logger.info(f"Order {order_id}: Adding 'Взять в работу' button")
        keyboard.append([
            InlineKeyboardButton(
                text="✅ Взять в работу",
                callback_data=f"update_status_{order_id}_processing_{status_list}"
            ),
            InlineKeyboardButton(
                text="❌ Отменить",
                callback_data=f"update_status_{order_id}_cancelled_{status_list}"
            )
        ])
    elif normalized_status == 'processing':
        logger.info(f"Order {order_id}: Adding 'Готов к выдаче' button")
        keyboard.append([
            InlineKeyboardButton(
                text="📦 Готов к выдаче",
                callback_data=f"update_status_{order_id}_ready_for_pickup_{status_list}"
            ),
            InlineKeyboardButton(
                text="❌ Отменить",
                callback_data=f"update_status_{order_id}_cancelled_{status_list}"
            )
        ])
    elif normalized_status == 'ready_for_pickup':
        logger.info(f"Order {order_id}: Adding 'Выдан' button")
        keyboard.append([
            InlineKeyboardButton(
                text="✅ Выдан",
                callback_data=f"update_status_{order_id}_delivered_{status_list}"
            ),
            InlineKeyboardButton(
                text="❌ Отменить",
                callback_data=f"update_status_{order_id}_cancelled_{status_list}"
            )
        ])
    else:
        logger.warning(f"Order {order_id}: No action buttons for status '{normalized_status}'")
    
    # Кнопка возврата к списку
    keyboard.append([InlineKeyboardButton(
        text="🔙 К списку",
        callback_data=f"back_to_orders_list_{status_list}"
    )])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_order_analytics_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура меню аналитики"""
    keyboard = [
        [
            InlineKeyboardButton(text="📊 Общая статистика", callback_data="analytics_general"),
            InlineKeyboardButton(text="👥 По отделам", callback_data="analytics_departments")
        ],
        [
            InlineKeyboardButton(text="📦 Топ товаров", callback_data="analytics_top_products"),
            InlineKeyboardButton(text="👑 Топ амбассадоров", callback_data="analytics_top_ambassadors")
        ],
        [InlineKeyboardButton(text="🔙 К заказам", callback_data="back_to_orders_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_analytics_details_keyboard(analytics_type: str) -> InlineKeyboardMarkup:
    """Клавиатура для страницы с детальной аналитикой"""
    keyboard = [[InlineKeyboardButton(text="🔙 К аналитике", callback_data="back_to_analytics")]]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_notification_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для уведомления о новом заказе"""
    keyboard = [
        [
            InlineKeyboardButton(text="✅ Принять", callback_data=f"order_accept_{order_id}"),
            InlineKeyboardButton(text="⏳ Позже", callback_data=f"order_later_{order_id}")
        ],
        [InlineKeyboardButton(text="❌ Скрыть", callback_data=f"order_dismiss_{order_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard) 