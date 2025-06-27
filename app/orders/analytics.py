from aiogram import Router, F
from aiogram.types import CallbackQuery
import logging

from ..services.order import OrderService
from ..services.user import UserService
from .keyboards.order_keyboards import (
    get_order_analytics_keyboard,
    get_analytics_details_keyboard
)
from ..utils.message_editor import update_message
from ..utils.callback_helpers import safe_callback_answer
from .utils import check_hr_access

analytics_router = Router()
logger = logging.getLogger(__name__)

@analytics_router.callback_query(F.data == "orders_analytics")
async def show_analytics_menu(callback: CallbackQuery, order_service: OrderService, user_service: UserService):
    """Показывает меню аналитики по заказам - рефакторинг: aiogram3-di"""
    await safe_callback_answer(callback)
    
    if not await check_hr_access(user_service, callback.from_user.id):
        await safe_callback_answer(callback, "❌ У вас нет доступа к этой функции", show_alert=True)
        return
    
    await update_message(
        callback,
        text="📊 <b>Аналитика заказов</b>\n\n"
             "Выберите раздел аналитики:",
        reply_markup=get_order_analytics_keyboard()
    )

@analytics_router.callback_query(F.data.startswith("analytics_"))
async def show_analytics_details(callback: CallbackQuery, order_service: OrderService, user_service: UserService):
    """Показывает детальную аналитику по выбранной категории - рефакторинг: aiogram3-di"""
    await safe_callback_answer(callback)
    
    if not await check_hr_access(user_service, callback.from_user.id):
        await safe_callback_answer(callback, "❌ У вас нет доступа к этой функции", show_alert=True)
        return
    
    try:
        analytics_type = callback.data.split("_")[1]
    except IndexError:
        await safe_callback_answer(callback, "❌ Неверный формат данных")
        return
    
    analytics_handlers = {
        "departments": _show_departments_analytics,
        "top_products": _show_top_products_analytics,
        "top_ambassadors": _show_top_ambassadors_analytics,
        "general": _show_general_analytics
    }
    
    handler = analytics_handlers.get(analytics_type)
    if handler:
        await handler(callback, order_service, analytics_type)
    else:
        await safe_callback_answer(callback, "❌ Неизвестный тип аналитики")

@analytics_router.callback_query(F.data == "back_to_analytics")
async def go_back_to_analytics(callback: CallbackQuery, user_service: UserService):
    """Возвращает пользователя к меню аналитики - рефакторинг: aiogram3-di"""
    await safe_callback_answer(callback)
    
    if not await check_hr_access(user_service, callback.from_user.id):
        await safe_callback_answer(callback, "❌ У вас нет доступа к этой функции", show_alert=True)
        return
    
    await update_message(
        callback,
        text="📊 <b>Аналитика заказов</b>\n\n"
             "Выберите раздел аналитики:",
        reply_markup=get_order_analytics_keyboard()
    )

async def _show_departments_analytics(callback: CallbackQuery, order_service: OrderService, analytics_type: str):
    """Показывает аналитику по отделам"""
    try:
        departments_data = await order_service.get_analytics_by_departments()
        
        if not departments_data:
            message_text = "📊 <b>Аналитика по отделам</b>\n\nНет данных для отображения."
        else:
            message_text = "📊 <b>Аналитика по отделам</b>\n\n"
            
            total_orders = sum(count for _, count, _ in departments_data)
            total_points = sum(total or 0 for _, _, total in departments_data)
            
            message_text += f"<b>Общие показатели:</b>\n"
            message_text += f"📋 Всего заказов: {total_orders}\n"
            message_text += f"💰 Общая сумма: {total_points:,} T-Points\n\n"
            message_text += f"<b>По отделам:</b>\n"
            
            for i, (dept, count, total) in enumerate(departments_data, 1):
                dept_name = dept or "Не указан"
                percentage = (count / total_orders * 100) if total_orders > 0 else 0
                message_text += (
                    f"{i}. <b>{dept_name}</b>\n"
                    f"   📦 Заказов: {count} ({percentage:.1f}%)\n"
                    f"   💰 Сумма: {total or 0:,} T-Points\n\n"
                )
        
        await update_message(
            callback,
            text=message_text,
            reply_markup=get_analytics_details_keyboard(analytics_type)
        )
    except Exception as e:
        logger.error(f"Ошибка получения аналитики по отделам: {e}")
        await safe_callback_answer(callback, "❌ Произошла ошибка при получении данных")

