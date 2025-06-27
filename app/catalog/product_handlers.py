from aiogram import Router, F
from aiogram.types import CallbackQuery, InputMediaPhoto
from ..services.catalog import CatalogService
from ..services.cart import CartService
from .keyboards.catalog_kb import CatalogKeyboard
from ..utils.message_editor import update_message
from ..utils.callback_helpers import safe_callback_answer
from .utils.product_formatters import format_product_card, format_success_add
from .utils.product_helpers import (
    get_available_quantity,
    validate_product_availability,
    format_sizes_info
)
import logging
from typing import Union, Optional

logger = logging.getLogger(__name__)

router = Router(name="product_handlers")

# Словарь для хранения текущего индекса каталога для каждого пользователя
catalog_indices = {}

@router.callback_query(F.data.startswith("catalog:page:"))
async def show_catalog_page(callback: CallbackQuery, catalog_service: CatalogService):
    """Показать страницу каталога товаров (пагинация) - рефакторинг: aiogram3-di автоматически инжектит CatalogService"""
    try:
        # Извлекаем номер страницы из callback_data
        page = int(callback.data.split(":")[2])
        logger.info(f"User {callback.from_user.id} opening catalog page {page}")
        
        # Получаем товары
        products = await catalog_service.get_available_products()
        
        text = "🛍 Каталог товаров:\n\n"
        if not products:
            text += "К сожалению, сейчас нет доступных товаров."
            keyboard = CatalogKeyboard.get_catalog_keyboard([], 1)
            await update_message(callback, text=text, reply_markup=keyboard)
            return
            
        keyboard = CatalogKeyboard.get_catalog_keyboard(products, page)
        await update_message(callback, text=text, reply_markup=keyboard)
        await safe_callback_answer(callback)
            
    except Exception as e:
        logger.error(f"Error showing catalog page for user {callback.from_user.id}: {e}")
        await safe_callback_answer(callback, "❌ Произошла ошибка при переходе по страницам каталога")

@router.callback_query(F.data.startswith("product:add_to_cart:"))
async def start_add_to_cart(callback: CallbackQuery, catalog_service: CatalogService):
    """Начать процесс добавления в корзину"""
    try:
        product_id = int(callback.data.split(":")[2])
        logger.info(f"User {callback.from_user.id} starting add to cart for product {product_id}")
        
        # Получаем товар через сервис
        product = await catalog_service.get_product(product_id)
        if not product:
            await safe_callback_answer(callback, "❌ Товар не найден")
            return
        
        if not product.is_available:
            await safe_callback_answer(callback, "❌ Товар недоступен")
            return
            
        # Получаем соседние товары для навигации
        products = await catalog_service.get_available_products()
        current_index = next((i for i, p in enumerate(products) if p.id == product_id), -1)
        
        prev_product = products[current_index - 1] if current_index > 0 else None
        next_product = products[current_index + 1] if current_index < len(products) - 1 else None
            
        # Формируем описание товара
        text = format_product_card(product)
        
        # Получаем клавиатуру с кнопками подтверждения
        keyboard = CatalogKeyboard.get_product_keyboard(
            product=product,
            prev_product=prev_product,
            next_product=next_product
        )
        
        # Отправляем сообщение с фото через message_editor
        if product.image_url:
            media = InputMediaPhoto(
                media=product.image_url,
                caption=text,
                parse_mode="HTML"
            )
            await update_message(callback, text=None, media=media, reply_markup=keyboard)
        else:
            await update_message(callback, text=text, reply_markup=keyboard)
            
        await safe_callback_answer(callback)
            
    except Exception as e:
        logger.error(f"Error starting add to cart for user {callback.from_user.id}: {e}")
        await safe_callback_answer(callback, "❌ Произошла ошибка при добавлении в корзину")

@router.callback_query(F.data.startswith("product:confirm:"))
async def confirm_add_to_cart(
    callback: CallbackQuery, 
    catalog_service: CatalogService, 
    cart_service: CartService
):
    """Подтвердить добавление в корзину - рефакторинг: множественная инжекция сервисов"""
    try:
        product_id = int(callback.data.split(":")[2])
        user_id = callback.from_user.id
        
        logger.info(f"User {user_id} confirming add to cart for product {product_id}")
        
        # Получаем товар через каталог-сервис
        product = await catalog_service.get_product(product_id)
        if not product:
            await safe_callback_answer(callback, "❌ Товар не найден")
            return
        
        # Проверяем доступность товара
        if not product.is_available or product.total_stock <= 0:
            await safe_callback_answer(callback, "❌ Товар недоступен")
            return
            
        # Добавляем в корзину через карт-сервис
        cart_item = await cart_service.add_item(
            user_id=user_id,
            product_id=product_id,
            quantity=1  # По умолчанию 1 шт
        )
        
        if cart_item:
            # Успешное добавление
            text = format_success_add(product, 1)
            keyboard = CatalogKeyboard.get_success_add_to_cart_keyboard(product_id)
            await update_message(callback, text=text, reply_markup=keyboard)
            await safe_callback_answer(callback, "✅ Товар добавлен в корзину!")
        else:
            await safe_callback_answer(callback, "❌ Не удалось добавить товар в корзину")
            
    except Exception as e:
        logger.error(f"Error confirming add to cart for user {callback.from_user.id}: {e}")
        await safe_callback_answer(callback, "❌ Произошла ошибка при подтверждении")

