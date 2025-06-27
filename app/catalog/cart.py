"""
Рефакторированные обработчики корзины.
Основная логика вынесена в utils/cart_helpers.py
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery
import logging

from ..utils.message_editor import update_message
from .keyboards.cart_kb import CartKeyboard
from ..services.cart import CartService
from ..services.user import UserService
from ..utils.callback_helpers import safe_callback_answer
from .utils.cart_helpers import (
    parse_cart_item_id,
    check_cart_item_access,
    format_cart_item_text,
    format_cart_summary_text,
    validate_item_quantity_change
)

logger = logging.getLogger(__name__)
router = Router(name="cart_handlers")



# =============================================================================
# НАВИГАЦИЯ В КОРЗИНУ
# =============================================================================

@router.callback_query(F.data == "menu:cart")
async def show_cart_menu(callback: CallbackQuery, cart_service: CartService, user_service: UserService):
    """Переход в корзину из главного меню"""
    try:
        logger.info(f"User {callback.from_user.id} opened cart")
        
        # Получаем пользователя для баланса
        user = await user_service.get_user(callback.from_user.id)
        if not user:
            await safe_callback_answer(callback, "❌ Пользователь не найден")
            return
        
        # Получаем корзину с предзагрузкой items
        cart = await cart_service.get_active_cart(callback.from_user.id, refresh=True)
            
        if not cart:
            text = f"🛒 <b>Ваша корзина пуста</b>\n\n💎 Ваш баланс: {user.tpoints:,} T-Points"
            keyboard = CartKeyboard.get_empty_cart_keyboard()
        else:
            # Безопасно проверяем items в корзине
            try:
                cart_items = list(cart.items) if hasattr(cart, 'items') and cart.items else []
            except Exception:
                cart_items = []
            
            # Используем универсальную функцию форматирования
            text = format_cart_summary_text(cart_items, user.tpoints)
            
            if cart_items:
                keyboard = CartKeyboard.get_cart_keyboard(cart_items)
            else:
                keyboard = CartKeyboard.get_empty_cart_keyboard()
        
        await update_message(callback, text=text, reply_markup=keyboard)
        await safe_callback_answer(callback)
        
    except Exception as e:
        logger.error(f"Error showing cart: {e}", exc_info=True)
        await safe_callback_answer(callback, "❌ Ошибка при переходе в корзину")

# =============================================================================
# ОБРАБОТЧИКИ ТОВАРОВ В КОРЗИНЕ
# =============================================================================

@router.callback_query(F.data.startswith("cart_item_"))
async def show_cart_item(
    callback: CallbackQuery, 
    cart_service: CartService,
    user_service: UserService
):
    """Показать товар в корзине"""
    try:
        cart_item_id = parse_cart_item_id(callback.data)
        if not cart_item_id:
            await safe_callback_answer(callback, "❌ Неверный формат данных")
            return
        
        cart_item = await cart_service.get_cart_item_by_id(cart_item_id)
        if not check_cart_item_access(cart_item, callback.from_user.id):
            await safe_callback_answer(callback, "❌ Товар не найден в корзине")
            return
        
        # Получаем пользователя для баланса
        user = await user_service.get_user(callback.from_user.id)
        if not user:
            await callback.message.edit_text("❌ Пользователь не найден")
            return
        
        # Формируем текст с помощью универсальной функции
        text = format_cart_item_text(cart_item)
        text += f"\n💎 Ваш баланс: {user.tpoints:,} T-Points"
        
        keyboard = CartKeyboard.get_cart_item_keyboard(cart_item)
        await update_message(callback, text=text, reply_markup=keyboard)
        await safe_callback_answer(callback)
        
    except Exception as e:
        logger.error(f"Unexpected error showing cart item for user {callback.from_user.id}: {e}")
        await safe_callback_answer(callback, "❌ Произошла ошибка при просмотре товара")

@router.callback_query(F.data.startswith("cart_remove_"))
async def remove_item(
    callback: CallbackQuery, 
    cart_service: CartService,
    user_service: UserService
):
    """Удалить товар из корзины"""
    try:
        cart_item_id = parse_cart_item_id(callback.data)
        if not cart_item_id:
            await safe_callback_answer(callback, "❌ Неверный формат данных")
            return
        
        cart_item = await cart_service.get_cart_item_by_id(cart_item_id)
        if not check_cart_item_access(cart_item, callback.from_user.id):
            await safe_callback_answer(callback, "❌ Товар не найден в корзине")
            return
        
        # Удаляем товар
        success = await cart_service.remove_item(
            user_id=callback.from_user.id,
            product_id=cart_item.product_id,
            size=cart_item.size
        )
        
        if success:
            # Принудительно обновляем корзину - создаём новое сообщение
            await safe_callback_answer(callback, "✅ Товар удален из корзины")
            
            # Получаем актуальные данные с принудительным обновлением из БД
            user = await user_service.get_user(callback.from_user.id)
            cart = await cart_service.get_active_cart(callback.from_user.id, refresh=True)
            
            if not cart or not cart.items:
                text = f"🛒 <b>Ваша корзина пуста</b>\n\n💎 Ваш баланс: {user.tpoints:,} T-Points"
                keyboard = CartKeyboard.get_empty_cart_keyboard()
            else:
                cart_items = list(cart.items)
                text = format_cart_summary_text(cart_items, user.tpoints)
                keyboard = CartKeyboard.get_cart_keyboard(cart_items)
            
            # ПРИНУДИТЕЛЬНО обновляем интерфейс
            await update_message(callback, text=text, reply_markup=keyboard)
        else:
            await safe_callback_answer(callback, "❌ Не удалось удалить товар")
            
    except Exception as e:
        logger.error(f"Unexpected error removing cart item for user {callback.from_user.id}: {e}")
        await safe_callback_answer(callback, "❌ Произошла ошибка при удалении товара")

@router.callback_query(F.data.startswith("cart_plus_"))
async def increase_quantity(
    callback: CallbackQuery, 
    cart_service: CartService,
    user_service: UserService
):
    """Увеличить количество товара в корзине"""
    try:
        cart_item_id = parse_cart_item_id(callback.data)
        if not cart_item_id:
            await safe_callback_answer(callback, "❌ Неверный формат данных")
            return
        
        cart_item = await cart_service.get_cart_item_by_id(cart_item_id)
        if not check_cart_item_access(cart_item, callback.from_user.id):
            await safe_callback_answer(callback, "❌ Товар не найден в корзине")
            return
        
        new_quantity = cart_item.quantity + 1
        
        # Валидируем изменение через универсальную функцию
        is_valid, message = validate_item_quantity_change(cart_item, new_quantity)
        if not is_valid:
            await safe_callback_answer(callback, message)
            return
        
        # Обновляем количество
        success = await cart_service.update_cart_item_quantity(
            user_id=callback.from_user.id,
            product_id=cart_item.product_id,
            size=cart_item.size,
            quantity=new_quantity
        )
        
        if success:
            await _update_cart_item_display(callback, cart_item_id, cart_service, user_service)
            await safe_callback_answer(callback, "✅ Количество увеличено")
        else:
            await safe_callback_answer(callback, "❌ Не удалось изменить количество")
            
    except Exception as e:
        logger.error(f"Unexpected error increasing quantity for user {callback.from_user.id}: {e}")
        await safe_callback_answer(callback, "❌ Произошла ошибка при изменении количества")

@router.callback_query(F.data.startswith("cart_minus_"))
async def decrease_quantity(
    callback: CallbackQuery, 
    cart_service: CartService,
    user_service: UserService
):
    """Уменьшить количество товара в корзине"""
    try:
        cart_item_id = parse_cart_item_id(callback.data)
        if not cart_item_id:
            await safe_callback_answer(callback, "❌ Неверный формат данных")
            return
        
        cart_item = await cart_service.get_cart_item_by_id(cart_item_id)
        if not check_cart_item_access(cart_item, callback.from_user.id):
            await safe_callback_answer(callback, "❌ Товар не найден в корзине")
            return
        
        new_quantity = cart_item.quantity - 1
        
        if new_quantity <= 0:
            # Если количество становится 0, удаляем товар
            await remove_item(callback, cart_service, user_service)
            return
        
        # Валидируем изменение
        is_valid, message = validate_item_quantity_change(cart_item, new_quantity)
        if not is_valid:
            await safe_callback_answer(callback, message)
            return
        
        # Обновляем количество
        success = await cart_service.update_cart_item_quantity(
            user_id=callback.from_user.id,
            product_id=cart_item.product_id,
            size=cart_item.size,
            quantity=new_quantity
        )
        
        if success:
            await _update_cart_item_display(callback, cart_item_id, cart_service, user_service)
            await safe_callback_answer(callback, "✅ Количество уменьшено")
        else:
            await safe_callback_answer(callback, "❌ Не удалось изменить количество")
            
    except Exception as e:
        logger.error(f"Unexpected error decreasing quantity for user {callback.from_user.id}: {e}")
        await safe_callback_answer(callback, "❌ Произошла ошибка при изменении количества")

@router.callback_query(F.data.startswith("cart_size_"))
async def show_size_selection(
    callback: CallbackQuery, 
    cart_service: CartService
):
    """Показать выбор размера для товара в корзине"""
    try:
        cart_item_id = parse_cart_item_id(callback.data)
        if not cart_item_id:
            await safe_callback_answer(callback, "❌ Неверный формат данных")
            return
        
        cart_item = await cart_service.get_cart_item_by_id(cart_item_id)
        if not check_cart_item_access(cart_item, callback.from_user.id):
            await safe_callback_answer(callback, "❌ Товар не найден в корзине")
            return
        
        if not cart_item.product or not cart_item.product.is_clothing():
            await safe_callback_answer(callback, "❌ Для этого товара нельзя выбрать размер")
            return
        
        # Формируем текст
        text = f"📏 <b>Выбор размера</b>\n\n"
        text += f"🛒 Товар: {cart_item.product.name}\n"
        text += f"🔢 Количество: {cart_item.quantity} шт.\n"
        if cart_item.size:
            text += f"📏 Текущий размер: {cart_item.size}\n\n"
        else:
            text += f"📏 Размер не выбран\n\n"
        
        text += f"Выберите новый размер:"
        
        keyboard = CartKeyboard.get_cart_size_keyboard(cart_item)
        await update_message(callback, text=text, reply_markup=keyboard)
        await safe_callback_answer(callback)
        
    except Exception as e:
        logger.error(f"Unexpected error showing size selection for user {callback.from_user.id}: {e}")
        await safe_callback_answer(callback, "❌ Произошла ошибка при выборе размера")

@router.callback_query(F.data.startswith("cart_setsize_"))
async def set_cart_item_size(
    callback: CallbackQuery, 
    cart_service: CartService,
    user_service: UserService
):
    """Установить размер для товара в корзине"""
    try:
        # Парсим данные
        try:
            parts = callback.data.split("_")
            if len(parts) < 4:
                raise ValueError("Invalid callback data format")
            cart_item_id = int(parts[2])
            encoded_size = parts[3]
            new_size = CartKeyboard._decode_size(encoded_size)
        except (ValueError, IndexError) as e:
            logger.error(f"Invalid callback data: {callback.data}, error: {e}")
            await safe_callback_answer(callback, "❌ Неверный формат данных")
            return
        
        cart_item = await cart_service.get_cart_item_by_id(cart_item_id)
        if not check_cart_item_access(cart_item, callback.from_user.id):
            await safe_callback_answer(callback, "❌ Товар не найден в корзине")
            return
        
        # Проверяем, что размер не тот же самый
        if cart_item.size == new_size:
            await safe_callback_answer(callback, "✅ Размер уже выбран")
            await _update_cart_item_display(callback, cart_item_id, cart_service, user_service)
            return
        
        # Проверяем доступность нового размера
        if new_size:
            available_qty = cart_item.product.sizes_dict.get(new_size, 0)
            if available_qty < cart_item.quantity:
                await safe_callback_answer(callback, f"❌ Недостаточно товара размера {new_size} (доступно: {available_qty})")
                return
        
        # Обновляем размер
        success = await cart_service.update_cart_item_size(
            user_id=callback.from_user.id,
            product_id=cart_item.product_id,
            old_size=cart_item.size,
            new_size=new_size
        )
        
        if success:
            await _update_cart_item_display(callback, cart_item_id, cart_service, user_service)
            await safe_callback_answer(callback, f"✅ Размер изменен на {new_size}")
        else:
            await safe_callback_answer(callback, "❌ Не удалось изменить размер")
            
    except Exception as e:
        logger.error(f"Unexpected error setting cart item size for user {callback.from_user.id}: {e}")
        await safe_callback_answer(callback, "❌ Произошла ошибка при изменении размера")

@router.callback_query(F.data == "cart:clear")
async def clear_cart(
    callback: CallbackQuery, 
    cart_service: CartService,
    user_service: UserService
):
    """Очистить корзину"""
    try:
        logger.info(f"User {callback.from_user.id} clearing cart")
        
        success = await cart_service.clear_cart(callback.from_user.id)
        
        if success:
            await safe_callback_answer(callback, "✅ Корзина очищена")
            await show_cart_menu(callback, cart_service, user_service)
        else:
            await safe_callback_answer(callback, "❌ Не удалось очистить корзину")
            
    except Exception as e:
        logger.error(f"Error clearing cart for user {callback.from_user.id}: {e}")
        await safe_callback_answer(callback, "❌ Произошла ошибка при очистке корзины")

# =============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ  
# =============================================================================

async def _update_cart_item_display(
    callback: CallbackQuery, 
    cart_item_id: int,
    cart_service: CartService,
    user_service: UserService
):
    """Обновить отображение товара в корзине"""
    cart_item = await cart_service.get_cart_item_by_id(cart_item_id)
    if not cart_item or not cart_item.product:
        await show_cart_menu(callback, cart_service, user_service)
        return
    
    user = await user_service.get_user(callback.from_user.id)
    if not user:
        await callback.message.edit_text("❌ Пользователь не найден")
        return
    
    # Используем универсальную функцию форматирования
    text = format_cart_item_text(cart_item)
    text += f"\n💎 Ваш баланс: {user.tpoints:,} T-Points"
    
    keyboard = CartKeyboard.get_cart_item_keyboard(cart_item)
    await update_message(callback, text=text, reply_markup=keyboard)