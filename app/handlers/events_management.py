"""
Обработчики для ручного управления событиями (для HR)
"""
from aiogram import Router, F, types
from datetime import date, timedelta
import logging

from ..services.auto_events_service import AutoEventsService
from ..keyboards.events_kb import EventsKeyboard

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "check_events")
async def check_events_menu(
    callback: types.CallbackQuery,
    auto_events_service: AutoEventsService
):
    """Меню проверки событий для HR"""
    # Проверяем права доступа
    if not await check_hr_access(callback.from_user.id, callback):
        return
    
    try:
        text = (
            "📅 <b>Проверка событий</b>\n\n"
            "Выберите что проверить:"
        )
        
        keyboard = EventsKeyboard.get_events_menu()
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Error showing events menu: {e}")
        await callback.answer("❌ Ошибка загрузки меню", show_alert=True)


@router.callback_query(F.data == "check_birthdays")
async def check_birthdays_report(
    callback: types.CallbackQuery,
    auto_events_service: AutoEventsService
):
    """Проверка ближайших дней рождения"""
    if not await check_hr_access(callback.from_user.id, callback):
        return
    
    try:
        await callback.answer("🔍 Проверяем дни рождения...", show_alert=False)
        
        # Получаем отчет о ближайших днях рождения через сервис
        birthday_report = await auto_events_service.get_birthdays_report()
        upcoming_birthdays = birthday_report.get('upcoming_birthdays', [])
        
        # Формируем отчет
        text = "🎂 <b>Ближайшие дни рождения</b>\n\n"
        
        if not upcoming_birthdays:
            text += "🤷‍♀️ На ближайшие 30 дней дней рождения не найдено"
        else:
            for user, days_until in upcoming_birthdays[:10]:  # Показываем первые 10
                if days_until == 0:
                    text += f"🎉 <b>СЕГОДНЯ</b> - {user.fullname}\n"
                elif days_until == 1:
                    text += f"📅 <b>ЗАВТРА</b> - {user.fullname}\n"
                else:
                    text += f"📅 Через {days_until} дн. - {user.fullname}\n"
            
            if len(upcoming_birthdays) > 10:
                text += f"\n... и ещё {len(upcoming_birthdays) - 10} человек"
        
        keyboard = EventsKeyboard.get_back_to_events()
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Error checking birthdays: {e}")
        await callback.answer("❌ Ошибка проверки", show_alert=True)


@router.callback_query(F.data == "check_anniversaries")
async def check_anniversaries_report(
    callback: types.CallbackQuery,
    auto_events_service: AutoEventsService
):
    """Проверка ближайших юбилеев"""
    if not await check_hr_access(callback.from_user.id, callback):
        return
    
    try:
        await callback.answer("🔍 Проверяем юбилеи...", show_alert=False)
        
        # Получаем отчет о ближайших юбилеях через сервис
        anniversary_report = await auto_events_service.get_anniversaries_report()
        upcoming_anniversaries = anniversary_report.get('upcoming_anniversaries', [])
        
        # Формируем отчет
        text = "🏆 <b>Ближайшие годовщины работы</b>\n\n"
        
        if not upcoming_anniversaries:
            text += "🤷‍♀️ На ближайшие 30 дней годовщин не найдено"
        else:
            for user, years, days_until in upcoming_anniversaries[:10]:
                if days_until == 0:
                    text += f"🎯 <b>СЕГОДНЯ</b> - {user.fullname} ({years} лет)\n"
                elif days_until == 1:
                    text += f"📅 <b>ЗАВТРА</b> - {user.fullname} ({years} лет)\n"
                elif days_until < 0:
                    # Прошедшие годовщины (дни назад)
                    days_ago = abs(days_until)
                    text += f"🕐 {days_ago} дн. назад - {user.fullname} ({years} лет)\n"
                else:
                    text += f"📅 Через {days_until} дн. - {user.fullname} ({years} лет)\n"
            
            if len(upcoming_anniversaries) > 10:
                text += f"\n... и ещё {len(upcoming_anniversaries) - 10} годовщин"
        
        keyboard = EventsKeyboard.get_back_to_events()
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Error checking anniversaries: {e}")
        await callback.answer("❌ Ошибка проверки", show_alert=True)