@router.callback_query(F.data.startswith("product:size:"))
async def show_size_selection(callback: CallbackQuery, catalog_service: CatalogService):
    """Показать выбор размера для одежды"""
    try:
        product_id = int(callback.data.split(":")[2])
        
        logger.info(f"User {callback.from_user.id} selecting size for product {product_id}")
        
        product = await catalog_service.get_product(product_id)
        if not product:
            await safe_callback_answer(callback, "❌ Товар не найден")
            return
        
        if not product.is_clothing():
            await safe_callback_answer(callback, "❌ У этого товара нет размеров")
            return
            
        text = f"📏 Выберите размер для {product.name}:\n\n"
        
        # Используем универсальную функцию форматирования размеров
        text += format_sizes_info(product)
        
        # Получаем соседние товары для навигации
        products = await catalog_service.get_available_products()
        current_index = next((i for i, p in enumerate(products) if p.id == product_id), -1)
        
        prev_product = products[current_index - 1] if current_index > 0 else None
        next_product = products[current_index + 1] if current_index < len(products) - 1 else None
        
        keyboard = CatalogKeyboard.get_size_selection_keyboard(product, prev_product, next_product)
        await update_message(callback, text=text, reply_markup=keyboard)
        await safe_callback_answer(callback)
        
    except Exception as e:
        logger.error(f"Error showing size selection for user {callback.from_user.id}: {e}")
        await safe_callback_answer(callback, "❌ Произошла ошибка при выборе размера")

@router.callback_query(F.data.startswith("product:quantity:"))
async def show_quantity_selection(callback: CallbackQuery, catalog_service: CatalogService):
    """Показать выбор количества товара"""
    try:
        parts = callback.data.split(":")
        product_id = int(parts[2])
        size = parts[3] if len(parts) > 3 and parts[3] != "none" else None
        
        logger.info(f"User {callback.from_user.id} selecting quantity for product {product_id}, size: {size}")
        
        product = await catalog_service.get_product(product_id)
        if not product:
            await safe_callback_answer(callback, "❌ Товар не найден")
            return
            
        # Используем универсальную функцию проверки доступности
        available = get_available_quantity(product, size)
        
        if size and product.is_clothing():
            text = f"🔢 Выберите количество для {product.name} (размер {size}):\n"
        else:
            text = f"🔢 Выберите количество для {product.name}:\n"
            
        if available <= 0:
            await safe_callback_answer(callback, "❌ Товар недоступен")
            return
            
        text += f"\nДоступно: {available} шт."
        text += f"\nЦена за единицу: {product.price} T-Points"
        
        keyboard = CatalogKeyboard.get_quantity_selection_keyboard(
            product_id=product_id,
            current_quantity=1,
            available_quantity=available,
            size=size
        )
        
        await update_message(callback, text=text, reply_markup=keyboard)
        await safe_callback_answer(callback)
        
    except Exception as e:
        logger.error(f"Error showing quantity selection for user {callback.from_user.id}: {e}")
        await safe_callback_answer(callback, "❌ Произошла ошибка при выборе количества")

