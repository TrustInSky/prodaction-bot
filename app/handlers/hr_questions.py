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
from ..middlewares.access_control import HROrAdminAccess

logger = logging.getLogger(__name__)

hr_questions_router = Router(name="hr_questions")

# Регистрируем middleware для проверки доступа HR/Admin
hr_questions_router.callback_query.middleware(HROrAdminAccess())
hr_questions_router.message.middleware(HROrAdminAccess())

class HRQuestionStates(StatesGroup):
    waiting_for_answer = State()
    confirming_answer = State()

@hr_questions_router.callback_query(F.data == "menu:questions")
async def hr_questions_menu(
    callback: CallbackQuery,
    question_service: QuestionService
):
    """Главное меню управления вопросами для HR"""
    await safe_callback_answer(callback)
    
    try:
        # Получаем статистику вопросов
        stats = await question_service.get_questions_statistics()
        
        message_text = (
            f"❓ <b>Управление анонимными вопросами</b>\n\n"
            f"📊 <b>Статистика:</b>\n"
            f"🆕 Новых: {stats['new']}\n"
            f"⏳ В обработке: {stats['in_progress']}\n"
            f"✅ Отвеченных: {stats['answered']}\n"
            f"📋 Всего: {stats['total']}\n\n"
            f"Выберите действие:"
        )
        
        kb = InlineKeyboardBuilder()
        
        if stats['new'] > 0:
            kb.row(InlineKeyboardButton(
                text=f"🆕 Новые вопросы ({stats['new']})",
                callback_data="hr_questions:new"
            ))
        
        if stats['in_progress'] > 0:
            kb.row(InlineKeyboardButton(
                text=f"⏳ В обработке ({stats['in_progress']})",
                callback_data="hr_questions:in_progress"
            ))
        
        kb.row(InlineKeyboardButton(
            text="📋 Все вопросы",
            callback_data="hr_questions:all"
        ))
        
        if stats['answered'] > 0:
            kb.row(InlineKeyboardButton(
                text=f"✅ Отвеченные ({stats['answered']})",
                callback_data="hr_questions:answered"
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
        
    except Exception as e:
        logger.error(f"Error in hr_questions_menu: {e}")
        await safe_callback_answer(callback, "❌ Ошибка загрузки меню вопросов", show_alert=True)

@hr_questions_router.callback_query(F.data.startswith("hr_questions:"))
async def show_questions_by_status(
    callback: CallbackQuery,
    question_service: QuestionService
):
    """Показать вопросы по статусу"""
    await safe_callback_answer(callback)
    
    status_filter = callback.data.split(":")[1]
    
    # Определяем статус для фильтрации
    status_map = {
        "new": "new",
        "in_progress": "in_progress", 
        "answered": "answered",
        "all": None
    }
    
    status = status_map.get(status_filter)
    
    try:
        questions = await question_service.get_all_questions_for_hr(status)
        
        if not questions:
            status_names = {
                "new": "новых",
                "in_progress": "в обработке",
                "answered": "отвеченных",
                "all": ""
            }
            
            text = f"📭 Нет {status_names.get(status_filter, '')} вопросов."
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="↩️ Назад", callback_data="menu:questions")]
            ])
            
            await update_message(callback, text=text, reply_markup=keyboard)
            return
        
        # Формируем список вопросов
        message_lines = []
        
        if status_filter == "all":
            message_lines.append("📋 <b>Все вопросы:</b>\n")
        else:
            status_names = {
                "new": "🆕 Новые вопросы",
                "in_progress": "⏳ Вопросы в обработке",
                "answered": "✅ Отвеченные вопросы"
            }
            message_lines.append(f"{status_names[status_filter]}:\n")
        
        for question in questions[:10]:  # Показываем первые 10
            status_emoji = {
                'new': '🆕',
                'in_progress': '⏳',
                'answered': '✅'
            }.get(question.status, '❓')
            
            # Показываем автора, если вопрос не анонимный
            author_info = ""
            if not question.is_anonymous and question.user:
                if question.user.fullname and question.user.fullname.strip():
                    author_info = f" от {question.user.fullname.strip()}"
                elif question.user.username and question.user.username.strip():
                    author_info = f" от @{question.user.username.strip()}"
                else:
                    author_info = f" от пользователя (ID: {question.user.telegram_id})"
            elif question.user:
                # Для анонимных вопросов показываем только что это анонимно
                author_info = " (анонимный)"
            
            # Добавляем информацию о том, кто ответил
            answered_by = ""
            if question.answers and question.answers[0].respondent:
                respondent = question.answers[0].respondent
                if respondent.username and respondent.username.strip():
                    answered_by = f"\n👤 Ответил: @{respondent.username.strip()}"
                elif respondent.fullname and respondent.fullname.strip():
                    answered_by = f"\n👤 Ответил: {respondent.fullname.strip()}"
                else:
                    answered_by = f"\n👤 Ответил: HR (ID: {respondent.telegram_id})"
            
            message_lines.append(
                f"{status_emoji} <b>Вопрос #{question.id}</b>{author_info}\n"
                f"📅 {question.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                f"💬 <i>{question.message[:80]}{'...' if len(question.message) > 80 else ''}</i>{answered_by}\n"
            )
        
        if len(questions) > 10:
            message_lines.append(f"\n... и ещё {len(questions) - 10} вопросов")
        
        # Создаём клавиатуру с вопросами
        kb = InlineKeyboardBuilder()
        
        for question in questions[:10]:
            status_emoji = {
                'new': '🆕',
                'in_progress': '⏳',
                'answered': '✅'
            }.get(question.status, '❓')
            
            kb.row(InlineKeyboardButton(
                text=f"{status_emoji} Вопрос #{question.id}",
                callback_data=f"hr_question_view:{question.id}"
            ))
        
        kb.row(InlineKeyboardButton(
            text="↩️ Назад",
            callback_data="menu:questions"
        ))
        
        await update_message(
            callback,
            text="\n".join(message_lines),
            reply_markup=kb.as_markup()
        )
        
    except Exception as e:
        logger.error(f"Error showing questions by status {status_filter}: {e}")
        await safe_callback_answer(callback, "❌ Ошибка загрузки вопросов", show_alert=True)


