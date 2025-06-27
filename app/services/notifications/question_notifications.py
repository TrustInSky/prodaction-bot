from typing import List
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from .base_notification_service import BaseNotificationService
from ...models.models import Question, User
import logging

logger = logging.getLogger(__name__)

class QuestionNotificationService(BaseNotificationService):
    """Сервис уведомлений о вопросах"""
    
    async def notify_hr_about_new_question(self, question: Question, user: User) -> bool:
        """
        Отправить уведомление HR о новом вопросе
        """
        try:
            # Получаем HR пользователей
            hr_users = await self._get_hr_users()
            
            if not hr_users:
                logger.warning("No HR users found for question notification")
                return False
            
            # Формируем анонимный текст уведомления (без данных пользователя)
            text = (
                f"❓ <b>Новый анонимный вопрос #{question.id}</b>\n\n"
                f"📅 Дата: {question.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
                f"💬 <b>Вопрос:</b>\n"
                f"<i>{question.message}</i>"
            )
            
            # Создаем клавиатуру
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="👀 Посмотреть вопрос",
                        callback_data=f"question_view:{question.id}"
                    ),
                    InlineKeyboardButton(
                        text="⏭️ Пропустить",
                        callback_data=f"question_skip:{question.id}"
                    )
                ]
            ])
            
            # Отправляем уведомления всем HR
            results = await self._send_message_to_users(hr_users, text, keyboard)
            
            success_count = sum(1 for success in results.values() if success)
            logger.info(f"Question {question.id} notification sent to {success_count}/{len(hr_users)} HR users")
            
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Error sending question notification for question {question.id}: {e}")
            return False
    
    async def notify_user_about_answer(self, question: Question, answer, hr_user: User) -> bool:
        """
        Отправить уведомление пользователю об ответе на вопрос
        """
        try:
            if not question.user_id:
                logger.warning(f"Question {question.id} has no user_id for answer notification")
                return False
            
            # Формируем текст уведомления
            hr_mention = self._format_user_mention(
                hr_user.telegram_id,
                hr_user.username,
                hr_user.fullname
            )
            
            text = (
                f"✅ <b>Получен ответ на ваш вопрос #{question.id}</b>\n\n"
                f"👤 Ответил: {hr_mention}\n"
                f"📅 Дата ответа: {answer.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
                f"💬 <b>Ваш вопрос:</b>\n"
                f"<i>{question.message[:200]}{'...' if len(question.message) > 200 else ''}</i>\n\n"
                f"📝 <b>Ответ HR:</b>\n"
                f"<i>{answer.message}</i>"
            )
            
            # Создаем клавиатуру
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📋 Мои вопросы",
                        callback_data="questions:my_questions"
                    ),
                    InlineKeyboardButton(
                        text="🏠 Главное меню",
                        callback_data="menu:main"
                    )
                ]
            ])
            
            # Отправляем уведомление пользователю
            results = await self._send_message_to_users([question.user_id], text, keyboard)
            
            success = results.get(question.user_id, False)
            if success:
                logger.info(f"Answer notification sent to user {question.user_id} for question {question.id}")
            else:
                logger.error(f"Failed to send answer notification to user {question.user_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending answer notification for question {question.id}: {e}")
            return False
    
    async def send_notification(self, notification_type: str = "question", **kwargs) -> bool:
        """
        Реализация абстрактного метода для отправки уведомлений о вопросах
        """
        try:
            if notification_type == "new_question":
                question = kwargs.get("question")
                user = kwargs.get("user")
                if question and user:
                    return await self.notify_hr_about_new_question(question, user)
                    
            elif notification_type == "answer":
                question = kwargs.get("question")
                answer = kwargs.get("answer")
                hr_user = kwargs.get("hr_user")
                if question and answer and hr_user:
                    return await self.notify_user_about_answer(question, answer, hr_user)
            
            logger.warning(f"Unknown notification type: {notification_type}")
            return False
            
        except Exception as e:
            logger.error(f"Error in send_notification: {e}")
            return False 