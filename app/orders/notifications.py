from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import logging

from ..services.order import OrderService
from ..services.user import UserService
from ..services.notifications.order_notifications import OrderNotificationService
from .keyboards.order_keyboards import get_order_details_keyboard
from ..utils.message_editor import update_message
from ..utils.callback_helpers import safe_callback_answer
from .utils import (
    check_hr_access,
    format_order_details_message
)

notifications_router = Router(name="notifications_handlers")
logger = logging.getLogger(__name__)

@notifications_router.callback_query(F.data.startswith("hr_acknowledge_cancel:"))
async def hr_acknowledge_cancellation(callback: CallbackQuery):
    """Обработчик кнопки 'Просмотрено' в уведомлении об отмене заказа"""
    try:
        order_id = int(callback.data.split(":")[1])
        
        # Просто удаляем сообщение после просмотра
        await callback.message.delete()
        await safe_callback_answer(callback, "✅ Отмечено как просмотренное")
        
        logger.info(f"HR user {callback.from_user.id} acknowledged cancellation of order {order_id}")
        
    except ValueError:
        await safe_callback_answer(callback, "❌ Неверный ID заказа", show_alert=True)
    except Exception as e:
        logger.error(f"Error in hr_acknowledge_cancellation: {e}")
        await safe_callback_answer(callback, "❌ Произошла ошибка", show_alert=True)

class CancelOrderStates(StatesGroup):
    waiting_for_reason = State()

@notifications_router.callback_query(F.data.startswith("order_accept_"))
async def process_order_accept(
    callback: CallbackQuery, 
    order_service: OrderService,
    user_service: UserService,
    notification_service: OrderNotificationService
):
    """Обработчик для кнопки 'Принять заказ' из уведомления - рефакторинг: aiogram3-di"""
    await safe_callback_answer(callback)
    
    if not await check_hr_access(user_service, callback.from_user.id):
        await safe_callback_answer(callback, "❌ У вас нет доступа к этой функции", show_alert=True)
        return
    
    try:
        order_id = int(callback.data.split("_")[2])
    except (IndexError, ValueError):
        await safe_callback_answer(callback, "❌ Неверный формат данных")
        return
    
    # ИСПРАВЛЕНО: Atomic операция для предотвращения race conditions
    try:
        # Получаем заказ с блокировкой для обновления
        order = await order_service.get_order_by_id(order_id)
        if not order:
            await safe_callback_answer(callback, "❌ Заказ не найден", show_alert=True)
            return
        
        # Проверяем, что заказ еще можно взять в работу
        if order.status != 'new':
            status_text = await order_service.get_status_display_text(order.status)
            await safe_callback_answer(
                callback, 
                f"❌ Заказ уже обрабатывается.\nТекущий статус: {status_text}", 
                show_alert=True
            )
            await _delete_notification_message(callback)
            return
    
        # Проверяем, не назначен ли уже HR
        if order.hr_user_id and order.hr_user_id != callback.from_user.id:
            hr_user = await user_service.get_user_by_telegram_id(order.hr_user_id)
            hr_name = hr_user.fullname if hr_user else "другим HR"
            await safe_callback_answer(
                callback, 
                f"❌ Заказ уже взят в работу {hr_name}", 
                show_alert=True
            )
            await _delete_notification_message(callback)
            return
        
        # Атомарно обновляем статус заказа (уведомления отправляются автоматически)
        success = await order_service.assign_order_to_hr(order_id, callback.from_user.id)
        
        if success:
            # Вместо удаления сообщения, показываем детали заказа для продолжения работы
            await _show_order_details_after_accept(callback, order_id, order_service, user_service)
            
            await safe_callback_answer(callback, f"✅ Заказ #{order_id} взят в работу!", show_alert=True)
        else:
            await safe_callback_answer(callback, "❌ Произошла ошибка при обновлении статуса заказа.")
            
    except Exception as e:
        logger.error(f"Error in process_order_accept for order {order_id}: {e}")
        await safe_callback_answer(callback, "❌ Произошла ошибка при обработке заказа")

@notifications_router.callback_query(F.data.startswith("order_later_"))
async def process_order_later(callback: CallbackQuery):
    """Обработчик для кнопки 'Просмотреть позже' из уведомления - рефакторинг: aiogram3-di"""
    await safe_callback_answer(callback)
    
    try:
        order_id = int(callback.data.split("_")[2])
    except (IndexError, ValueError):
        await safe_callback_answer(callback, "❌ Неверный формат данных")
        return
    
    await _delete_notification_message(callback)
    
    await safe_callback_answer(callback, f"📋 Заказ #{order_id} отложен. Он доступен в разделе 'Новые заказы'.", show_alert=True)

@notifications_router.callback_query(F.data.startswith("order_cancel_"))
async def process_order_cancel(
    callback: CallbackQuery, 
    state: FSMContext,
    order_service: OrderService,
    user_service: UserService
):
    """Обработчик для кнопки 'Отменить заказ' из уведомления"""
    await safe_callback_answer(callback)
    
    if not await check_hr_access(user_service, callback.from_user.id):
        await safe_callback_answer(callback, "❌ У вас нет доступа к этой функции", show_alert=True)
        return
    
    try:
        order_id = int(callback.data.split("_")[2])
    except (IndexError, ValueError):
        await safe_callback_answer(callback, "❌ Неверный формат данных")
        return
    
    # ИСПРАВЛЕНО: Проверяем заказ с atomic операцией
    try:
        order = await order_service.get_order_by_id(order_id)
        if not order:
            await safe_callback_answer(callback, "❌ Заказ не найден", show_alert=True)
            return
        
        # Проверяем, что заказ можно отменить
        if order.status in ['delivered', 'cancelled']:
            await safe_callback_answer(callback, "❌ Заказ уже нельзя отменить", show_alert=True)
            await _delete_notification_message(callback)
            return
    
        # Сохраняем ID заказа в состоянии
        await state.update_data(order_id=order_id, hr_user_id=callback.from_user.id)
        await state.set_state(CancelOrderStates.waiting_for_reason)
        
        # Обновляем сообщение с запросом причины отмены
        await update_message(
            callback,
            text=f"❌ Отмена заказа #{order_id}\n\nУкажите причину отмены заказа:",
            reply_markup=None
        )
            
    except Exception as e:
        logger.error(f"Error in process_order_cancel for order {order_id}: {e}")
        await safe_callback_answer(callback, "❌ Произошла ошибка при обработке заказа")

