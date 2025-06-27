from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
import logging

from ..services.order import OrderService
from ..services.user import UserService
from ..services.notifications.order_notifications import OrderNotificationService
from ..repositories.status_repository import StatusRepository
from ..services.status_service import StatusService
from .keyboards.order_keyboards import (
    get_orders_menu_keyboard,
    get_orders_list_keyboard,
    get_order_details_keyboard
)
from ..utils.message_editor import update_message
from ..utils.callback_helpers import safe_callback_answer
from .utils import (
    format_order_details_message
)
from ..middlewares.access_control import HROrAdminAccess


management_router = Router()
logger = logging.getLogger(__name__)

# Регистрируем middleware для проверки доступа
management_router.callback_query.middleware(HROrAdminAccess())

@management_router.callback_query(F.data == "menu:orders")
async def show_orders_menu(callback: CallbackQuery):
    """Показывает главное меню раздела заказов - рефакторинг: aiogram3-di"""
    try:
        await safe_callback_answer(callback)
    except TelegramBadRequest as e:
        if "query is too old" in str(e):
            # Если callback устарел, просто показываем меню без ответа на callback
            logger.warning("Callback query is too old, proceeding without answering")
        else:
            # Если другая ошибка - логируем и возвращаемся
            logger.error(f"Error answering callback: {e}")
            return
    
    await update_message(
        callback,
        text="📦 <b>Управление заказами</b>\n\n"
             "Выберите раздел для работы с заказами:",
        reply_markup=get_orders_menu_keyboard()
    )

@management_router.callback_query(F.data.startswith("orders_status_"))
async def show_orders_by_status(callback: CallbackQuery, order_service: OrderService):
    """Показывает список заказов с определенным статусом - рефакторинг: aiogram3-di"""
    await safe_callback_answer(callback)
    
    status = callback.data.split("_")[2]
    await _show_orders_list_by_status(callback, status, order_service)

@management_router.callback_query(F.data.startswith("view_order_"))
async def view_order_details(
    callback: CallbackQuery, 
    order_service: OrderService,
    user_service: UserService,
    status_service: StatusService
):
    """Показывает детали конкретного заказа - рефакторинг: aiogram3-di"""
    await safe_callback_answer(callback)
    
    # Извлекаем ID заказа и статус списка из callback_data
    parts = callback.data.split("_")
    try:
        order_id = int(parts[2])
        status_list = parts[3] if len(parts) > 3 else "all"
    except (IndexError, ValueError):
        await safe_callback_answer(callback, "❌ Неверный формат данных")
        return
    
    # Получаем полную информацию о заказе
    order_details = await order_service.get_order_details(order_id)
    
    if not order_details:
        await safe_callback_answer(callback, "❌ Заказ не найден")
        return
    
    order = order_details['order']
    items = order_details['items']
    user = order.user  # user доступен через связь в модели Order
    
    # Получаем информацию о HR-пользователе, если заказ обрабатывается
    hr_user = None
    if order.hr_user_id:
        hr_user = await user_service.get_user_by_telegram_id(order.hr_user_id)
    
    # Получаем статус из БД
    status_obj = await status_service.get_status_by_code(order.status)
    status_display = status_obj.display_name if status_obj else order.status
    status_comment = status_obj.comment_hr if status_obj else None
    
    # Формируем сообщение с деталями заказа
    message_text = format_order_details_message(order, user, items, hr_user, status_display, status_comment)
    
    # Отправляем сообщение с деталями заказа и кнопками для управления
    await update_message(
        callback,
        text=message_text,
        reply_markup=get_order_details_keyboard(order_id, order.status, status_list)
    )

@management_router.callback_query(F.data.startswith("update_status_"))
async def update_order_status(callback: CallbackQuery, order_service: OrderService):
    """Обновляет статус заказа - рефакторинг: aiogram3-di"""
    await safe_callback_answer(callback)
    
    # Извлекаем данные из callback_data
    # ИСПРАВЛЕНО: Правильный парсинг для ready_for_pickup
    # Формат: update_status_{order_id}_{status}_{status_list}
    parts = callback.data.split("_")
    try:
        order_id = int(parts[2])
        
        # Обрабатываем составные статусы типа ready_for_pickup
        if len(parts) >= 6 and parts[3] == "ready" and parts[4] == "for" and parts[5] == "pickup":
            status = "ready_for_pickup"
            status_list = parts[6] if len(parts) > 6 else "all"
        else:
            status = parts[3]
            status_list = parts[4] if len(parts) > 4 else "all"
    except (IndexError, ValueError):
        await safe_callback_answer(callback, "❌ Неверный формат данных")
        return
    
    # Получаем информацию о заказе ДО обновления для проверки существования
    order = await order_service.order_repo.get_order_with_details(order_id)
    if not order:
        await safe_callback_answer(callback, "❌ Заказ не найден")
        return
    
    # Валидация статуса
    valid_statuses = ['new', 'processing', 'ready_for_pickup', 'delivered', 'cancelled']
    if status not in valid_statuses:
        await safe_callback_answer(callback, f"❌ Неверный статус: {status}")
        return
    
    success = await order_service.update_order_status(
        order_id=order_id,
        new_status=status,
        hr_user_id=callback.from_user.id
    )
    
    if success:
        # Создаем сообщение об успехе
        status_messages = {
            'processing': '✅ Заказ взят в работу!',
            'ready_for_pickup': '📦 Заказ готов к выдаче!',
            'delivered': '✅ Заказ помечен как выданный!',
            'cancelled': '❌ Заказ отменён!'
        }
        success_message = status_messages.get(status, '✅ Статус заказа обновлен!')
        
        await safe_callback_answer(callback, success_message)
        
        # Если заказ взят в работу, перенаправляем в соответствующий раздел
        if status == 'processing':
            # Перенаправляем к заказу в разделе "В работе"
            await _refresh_order_details(callback, order_id, "processing", order_service)
        else:
            # Возвращаемся к деталям заказа с обновленным статусом
            await _refresh_order_details(callback, order_id, status_list, order_service)
    else:
        await safe_callback_answer(callback, "❌ Произошла ошибка при обновлении статуса заказа.")

