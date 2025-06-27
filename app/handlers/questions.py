from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
import logging

from ..services.question import QuestionService
from ..services.notifications.question_notifications import QuestionNotificationService
from ..services.user import UserService
from ..utils.message_editor import update_message
from ..utils.callback_helpers import safe_callback_answer
from ..keyboards.main_menu import MainKeyboard

logger = logging.getLogger(__name__)
router = Router(name="questions_handlers")

def format_respondent_info(respondent) -> str:
    """
    Форматирует информацию о респонденте с учетом роли
    """
    if not respondent:
        return "HR"
    
    # Определяем роль
    role_text = "HR" if respondent.role == "hr" else "Администратора"
    
    # Формируем имя - для обеих ролей приоритет отдается username
    name_info = ""
    if respondent.username and respondent.username.strip():
        name_info = f" (@{respondent.username.strip()})"
    elif respondent.fullname and respondent.fullname.strip():
        name_info = f" ({respondent.fullname.strip()})"
    
    return f"{role_text}{name_info}"

class QuestionStates(StatesGroup):
    waiting_for_question = State()
    confirming_question = State()

@router.callback_query(F.data == "menu:ask_question")
async def ask_question_menu(
    callback: CallbackQuery, 
    question_service: QuestionService
):
    """Меню для задания вопроса"""
    await safe_callback_answer(callback)
    
    user_id = callback.from_user.id
    
    # Проверяем, есть ли у пользователя вопросы
    has_questions = await question_service.has_user_questions(user_id)
    
    # Формируем сообщение
    message_text = (
        "💬 <b>Система анонимных вопросов</b>\n\n"
        "Здесь вы можете:\n"
        "• Задать анонимный вопрос или предложение для компании\n"
        "• Предложить улучшения функционала\n"
        "• Задать вопрос по работе бота\n\n"
        "❗️ <b>Важно:</b> На ваш вопрос будет дан ответ лично вам.\n"
        "Вопрос будет анонимным для HR, но система запомнит, "
        "чтобы отправить вам ответ."
    )
    
    # Создаём клавиатуру
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(
        text="✍️ Задать вопрос",
        callback_data="questions:ask"
    ))
    
    # Кнопка "Мои вопросы" всегда видна
    kb.row(InlineKeyboardButton(
        text="📋 Мои вопросы",
        callback_data="questions:my_questions"
    ))
    
    kb.row(InlineKeyboardButton(
        text="↩️ В главное меню",
        callback_data="menu:main"
    ))
    
    await update_message(
        callback,
        text=message_text,
        reply_markup=kb.as_markup()
    )

@router.callback_query(F.data == "questions:ask")
async def start_asking_question(
    callback: CallbackQuery,
    state: FSMContext,
    question_service: QuestionService
):
    """Начать процесс задания вопроса"""
    await safe_callback_answer(callback)
    
    user_id = callback.from_user.id
    
    # Проверяем, может ли пользователь задать вопрос
    can_ask, error_message = await question_service.can_user_ask_question(user_id)
    if not can_ask:
        await safe_callback_answer(callback, f"❌ {error_message}", show_alert=True)
        return
    
    # Переводим в состояние ожидания вопроса
    await state.set_state(QuestionStates.waiting_for_question)
    
    await update_message(
        callback,
        text=(
            "✍️ <b>Задать вопрос</b>\n\n"
            "Напишите ваш вопрос или предложение.\n\n"
            "💡 <b>Примеры:</b>\n"
            "• Предложение по улучшению рабочего процесса\n"
            "• Вопрос по функционалу бота\n"
            "• Идея для новых товаров в каталоге\n\n"
            "Ваш вопрос будет анонимным, но ответ придёт лично вам."
        ),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="❌ Отмена", callback_data="questions:cancel")
        ]])
    )

@router.message(QuestionStates.waiting_for_question)
async def process_question_preview(
    message: Message,
    state: FSMContext,
    question_service: QuestionService
):
    """Предварительный просмотр вопроса перед отправкой"""
    user_id = message.from_user.id
    question_text = message.text
    
    if not question_text:
        await message.answer("❌ Пожалуйста, отправьте текстовое сообщение с вашим вопросом.")
        return
    
    # Проверяем длину вопроса
    if len(question_text.strip()) < 5:
        await message.answer("❌ Вопрос слишком короткий. Минимум 5 символов.")
        return
        
    if len(question_text) > 1000:
        await message.answer("❌ Вопрос слишком длинный. Максимум 1000 символов.")
        return
    
    # Сохраняем вопрос в состоянии для подтверждения
    await state.update_data(question_text=question_text)
    await state.set_state(QuestionStates.confirming_question)
    
    # Показываем превью вопроса
    preview_text = (
        f"📝 <b>Предварительный просмотр вопроса</b>\n\n"
        f"💬 <b>Ваш вопрос:</b>\n"
        f"<i>{question_text}</i>\n\n"
        f"❗️ <b>Обратите внимание:</b>\n"
        f"• Вопрос будет анонимным для HR\n"
        f"• Ответ придёт лично вам\n"
        f"• После отправки изменить вопрос будет нельзя\n\n"
        f"Отправить этот вопрос?"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Отправить", callback_data="question_confirm"),
            InlineKeyboardButton(text="✏️ Исправить", callback_data="question_edit")
        ],
        [
            InlineKeyboardButton(text="❌ Отмена", callback_data="questions:cancel")
        ]
    ])
    
    await message.answer(text=preview_text, reply_markup=keyboard)

