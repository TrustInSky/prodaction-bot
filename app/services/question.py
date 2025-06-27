from sqlalchemy.ext.asyncio import AsyncSession
from ..repositories.question_repository import QuestionRepository
from ..core.base import BaseService
from ..models.models import Question, Answer
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

class QuestionService(BaseService):
    """
    Сервис для работы с вопросами
    Следует архитектуре: только бизнес-логика, работает через репозиторий
    """

    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.question_repo = QuestionRepository(session)

    async def create_question(self, user_id: int, message: str, is_anonymous: bool = True) -> Optional[Question]:
        """
        Создать новый вопрос
        Бизнес-логика: валидация сообщения
        """
        # Бизнес-логика: валидация
        if not message or len(message.strip()) < 5:
            logger.warning(f"Question too short from user {user_id}")
            return None
            
        if len(message) > 1000:
            logger.warning(f"Question too long from user {user_id}")
            return None
        
        # Для анонимных вопросов сохраняем user_id для связи, но не показываем в интерфейсе
        return await self.question_repo.create_question(user_id, message.strip(), is_anonymous)

    async def get_user_questions(self, user_id: int) -> List[Question]:
        """Получить вопросы пользователя (включая анонимные по user_id)"""
        return await self.question_repo.get_user_questions(user_id)

    async def get_question_by_id(self, question_id: int) -> Optional[Question]:
        """Получить вопрос по ID"""
        return await self.question_repo.get_question_by_id(question_id)

    async def get_all_questions_for_hr(self, status: Optional[str] = None) -> List[Question]:
        """Получить все вопросы для HR"""
        return await self.question_repo.get_all_questions(status)

    async def create_answer(self, question_id: int, respondent_id: int, message: str) -> Optional[Answer]:
        """
        Создать ответ на вопрос
        Бизнес-логика: валидация ответа и проверка статуса вопроса
        """
        # Бизнес-логика: валидация
        if not message or len(message.strip()) < 1:
            logger.warning(f"Answer too short for question {question_id}")
            return None
            
        if len(message) > 2000:
            logger.warning(f"Answer too long for question {question_id}")
            return None

        # Проверяем, что вопрос существует и не отвечен
        question = await self.question_repo.get_question_by_id(question_id)
        if not question:
            logger.warning(f"Question {question_id} not found")
            return None
            
        if question.status == 'answered':
            logger.warning(f"Question {question_id} already answered")
            return None

        return await self.question_repo.create_answer(question_id, respondent_id, message.strip())

    async def update_question_status(self, question_id: int, status: str) -> bool:
        """
        Обновить статус вопроса
        Бизнес-логика: валидация статуса
        """
        # Бизнес-логика: валидация статуса
        valid_statuses = ['new', 'in_progress', 'answered']
        if status not in valid_statuses:
            logger.warning(f"Invalid status {status} for question {question_id}")
            return False

        return await self.question_repo.update_question_status(question_id, status)

    async def get_questions_statistics(self) -> dict:
        """
        Получить статистику по вопросам
        Бизнес-логика: форматирование статистики
        """
        counts = await self.question_repo.get_questions_count_by_status()
        
        # Бизнес-логика: добавляем недостающие статусы с нулевыми значениями
        default_counts = {'new': 0, 'in_progress': 0, 'answered': 0}
        default_counts.update(counts)
        
        return {
            'total': sum(default_counts.values()),
            'new': default_counts['new'],
            'in_progress': default_counts['in_progress'],
            'answered': default_counts['answered']
        }

    async def can_user_ask_question(self, user_id: int) -> tuple[bool, str]:
        """
        Проверить, может ли пользователь задать вопрос
        Бизнес-логика: ограничения на частоту вопросов
        """
        # Пока без ограничений, но можно добавить:
        # - максимум вопросов в день
        # - проверка на спам
        # - проверка активности пользователя
        return True, ""

    async def has_user_questions(self, user_id: int) -> bool:
        """Проверить, есть ли у пользователя вопросы"""
        questions = await self.get_user_questions(user_id)
        return len(questions) > 0 