from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from ..services.user import UserService
from ..keyboards.main_menu import MainKeyboard
from ..utils.message_editor import update_message
from ..utils.callback_helpers import safe_callback_answer
import logging
from datetime import datetime, date, timedelta

logger = logging.getLogger(__name__)

router = Router(name="main_menu")

# Время запуска бота для фильтрации старых команд
BOT_START_TIME = datetime.now()



# Состояния для онбординга нового пользователя
class OnboardingStates(StatesGroup):
    waiting_for_fullname = State()
    waiting_for_birth_date = State()
    waiting_for_hire_date = State()
    waiting_for_department = State()


@router.message(Command("start"))
async def cmd_start(message: Message, user_service: UserService, state: FSMContext, onboarding_service):
    """
    Обработчик команды /start
    Если пользователь новый - запускаем онбординг, иначе - обычное меню
    """
    try:
        # Проверяем, не является ли команда старой (отправленной до запуска бота)
        message_time = datetime.fromtimestamp(message.date.timestamp())
        if message_time < BOT_START_TIME:
            logger.info(f"Ignoring old /start command from user {message.from_user.id} sent at {message_time}")
            return
        
        logger.info(f"Start command called for user {message.from_user.id}")
        
        # Проверяем, есть ли пользователь в БД
        user = await user_service.get_user(message.from_user.id)
        
        if not user:
            # Новый пользователь - запускаем онбординг
            logger.info(f"New user {message.from_user.id}, starting onboarding")
            await start_onboarding(message, state, onboarding_service)
            return
        
        logger.info(f"Existing user {user.telegram_id} role: {user.role}")
        
        # Существующий пользователь - показываем главное меню
        welcome_text = await user_service.get_welcome_message(user)
        keyboard = await MainKeyboard.get_main_keyboard(
            user_id=message.from_user.id,
            role=user.role
        )
        
        await message.answer(text=welcome_text, reply_markup=keyboard)
        logger.info(f"Main menu sent to existing user {user.telegram_id}")
        
    except Exception as e:
        logger.error(f"Error in start command: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка")


async def start_onboarding(message: Message, state: FSMContext, onboarding_service):
    """Начало процесса онбординга нового сотрудника"""
    await state.set_state(OnboardingStates.waiting_for_fullname)
    
    welcome_text = await onboarding_service.get_onboarding_welcome_text()
    await message.answer(welcome_text)


@router.message(OnboardingStates.waiting_for_fullname)
async def process_fullname(message: Message, state: FSMContext, onboarding_service):
    """Обработка ввода ФИО"""
    # Используем OnboardingService для валидации
    validation = await onboarding_service.validate_fullname(message.text)
    
    if not validation['valid']:
        await message.answer(validation['message'])
        return
    
    # Сохраняем ФИО в состоянии
    await state.update_data(fullname=message.text.strip())
    await state.set_state(OnboardingStates.waiting_for_birth_date)
    
    first_name = validation['first_name']
    
    text = (
        f"✅ Спасибо, {first_name}!\n\n"
        f"📅 Теперь укажите вашу дату рождения в формате ДД.ММ.ГГГГ:\n\n"
        f"💡 Пример: 15.03.1990"
    )
    
    await message.answer(text)


@router.message(OnboardingStates.waiting_for_birth_date)
async def process_birth_date(message: Message, state: FSMContext, onboarding_service):
    """Обработка ввода даты рождения"""
    # Используем OnboardingService для валидации
    validation = await onboarding_service.validate_birth_date(message.text)
    
    if not validation['valid']:
        await message.answer(validation['message'])
        return
    
    # Сохраняем дату рождения
    await state.update_data(birth_date=validation['birth_date'])
    await state.set_state(OnboardingStates.waiting_for_hire_date)
    
    text = (
        f"✅ Дата рождения сохранена: {validation['birth_date'].strftime('%d.%m.%Y')}\n\n"
        f"💼 Теперь укажите дату вашего трудоустройства в формате ДД.ММ.ГГГГ:\n\n"
        f"💡 Пример: 01.09.2023"
    )
    
    await message.answer(text)