@router.callback_query(F.data == "question_confirm")
async def confirm_question(
    callback: CallbackQuery,
    state: FSMContext,
    question_service: QuestionService,
    question_notification_service: QuestionNotificationService,
    user_service: UserService
):
    """Подтверждение и отправка вопроса"""
    await safe_callback_answer(callback)
    
    # Получаем данные из состояния
    data = await state.get_data()
    question_text = data.get("question_text")
    
    if not question_text:
        await safe_callback_answer(callback, "❌ Ошибка: текст вопроса не найден", show_alert=True)
        await state.clear()
        return
    
    user_id = callback.from_user.id
    
    try:
        # Создаём вопрос
        question = await question_service.create_question(
            user_id=user_id,
            message=question_text,
            is_anonymous=True
        )
        
        if not question:
            await update_message(
                callback,
                text="❌ Ошибка при создании вопроса. Попробуйте снова.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="↩️ В главное меню", callback_data="menu:main")
                ]])
            )
            await state.clear()
            return
        
        # Получаем данные пользователя для уведомления
        user = await user_service.get_user_by_telegram_id(user_id)
        if not user:
            logger.error(f"User {user_id} not found for question notification")
        
        # Уведомляем HR о новом вопросе
        if user:
            try:
                await question_notification_service.notify_hr_about_new_question(question, user)
                logger.info(f"HR notified about question {question.id} from user {user_id}")
            except Exception as e:
                logger.error(f"Failed to notify HR about question {question.id}: {e}")
        
        # Подтверждение пользователю
        await update_message(
            callback,
            text=(
                f"✅ <b>Вопрос #{question.id} отправлен!</b>\n\n"
                f"Спасибо за ваш вопрос. HR-менеджер рассмотрит его "
                f"и ответ будет отправлен лично вам.\n\n"
                f"Вы можете посмотреть статус своих вопросов в меню "
                f"\"Задать анонимный вопрос\" → \"Мои вопросы\"."
            ),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="↩️ В главное меню", callback_data="menu:main")
            ]])
        )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error creating question: {e}")
        await update_message(
            callback,
            text="❌ Произошла ошибка при отправке вопроса. Попробуйте позже.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="↩️ В главное меню", callback_data="menu:main")
            ]])
        )
        await state.clear()

@router.callback_query(F.data == "question_edit")
async def edit_question(callback: CallbackQuery, state: FSMContext):
    """Вернуться к редактированию вопроса"""
    await safe_callback_answer(callback)
    
    await state.set_state(QuestionStates.waiting_for_question)
    
    await update_message(
        callback,
        text=(
            "✏️ <b>Редактирование вопроса</b>\n\n"
            "Напишите ваш вопрос заново.\n\n"
            "💡 <b>Примеры:</b>\n"
            "• Предложение по улучшению рабочего процесса\n"
            "• Вопрос по функционалу бота\n"
            "• Идея для новых товаров в каталоге\n\n"
            "Ваш вопрос будет анонимным, но ответ придёт лично вам."
        ),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="❌ Отмена", callback_data="questions:cancel")
        ]])
    )

@router.callback_query(F.data == "questions:cancel")
async def cancel_question(callback: CallbackQuery, state: FSMContext):
    """Отмена задания вопроса"""
    await safe_callback_answer(callback)
    await state.clear()
    
    await update_message(
        callback,
        text="❌ Задание вопроса отменено.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="↩️ В главное меню", callback_data="menu:main")
        ]])
    )

@router.callback_query(F.data == "questions:my_questions")
async def show_my_questions(
    callback: CallbackQuery,
    question_service: QuestionService
):
    """Показать вопросы пользователя с пагинацией"""
    await safe_callback_answer(callback)
    
    user_id = callback.from_user.id
    page = 0  # Первая страница
    
    await show_my_questions_page(callback, question_service, user_id, page)