async def _show_top_products_analytics(callback: CallbackQuery, order_service: OrderService, analytics_type: str):
    """Показывает топ товаров"""
    try:
        products_data = await order_service.get_top_products()
        
        if not products_data:
            message_text = "📊 <b>Топ товаров</b>\n\nНет данных для отображения."
        else:
            message_text = "📊 <b>Топ товаров</b>\n\n"
            
            total_quantity = sum(quantity for _, quantity, _ in products_data)
            total_revenue = sum(revenue or 0 for _, _, revenue in products_data)
            
            message_text += f"<b>Общие показатели:</b>\n"
            message_text += f"📦 Всего продано: {total_quantity} шт.\n"
            message_text += f"💰 Общая выручка: {total_revenue:,} T-Points\n\n"
            message_text += f"<b>Топ товаров:</b>\n"
            
            for i, (name, quantity, revenue) in enumerate(products_data, 1):
                percentage = (quantity / total_quantity * 100) if total_quantity > 0 else 0
                avg_price = (revenue / quantity) if quantity > 0 else 0
                
                message_text += (
                    f"{i}. <b>{name}</b>\n"
                    f"   📦 Продано: {quantity} шт. ({percentage:.1f}%)\n"
                    f"   💰 Выручка: {revenue or 0:,} T-Points\n"
                    f"   💵 Средняя цена: {avg_price:.0f} T-Points\n\n"
                )
        
        await update_message(
            callback,
            text=message_text,
            reply_markup=get_analytics_details_keyboard(analytics_type)
        )
    except Exception as e:
        logger.error(f"Ошибка получения топ товаров: {e}")
        await safe_callback_answer(callback, "❌ Произошла ошибка при получении данных")

async def _show_top_ambassadors_analytics(callback: CallbackQuery, order_service: OrderService, analytics_type: str):
    """Показывает топ амбассадоров мерча"""
    try:
        ambassadors_data = await order_service.get_top_ambassadors()
        
        if not ambassadors_data:
            message_text = "📊 <b>Топ-5 амбассадоров мерча</b>\n\nНет данных для отображения."
        else:
            message_text = "📊 <b>Топ-5 амбассадоров мерча</b>\n\n"
            
            total_orders = sum(count for _, _, count, _ in ambassadors_data)
            total_points = sum(total or 0 for _, _, _, total in ambassadors_data)
            
            message_text += f"<b>Общие показатели:</b>\n"
            message_text += f"📋 Всего заказов: {total_orders}\n"
            message_text += f"💰 Общая сумма: {total_points:,} T-Points\n\n"
            message_text += f"<b>Топ амбассадоров:</b>\n"
            
            for i, (name, username, count, total) in enumerate(ambassadors_data, 1):
                username_text = f"(@{username})" if username else "(без username)"
                percentage = (count / total_orders * 100) if total_orders > 0 else 0
                avg_order = (total / count) if count > 0 else 0
                
                trophy = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"{i}."
                
                message_text += (
                    f"{trophy} <b>{name}</b> {username_text}\n"
                    f"   📦 Заказов: {count} ({percentage:.1f}%)\n"
                    f"   💰 Потрачено: {total or 0:,} T-Points\n"
                    f"   💵 Средний заказ: {avg_order:.0f} T-Points\n\n"
                )
        
        await update_message(
            callback,
            text=message_text,
            reply_markup=get_analytics_details_keyboard(analytics_type)
        )
    except Exception as e:
        logger.error(f"Ошибка получения топ амбассадоров: {e}")
        await safe_callback_answer(callback, "❌ Произошла ошибка при получении данных")

async def _show_general_analytics(callback: CallbackQuery, order_service: OrderService, analytics_type: str):
    """Показывает общую статистику заказов"""
    try:
        general_stats = await order_service.get_general_statistics()
        
        total_orders = sum(general_stats.get(status, 0) for status in 
                          ["pending", "processing", "ready_for_pickup", "delivered", "cancelled"])
        
        delivered_orders = general_stats.get('delivered', 0)
        cancelled_orders = general_stats.get('cancelled', 0)
        active_orders = total_orders - delivered_orders - cancelled_orders
        
        success_rate = (delivered_orders / total_orders * 100) if total_orders > 0 else 0
        cancel_rate = (cancelled_orders / total_orders * 100) if total_orders > 0 else 0
        
        message_text = "📊 <b>Общая статистика заказов</b>\n\n"
            
        message_text += f"<b>Общие показатели:</b>\n"
        message_text += f"📋 Всего заказов: {total_orders}\n"
        message_text += f"✅ Выполнено: {delivered_orders} ({success_rate:.1f}%)\n"
        message_text += f"❌ Отменено: {cancelled_orders} ({cancel_rate:.1f}%)\n"
        message_text += f"⏳ В работе: {active_orders}\n\n"
        
        message_text += f"<b>По статусам:</b>\n"
        status_names = {
            'pending': '📋 Ожидают',
            'processing': '⚡ В работе',
            'ready_for_pickup': '📦 Готовы к выдаче',
            'delivered': '✅ Выполнены',
            'cancelled': '❌ Отменены'
        }
        
        for status, name in status_names.items():
            count = general_stats.get(status, 0)
            percentage = (count / total_orders * 100) if total_orders > 0 else 0
            message_text += f"{name}: {count} ({percentage:.1f}%)\n"
        
        await update_message(
            callback,
            text=message_text,
            reply_markup=get_analytics_details_keyboard(analytics_type)
        )
    except Exception as e:
        logger.error(f"Ошибка получения общей статистики: {e}")
        await safe_callback_answer(callback, "❌ Произошла ошибка при получении данных")