@router.message(OnboardingStates.waiting_for_hire_date)
async def process_hire_date(message: Message, state: FSMContext, onboarding_service):
    """Обработка даты трудоустройства"""
    # Используем OnboardingService для валидации
    validation = await onboarding_service.validate_hire_date(message.text)
    
    if not validation['valid']:
        await message.answer(validation['message'])
        return
    
    await state.update_data(hire_date=validation['hire_date'])
    await state.set_state(OnboardingStates.waiting_for_department)
    
    # Показываем кнопки с отделами
    departments = onboarding_service.get_available_departments()
    
    text = (
        f"✅ Дата трудоустройства сохранена: {validation['hire_date'].strftime('%d.%m.%Y')}\n\n"
        f"🏢 Выберите ваш отдел:"
    )
    
    # Создаем клавиатуру с отделами
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard_buttons = []
    
    # Группируем отделы по 2 в ряд
    for i in range(0, len(departments), 2):
        row = []
        for dept in departments[i:i+2]:
            row.append(InlineKeyboardButton(
                text=dept, 
                callback_data=f"onboarding_dept_{dept}"
            ))
        keyboard_buttons.append(row)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("onboarding_dept_"))
async def process_department_selection(callback: CallbackQuery, state: FSMContext, user_service: UserService, onboarding_service):
    """Обработка выбора отдела через кнопку"""
    try:
        # Извлекаем название отдела из callback_data
        department = callback.data.replace("onboarding_dept_", "")
        
        # Завершаем онбординг используя сервис
        await complete_onboarding_ui(callback, state, user_service, onboarding_service, department)
        
    except Exception as e:
        logger.error(f"Error in department selection: {e}")
        await callback.answer("❌ Ошибка при выборе отдела", show_alert=True)





async def complete_onboarding_ui(message_or_callback, state: FSMContext, user_service: UserService, onboarding_service, department: str):
    """UI обёртка для завершения онбординга"""
    try:
        # Получаем все собранные данные
        user_data = await state.get_data()
        user_data['department'] = department
        
        # Определяем telegram_id и username
        if hasattr(message_or_callback, 'from_user'):
            # Это Message
            telegram_id = message_or_callback.from_user.id
            username = message_or_callback.from_user.username or ""
        else:
            # Это CallbackQuery
            telegram_id = message_or_callback.from_user.id
            username = message_or_callback.from_user.username or ""
        
        # Завершаем онбординг через сервис
        result = await onboarding_service.complete_onboarding(telegram_id, username, user_data)
        
        if not result['success']:
            error_text = result['message']
            if hasattr(message_or_callback, 'message'):
                # Это CallbackQuery
                await message_or_callback.message.edit_text(error_text)
                await message_or_callback.answer()
            else:
                # Это Message
                await message_or_callback.reply(error_text)
            await state.clear()
            return
        
        user = result['user']
        
        # Уведомляем HR о новом сотруднике
        bot = message_or_callback.bot if hasattr(message_or_callback, 'bot') else message_or_callback.message.bot
        await user_service.notify_hr_about_new_employee(bot, user)
        
        # Завершаем онбординг
        await state.clear()
        
        # Извлекаем имя из ФИО используя сервис
        first_name = onboarding_service._extract_first_name(user_data['fullname'])
        
        # Формируем сообщение о завершении через сервис
        completion_text = await onboarding_service.format_completion_message(user_data, first_name, user.tpoints)
        
        # Прикрепляем главное меню к сообщению о завершении
        keyboard = await MainKeyboard.get_main_keyboard(
            user_id=telegram_id,
            role=user.role
        )
        
        if hasattr(message_or_callback, 'message'):
            # Это CallbackQuery
            await message_or_callback.message.edit_text(text=completion_text, reply_markup=keyboard)
            await message_or_callback.answer()
        else:
            # Это Message
            await message_or_callback.reply(text=completion_text, reply_markup=keyboard)
        
        logger.info(f"Onboarding completed for user {user.telegram_id}")
        
    except Exception as e:
        logger.error(f"Error completing onboarding UI: {e}", exc_info=True)
        error_text = "❌ Произошла ошибка при завершении регистрации"
        
        if hasattr(message_or_callback, 'message'):
            # Это CallbackQuery
            await message_or_callback.message.edit_text(error_text)
            await message_or_callback.answer()
        else:
            # Это Message
            await message_or_callback.reply(error_text)
        await state.clear()


@router.callback_query(F.data == "menu:main")
async def show_main_menu(callback: CallbackQuery, user_service: UserService, success_message: str = None):
    """Показать главное меню с опциональным уведомлением"""
    try:
        logger.info(f"Main menu callback for user {callback.from_user.id}")
        
        # Получаем пользователя
        user = await user_service.get_user(callback.from_user.id)
        
        if not user:
            await callback.message.edit_text("❌ Пользователь не найден")
            await safe_callback_answer(callback)
            return
        
        # Формируем главное меню
        keyboard = await MainKeyboard.get_main_keyboard(
            user_id=callback.from_user.id,
            role=user.role
        )
        
        # Если есть сообщение об успехе - показываем его сверху
        if success_message:
            main_text = (
                f"{success_message}\n\n"
                f"🏠 <b>Главное меню</b>\n\n"
                f"💎 Ваш баланс: {user.tpoints:,} T-Points\n\n"
                f"Выберите действие:"
            )
        else:
            main_text = (
                f"🏠 Главное меню\n\n"
                f"💎 Ваш баланс: {user.tpoints:,} T-Points\n\n"
                f"Выберите действие:"
            )
        
        await callback.message.edit_text(
            text=main_text,
            reply_markup=keyboard
        )
        await safe_callback_answer(callback)
        
    except Exception as e:
        logger.error(f"Error showing main menu: {e}", exc_info=True)
        await safe_callback_answer(callback, "❌ Произошла ошибка")


