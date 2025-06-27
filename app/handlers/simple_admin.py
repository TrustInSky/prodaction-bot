import logging
from aiogram import Router, F, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from datetime import datetime, time

from ..services.auto_events_service import AutoEventsService
from ..services.user import UserService
from ..keyboards.admin_kb import AdminKeyboard
from ..middlewares.access_control import HROrAdminAccess

router = Router(name="simple_admin")
logger = logging.getLogger(__name__)

# Регистрируем middleware для проверки доступа HR/Admin
router.message.middleware(HROrAdminAccess())
router.callback_query.middleware(HROrAdminAccess())

class AdminStates(StatesGroup):
    waiting_for_days = State()
    waiting_for_time = State()
    waiting_for_points = State()
    waiting_for_threshold = State()

@router.message(Command("admin"))
async def admin_main_menu(message: types.Message, auto_events_service: AutoEventsService):
    """Главное меню админки"""
    text = (
        "🎛️ <b>Панель управления автоматическими событиями</b>\n\n"
        "📊 Управление:\n"
        "• 🎂 Дни рождения\n"
        "• 🏆 Юбилеи работы\n"
        "• 📦 Остатки товаров\n"
        "• 👤 Персональные настройки\n\n"
        "💡 Выберите раздел для настройки:"
    )
    
    await message.answer(text, reply_markup=AdminKeyboard.get_admin_settings_menu())

# =============================================================================
# ОСНОВНЫЕ ОБРАБОТЧИКИ НАСТРОЕК
# =============================================================================

@router.callback_query(F.data.startswith("admin:"))
async def handle_admin_callback(callback: CallbackQuery, auto_events_service: AutoEventsService, state: FSMContext):
    """Обработчик всех admin callback'ов"""
    data = callback.data.split(":")
    
    if len(data) < 2:
        await callback.answer("❌ Неверный формат команды")
        return
    
    action = data[1]
    
    # Возврат к главному меню админки
    if action == "menu":
        await admin_main_menu_callback(callback, auto_events_service, state)
    
    # Основные разделы настроек
    elif action in ["birthday", "anniversary", "stock_low"]:
        await show_event_settings(callback, auto_events_service, action)
    elif action == "personal":
        await show_personal_settings(callback, auto_events_service)
    
    # Переключение состояния событий
    elif action == "toggle" and len(data) >= 3:
        event_type = data[2]
        await toggle_event_setting(callback, auto_events_service, event_type)
    
    # Редактирование настроек
    elif action == "edit" and len(data) >= 4:
        event_type = data[2]
        setting_type = data[3]
        await start_edit_setting(callback, auto_events_service, event_type, setting_type, state)
    
    # Тестирование уведомлений
    elif action == "test" and len(data) >= 3:
        event_type = data[2]
        await test_notification(callback, auto_events_service, event_type)
    
    # Отмена редактирования
    elif action == "cancel":
        await cancel_edit(callback, state)
    
    # Сохранение настроек (обработка в FSM)
    elif action == "save":
        await callback.answer("💾 Используйте кнопки для сохранения")
    
    else:
        await callback.answer("❌ Неизвестное действие")

async def admin_main_menu_callback(callback: CallbackQuery, auto_events_service: AutoEventsService, state: FSMContext):
    """Показать главное меню админки через callback"""
    # Очищаем состояние
    await state.clear()
    
    text = (
        "🎛️ <b>Панель управления автоматическими событиями</b>\n\n"
        "📊 Управление:\n"
        "• 🎂 Дни рождения\n"
        "• 🏆 Юбилеи работы\n"
        "• 📦 Остатки товаров\n"
        "• 👤 Персональные настройки\n\n"
        "💡 Выберите раздел для настройки:"
    )
    
    await callback.message.edit_text(text, reply_markup=AdminKeyboard.get_admin_settings_menu())
    await callback.answer()

async def show_event_settings(callback: CallbackQuery, auto_events_service: AutoEventsService, event_type: str):
    """Показать настройки конкретного события"""
    try:
        settings = await auto_events_service.get_event_settings(event_type)
        
        if not settings:
            text = f"❌ Настройки для {event_type} не найдены"
            await callback.message.edit_text(text)
            return
        
        # Формируем описание настроек
        if event_type == "birthday":
            emoji = "🎂"
            title = "Дни рождения"
            specific_settings = f"🎁 T-Points за ДР: {settings.tpoints_amount}"
        elif event_type == "anniversary": 
            emoji = "🏆"
            title = "Юбилеи работы"
            specific_settings = f"🎁 T-Points: {settings.tpoints_amount} + {settings.tpoints_multiplier} за каждый год"
        elif event_type == "stock_low":
            emoji = "📦"
            title = "Низкие остатки"
            specific_settings = f"📊 Порог уведомления: {settings.stock_threshold} шт."
        else:
            emoji = "⚙️"
            title = event_type
            specific_settings = ""
        
        status = "✅ Включено" if settings.is_enabled else "❌ Выключено"
        
        text = (
            f"{emoji} <b>Настройки: {title}</b>\n\n"
            f"📊 Статус: {status}\n"
            f"📅 Дни уведомлений: {settings.notification_days}\n"
            f"⏰ Время: {settings.notification_time}\n"
        )
        
        if specific_settings:
            text += f"{specific_settings}\n"
        
        text += "\n💡 Выберите действие:"
        
        keyboard = AdminKeyboard.get_event_settings_menu(event_type, settings.is_enabled)
        
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error showing {event_type} settings: {e}")
        await callback.answer("❌ Ошибка при загрузке настроек", show_alert=True)