@management_router.callback_query(F.data == "back_to_orders_menu")
async def go_back_to_orders_menu(callback: CallbackQuery):
    """Возвращает пользователя в главное меню заказов - рефакторинг: aiogram3-di"""
    await safe_callback_answer(callback)
    
    await update_message(
        callback,
        text="📦 <b>Управление заказами</b>\n\n"
             "Выберите раздел для работы с заказами:",
        reply_markup=get_orders_menu_keyboard()
    )

@management_router.callback_query(F.data.startswith("back_to_orders_list_"))
async def go_back_to_orders_list(callback: CallbackQuery, order_service: OrderService):
    """Возвращает пользователя к списку заказов определенного статуса - рефакторинг: aiogram3-di"""
    await safe_callback_answer(callback)
    
    # Извлекаем статус из callback_data
    try:
        status = callback.data.split("_")[4]
    except IndexError:
        await safe_callback_answer(callback, "❌ Неверный формат данных")
        return
    
    await _show_orders_list_by_status(callback, status, order_service)

# Обработчик menu:my_orders перенесен в main_router.py для доступа всем пользователям

# Вспомогательные функции

async def _show_orders_list_by_status(callback: CallbackQuery, status: str, order_service: OrderService):
    """Вспомогательная функция для отображения списка заказов по статусу"""
    from ..orders.constants import normalize_admin_status
    
    # Нормализуем статус для совместимости с кнопками
    normalized_status = normalize_admin_status(status)
    
    # Создаем заголовки статусов
    status_titles = {
        'new': 'Новые заказы',
        'processing': 'Заказы в работе',
        'ready_for_pickup': 'Готовы к выдаче',
        'delivered': 'Выполненные заказы',
        'cancelled': 'Отмененные заказы',
        'all': 'Все заказы'
    }
    status_title = status_titles.get(normalized_status, 'Заказы')
    
    # Получаем заказы через сервис
    if normalized_status == "all":
        orders = await order_service.get_all_orders()
    else:
        orders = await order_service.get_orders_by_status(normalized_status)
    
    if not orders:
        await update_message(
            callback,
            text=f"📭 <b>{status_title}</b>\n\n"
                 f"В данном разделе нет заказов.",
            reply_markup=get_orders_menu_keyboard()
        )
        return
    
    # Показываем список заказов
    await update_message(
        callback,
        text=f"<b>{status_title}</b>\n\n"
             f"Найдено заказов: {len(orders)}",
        reply_markup=get_orders_list_keyboard(orders, status)
    )

async def _refresh_order_details(
    callback: CallbackQuery, 
    order_id: int, 
    status_list: str, 
    order_service: OrderService
):
    """Обновляет детали заказа после изменения статуса"""
    try:
        # Получаем обновленную информацию о заказе
        order = await order_service.order_repo.get_order_with_details(order_id)
        
        if not order:
            await safe_callback_answer(callback, "❌ Заказ не найден")
            return
        
        user = order.user
        items = order.items
        
        # Получаем информацию о HR-пользователе, если заказ обрабатывается
        hr_user = None
        if order.hr_user_id:
            # Используем тот же order_service для получения пользователя
            # (можно было бы инжектить user_service, но для простоты используем существующий)
            pass  # hr_user останется None, но это не критично
        
        # Формируем сообщение с деталями заказа
        message_text = format_order_details_message(order, user, items, hr_user)
        
        # Отправляем обновленное сообщение
        await update_message(
            callback,
            text=message_text,
            reply_markup=get_order_details_keyboard(order_id, order.status, status_list)
        )
        
    except Exception as e:
        logger.error(f"Error refreshing order details: {e}")
        await safe_callback_answer(callback, "❌ Ошибка при обновлении информации о заказе")