@router.callback_query(F.data.startswith("cart:add:"))
async def handle_add_to_cart(
    callback: CallbackQuery, 
    catalog_service: CatalogService, 
    cart_service: CartService
):
    """Обработать добавление товара в корзину с параметрами - рефакторинг для aiogram3-di"""
    try:
        # Парсим данные: cart:add:product_id:quantity:size
        parts = callback.data.split(":")
        product_id = int(parts[2])
        quantity = int(parts[3])
        size = parts[4] if len(parts) > 4 and parts[4] != "none" else None
        
        user_id = callback.from_user.id
        
        logger.info(f"User {user_id} adding to cart: product {product_id}, qty {quantity}, size {size}")
        
        # Получаем товар и валидируем его
        product = await catalog_service.get_product(product_id)
        if not product or not product.is_available:
            await safe_callback_answer(callback, "❌ Товар недоступен")
            return
            
        # Используем универсальную функцию валидации
        is_valid, message = validate_product_availability(product, quantity, size)
        if not is_valid:
            await safe_callback_answer(callback, message)
            return
            
        # Добавляем в корзину через сервис
        cart_item = await cart_service.add_item(
            user_id=user_id,
            product_id=product_id,
            quantity=quantity,
            size=size
        )
        
        if cart_item:
            # Формируем сообщение об успехе
            text = format_success_add(product, quantity, size)
            keyboard = CatalogKeyboard.get_success_add_to_cart_keyboard(product_id)
            await update_message(callback, text=text, reply_markup=keyboard)
            await safe_callback_answer(callback, "✅ Товар добавлен в корзину!")
        else:
            await safe_callback_answer(callback, "❌ Не удалось добавить товар в корзину")
            
    except Exception as e:
        logger.error(f"Error handling add to cart for user {callback.from_user.id}: {e}")
        await safe_callback_answer(callback, "❌ Произошла ошибка при добавлении в корзину")

@router.callback_query(F.data.startswith("product:adjust_quantity:"))
async def adjust_quantity(callback: CallbackQuery, catalog_service: CatalogService):
    """Изменить количество товара"""
    try:
        # Парсим данные: product:adjust_quantity:product_id:size:new_quantity
        parts = callback.data.split(":")
        product_id = int(parts[2])
        size = parts[3] if parts[3] != "none" else None
        new_quantity = int(parts[4])
        
        logger.info(f"User {callback.from_user.id} adjusting quantity for product {product_id}, size: {size}, new_quantity: {new_quantity}")
        
        product = await catalog_service.get_product(product_id)
        if not product:
            await safe_callback_answer(callback, "❌ Товар не найден")
            return
            
        # Используем универсальную функцию проверки доступности
        available = get_available_quantity(product, size)
        
        if size and product.is_clothing():
            text = f"🔢 Выберите количество для {product.name} (размер {size}):\n"
        else:
            text = f"🔢 Выберите количество для {product.name}:\n"
            
        if available <= 0:
            await safe_callback_answer(callback, "❌ Товар недоступен")
            return
            
        text += f"\nДоступно: {available} шт."
        text += f"\nЦена за единицу: {product.price} T-Points"
        text += f"\nОбщая стоимость: {product.price * new_quantity} T-Points"
        
        keyboard = CatalogKeyboard.get_quantity_selection_keyboard(
            product_id=product_id,
            current_quantity=new_quantity,
            available_quantity=available,
            size=size
        )
        
        await update_message(callback, text=text, reply_markup=keyboard)
        await safe_callback_answer(callback)
        
    except Exception as e:
        logger.error(f"Error adjusting quantity for user {callback.from_user.id}: {e}")
        await safe_callback_answer(callback, "❌ Произошла ошибка при изменении количества")

@router.callback_query(F.data.regexp(r"^product:\d+$"))
async def show_product(callback: CallbackQuery, catalog_service: CatalogService):
    """Показать детальную информацию о товаре"""
    try:
        product_id = int(callback.data.split(":")[1])
        
        logger.info(f"User {callback.from_user.id} viewing product {product_id}")
        
        product = await catalog_service.get_product(product_id)
        if not product:
            await safe_callback_answer(callback, "❌ Товар не найден")
            return
            
        # Получаем соседние товары для навигации
        products = await catalog_service.get_available_products()
        current_index = next((i for i, p in enumerate(products) if p.id == product_id), -1)
        
        prev_product = products[current_index - 1] if current_index > 0 else None
        next_product = products[current_index + 1] if current_index < len(products) - 1 else None
            
        # Формируем карточку товара
        text = format_product_card(product)
        
        keyboard = CatalogKeyboard.get_product_keyboard(
            product=product,
            prev_product=prev_product,
            next_product=next_product
        )
        
        # Отправляем с фото если есть
        # Используем message_editor для корректной обработки картинок
        if product.image_url:
            media = InputMediaPhoto(
                media=product.image_url,
                caption=text,
                parse_mode="HTML"
            )
            await update_message(callback, text=None, media=media, reply_markup=keyboard)
        else:
            await update_message(callback, text=text, reply_markup=keyboard)
            
        await safe_callback_answer(callback)
        
    except Exception as e:
        logger.error(f"Error showing product for user {callback.from_user.id}: {e}")
        await safe_callback_answer(callback, "❌ Произошла ошибка при просмотре товара")