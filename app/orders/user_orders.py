from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import logging
from datetime import datetime
import math

from ..services.order import OrderService
from ..repositories.status_repository import StatusRepository
from ..services.status_service import StatusService
from ..utils.message_editor import update_message
from ..utils.callback_helpers import safe_callback_answer
from .keyboards.user_order_keyboards import (
    get_user_orders_keyboard,
    get_order_detail_keyboard,
    get_order_cancel_confirmation_keyboard
)


logger = logging.getLogger(__name__)

user_orders_router = Router(name="user_orders")

# Импорт константы пагинации
from .constants import ORDERS_PER_PAGE

async def _send_hr_cancellation_notification(order, user_id, reason="Отменено пользователем"):
    """Отправляет уведомление HR об отмене заказа пользователем - ОПТИМИЗИРОВАНО: универсальный метод"""
    try:
        from ..middlewares.database import add_pending_notification
        
        # Добавляем уведомление в очередь для отправки после коммита
        notification_data = {
            'order_id': order.id,
            'user_id': user_id,
            'reason': reason
        }
        
        add_pending_notification('order_cancelled_by_user', notification_data)
        logger.info(f"Queued HR cancellation notification for order {order.id} with reason: {reason}")
        
    except Exception as e:
        logger.error(f"Error queuing HR cancellation notification for order {order.id}: {e}")
        raise

@user_orders_router.callback_query(F.data == 'menu:my_orders')
async def show_my_orders(callback: CallbackQuery, order_service: OrderService, status_service: StatusService):
    """Показывает заказы пользователя с пагинацией"""
    try:
        user_id = callback.from_user.id
        orders = await order_service.get_user_orders(user_id)
        
        await _show_orders_page(callback, orders, page=1, status_service=status_service)
        
    except Exception as e:
        logger.error(f'Error in show_my_orders: {e}')
        await safe_callback_answer(callback, '❌ Произошла ошибка при загрузке заказов', show_alert=True)

@user_orders_router.callback_query(F.data.startswith('user_orders_page:'))
async def show_orders_page(callback: CallbackQuery, order_service: OrderService, status_service: StatusService):
    """Показывает определённую страницу заказов"""
    try:
        page = int(callback.data.split(':')[1])
        user_id = callback.from_user.id
        orders = await order_service.get_user_orders(user_id)
        
        await _show_orders_page(callback, orders, page, status_service=status_service)
        
    except ValueError:
        await safe_callback_answer(callback, '❌ Неверный номер страницы', show_alert=True)
    except Exception as e:
        logger.error(f'Error in show_orders_page: {e}')
        await safe_callback_answer(callback, '❌ Произошла ошибка при загрузке заказов', show_alert=True)

async def _show_orders_page(callback: CallbackQuery, orders: list, page: int, status_service: StatusService):
    """Внутренняя функция для отображения страницы заказов"""
    total_orders = len(orders)
    total_pages = math.ceil(total_orders / ORDERS_PER_PAGE) if total_orders > 0 else 1
    
    # Проверяем валидность страницы
    if page < 1:
        page = 1
    elif page > total_pages and total_orders > 0:
        page = total_pages
    
    if not orders:
        text = (
            '📦 <b>Мои заказы</b>\n\n'
            'У вас пока нет заказов.\n\n'
            'Вы можете сделать заказ в каталоге товаров.'
        )
    else:
        text = f'📦 <b>Мои заказы</b> (Страница {page} из {total_pages})\n\n'
        
        # Вычисляем индексы для текущей страницы
        start_idx = (page - 1) * ORDERS_PER_PAGE
        end_idx = min(start_idx + ORDERS_PER_PAGE, total_orders)
        page_orders = orders[start_idx:end_idx]
        
        # Получаем статусы из БД для страницы заказов
        status_codes = list(set(order.status for order in page_orders))
        statuses = await status_service.get_statuses_by_codes(status_codes)
        status_map = {s.code: s for s in statuses}
        
        # Добавляем эмодзи к заказам для клавиатуры
        for order in page_orders:
            status_obj = status_map.get(order.status)
            if status_obj:
                order.status_emoji = status_obj.emoji
        
        for i, order in enumerate(page_orders, start=start_idx + 1):
            status_obj = status_map.get(order.status)
            status_display = status_obj.display_name if status_obj else order.status
            
            text += (
                f'<b>{i}. Заказ #{order.id}</b>\n'
                f'📊 Статус: {status_display}\n'
                f'💎 Сумма: {order.total_cost:,} T-Points\n'
                f'📅 Дата: {order.created_at.strftime("%d.%m.%Y %H:%M")}\n\n'
            )
    
    keyboard = get_user_orders_keyboard(orders, page, total_pages)
    await update_message(callback, text=text, reply_markup=keyboard)
    await safe_callback_answer(callback)

