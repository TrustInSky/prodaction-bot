"""
Вспомогательные функции для работы с корзиной.
Выносим дублирующуюся логику из cart.py для упрощения кода.
"""
from typing import Tuple, Optional, List
from decimal import Decimal
import logging
from ...models.models import CartItem, Product
from .product_helpers import get_available_quantity

logger = logging.getLogger(__name__)

def parse_cart_item_id(callback_data: str) -> Optional[int]:
    """Безопасно парсит ID элемента корзины из callback_data"""
    try:
        return int(callback_data.split("_")[2])
    except (ValueError, IndexError) as e:
        logger.error(f"Invalid callback data: {callback_data}, error: {e}")
        return None

def check_cart_item_access(cart_item: CartItem, user_id: int) -> bool:
    """Проверяет, может ли пользователь работать с элементом корзины"""
    return (
        cart_item and 
        cart_item.product and 
        cart_item.cart.user_id == user_id
    )



def format_cart_item_info(cart_item: CartItem) -> dict:
    """Форматирует информацию об элементе корзины"""
    if not cart_item or not cart_item.product:
        return {}
    
    product = cart_item.product
    
    # Основная информация
    info = {
        'name': product.name,
        'quantity': cart_item.quantity,
        'price': product.price,
        'total': cart_item.quantity * product.price,
        'size': cart_item.size,
        'color': product.color,
    }
    
    # Информация о доступности
    available_stock = get_available_quantity(product, cart_item.size)
    info['available_stock'] = available_stock
    info['is_available'] = available_stock >= cart_item.quantity and product.is_available
    
    if cart_item.size and product.is_clothing():
        info['stock_info'] = f"(размер {cart_item.size}, остаток: {available_stock})"
    else:
        info['stock_info'] = f"(остаток: {available_stock})"
    
    return info

def format_cart_item_text(cart_item: CartItem) -> str:
    """Форматирует текст для отображения элемента корзины"""
    info = format_cart_item_info(cart_item)
    if not info:
        return "❌ Товар недоступен"
    
    # Формируем основной текст
    text = f"🛒 <b>{info['name']}</b>\n\n"
    
    if info['size']:
        text += f"📏 Размер: {info['size']}\n"
    
    if info['color']:
        text += f"🎨 Цвет: {info['color']}\n"
    
    text += f"🔢 Количество: {info['quantity']} шт.\n"
    text += f"💰 Цена за единицу: {info['price']:,} T-Points\n"
    text += f"💰 Общая стоимость: {info['total']:,} T-Points\n\n"
    
    # Информация о доступности
    text += f"📦 Остаток: {info['available_stock']} шт.\n"
    
    if not info['is_available']:
        text += f"⚠️ <b>Внимание: доступно только {info['available_stock']} шт.</b>\n"
    elif not cart_item.product.is_available:
        text += f"❌ <b>Товар больше не доступен для заказа</b>\n"
    else:
        text += f"✅ <b>Товар доступен</b>\n"
    
    return text

def calculate_cart_totals(cart_items: List[CartItem]) -> dict:
    """Рассчитывает итоги корзины"""
    total_price = 0
    has_unavailable_items = False
    item_details = []
    
    for item in cart_items:
        if not item.product:
            continue
        
        info = format_cart_item_info(item)
        if not info:
            continue
        
        item_details.append(info)
        
        if info['is_available']:
            total_price += info['total']
        else:
            has_unavailable_items = True
    
    return {
        'total_price': total_price,
        'has_unavailable_items': has_unavailable_items,
        'item_details': item_details,
        'items_count': len(item_details)
    }

def format_cart_summary_text(cart_items: List[CartItem], user_balance: int) -> str:
    """Форматирует текст корзины с итогами"""
    if not cart_items:
        return f"🛒 <b>Ваша корзина пуста</b>\n\n💎 Ваш баланс: {user_balance:,} T-Points"
    
    totals = calculate_cart_totals(cart_items)
    
    # Заголовок
    text = f"🛒 <b>Ваша корзина:</b>\n\n"
    
    # Список товаров
    for info in totals['item_details']:
        if info['is_available']:
            text += f"✅ {info['name']}"
            if info['size']:
                text += f" (размер {info['size']})"
            text += f"\n   {info['stock_info']}\n"
            text += f"   {info['quantity']} шт. × {info['price']} = {info['total']} T-Points\n"
        else:
            text += f"❌ {info['name']}"
            if info['size']:
                text += f" (размер {info['size']})"
            text += f"\n   ⚠️ Недоступно! Запрошено: {info['quantity']}, доступно: {info['available_stock']}\n"
        text += "\n"
    
    # Итоги
    text += f"💰 <b>Итого: {totals['total_price']:,} T-Points</b>\n"
    text += f"💎 Ваш баланс: {user_balance:,} T-Points\n"
    
    # Статус заказа
    if totals['total_price'] > user_balance:
        text += f"⚠️ <b>Недостаточно средств! Не хватает: {totals['total_price'] - user_balance:,} T-Points</b>\n"
    elif totals['has_unavailable_items']:
        text += f"⚠️ <b>В корзине есть недоступные товары</b>\n"
    else:
        text += f"✅ <b>Можно оформить заказ</b>\n"
    
    return text

def validate_item_quantity_change(cart_item: CartItem, new_quantity: int) -> Tuple[bool, str]:
    """Валидирует изменение количества товара в корзине"""
    if new_quantity < 1:
        return False, "❌ Количество не может быть меньше 1"
    
    available_quantity = get_available_quantity(cart_item.product, cart_item.size)
    
    if new_quantity > available_quantity:
        return False, f"❌ Недостаточно товара на складе (доступно: {available_quantity})"
    
    return True, "✅ Количество можно изменить" 