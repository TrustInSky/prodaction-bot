from typing import Optional
from ...models.models import Product

def format_product_card(product: Product, size: Optional[str] = None, quantity: Optional[int] = None) -> str:
    """Форматирует полную карточку товара"""
    text = f"📦 <b>{product.name}</b>\n\n"
    
    if product.color:
        text += f"🎨 Цвет: {product.color}\n"
    text += f"💰 Цена: {product.price} T-Points\n"
    
    if quantity:
        text += f"🔢 Количество: {quantity} шт.\n"
    
    if size:
        text += f"📏 Размер: {size}\n"
    
    if product.is_clothing():
        sizes = product.sizes_dict
        text += "\n📏 Доступные размеры:\n"
        for size, qty in sizes.items():
            text += f"- {size}: {qty} шт.\n"
    else:
        # Исправлено: используем total_stock вместо get_quantity()
        text += f"\n📦 В наличии: {product.total_stock} шт.\n"
    
    text += f"\n📝 Описание: {product.description}"
    return text



def format_success_add(product: Product, quantity: int, size: Optional[str] = None) -> str:
    """Форматирует сообщение об успешном добавлении в корзину"""
    text = f"✅ Товар добавлен в корзину!\n\n"
    text += f"📦 {product.name}\n"
    
    if product.color:
        text += f"🎨 Цвет: {product.color}\n"
    
    text += f"💰 Цена: {product.price} T-Points\n"
    text += f"🔢 Количество: {quantity} шт.\n"
    
    if size:
        text += f"📏 Размер: {size}\n"
    
    return text