@hr_questions_router.callback_query(F.data.startswith("hr_question_answer:"))
async def start_answering_question(
    callback: CallbackQuery,
    state: FSMContext,
    question_service: QuestionService
):
    """Начать процесс ответа на вопрос"""
    await safe_callback_answer(callback)
    
    question_id = int(callback.data.split(":")[1])
    
    try:
        question = await question_service.get_question_by_id(question_id)
        
        if not question:
            await safe_callback_answer(callback, "❌ Вопрос не найден", show_alert=True)
            return
        
        # Сохраняем ID вопроса в состоянии
        await state.update_data(question_id=question_id)
        await state.set_state(HRQuestionStates.waiting_for_answer)
        
        await update_message(
            callback,
            text=(
                f"📝 <b>Ответ на вопрос #{question_id}</b>\n\n"
                f"💬 <b>Вопрос:</b>\n"
                f"<i>{question.message}</i>\n\n"
                f"Напишите ваш ответ:"
            ),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data=f"hr_question_view:{question_id}")]
            ])
        )
        
    except Exception as e:
        logger.error(f"Error starting answer for question {question_id}: {e}")
        await safe_callback_answer(callback, "❌ Ошибка начала ответа", show_alert=True)

@hr_questions_router.callback_query(F.data.startswith("hr_question_take:"))
async def take_question_in_progress(
    callback: CallbackQuery,
    question_service: QuestionService
):
    """Взять вопрос в работу"""
    await safe_callback_answer(callback)
    
    question_id = int(callback.data.split(":")[1])
    
    try:
        success = await question_service.update_question_status(question_id, 'in_progress')
        
        if success:
            await safe_callback_answer(callback, "✅ Вопрос взят в работу!")
            
            # Получаем обновленную информацию о вопросе
            question = await question_service.get_question_by_id(question_id)
            
            if question:
                # Формируем детальную информацию
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
                
                # Информация об авторе
                author_info = "Анонимный пользователь"
                if question.user and not question.is_anonymous:
                    if question.user.username and question.user.username.strip():
                        author_info = f"@{question.user.username.strip()}"
                    else:
                        author_info = f"Пользователь (ID: {question.user.telegram_id})"
                
                message_text = (
                    f"{status_emoji} <b>Вопрос #{question.id}</b>\n\n"
                    f"👤 <b>От:</b> {author_info}\n"
                    f"📅 <b>Дата:</b> {question.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                    f"📊 <b>Статус:</b> {status_text}\n\n"
                    f"💬 <b>Вопрос:</b>\n"
                    f"<i>{question.message}</i>"
                )
                
                # Показываем ответы, если есть
                if question.answers:
                    for answer in question.answers:
                        hr_username = ""
                        if answer.respondent and answer.respondent.username and answer.respondent.username.strip():
                            hr_username = f" (@{answer.respondent.username.strip()})"
                        
                        message_text += (
                            f"\n\n📝 <b>Ответ HR{hr_username}:</b>\n"
                            f"<i>{answer.message}</i>\n"
                            f"📅 {answer.created_at.strftime('%d.%m.%Y %H:%M')}"
                        )
                
                # Создаём клавиатуру действий
                kb = InlineKeyboardBuilder()
                
                if question.status == 'new':
                    kb.row(InlineKeyboardButton(
                        text="⏳ Взять в работу",
                        callback_data=f"hr_question_take:{question.id}"
                    ))
                
                if question.status in ['new', 'in_progress'] and not question.answers:
                    kb.row(InlineKeyboardButton(
                        text="📝 Ответить",
                        callback_data=f"hr_question_answer:{question.id}"
                    ))
                
                kb.row(InlineKeyboardButton(
                    text="↩️ Назад к списку",
                    callback_data="menu:questions"
                ))
                
                await update_message(
                    callback,
                    text=message_text,
                    reply_markup=kb.as_markup()
                )
        else:
            await safe_callback_answer(callback, "❌ Ошибка изменения статуса", show_alert=True)
            
    except Exception as e:
        logger.error(f"Error taking question {question_id}: {e}")
        await safe_callback_answer(callback, "❌ Ошибка при взятии вопроса в работу", show_alert=True)