@router.callback_query(F.data == "menu:balance")
async def show_balance_details(callback: CallbackQuery, user_service: UserService):
    """Детальная информация о балансе"""
    try:
        # Получаем пользователя
        user = await user_service.get_user(callback.from_user.id)
        
        if not user:
            await callback.message.edit_text("❌ Пользователь не найден")
            await safe_callback_answer(callback)
            return
        
        formatted_balance = f"{user.tpoints:,}".replace(",", " ")
        
        balance_info = (
            f"💎 <b>Ваш баланс T-Points</b>\n\n"
            f"👤 Пользователь: {user.fullname}\n"
            f"💰 Текущий баланс: <b>{formatted_balance} T-Points</b>\n"
            f"📊 Роль: {user.role}\n\n"
            f"ℹ️ T-Points можно тратить на товары в корпоративном магазине.\n"
            f"Зарабатывайте T-Points за активности и достижения!"
        )
        
        await update_message(
            callback,
            text=balance_info,
            reply_markup=MainKeyboard.get_back_to_main_menu()
        )
        await safe_callback_answer(callback)
        
    except Exception as e:
        logger.error(f"Error showing balance: {e}", exc_info=True)
        await safe_callback_answer(callback, "❌ Произошла ошибка")


# ===== НАВИГАЦИОННЫЕ ХЕНДЛЕРЫ - ТОЛЬКО ПЕРЕНАПРАВЛЕНИЕ =====

# УДАЛЕНЫ неработающие перенаправления:
# @router.callback_query(F.data == "menu:catalog") - обрабатывается в catalog_router
# @router.callback_query(F.data == "menu:cart") - обрабатывается в catalog/cart


# УДАЛЕН: @router.callback_query(F.data == "menu:my_orders")
# Обработчик menu:my_orders находится в app/orders/user_orders.py


@router.callback_query(F.data == "menu:users")
async def redirect_to_users_management(callback: CallbackQuery):
    """Перенаправление к управлению пользователями - обрабатывается в user_management"""
    await safe_callback_answer(callback)
    logger.info(f"User {callback.from_user.id} redirected to users management")


@router.callback_query(F.data == "menu:tpoints")
async def redirect_to_tpoints_management(callback: CallbackQuery):
    """Перенаправление к управлению T-Points - обрабатывается в user_management"""
    await safe_callback_answer(callback)
    logger.info(f"User {callback.from_user.id} redirected to tpoints management")


@router.callback_query(F.data == "menu:how_to_get_tpoints")
async def redirect_to_tpoints_activity(callback: CallbackQuery):
    """Перенаправление к списку активностей T-Points - обрабатывается в tpoints_activity"""
    await safe_callback_answer(callback)
    logger.info(f"User {callback.from_user.id} redirected to tpoints activity")

@router.callback_query(F.data == "menu:settings")
async def redirect_to_admin_settings(callback: CallbackQuery, user_service: UserService):
    """Перенаправление в админские настройки"""
    try:
        # Проверяем права доступа
        user = await user_service.get_user_by_telegram_id(callback.from_user.id)
        if not user or user.role != "admin" or not user.is_active:
            await safe_callback_answer(callback, "❌ У вас нет прав доступа к настройкам", show_alert=True)
            return
        
        # Показываем админское меню
        text = (
            "🔧 <b>Панель администратора</b>\n\n"
            "Выберите раздел для управления:"
        )
        
        # Импортируем клавиатуру админки
        from ..keyboards.admin_kb import AdminKeyboard
        keyboard = AdminKeyboard.get_admin_settings_menu()
        
        await callback.message.edit_text(text, reply_markup=keyboard)
        await safe_callback_answer(callback)
        
        logger.info(f"Admin panel opened by user {callback.from_user.id}")
        
    except Exception as e:
        logger.error(f"Error redirecting to admin settings: {e}")
        await safe_callback_answer(callback, "❌ Ошибка доступа к настройкам", show_alert=True)