@user_orders_router.callback_query(F.data.startswith('user_order_view:'))
async def view_order_detail(callback: CallbackQuery, order_service: OrderService, status_service: StatusService):
    """Показывает детали заказа с возможностью отмены"""
    try:
        order_id = int(callback.data.split(':')[1])
        user_id = callback.from_user.id
        
        # Получаем заказ с деталями
        order = await order_service.get_order_by_id(order_id)
        
        if not order:
            await safe_callback_answer(callback, '❌ Заказ не найден', show_alert=True)
            return
        
        # Проверяем, что заказ принадлежит пользователю
        if order.user_id != user_id:
            await safe_callback_answer(callback, '❌ Доступ запрещён', show_alert=True)
            return
        
        # Получаем статус из БД
        status_obj = await status_service.get_status_by_code(order.status)
        status_display = status_obj.display_name if status_obj else order.status
        
        # Формируем текст с деталями заказа
        text = (
            f'📦 <b>Заказ #{order.id}</b>\n\n'
            f'📊 <b>Статус:</b> {status_display}\n'
            f'📅 <b>Дата создания:</b> {order.created_at.strftime("%d.%m.%Y %H:%M")}\n'
            f'💎 <b>Общая сумма:</b> {order.total_cost:,} T-Points\n\n'
            f'<b>Товары в заказе:</b>\n'
        )
        
        # Добавляем информацию о товарах
        for item in order.items:
            text += (
                f'• <b>{item.product.name}</b>\n'
                f'  Количество: {item.quantity} шт.\n'
                f'  Цена: {item.price:,} T-Points за шт.\n'
            )
            if item.size:
                text += f'  Размер: {item.size}\n'
            text += '\n'
        
        # Добавляем комментарий о статусе из БД
        if status_obj and status_obj.comment_user:
            text += f'<i>{status_obj.comment_user}</i>'
        
        keyboard = get_order_detail_keyboard(order)
        await update_message(callback, text=text, reply_markup=keyboard)
        await safe_callback_answer(callback)
        
    except ValueError:
        await safe_callback_answer(callback, '❌ Неверный ID заказа', show_alert=True)
    except Exception as e:
        logger.error(f'Error in view_order_detail: {e}')
        await safe_callback_answer(callback, '❌ Произошла ошибка при загрузке заказа', show_alert=True)