@hr_questions_router.callback_query(F.data.startswith("hr_question_view:"))
async def view_question_detail(
    callback: CallbackQuery,
    question_service: QuestionService
):
    """Детальный просмотр вопроса"""
    await safe_callback_answer(callback)
    
    question_id = int(callback.data.split(":")[1])
    
    try:
        question = await question_service.get_question_by_id(question_id)
        
        if not question:
            await safe_callback_answer(callback, "❌ Вопрос не найден", show_alert=True)
            return
        
        # Формируем детальную информацию
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
        
        # Информация об авторе
        author_info = "Анонимный пользователь"
        if question.user and not question.is_anonymous:
            if question.user.username and question.user.username.strip():
                author_info = f"@{question.user.username.strip()}"
            else:
                author_info = f"Пользователь (ID: {question.user.telegram_id})"
        
        message_text = (
            f"{status_emoji} <b>Вопрос #{question.id}</b>\n\n"
            f"👤 <b>От:</b> {author_info}\n"
            f"📅 <b>Дата:</b> {question.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            f"📊 <b>Статус:</b> {status_text}\n\n"
            f"💬 <b>Вопрос:</b>\n"
            f"<i>{question.message}</i>"
        )
        
        # Показываем ответы, если есть
        if question.answers:
            for answer in question.answers:
                hr_username = ""
                if answer.respondent and answer.respondent.username and answer.respondent.username.strip():
                    hr_username = f" (@{answer.respondent.username.strip()})"
                
                message_text += (
                    f"\n\n📝 <b>Ответ HR{hr_username}:</b>\n"
                    f"<i>{answer.message}</i>\n"
                    f"📅 {answer.created_at.strftime('%d.%m.%Y %H:%M')}"
                )
        
        # Создаём клавиатуру действий
        kb = InlineKeyboardBuilder()
        
        if question.status == 'new':
            kb.row(InlineKeyboardButton(
                text="⏳ Взять в работу",
                callback_data=f"hr_question_take:{question.id}"
            ))
        
        if question.status in ['new', 'in_progress'] and not question.answers:
            kb.row(InlineKeyboardButton(
                text="📝 Ответить",
                callback_data=f"hr_question_answer:{question.id}"
            ))
        
        kb.row(InlineKeyboardButton(
            text="↩️ Назад к списку",
            callback_data="menu:questions"
        ))
        
        await update_message(
            callback,
            text=message_text,
            reply_markup=kb.as_markup()
        )
        
    except Exception as e:
        logger.error(f"Error viewing question {question_id}: {e}")
        await safe_callback_answer(callback, "❌ Ошибка загрузки вопроса", show_alert=True)