@notifications_router.message(CancelOrderStates.waiting_for_reason)
async def process_cancel_reason(
    message,
    state: FSMContext,
    order_service: OrderService,
    notification_service: OrderNotificationService
):
    """Обработчик ввода причины отмены заказа"""
    data = await state.get_data()
    order_id = data.get('order_id')
    hr_user_id = data.get('hr_user_id')
    cancel_reason = message.text
    
    if not order_id or not hr_user_id:
        await message.answer("❌ Ошибка: данные заказа не найдены")
        await state.clear()
        return
    
    # Получаем данные заказа ПЕРЕД отменой
    order = await order_service.order_repo.get_order_with_details(order_id)
    if not order:
        await message.answer(f"❌ Заказ #{order_id} не найден")
        await state.clear()
        return
    
    user = order.user
    items = order.items
    old_status = order.status
    
    # Отменяем заказ (уведомления пользователю отправляются автоматически)
    success = await order_service.cancel_order(order_id, hr_user_id)
    
    if success:
        # Получаем обновленный заказ
        updated_order = await order_service.get_order_by_id(order_id)
        
        # Отправляем уведомление HR об отмене заказа с причиной
        try:
            await notification_service.send_hr_order_cancellation_notification(
                order=updated_order,
                user=user,
                hr_user_id=hr_user_id,
                reason=cancel_reason
            )
        except Exception as e:
            logger.error(f"Failed to send HR cancellation notification for order {order_id}: {e}")
        
        await message.answer(
            f"✅ Заказ #{order_id} отменён\n"
            f"Причина: {cancel_reason}\n\n"
            "T-Points возвращены пользователю, товары возвращены на склад."
        )
    else:
        await message.answer(f"❌ Ошибка при отмене заказа #{order_id}")
    
    await state.clear()

@notifications_router.callback_query(F.data.startswith("order_dismiss_"))
async def process_order_dismiss(callback: CallbackQuery):
    """Обработчик для скрытия уведомления о заказе - рефакторинг: aiogram3-di"""
    await safe_callback_answer(callback)
    
    try:
        order_id = int(callback.data.split("_")[2])
    except (IndexError, ValueError):
        await safe_callback_answer(callback, "❌ Неверный формат данных")
        return
    
    await _delete_notification_message(callback)
    await safe_callback_answer(callback, f"✅ Уведомление о заказе #{order_id} скрыто")

async def _delete_notification_message(callback: CallbackQuery):
    """Удалить сообщение с уведомлением"""
    try:
        await callback.message.delete()
    except Exception as e:
        logger.error(f"Error deleting notification message: {e}")

async def _show_order_details_after_accept(
    callback: CallbackQuery, 
    order_id: int, 
    order_service: OrderService,
    user_service: UserService
):
    """
    Показывает детали заказа после принятия из уведомления
    
    Args:
        callback: Объект callback
        order_id: ID заказа
        order_service: Сервис заказов
        user_service: Сервис пользователей
    """
    try:
        # Получаем обновленную информацию о заказе
        order = await order_service.order_repo.get_order_with_details(order_id)
        
        if not order:
            await safe_callback_answer(callback, "❌ Заказ не найден")
            return
        
        user_data = order.user
        items = order.items
        
        # Получаем информацию о HR-пользователе
        hr_user = await user_service.get_user_by_telegram_id(callback.from_user.id)
        
        # Формируем сообщение с деталями заказа
        message_text = format_order_details_message(order, user_data, items, hr_user)
        
        # Обновляем сообщение с деталями заказа и кнопками для управления
        await update_message(
            callback,
            text=message_text,
            reply_markup=get_order_details_keyboard(order_id, order.status, "processing")
        )
        
    except Exception as e:
        logger.error(f"Ошибка при отображении деталей заказа после принятия: {e}")
        await safe_callback_answer(callback, "❌ Произошла ошибка при отображении деталей заказа")

async def _check_order_availability(order_id: int, order_service: OrderService) -> tuple[bool, str]:
    """Проверить доступность заказа для операций"""
    try:
        order = await order_service.get_order_by_id(order_id)
        if not order:
            return False, "Заказ не найден"
        
        if order.status == 'cancelled':
            return False, "Заказ уже отменен"
        elif order.status == 'delivered':
            return False, "Заказ уже выполнен"
        elif order.status == 'processing' and order.hr_user_id:
            return False, "Заказ уже взят в работу другим HR"
    
        return True, ""
    except Exception as e:
        logger.error(f"Error checking order availability for order {order_id}: {e}")
        return False, "Ошибка при проверке заказа"

async def _handle_order_acceptance_error(callback: CallbackQuery, error_message: str):
    """
    Обрабатывает ошибки при принятии заказа
    
    Args:
        callback: Объект callback
        error_message: Сообщение об ошибке для отображения
    """
    await safe_callback_answer(callback, f"❌ {error_message}")
    await _delete_notification_message(callback)