"""
Вспомогательные функции для работы с товарами.
Универсальная логика проверки доступности, валидации и форматирования.
"""
from typing import Tuple, Optional
from ...models.models import Product

def get_available_quantity(product: Product, size: Optional[str] = None) -> int:
    """
    Универсальная функция получения доступного количества товара.
    
    Args:
        product: Товар для проверки
        size: Размер (для одежды), если None - общее количество
        
    Returns:
        Доступное количество товара
    """
    if not product:
        return 0
    
    if size and product.is_clothing():
        return product.sizes_dict.get(size, 0)
    else:
        return product.quantity_as_number

def validate_product_availability(product: Product, quantity: int, size: Optional[str] = None) -> Tuple[bool, str]:
    """
    Валидирует доступность товара в нужном количестве.
    
    Args:
        product: Товар для проверки
        quantity: Запрашиваемое количество
        size: Размер (для одежды)
        
    Returns:
        Tuple[bool, str]: (успех, сообщение)
    """
    if not product:
        return False, "❌ Товар не найден"
    
    if not product.is_available:
        return False, "❌ Товар больше не доступен для заказа"
    
    if quantity <= 0:
        return False, "❌ Количество должно быть больше 0"
    
    available = get_available_quantity(product, size)
    
    if available <= 0:
        if size:
            return False, f"❌ Размер {size} не доступен"
        else:
            return False, "❌ Товар закончился"
    
    if quantity > available:
        if size:
            return False, f"❌ Недостаточно товара размера {size}. Доступно: {available}"
        else:
            return False, f"❌ Недостаточно товара. Доступно: {available}"
    
    return True, "✅ Товар доступен"

def get_product_info(product: Product, size: Optional[str] = None) -> dict:
    """
    Получает полную информацию о товаре.
    
    Args:
        product: Товар
        size: Размер (для одежды)
        
    Returns:
        Словарь с информацией о товаре
    """
    if not product:
        return {}
    
    info = {
        'id': product.id,
        'name': product.name,
        'price': product.price,
        'color': product.color,
        'description': product.description,
        'is_available': product.is_available,
        'is_clothing': product.is_clothing(),
        'size': size,
    }
    
    # Добавляем информацию о количестве
    available_stock = get_available_quantity(product, size)
    info['available_stock'] = available_stock
    info['has_stock'] = available_stock > 0
    
    if size and product.is_clothing():
        info['stock_info'] = f"размер {size}, остаток: {available_stock}"
        info['all_sizes'] = product.sizes_dict
    else:
        info['stock_info'] = f"остаток: {available_stock}"
        if product.is_clothing():
            info['all_sizes'] = product.sizes_dict
    
    return info

def format_availability_text(product: Product, size: Optional[str] = None) -> str:
    """
    Форматирует текст о доступности товара.
    
    Args:
        product: Товар
        size: Размер (для одежды)
        
    Returns:
        Текст с информацией о доступности
    """
    if not product:
        return "❌ Товар не найден"
    
    if not product.is_available:
        return "❌ <b>Товар больше не доступен для заказа</b>"
    
    available = get_available_quantity(product, size)
    
    if available <= 0:
        if size:
            return f"❌ <b>Размер {size} недоступен</b>"
        else:
            return "❌ <b>Товар закончился</b>"
    
    if size and product.is_clothing():
        return f"✅ <b>Размер {size} доступен ({available} шт.)</b>"
    else:
        return f"✅ <b>Товар доступен ({available} шт.)</b>"

def format_sizes_info(product: Product, current_size: Optional[str] = None) -> str:
    """
    Форматирует информацию о размерах товара.
    
    Args:
        product: Товар
        current_size: Текущий выбранный размер
        
    Returns:
        Текст с информацией о размерах
    """
    if not product or not product.is_clothing():
        return ""
    
    sizes_dict = product.sizes_dict
    if not sizes_dict:
        return "📏 Размеры недоступны"
    
    text = "📏 Доступные размеры:\n"
    for size, qty in sizes_dict.items():
        status = "✅" if qty > 0 else "❌"
        marker = " 👈" if size == current_size else ""
        text += f"{status} {size}: {qty} шт.{marker}\n"
    
    return text.rstrip()

def get_size_availability_summary(product: Product) -> dict:
    """
    Получает сводку по доступности размеров.
    
    Args:
        product: Товар
        
    Returns:
        Словарь с информацией о размерах
    """
    if not product or not product.is_clothing():
        return {}
    
    sizes_dict = product.sizes_dict
    if not sizes_dict:
        return {}
    
    available_sizes = [(size, qty) for size, qty in sizes_dict.items() if qty > 0]
    unavailable_sizes = [(size, qty) for size, qty in sizes_dict.items() if qty <= 0]
    
    return {
        'total_sizes': len(sizes_dict),
        'available_sizes': available_sizes,
        'unavailable_sizes': unavailable_sizes,
        'has_available': len(available_sizes) > 0,
        'all_sizes_available': len(unavailable_sizes) == 0
    } 