@router.callback_query(F.data == "check_stock")
async def check_stock_report(
    callback: types.CallbackQuery,
    auto_events_service: AutoEventsService
):
    """Проверка остатков товаров"""
    if not await check_hr_access(callback.from_user.id, callback):
        return
    
    try:
        await callback.answer("🔍 Проверяем остатки...", show_alert=False)
        
        # Запускаем проверку остатков
        results = await auto_events_service.check_low_stock()
        
        text = "📦 <b>Остатки товаров</b>\n\n"
        
        if results['low_stock_products'] == 0:
            text += "✅ Все товары в достаточном количестве"
        else:
            text += f"⚠️ Найдено {results['low_stock_products']} товаров с низким остатком"
            
            if results.get('errors'):
                text += f"\n\n❌ Ошибки: {', '.join(results['errors'])}"
        
        keyboard = EventsKeyboard.get_back_to_events()
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Error checking stock: {e}")
        await callback.answer("❌ Ошибка проверки", show_alert=True)


@router.callback_query(F.data == "check_all_events")
async def check_all_events_report(
    callback: types.CallbackQuery,
    auto_events_service: AutoEventsService
):
    """Полная проверка всех событий (только отчеты без начисления)"""
    if not await check_hr_access(callback.from_user.id, callback):
        return
    
    try:
        await callback.answer("🔍 Выполняем полную проверку...", show_alert=False)
        
        # Получаем отчеты по всем событиям (без начисления T-Points)
        birthday_report = await auto_events_service.get_birthdays_report()
        anniversary_report = await auto_events_service.get_anniversaries_report()
        
        # Формируем сводный отчет
        text = "📊 <b>Сводка по всем событиям</b>\n\n"
        
        # Дни рождения
        upcoming_birthdays = birthday_report.get('upcoming_birthdays', [])
        today_birthdays = [user for user, days in upcoming_birthdays if days == 0]
        upcoming_birthdays_7 = [user for user, days in upcoming_birthdays if 0 < days <= 7]
        
        text += f"🎂 <b>Дни рождения:</b>\n"
        text += f"   Сегодня: {len(today_birthdays)} чел.\n"
        text += f"   На неделе: {len(upcoming_birthdays_7)} чел.\n"
        text += f"   Всего на 30 дней: {len(upcoming_birthdays)} чел.\n\n"
        
        # Годовщины
        upcoming_anniversaries = anniversary_report.get('upcoming_anniversaries', [])
        today_anniversaries = [user for user, years, days in upcoming_anniversaries if days == 0]
        upcoming_anniversaries_7 = [user for user, years, days in upcoming_anniversaries if 0 < days <= 7]
        past_anniversaries_7 = [user for user, years, days in upcoming_anniversaries if -7 <= days < 0]
        
        text += f"🏆 <b>Годовщины работы:</b>\n"
        text += f"   Сегодня: {len(today_anniversaries)} чел.\n"
        text += f"   На неделе: {len(upcoming_anniversaries_7)} чел.\n"
        text += f"   На прошлой неделе: {len(past_anniversaries_7)} чел.\n"
        text += f"   Всего (±30 дней): {len(upcoming_anniversaries)} чел.\n\n"
        
        # Остатки товаров
        stock_result = await auto_events_service.check_low_stock()
        text += f"📦 <b>Остатки товаров:</b>\n"
        text += f"   Товаров с низким остатком: {stock_result.get('low_stock_products', 0)} шт.\n\n"
        
        text += f"⏰ Отчет сформирован: {date.today().strftime('%d.%m.%Y')}\n\n"
        text += "💡 <i>Это только отчет. Уведомления и начисления происходят автоматически по расписанию.</i>"
        
        keyboard = EventsKeyboard.get_back_to_events()
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Error in full events check: {e}")
        await callback.answer("❌ Ошибка проверки", show_alert=True)


async def check_hr_access(user_id: int, callback: types.CallbackQuery) -> bool:
    """Проверка доступа HR"""
    # Здесь должна быть проверка роли, пока заглушка
    return True 