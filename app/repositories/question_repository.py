from sqlalchemy import select, update, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload
from ..models.models import Question, Answer, User
from ..core.base import BaseRepository
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

class QuestionRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def create_question(self, user_id: Optional[int], message: str, is_anonymous: bool = True) -> Optional[Question]:
        """Создать новый вопрос"""
        try:
            question = Question(
                user_id=user_id,
                message=message,
                is_anonymous=is_anonymous,
                status='new'
            )
            self.session.add(question)
            await self.session.flush()
            return question
        except Exception as e:
            logger.error(f"Error creating question: {e}")
            return None

    async def get_question_by_id(self, question_id: int) -> Optional[Question]:
        """Получить вопрос по ID с ответами"""
        try:
            query = (
                select(Question)
                .options(
                    selectinload(Question.answers).selectinload(Answer.respondent),
                    selectinload(Question.user)
                )
                .where(Question.id == question_id)
            )
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting question {question_id}: {e}")
            return None

    async def get_user_questions(self, user_id: int) -> List[Question]:
        """Получить все вопросы пользователя"""
        try:
            query = (
                select(Question)
                .options(selectinload(Question.answers).selectinload(Answer.respondent))
                .where(Question.user_id == user_id)
                .order_by(desc(Question.created_at))
            )
            result = await self.session.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting user questions for user {user_id}: {e}")
            return []

    async def get_all_questions(self, status: Optional[str] = None) -> List[Question]:
        """Получить все вопросы (для HR)"""
        try:
            query = (
                select(Question)
                .options(
                    selectinload(Question.answers).selectinload(Answer.respondent),
                    selectinload(Question.user)
                )
                .order_by(desc(Question.created_at))
            )
            
            if status:
                query = query.where(Question.status == status)
                
            result = await self.session.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting all questions: {e}")
            return []

    async def create_answer(self, question_id: int, respondent_id: int, message: str) -> Optional[Answer]:
        """Создать ответ на вопрос"""
        try:
            answer = Answer(
                question_id=question_id,
                respondent_id=respondent_id,
                message=message
            )
            self.session.add(answer)
            
            # Обновляем статус вопроса
            await self.session.execute(
                update(Question)
                .where(Question.id == question_id)
                .values(status='answered')
            )
            
            await self.session.flush()
            return answer
        except Exception as e:
            logger.error(f"Error creating answer for question {question_id}: {e}")
            return None

    async def update_question_status(self, question_id: int, status: str) -> bool:
        """Обновить статус вопроса"""
        try:
            result = await self.session.execute(
                update(Question)
                .where(Question.id == question_id)
                .values(status=status)
            )
            return result.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating question {question_id} status: {e}")
            return False

    async def get_questions_count_by_status(self) -> dict:
        """Получить количество вопросов по статусам"""
        try:
            from sqlalchemy import func
            
            query = (
                select(Question.status, func.count(Question.id))
                .group_by(Question.status)
            )
            result = await self.session.execute(query)
            
            counts = {}
            for status, count in result.all():
                counts[status] = count
                
            return counts
        except Exception as e:
            logger.error(f"Error getting questions count: {e}")
            return {} 