async def show_personal_settings(callback: CallbackQuery, auto_events_service: AutoEventsService):
    """Показать персональные настройки админа"""
    try:
        user_id = callback.from_user.id
        preferences = await auto_events_service.get_admin_preferences(user_id)
        
        birthday_status = "✅" if preferences.birthday_enabled else "❌"
        anniversary_status = "✅" if preferences.anniversary_enabled else "❌"
        stock_status = "✅" if preferences.stock_low_enabled else "❌"
        
        text = (
            f"👤 <b>Персональные настройки</b>\n\n"
            f"Ваши уведомления:\n"
            f"🎂 Дни рождения: {birthday_status}\n"
            f"🏆 Юбилеи: {anniversary_status}\n"
            f"📦 Низкие остатки: {stock_status}\n\n"
            f"💡 Управляйте своими уведомлениями:"
        )
        
        keyboard = AdminKeyboard.get_personal_settings_menu(preferences)
        
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error showing personal settings: {e}")
        await callback.answer("❌ Ошибка при загрузке настроек", show_alert=True)

async def toggle_event_setting(callback: CallbackQuery, auto_events_service: AutoEventsService, event_type: str):
    """Переключить включение/выключение события"""
    try:
        settings = await auto_events_service.get_event_settings(event_type)
        if not settings:
            await callback.answer("❌ Настройки не найдены", show_alert=True)
            return
        
        new_state = not settings.is_enabled
        success = await auto_events_service.update_event_settings(event_type, is_enabled=new_state)
        
        if success:
            status_text = "включены" if new_state else "выключены"
            await callback.answer(f"✅ Уведомления {status_text}")
            # Обновляем отображение
            await show_event_settings(callback, auto_events_service, event_type)
        else:
            await callback.answer("❌ Ошибка при обновлении", show_alert=True)
            
    except Exception as e:
        logger.error(f"Error toggling {event_type}: {e}")
        await callback.answer("❌ Ошибка при изменении настроек", show_alert=True)

async def start_edit_setting(callback: CallbackQuery, auto_events_service: AutoEventsService, event_type: str, setting_type: str, state: FSMContext):
    """Начать редактирование настройки"""
    try:
        # Сохраняем контекст редактирования
        await state.update_data({
            'editing_event_type': event_type,
            'editing_setting_type': setting_type
        })
        
        # Определяем что редактируем и переходим в соответствующее состояние
        if setting_type == "days":
            text = "📅 Введите дни уведомлений через запятую (например: 3,1,0)"
            await state.set_state(AdminStates.waiting_for_days)
        elif setting_type == "time":
            text = "⏰ Введите время в формате ЧЧ:ММ (например: 09:00)"
            await state.set_state(AdminStates.waiting_for_time)
        elif setting_type == "points":
            text = "💎 Введите количество T-Points (число)"
            await state.set_state(AdminStates.waiting_for_points)
        elif setting_type == "threshold":
            text = "📊 Введите порог остатков (число)"
            await state.set_state(AdminStates.waiting_for_threshold)
        else:
            await callback.answer("❌ Неизвестный тип настройки", show_alert=True)
            return
        
        # Показываем инструкцию и кнопку отмены
        keyboard = AdminKeyboard.get_edit_cancel_keyboard()
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error starting edit {event_type}.{setting_type}: {e}")
        await callback.answer("❌ Ошибка при начале редактирования", show_alert=True)

async def test_notification(callback: CallbackQuery, auto_events_service: AutoEventsService, event_type: str):
    """Отправить тестовое уведомление"""
    try:
        user_id = callback.from_user.id
        
        if event_type == "birthday":
            success = await auto_events_service.test_birthday_notification(user_id)
        elif event_type == "anniversary":
            success = await auto_events_service.test_anniversary_notification(user_id)
        elif event_type == "stock_low":
            success = await auto_events_service.test_stock_notification()
        else:
            await callback.answer("❌ Неизвестный тип уведомления", show_alert=True)
            return
        
        if success:
            await callback.answer("✅ Тестовое уведомление отправлено")
        else:
            await callback.answer("❌ Ошибка при отправке", show_alert=True)
        
    except Exception as e:
        logger.error(f"Error testing {event_type} notification: {e}")
        await callback.answer("❌ Ошибка при тестировании", show_alert=True)

