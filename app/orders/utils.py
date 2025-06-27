from typing import Optional, Tuple, List, Any, Dict
from aiogram.types import CallbackQuery
from ..models.models import Order, User, OrderItem, Product
from .constants import (
    normalize_admin_status
)
from datetime import datetime


async def check_hr_access(user_service, telegram_id: int) -> bool:
    """Проверяет, имеет ли пользователь доступ к функциям HR - рефакторинг: aiogram3-di"""
    user = await user_service.get_user_by_telegram_id(telegram_id)
    if not user or user.role not in ("hr", "admin"):
        return False
    return True


def format_user_link(user: User) -> str:
    """Форматирует ссылку на пользователя"""
    return f"@{user.username}" if user.username else "без username"


def format_order_details_message(
    order: Order,
    user: User,
    items: List[OrderItem],
    hr_user: Optional[User] = None,
    status_display: Optional[str] = None,
    status_comment: Optional[str] = None
) -> str:
    """Форматирует сообщение с деталями заказа"""
    status_text = status_display or order.status
    
    message = [
        f"📦 <b>Заказ #{order.id}</b>",
        f"📅 Создан: {order.created_at.strftime('%d.%m.%Y %H:%M')}",
        f"👤 Заказчик: {user.fullname}",
        f"📱 Telegram: @{user.username}" if user.username else "",
        f"💼 Отдел: {user.department or 'Не указан'}",
        f"📊 Статус: {status_text}",
        "",
        "<b>Товары в заказе:</b>"
    ]
    
    total_cost = 0
    for item in items:
        cost = item.quantity * item.price
        total_cost += cost
        size_text = f" (размер {item.size})" if item.size else ""
        message.append(
            f"• {item.product.name}{size_text}\n"
            f"  {item.quantity} шт. x {item.price} T-Points = {cost} T-Points"
        )
    
    message.extend([
        "",
        f"💰 <b>Итого:</b> {total_cost} T-Points"
    ])
    
    if hr_user:
        message.extend([
            "",
            f"👨‍💼 <b>HR-менеджер:</b> {hr_user.fullname}"
        ])
    
    # Добавляем комментарий статуса
    if status_comment:
        message.extend([
            "",
            f"ℹ️ {status_comment}"
        ])
    
    return "\n".join(filter(None, message))


def format_analytics_departments(departments_data: List[Tuple[str, int, float]]) -> str:
    """
    Форматирует аналитику по отделам
    
    Args:
        departments_data: Список кортежей (отдел, количество заказов, сумма)
    """
    if not departments_data:
        return "📊 <b>Аналитика по отделам</b>\n\nНет данных для отображения."
    
    message_text = "📊 <b>Аналитика по отделам</b>\n\n"
    for i, (dept, count, total) in enumerate(departments_data, 1):
        dept_name = dept or "Не указан"
        message_text += f"{i}. <b>{dept_name}:</b> {count} заказов, {total or 0} T-points\n"
    
    return message_text


def format_analytics_products(products_data: List[Tuple[str, int, float]]) -> str:
    """
    Форматирует аналитику по топ товарам
    
    Args:
        products_data: Список кортежей (название товара, количество, выручка)
    """
    if not products_data:
        return "📊 <b>Топ товаров</b>\n\nНет данных для отображения."
    
    message_text = "📊 <b>Топ товаров</b>\n\n"
    for i, (name, quantity, revenue) in enumerate(products_data, 1):
        message_text += f"{i}. <b>{name}:</b> {quantity} шт., {revenue or 0} T-points\n"
    
    return message_text


def format_analytics_ambassadors(ambassadors_data: List[Tuple[str, str, int, float]]) -> str:
    """
    Форматирует аналитику по топ амбассадорам
    
    Args:
        ambassadors_data: Список кортежей (имя, username, количество заказов, сумма)
    """
    if not ambassadors_data:
        return "📊 <b>Топ-5 амбассадоров мерча</b>\n\nНет данных для отображения."
    
    message_text = "📊 <b>Топ-5 амбассадоров мерча</b>\n\n"
    for i, (name, username, count, total) in enumerate(ambassadors_data, 1):
        username_text = f"(@{username})" if username else "(без username)"
        message_text += f"{i}. <b>{name}</b> {username_text}: {count} заказов, {total or 0} T-points\n"
    
    return message_text


def format_general_statistics(general_stats: Dict[str, Any]) -> str:
    """
    Форматирует общую статистику заказов
    
    Args:
        general_stats: Словарь с общей статистикой
    """
    return (
        "📊 <b>Общая статистика заказов</b>\n\n"
        f"📋 <b>Новые заказы:</b> {general_stats.get('new', 0)}\n"
        f"⚡ <b>В работе:</b> {general_stats.get('processing', 0)}\n"
        f"📦 <b>Готовы к выдаче:</b> {general_stats.get('ready_for_pickup', 0)}\n"
        f"✅ <b>Выполненные:</b> {general_stats.get('delivered', 0)}\n"
        f"❌ <b>Отмененные:</b> {general_stats.get('cancelled', 0)}\n\n"
        f"💰 <b>Общая сумма заказов:</b> {general_stats.get('total_amount', 0)} T-points\n"
        f"📈 <b>Средний чек:</b> {general_stats.get('avg_order', 0)} T-points"
    )


def parse_callback_data(callback_data: str, expected_parts: int) -> Optional[List[str]]:
    """
    Безопасно парсит callback_data
    
    Args:
        callback_data: Строка callback_data
        expected_parts: Ожидаемое количество частей
        
    Returns:
        Список частей или None если формат неверный
    """
    parts = callback_data.split("_")
    if len(parts) >= expected_parts:
        return parts
        return None