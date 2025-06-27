from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from ..repositories.user_repository import UserRepository
from ..repositories.tpoints_activity_repository import TPointsActivityRepository
from ..services.tpoints_activity_service import TPointsActivityService
from ..utils.callback_helpers import safe_callback_answer
from ..keyboards.tpoints_activity_keyboard import (
    create_tpoints_keyboard, 
    create_edit_keyboard,
    create_confirmation_keyboard,
    create_role_based_keyboard
)

class EditTPointsStates(StatesGroup):
    editing_list = State()


tpoints_activity_router = Router()

def format_tpoints_text(tpoints_dict: dict) -> str:
    """Форматирует список T-поинтов в читаемый текст"""
    if not tpoints_dict:
        return "📊 <b>Список T-поинтов пуст</b>"
    
    text = "📊 <b>Как получить T-поинты:</b>\n\n"
    
    # Сортируем по количеству поинтов
    sorted_items = sorted(tpoints_dict.items(), key=lambda x: x[1])
    
    for activity, points in sorted_items:
        text += f"• <b>{activity}</b> — {points} T-поинтов\n"
    
    return text


@tpoints_activity_router.callback_query(F.data == "menu:how_to_get_tpoints")
async def show_tpoints_list(callback: CallbackQuery, user_repository: UserRepository, tpoints_activity_service: TPointsActivityService):
    """Показывает список способов получения T-поинтов - aiogram3-di"""
    user_id = callback.from_user.id
    
    # Получаем роль пользователя через репозиторий
    try:
        user = await user_repository.get_user_by_telegram_id(user_id)
        user_role = user.role if user else None
    except Exception as e:
        user_role = None
    
    # Получаем актуальный список T-поинтов через сервис (он использует TPointsActivityRepository)
    tpoints_dict = await tpoints_activity_service.get_activities_dict()
    
    text = format_tpoints_text(tpoints_dict)
    keyboard = create_tpoints_keyboard(user_id, user_role)  
    
    await callback.message.edit_text(
        text=text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await safe_callback_answer(callback)

@tpoints_activity_router.callback_query(F.data == "edit_tpoints")
async def start_edit_tpoints(callback: CallbackQuery, state: FSMContext, user_repository: UserRepository):
    """Начинает режим редактирования T-поинтов - aiogram3-di"""
    user_id = callback.from_user.id
    
    # Проверяем роль пользователя через репозиторий
    try:
        user = await user_repository.get_user_by_telegram_id(user_id)
        user_role = user.role if user else None
        
        if user_role not in ["hr", "admin"]:
            await safe_callback_answer(callback, "❌ У вас нет прав для редактирования списка", show_alert=True)
            return
    except Exception as e:
        await safe_callback_answer(callback, "❌ Не удалось проверить ваши права", show_alert=True)
        return
    
    await state.set_state(EditTPointsStates.editing_list)
    
    text = ("✏️ <b>Режим редактирования T-поинтов</b>\n\n"
            "Отправьте новый список в формате:\n"
            "<code>Название активности:Количество поинтов</code>\n\n"
            "Пример:\n"
            "<code>Репост поста в соц сетях:10\n"
            "Магнитик на холодильник:30\n"
            "Отзыв на хх:30</code>\n\n"
            "Каждая строка = одна активность\n"
            "Старый список будет заменен новым!")
    
    keyboard = create_edit_keyboard()
    
    await callback.message.edit_text(
        text=text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await safe_callback_answer(callback)

@tpoints_activity_router.message(EditTPointsStates.editing_list)
async def process_tpoints_edit(message: Message, state: FSMContext, tpoints_activity_service: TPointsActivityService):
    """Обрабатывает новый список T-поинтов - aiogram3-di"""
    try:
        # Парсим и валидируем данные через сервис
        new_tpoints = {}
        lines = message.text.strip().split('\n')
        
        for line in lines:
            if ':' not in line:
                continue
                
            parts = line.split(':', 1)
            if len(parts) != 2:
                continue
                
            activity = parts[0].strip()
            try:
                points = int(parts[1].strip())
                if activity and points >= 0:
                    new_tpoints[activity] = points
            except ValueError:
                continue
        
        if not new_tpoints:
            await message.reply("❌ Не удалось распознать ни одной активности. Проверьте формат.")
            return
        
        # Сохраняем превью во временное хранилище состояния
        await state.update_data(preview_tpoints=new_tpoints)
        
        # Показываем превью
        preview_text = "🔍 <b>Превью нового списка:</b>\n\n"
        preview_text += format_tpoints_text(new_tpoints)
        preview_text += f"\n\n📊 Всего активностей: {len(new_tpoints)}"
        preview_text += "\n✅ Для применения изменений нажмите 'Сохранить'"
        
        keyboard = create_edit_keyboard()
        
        await message.reply(
            text=preview_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except Exception as e:
        await message.reply(f"❌ Ошибка при обработке списка: {str(e)}")

@tpoints_activity_router.callback_query(F.data == "save_tpoints")
async def save_tpoints_changes(callback: CallbackQuery, state: FSMContext, user_repository: UserRepository, tpoints_activity_service: TPointsActivityService):
    """Сохраняет изменения в списке T-поинтов - aiogram3-di"""
    
    # Проверяем права еще раз через репозиторий
    try:
        user = await user_repository.get_user_by_telegram_id(callback.from_user.id)
        user_role = user.role if user else None
        
        if user_role not in ["hr", "admin"]:
            await safe_callback_answer(callback, "❌ У вас нет прав для сохранения изменений", show_alert=True)
            return
    except Exception as e:
        await safe_callback_answer(callback, "❌ Не удалось проверить ваши права", show_alert=True)
        return
    
    # Получаем данные из состояния
    data = await state.get_data()
    preview_tpoints = data.get("preview_tpoints")
    
    if not preview_tpoints:
        await safe_callback_answer(callback, "❌ Нет изменений для сохранения", show_alert=True)
        return
    
    # Сохраняем через сервис (он использует TPointsActivityRepository)
    try:
        # Преобразуем в текстовый формат для сервиса
        text_data = "\n".join([f"{name}:{points}" for name, points in preview_tpoints.items()])
        success, message = await tpoints_activity_service.update_activities_from_text(text_data)
        
        if success:
            await state.clear()
            
            # Получаем обновленный список через сервис (он использует TPointsActivityRepository)
            updated_tpoints = await tpoints_activity_service.get_activities_dict()
            
            text = "✅ <b>Список T-поинтов успешно обновлен!</b>\n\n"
            text += format_tpoints_text(updated_tpoints)
            
            keyboard = create_tpoints_keyboard(callback.from_user.id, user_role)
            
            await callback.message.edit_text(
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            await safe_callback_answer(callback, "💾 Изменения сохранены в базе данных!")
        else:
            await safe_callback_answer(callback, f"❌ Ошибка сохранения: {message}", show_alert=True)
            
    except Exception as e:
        await safe_callback_answer(callback, f"❌ Ошибка при сохранении: {str(e)}", show_alert=True)

@tpoints_activity_router.callback_query(F.data == "cancel_edit")
async def cancel_tpoints_edit(callback: CallbackQuery, state: FSMContext, user_repository: UserRepository, tpoints_activity_service: TPointsActivityService):
    """Отменяет редактирование T-поинтов - aiogram3-di"""
    await state.clear()
    
    # Получаем роль пользователя через UserRepository, активности через TPointsActivityService
    try:
        user = await user_repository.get_user_by_telegram_id(callback.from_user.id)
        user_role = user.role if user else None
    except Exception as e:
        user_role = None
    
    # Получаем актуальные данные через сервис (он использует TPointsActivityRepository)
    tpoints_dict = await tpoints_activity_service.get_activities_dict()
    text = format_tpoints_text(tpoints_dict)
    keyboard = create_tpoints_keyboard(callback.from_user.id, user_role)
    
    await callback.message.edit_text(
        text=text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await safe_callback_answer(callback, "❌ Редактирование отменено")


@tpoints_activity_router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext, user_repository: UserRepository):
    """Возвращается в главное меню - aiogram3-di"""
    await state.clear()
    
    # Получаем пользователя через репозиторий
    try:
        user = await user_repository.get_user_by_telegram_id(callback.from_user.id)
        if not user:
            await safe_callback_answer(callback, "❌ Пользователь не найден", show_alert=True)
            return
    except Exception as e:
        await safe_callback_answer(callback, "❌ Ошибка при получении данных пользователя", show_alert=True)
        return
    
    # Формируем главное меню
    from ..keyboards.main_menu import MainKeyboard
    keyboard = await MainKeyboard.get_main_keyboard(user_id=callback.from_user.id, role=user.role)
    
    main_text = (
        f"🏠 Главное меню\n\n"
        f"💎 Ваш баланс: {user.tpoints:,} T-Points\n\n"
        f"Выберите действие:"
    )
    
    await callback.message.edit_text(
        text=main_text,
        reply_markup=keyboard
    )
    await safe_callback_answer(callback, "🏠 Возвращаемся в главное меню...")