async def cancel_edit(callback: CallbackQuery, state: FSMContext):
    """Отменить редактирование"""
    try:
        if state:
            await state.clear()
        
        text = (
            "🎛️ <b>Панель управления автоматическими событиями</b>\n\n"
            "📊 Управление:\n"
            "• 🎂 Дни рождения\n"
            "• 🏆 Юбилеи работы\n"
            "• 📦 Остатки товаров\n"
            "• 👤 Персональные настройки\n\n"
            "💡 Выберите раздел для настройки:"
        )
        
        keyboard = AdminKeyboard.get_admin_settings_menu()
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer("❌ Редактирование отменено")
            
    except Exception as e:
        logger.error(f"Error cancelling edit: {e}")
        await callback.answer("❌ Ошибка при отмене", show_alert=True)

# =============================================================================
# FSM ОБРАБОТЧИКИ ВВОДА
# =============================================================================

@router.message(AdminStates.waiting_for_days)
async def process_days_input(message: types.Message, state: FSMContext, auto_events_service: AutoEventsService):
    """Обработать введенные дни"""
    try:
        data = await state.get_data()
        event_type = data.get('editing_event_type')
        
        # Валидируем ввод
        days_text = message.text.strip()
        try:
            days = [int(d.strip()) for d in days_text.split(',')]
            if any(d < 0 for d in days):
                raise ValueError("Отрицательные дни не допускаются")
        except ValueError as e:
            await message.answer(f"❌ Неверный формат: {e}\nВведите дни через запятую, например: 3,1,0")
            return
        
        # Сохраняем настройку
        success = await auto_events_service.update_event_settings(event_type, notification_days=days_text)
        
        if success:
            await message.answer(f"✅ Дни уведомлений обновлены: {days_text}")
            await state.clear()
            
            # Возвращаемся к настройкам события
            text = (
                "🎛️ <b>Панель управления автоматическими событиями</b>\n\n"
                "📊 Управление:\n"
                "• 🎂 Дни рождения\n"
                "• 🏆 Юбилеи работы\n"
                "• 📦 Остатки товаров\n"
                "• 👤 Персональные настройки\n\n"
                "💡 Выберите раздел для настройки:"
            )
            
            keyboard = AdminKeyboard.get_admin_settings_menu()
            await message.answer(text, reply_markup=keyboard)
        else:
            await message.answer("❌ Ошибка при сохранении настроек")
        
    except Exception as e:
        logger.error(f"Error processing days input: {e}")
        await message.answer("❌ Ошибка при обработке ввода")

@router.message(AdminStates.waiting_for_time)
async def process_time_input(message: types.Message, state: FSMContext, auto_events_service: AutoEventsService):
    """Обработать введенное время"""
    try:
        data = await state.get_data()
        event_type = data.get('editing_event_type')
        
        # Валидируем время
        time_text = message.text.strip()
        try:
            time.fromisoformat(time_text)
        except ValueError:
            await message.answer("❌ Неверный формат времени. Используйте ЧЧ:ММ, например: 09:00")
            return
        
        # Сохраняем настройку
        success = await auto_events_service.update_event_settings(event_type, notification_time=time_text)
        
        if success:
            await message.answer(f"✅ Время уведомлений обновлено: {time_text}")
            await state.clear()
            
            # Возвращаемся к главному меню
            text = (
                "🎛️ <b>Панель управления автоматическими событиями</b>\n\n"
                "📊 Управление:\n"
                "• 🎂 Дни рождения\n"
                "• 🏆 Юбилеи работы\n"
                "• 📦 Остатки товаров\n"
                "• 👤 Персональные настройки\n\n"
                "💡 Выберите раздел для настройки:"
            )
            
            keyboard = AdminKeyboard.get_admin_settings_menu()
            await message.answer(text, reply_markup=keyboard)
        else:
            await message.answer("❌ Ошибка при сохранении настроек")
        
    except Exception as e:
        logger.error(f"Error processing time input: {e}")
        await message.answer("❌ Ошибка при обработке ввода")

