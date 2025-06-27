"""
Обработчики оформления заказа.
Отделены от основной логики корзины для лучшей структуры кода.
"""
import logging
from decimal import Decimal
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from ..utils.message_editor import update_message
from ..utils.callback_helpers import safe_callback_answer
from app.catalog.keyboards.cart_kb import CartKeyboard
from ..services.cart import CartService
from ..services.user import UserService
from ..services.order import OrderService
from ..services.transaction_service import TransactionService
from app.services.notifications.order_notifications import OrderNotificationService
from .states import CartStates

logger = logging.getLogger(__name__)
router = Router()

@router.callback_query(F.data == "cart:start_checkout")
async def handle_start_checkout(
    callback: CallbackQuery, 
    cart_service: CartService,
    user_service: UserService,
    state: FSMContext
):
    """Начало процесса оформления заказа"""
    try:
        logger.info(f"User {callback.from_user.id} starting checkout")
        
        # Получаем корзину и пользователя
        cart = await cart_service.get_active_cart(callback.from_user.id)
        user = await user_service.get_user(callback.from_user.id)
        
        # Базовые проверки
        if not user:
            await safe_callback_answer(callback, "❌ Пользователь не найден")
            return
            
        if not cart or not cart.items:
            await safe_callback_answer(callback, "❌ Корзина пуста")
            return
        
        # Полная валидация корзины через сервис
        is_valid, validation_errors = await cart_service.validate_cart_for_checkout(callback.from_user.id)
        
        if not is_valid:
            error_text = "❌ Невозможно оформить заказ:\n\n" + "\n".join(validation_errors)
            await safe_callback_answer(callback, error_text, show_alert=True)
            return
        
        # Рассчитываем общую стоимость
        total_price = Decimal('0')
        for item in cart.items:
            if item.product:
                item_total = Decimal(str(item.quantity)) * Decimal(str(item.product.price))
                total_price += item_total
        
        # Проверяем баланс
        user_balance = Decimal(str(user.tpoints))
        if user_balance < total_price:
            await safe_callback_answer(
                callback,
                f"❌ Недостаточно T-points\nТребуется: {total_price}\nДоступно: {user_balance}",
                show_alert=True
            )
            return
        
        # Сохраняем данные в состояние
        await state.set_state(CartStates.confirming_order)
        await state.update_data(
            cart_id=cart.id,
            total_price=float(total_price)
        )
        
        # Формируем сообщение подтверждения
        text = _format_checkout_confirmation_text(cart, user_balance, total_price)
        
        await update_message(
            callback,
            text,
            reply_markup=CartKeyboard.get_checkout_confirmation_keyboard(float(total_price))
        )
        await safe_callback_answer(callback)
        
    except Exception as e:
        logger.error(f"Unexpected error starting checkout for user {callback.from_user.id}: {e}")
        await safe_callback_answer(callback, "❌ Произошла ошибка при оформлении заказа")