@router.callback_query(F.data.startswith("my_questions:"))
async def handle_my_questions_pagination(
    callback: CallbackQuery,
    question_service: QuestionService
):
    """Обработка пагинации в моих вопросах"""
    await safe_callback_answer(callback)
    
    user_id = callback.from_user.id
    data_parts = callback.data.split(":")
    
    if len(data_parts) >= 2:
        action = data_parts[1]
        
        if action == "page":
            page = int(data_parts[2]) if len(data_parts) > 2 else 0
            await show_my_questions_page(callback, question_service, user_id, page)
        elif action == "view":
            question_id = int(data_parts[2])
            page = int(data_parts[3]) if len(data_parts) > 3 else 0
            await show_question_detail(callback, question_service, question_id, page)

async def show_my_questions_page(
    callback: CallbackQuery,
    question_service: QuestionService,
    user_id: int,
    page: int
):
    """Показать страницу с вопросами пользователя"""
    questions = await question_service.get_user_questions(user_id)
    
    if not questions:
        await update_message(
            callback,
            text="📋 У вас пока нет вопросов.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="↩️ Назад", callback_data="menu:ask_question")
            ]])
        )
        return
    
    # Параметры пагинации
    per_page = 5
    total_questions = len(questions)
    total_pages = (total_questions + per_page - 1) // per_page
    
    # Проверяем корректность страницы
    if page < 0:
        page = 0
    elif page >= total_pages:
        page = total_pages - 1
    
    # Получаем вопросы для текущей страницы
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_questions = questions[start_idx:end_idx]
    
    # Формируем текст сообщения
    message_text = (
        f"📋 <b>Ваши вопросы</b>\n"
        f"Страница {page + 1} из {total_pages} (всего: {total_questions})\n\n"
        f"Выберите вопрос для детального просмотра:"
    )
    
    # Создаём клавиатуру с вопросами
    kb = InlineKeyboardBuilder()
    
    for question in page_questions:
        # Иконка статуса
        if question.status == 'answered':
            status_icon = "✅"  # Зелёная галочка для отвеченных
        elif question.status == 'in_progress':
            status_icon = "⏳"
        else:
            status_icon = "🆕"
        
        # Формируем текст кнопки
        question_preview = question.message[:30] + "..." if len(question.message) > 30 else question.message
        button_text = f"{status_icon} Вопрос #{question.id}: {question_preview}"
        
        kb.row(InlineKeyboardButton(
            text=button_text,
            callback_data=f"my_questions:view:{question.id}:{page}"
        ))
    
    # Кнопки пагинации
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=f"my_questions:page:{page - 1}"
        ))
    
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(
            text="Вперёд ➡️",
            callback_data=f"my_questions:page:{page + 1}"
        ))
    
    if nav_buttons:
        kb.row(*nav_buttons)
    
    # Кнопка возврата
    kb.row(InlineKeyboardButton(text="↩️ Назад", callback_data="menu:ask_question"))
    
    await update_message(
        callback,
        text=message_text,
        reply_markup=kb.as_markup()
    )

async def show_question_detail(
    callback: CallbackQuery,
    question_service: QuestionService,
    question_id: int,
    return_page: int
):
    """Показать детальную информацию о вопросе"""
    question = await question_service.get_question_by_id(question_id)
    
    if not question:
        await safe_callback_answer(callback, "❌ Вопрос не найден", show_alert=True)
        return
    
    # Статус с эмодзи
    status_emoji = {
        'new': '🆕',
        'in_progress': '⏳',
        'answered': '✅'
    }.get(question.status, '❓')
    
    status_text = {
        'new': 'Новый',
        'in_progress': 'В обработке',
        'answered': 'Отвечен'
    }.get(question.status, 'Неизвестно')
    
    # Формируем детальную информацию
    message_text = (
        f"{status_emoji} <b>Вопрос #{question.id}</b>\n\n"
        f"📊 <b>Статус:</b> {status_text}\n"
        f"📅 <b>Дата:</b> {question.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        f"💬 <b>Ваш вопрос:</b>\n"
        f"<i>{question.message}</i>"
    )
    
    # Показываем ответы, если есть
    if question.answers:
        message_text += "\n\n📝 <b>Ответы:</b>"
        for answer in question.answers:
            # Определяем информацию о респонденте с учетом роли
            respondent_info = format_respondent_info(answer.respondent)
            
            message_text += (
                f"\n\n💬 <b>Ответ от {respondent_info}:</b>\n"
                f"<i>{answer.message}</i>\n"
                f"📅 {answer.created_at.strftime('%d.%m.%Y %H:%M')}"
            )
    
    # Создаём клавиатуру возврата
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(
        text="↩️ К списку вопросов",
        callback_data=f"my_questions:page:{return_page}"
    ))
    
    await update_message(
        callback,
        text=message_text,
        reply_markup=kb.as_markup()
    ) 