@router.message(AdminStates.waiting_for_points)
async def process_points_input(message: types.Message, state: FSMContext, auto_events_service: AutoEventsService):
    """Обработать введенное количество T-Points"""
    try:
        data = await state.get_data()
        event_type = data.get('editing_event_type')
        setting_type = data.get('editing_setting_type')
        
        # Валидируем число
        try:
            points = int(message.text.strip())
            if points < 0:
                raise ValueError("Отрицательные значения не допускаются")
        except ValueError as e:
            await message.answer(f"❌ Неверное число: {e}")
            return
        
        # Определяем какое поле обновлять
        if setting_type == "points":
            field_name = "tpoints_amount"
        elif setting_type == "multiplier":
            field_name = "tpoints_multiplier"
        else:
            await message.answer("❌ Неизвестный тип настройки")
            return
        
        # Сохраняем настройку
        success = await auto_events_service.update_event_settings(event_type, **{field_name: points})
        
        if success:
            await message.answer(f"✅ T-Points обновлены: {points}")
            await state.clear()
            
            # Возвращаемся к главному меню
            text = (
                "🎛️ <b>Панель управления автоматическими событиями</b>\n\n"
                "📊 Управление:\n"
                "• 🎂 Дни рождения\n"
                "• 🏆 Юбилеи работы\n"
                "• 📦 Остатки товаров\n"
                "• 👤 Персональные настройки\n\n"
                "💡 Выберите раздел для настройки:"
            )
            
            keyboard = AdminKeyboard.get_admin_settings_menu()
            await message.answer(text, reply_markup=keyboard)
        else:
            await message.answer("❌ Ошибка при сохранении настроек")
        
    except Exception as e:
        logger.error(f"Error processing points input: {e}")
        await message.answer("❌ Ошибка при обработке ввода")

@router.message(AdminStates.waiting_for_threshold)
async def process_threshold_input(message: types.Message, state: FSMContext, auto_events_service: AutoEventsService):
    """Обработать введенный порог остатков"""
    try:
        data = await state.get_data()
        event_type = data.get('editing_event_type')
        
        # Валидируем число
        try:
            threshold = int(message.text.strip())
            if threshold < 0:
                raise ValueError("Отрицательные значения не допускаются")
        except ValueError as e:
            await message.answer(f"❌ Неверное число: {e}")
            return
        
        # Сохраняем настройку
        success = await auto_events_service.update_event_settings(event_type, stock_threshold=threshold)
        
        if success:
            await message.answer(f"✅ Порог остатков обновлен: {threshold}")
            await state.clear()
            
            # Возвращаемся к главному меню
            text = (
                "🎛️ <b>Панель управления автоматическими событиями</b>\n\n"
                "📊 Управление:\n"
                "• 🎂 Дни рождения\n"
                "• 🏆 Юбилеи работы\n"
                "• 📦 Остатки товаров\n"
                "• 👤 Персональные настройки\n\n"
                "💡 Выберите раздел для настройки:"
            )
            
            keyboard = AdminKeyboard.get_admin_settings_menu()
            await message.answer(text, reply_markup=keyboard)
        else:
            await message.answer("❌ Ошибка при сохранении настроек")
        
    except Exception as e:
        logger.error(f"Error processing threshold input: {e}")
        await message.answer("❌ Ошибка при обработке ввода")

# =============================================================================
# ПЕРСОНАЛЬНЫЕ НАСТРОЙКИ АДМИНОВ
# =============================================================================

@router.callback_query(F.data.startswith("personal:"))
async def handle_personal_settings(callback: CallbackQuery, auto_events_service: AutoEventsService):
    """Обработчик персональных настроек админа"""
    try:
        data = callback.data.split(":")
        if len(data) < 3:
            await callback.answer("❌ Неверный формат команды")
            return
        
        action = data[1]  # toggle
        setting_type = data[2]  # birthday, anniversary, stock_low
        
        user_id = callback.from_user.id
        
        if action == "toggle":
            # Получаем текущие настройки
            preferences = await auto_events_service.get_admin_preferences(user_id)
            
            # Определяем новое значение
            if setting_type == "birthday":
                new_value = not preferences.birthday_enabled
                field_name = "birthday_enabled"
            elif setting_type == "anniversary":
                new_value = not preferences.anniversary_enabled
                field_name = "anniversary_enabled"
            elif setting_type == "stock_low":
                new_value = not preferences.stock_low_enabled
                field_name = "stock_low_enabled"
            else:
                await callback.answer("❌ Неизвестная настройка")
                return
            
            # Обновляем настройки
            success = await auto_events_service.update_admin_preferences(user_id, **{field_name: new_value})
            
            if success:
                status_text = "включено" if new_value else "выключено"
                await callback.answer(f"✅ Уведомление {status_text}")
                # Обновляем отображение
                await show_personal_settings(callback, auto_events_service)
            else:
                await callback.answer("❌ Ошибка при обновлении", show_alert=True)
        else:
            await callback.answer("❌ Неизвестное действие")
            
    except Exception as e:
        logger.error(f"Error handling personal settings: {e}")
        await callback.answer("❌ Ошибка при изменении настроек", show_alert=True) 