@router.callback_query(CartStates.confirming_order, F.data == "cart:checkout")
async def handle_checkout(
    callback: CallbackQuery, 
    cart_service: CartService,
    user_service: UserService,
    order_service: OrderService,
    transaction_service: TransactionService,
    notification_service: OrderNotificationService,
    state: FSMContext
):
    """Окончательное оформление заказа"""
    try:
        logger.info(f"User {callback.from_user.id} confirming checkout")
        
        # Получаем данные из состояния
        state_data = await state.get_data()
        cart_id = state_data.get('cart_id')
        expected_total = Decimal(str(state_data.get('total_price', 0)))
        
        if not cart_id:
            await safe_callback_answer(callback, "❌ Данные заказа не найдены")
            await state.clear()
            return
        
        # Получаем актуальные данные
        cart = await cart_service.get_cart_by_id(cart_id)
        user = await user_service.get_user(callback.from_user.id)
        
        if not cart or not user:
            await safe_callback_answer(callback, "❌ Данные не найдены")
            await state.clear()
            return

        # Повторная валидация (могло что-то измениться)
        is_valid, validation_errors = await cart_service.validate_cart_for_checkout(callback.from_user.id)
        if not is_valid:
            error_text = "❌ Заказ больше невозможен:\n\n" + "\n".join(validation_errors)
            await safe_callback_answer(callback, error_text, show_alert=True)
            await state.clear()
            return

        # Пересчитываем стоимость
        actual_total = _calculate_cart_total(cart)
        
        # Проверяем, не изменилась ли стоимость
        if abs(actual_total - expected_total) > Decimal('0.01'):
            await safe_callback_answer(
                callback,
                f"❌ Стоимость заказа изменилась\nБыло: {expected_total}\nСтало: {actual_total}\nПожалуйста, оформите заказ заново",
                show_alert=True
            )
            await state.clear()
            return
        
        # Проверяем баланс
        if user.tpoints < float(actual_total):
            await safe_callback_answer(
                callback,
                f"❌ Недостаточно T-points\nТребуется: {actual_total}\nДоступно: {user.tpoints}",
                show_alert=True
            )
            await state.clear()
            return
        
        # Оформляем заказ
        try:
            order = await order_service.create_order_from_cart(
                cart_id=cart_id,
                user_id=callback.from_user.id
            )
            
            if order:
                # Списываем T-points
                from ..core.constants import TransactionType
                transaction = await transaction_service.create_transaction(
                    user_id=callback.from_user.id,
                    amount=-float(actual_total),
                    transaction_type=TransactionType.PURCHASE,
                    description=f"Оплата заказа #{order.id}",
                    order_id=order.id
                )
                
                # Баланс обновляется автоматически при создании транзакции
                
                # Очищаем корзину (в OrderService корзина НЕ очищается)
                await cart_service.clear_cart(callback.from_user.id)
                
                # Уведомления HR уже отправлены через очередь в OrderService
                
                # Формируем сообщение об успехе
                success_text = _format_order_success_text(order, transaction)
                
                await update_message(
                    callback,
                    success_text,
                    reply_markup=CartKeyboard.get_order_success_keyboard()
                )
                
                await safe_callback_answer(callback, "✅ Заказ успешно оформлен!")
                logger.info(f"Order {order.id} created successfully for user {callback.from_user.id}")
                
            else:
                await safe_callback_answer(callback, "❌ Не удалось создать заказ")
                
        except Exception as e:
            logger.error(f"Error creating order for user {callback.from_user.id}: {e}")
            await safe_callback_answer(callback, "❌ Произошла ошибка при создании заказа")
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Unexpected error during checkout for user {callback.from_user.id}: {e}")
        await safe_callback_answer(callback, "❌ Произошла ошибка при оформлении заказа")
        await state.clear()

@router.callback_query(CartStates.confirming_order, F.data == "cart:cancel_checkout")
async def cancel_checkout(callback: CallbackQuery, state: FSMContext):
    """Отмена оформления заказа"""
    await state.clear()
    await safe_callback_answer(callback, "❌ Оформление заказа отменено")
    
    # Возвращаемся к корзине
    from .cart import show_cart_menu
    from ..repositories.cart_repository import CartService
    from ..repositories.user_repository import UserService
    
    # Здесь нужно будет получить сервисы через DI
    # Пока заглушка
    await callback.message.edit_text(
        "🛒 Оформление заказа отменено.\nВозвращайтесь к корзине через меню.",
        reply_markup=CartKeyboard.get_back_to_cart_keyboard()
    )

# Вспомогательные функции

def _calculate_cart_total(cart) -> Decimal:
    """Рассчитывает общую стоимость корзины"""
    total = Decimal('0')
    for item in cart.items:
        if item.product:
            item_total = Decimal(str(item.quantity)) * Decimal(str(item.product.price))
            total += item_total
    return total

def _format_checkout_confirmation_text(cart, user_balance: Decimal, total_price: Decimal) -> str:
    """Форматирует текст подтверждения заказа"""
    items_text = []
    for item in cart.items:
        if not item.product:
            continue
        item_text = f"• {item.product.name}"
        if item.size:
            item_text += f" (размер: {item.size})"
        item_total = item.quantity * item.product.price
        item_text += f" - {item.quantity} шт. × {item.product.price} = {item_total} T-points"
        items_text.append(item_text)
    
    remaining_balance = user_balance - total_price
    
    return (
        f"🛒 Подтверждение заказа\n\n"
        f"Товары:\n" + "\n".join(items_text) + f"\n\n"
        f"💰 Итого: {total_price} T-points\n"
        f"💳 Ваш баланс: {user_balance} T-points\n"
        f"💳 Останется: {remaining_balance} T-points\n\n"
        f"Подтвердите оформление заказа:"
    )

def _format_order_success_text(order, transaction) -> str:
    """Форматирует текст успешного заказа"""
    return (
        f"✅ <b>Заказ успешно оформлен!</b>\n\n"
        f"📋 Номер заказа: #{order.id}\n"
        f"💰 Сумма: {abs(transaction.points_amount)} T-points\n"
        f"📅 Дата: {order.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        f"🚀 Заказ передан в обработку.\n"
        f"О статусе заказа мы сообщим дополнительно."
    ) 