@hr_questions_router.callback_query(F.data.startswith("question_view:"))
async def hr_question_from_notification(
    callback: CallbackQuery,
    question_service: QuestionService
):
    """Просмотр вопроса из уведомления"""
    await safe_callback_answer(callback)
    
    question_id = int(callback.data.split(":")[1])
    
    try:
        question = await question_service.get_question_by_id(question_id)
        
        if not question:
            await safe_callback_answer(callback, "❌ Вопрос не найден", show_alert=True)
            return
        
        # Формируем детальную информацию
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
        
        # Информация об авторе (анонимно)
        author_info = "Анонимный пользователь"
        
        message_text = (
            f"{status_emoji} <b>Вопрос #{question.id}</b>\n\n"
            f"👤 <b>От:</b> {author_info}\n"
            f"📅 <b>Дата:</b> {question.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            f"📊 <b>Статус:</b> {status_text}\n\n"
            f"💬 <b>Вопрос:</b>\n"
            f"<i>{question.message}</i>"
        )
        
        # Показываем ответы, если есть
        if question.answers:

            for answer in question.answers:
                hr_username = ""
                if answer.respondent and answer.respondent.username and answer.respondent.username.strip():
                    hr_username = f" (@{answer.respondent.username.strip()})"
                
                message_text += (
                    f"\n\n📝 <b>Ответ HR{hr_username}:</b>\n"
                    f"<i>{answer.message}</i>\n"
                    f"📅 {answer.created_at.strftime('%d.%m.%Y %H:%M')}"
                )
        
        # Создаём клавиатуру действий
        kb = InlineKeyboardBuilder()
        
        if question.status == 'new':
            kb.row(InlineKeyboardButton(
                text="⏳ Взять в работу",
                callback_data=f"hr_question_take:{question.id}"
            ))
        
        if question.status in ['new', 'in_progress'] and not question.answers:
            kb.row(InlineKeyboardButton(
                text="📝 Ответить",
                callback_data=f"hr_question_answer:{question.id}"
            ))
        
        kb.row(InlineKeyboardButton(
            text="↩️ Назад к списку",
            callback_data="menu:questions"
        ))
        
        await update_message(
            callback,
            text=message_text,
            reply_markup=kb.as_markup()
        )
        
    except Exception as e:
        logger.error(f"Error viewing question {question_id}: {e}")
        await safe_callback_answer(callback, "❌ Ошибка загрузки вопроса", show_alert=True)

@hr_questions_router.callback_query(F.data.startswith("question_skip:"))
async def skip_question_notification(callback: CallbackQuery):
    """Пропустить вопрос из уведомления"""
    await safe_callback_answer(callback, "⏭️ Вопрос пропущен")
    
    # Удаляем сообщение уведомления
    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Failed to delete notification message: {e}")