@user_orders_router.callback_query(F.data.startswith('user_order_cancel:'))
async def cancel_order_confirmation(callback: CallbackQuery, order_service: OrderService):
    """Показывает подтверждение отмены заказа"""
    try:
        order_id = int(callback.data.split(':')[1])
        user_id = callback.from_user.id
        
        # Получаем заказ
        order = await order_service.get_order_by_id(order_id)
        
        if not order:
            await safe_callback_answer(callback, '❌ Заказ не найден', show_alert=True)
            return
        
        # Проверяем, что заказ принадлежит пользователю
        if order.user_id != user_id:
            await safe_callback_answer(callback, '❌ Доступ запрещён', show_alert=True)
            return
        
        # Проверяем, можно ли отменить заказ
        if order.status in ['delivered', 'cancelled']:
            await safe_callback_answer(callback, '❌ Этот заказ нельзя отменить', show_alert=True)
            return
        
        text = (
            f'❓ <b>Отмена заказа #{order.id}</b>\n\n'
            f'Вы действительно хотите отменить заказ?\n\n'
            f'💎 <b>Сумма к возврату:</b> {order.total_cost:,} T-Points\n\n'
            f'<i>T-Points будут возвращены на ваш баланс,\n'
            f'а товары вернутся на склад.</i>'
        )
        
        keyboard = get_order_cancel_confirmation_keyboard(order_id)
        await update_message(callback, text=text, reply_markup=keyboard)
        await safe_callback_answer(callback)
        
    except ValueError:
        await safe_callback_answer(callback, '❌ Неверный ID заказа', show_alert=True)
    except Exception as e:
        logger.error(f'Error in cancel_order_confirmation: {e}')
        await safe_callback_answer(callback, '❌ Произошла ошибка', show_alert=True)

@user_orders_router.callback_query(F.data.startswith('user_order_cancel_confirm:'))
async def cancel_order_confirm(callback: CallbackQuery, order_service: OrderService):
    """Подтверждение отмены заказа пользователем БЕЗ запроса причины"""
    try:
        order_id = int(callback.data.split(':')[1])
        user_id = callback.from_user.id
        
        # Получаем заказ для проверки
        order = await order_service.get_order_by_id(order_id)
        if not order:
            await safe_callback_answer(callback, '❌ Заказ не найден', show_alert=True)
            return
        
        # Проверяем, что заказ принадлежит пользователю
        if order.user_id != user_id:
            await safe_callback_answer(callback, '❌ Доступ запрещён', show_alert=True)
            return
        
        # Проверяем, можно ли отменить заказ
        if order.status in ['delivered', 'cancelled']:
            await safe_callback_answer(callback, '❌ Этот заказ нельзя отменить', show_alert=True)
            return
        
        # Отменяем заказ
        success = await order_service.cancel_order(order_id, user_id)
        
        if success:
            # Формируем причину с данными пользователя для HR
            username = callback.from_user.username
            first_name = callback.from_user.first_name or ""
            user_display = f"@{username}" if username else f"{first_name} (ID: {user_id})"
            cancel_reason = f"Отменил пользователь {user_display}"
            
            # Отправляем уведомление HR
            await _send_hr_cancellation_notification(order, user_id, cancel_reason)
            
            await update_message(
                callback,
                text=(
                    f'✅ <b>Заказ #{order_id} отменён</b>\n\n'
                    f'💰 T-Points возвращены на ваш баланс\n'
                    f'📦 Товары вернулись на склад\n\n'
                    f'Спасибо за использование нашего сервиса!'
                ),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text='📦 Мои заказы', callback_data='menu:my_orders')],
                    [InlineKeyboardButton(text='🏠 Главное меню', callback_data='menu:main')]
                ])
            )
            
            await safe_callback_answer(callback, "✅ Заказ отменён")
            logger.info(f'User {user_id} ({user_display}) cancelled order {order_id}')
        else:
            await safe_callback_answer(callback, '❌ Произошла ошибка при отмене заказа', show_alert=True)
            logger.error(f'Failed to cancel order {order_id} for user {user_id}')
            
    except ValueError:
        await safe_callback_answer(callback, '❌ Неверный ID заказа', show_alert=True)
    except Exception as e:
        logger.error(f'Error in cancel_order_confirm: {e}')
        await safe_callback_answer(callback, '❌ Произошла ошибка при отмене заказа', show_alert=True)

@user_orders_router.callback_query(F.data == 'noop')
async def handle_noop(callback: CallbackQuery):
    """Обработчик для неактивных кнопок (номер страницы)"""
    await safe_callback_answer(callback)

__all__ = ["user_orders_router"] 