@hr_questions_router.message(HRQuestionStates.waiting_for_answer)
async def process_question_answer(
    message: Message,
    state: FSMContext,
    question_service: QuestionService
):
    """Обработка ответа на вопрос - показ превью"""
    answer_text = message.text
    
    if not answer_text:
        await message.answer("❌ Пожалуйста, отправьте текстовое сообщение с ответом.")
        return
    
    if len(answer_text.strip()) < 1:
        await message.answer("❌ Ответ не может быть пустым.")
        return
    
    if len(answer_text) > 2000:
        await message.answer("❌ Ответ слишком длинный. Максимум 2000 символов.")
        return
    
    try:
        # Получаем данные из состояния
        data = await state.get_data()
        question_id = data.get("question_id")
        
        if not question_id:
            await message.answer("❌ Ошибка: ID вопроса не найден.")
            await state.clear()
            return
        
        # Получаем информацию о вопросе
        question = await question_service.get_question_by_id(question_id)
        
        if not question:
            await message.answer("❌ Вопрос не найден.")
            await state.clear()
            return
        
        # Сохраняем текст ответа в состоянии
        await state.update_data(answer_text=answer_text)
        await state.set_state(HRQuestionStates.confirming_answer)
        
        # Показываем превью ответа с подтверждением
        message_text = (
            f"📝 <b>Предварительный просмотр ответа на вопрос #{question_id}</b>\n\n"
            f"💬 <b>Исходный вопрос:</b>\n"
            f"<i>{question.message}</i>\n\n"
            f"📤 <b>Ваш ответ:</b>\n"
            f"<i>{answer_text}</i>\n\n"
            f"Отправить этот ответ пользователю?"
        )
        
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(
            text="✅ Отправить ответ",
            callback_data=f"hr_confirm_answer:{question_id}"
        ))
        kb.row(InlineKeyboardButton(
            text="✏️ Изменить ответ",
            callback_data=f"hr_question_answer:{question_id}"
        ))
        kb.row(InlineKeyboardButton(
            text="❌ Отмена",
            callback_data=f"hr_question_view:{question_id}"
        ))
        
        await message.answer(
            text=message_text,
            reply_markup=kb.as_markup()
        )
        
    except Exception as e:
        logger.error(f"Error processing answer preview: {e}")
        await message.answer("❌ Произошла ошибка при обработке ответа.")
        await state.clear()

@hr_questions_router.callback_query(F.data.startswith("hr_confirm_answer:"))
async def confirm_answer_sending(
    callback: CallbackQuery,
    state: FSMContext,
    question_service: QuestionService,
    question_notification_service: QuestionNotificationService,
    user_service: UserService
):
    """Подтверждение отправки ответа"""
    await safe_callback_answer(callback)
    
    question_id = int(callback.data.split(":")[1])
    
    try:
        # Получаем данные из состояния
        data = await state.get_data()
        answer_text = data.get("answer_text")
        
        if not answer_text:
            await safe_callback_answer(callback, "❌ Ошибка: текст ответа не найден", show_alert=True)
            await state.clear()
            return
        
        hr_user_id = callback.from_user.id
        
        # Создаём ответ
        answer = await question_service.create_answer(
            question_id=question_id,
            respondent_id=hr_user_id,
            message=answer_text
        )
        
        if not answer:
            await safe_callback_answer(callback, "❌ Ошибка при создании ответа. Возможно, на вопрос уже отвечен", show_alert=True)
            await state.clear()
            return
        
        # Получаем данные для уведомления
        question = await question_service.get_question_by_id(question_id)
        hr_user = await user_service.get_user_by_telegram_id(hr_user_id)
        
        # Отправляем уведомление пользователю
        if question and hr_user:
            try:
                await question_notification_service.notify_user_about_answer(question, answer, hr_user)
                logger.info(f"User notified about answer to question {question_id}")
            except Exception as e:
                logger.error(f"Failed to notify user about answer to question {question_id}: {e}")
        
        # Подтверждение HR
        await update_message(
            callback,
            text=(
                f"✅ <b>Ответ на вопрос #{question_id} отправлен!</b>\n\n"
                f"Пользователь получил уведомление о вашем ответе."
            ),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="📋 К списку вопросов", callback_data="menu:questions"),
                    InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main")
                ]
            ])
        )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error confirming answer: {e}")
        await safe_callback_answer(callback, "❌ Произошла ошибка при отправке ответа", show_alert=True)
        await state.clear()
